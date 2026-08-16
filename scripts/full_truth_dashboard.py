from __future__ import annotations

import html
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from src.truth_status import action_counts, incident_reason, queue_slo

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = Path(os.getenv("TRUTH_ARTIFACT_DIR", ROOT / "artifacts"))
TZ = ZoneInfo("Europe/Athens")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"_parse_error": True, "_path": str(path)}


def esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def main() -> int:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    preflight = load_json(ARTIFACT_DIR / "buffer-preflight.json")
    scheduler = load_json(ARTIFACT_DIR / "scheduler-result.json")

    queue_limit = int(
        (scheduler.get("queue_slo") or {}).get("queue_limit")
        or scheduler.get("queue_limit")
        or preflight.get("active_queue_limit")
        or 10
    )
    active = int(
        (scheduler.get("queue_slo") or {}).get("active_queue")
        or scheduler.get("active_queue")
        or preflight.get("active_queue")
        or 0
    )
    slo = queue_slo(active, queue_limit)
    actions = list(scheduler.get("actions") or [])
    counts = action_counts(actions)
    status_counts = scheduler.get("post_write_status_counts") or preflight.get("status_counts") or {}
    buffer_errors = int(status_counts.get("error") or 0)
    outbox_jobs_received = int(scheduler.get("outbox_jobs_received") or 0)
    reason = incident_reason(
        missing_slots=slo["missing_slots"],
        outbox_jobs_received=outbox_jobs_received,
        blocked_actions=int(counts.get("blocked") or 0),
        buffer_errors=buffer_errors,
    )

    overall = "HEALTHY" if slo["met"] and buffer_errors == 0 and scheduler.get("ok", True) else "CRITICAL"
    generated_at = datetime.now(TZ).isoformat(timespec="seconds")
    dashboard = {
        "generated_at": generated_at,
        "overall_status": overall,
        "hard_slo": "BUFFER_FILL_RATE_100_PERCENT",
        "queue_slo": slo,
        "incident_reason": reason,
        "buffer": {
            "organization": scheduler.get("organization") or (preflight.get("organization") or {}).get("id"),
            "channel_count": preflight.get("channel_count"),
            "status_counts": status_counts,
            "post_count": preflight.get("post_count"),
            "ideas_count": preflight.get("ideas_count"),
            "errors": preflight.get("errors") or [],
        },
        "socialmarket_outbox": {
            "jobs_received_this_run": outbox_jobs_received,
            "pending_preview_count": scheduler.get("outbox_pending_preview_count"),
            "health_ok": scheduler.get("outbox_health_ok"),
            "sync": scheduler.get("outbox_sync") or {},
        },
        "scheduler": {
            "mode": scheduler.get("mode"),
            "content_source": scheduler.get("content_source"),
            "action_counts": counts,
            "preclaim_active_queue": scheduler.get("preclaim_active_queue"),
            "preclaim_free_slots": scheduler.get("preclaim_free_slots"),
            "scheduled_created": scheduler.get("scheduled_created", 0),
        },
        "next_scheduled": scheduler.get("next_scheduled") or [],
        "truth_notes": [
            "Workflow success alone is not treated as healthy; Buffer fill rate must be 100%.",
            "SocialScheduler never invents content: it schedules only SocialMarket-approved jobs.",
            "If approved supply is insufficient, the state is CRITICAL rather than silently underfilled.",
        ],
    }

    (ARTIFACT_DIR / "full-truth.json").write_text(json.dumps(dashboard, ensure_ascii=False, indent=2), encoding="utf-8")

    icon = "✅" if overall == "HEALTHY" else "🚨"
    md = f"""# {icon} SocialScheduler Admin Dashboard

**Updated:** {generated_at}  
**Overall:** **{overall}**  
**Hard SLO:** Buffer fill rate = **100%**

## Buffer Truth

| KPI | Value |
|---|---:|
| Active scheduled queue | **{slo['active_queue']} / {slo['queue_limit']}** |
| Fill rate | **{slo['fill_rate_pct']:.2f}%** |
| Missing slots | **{slo['missing_slots']}** |
| Sent | {status_counts.get('sent', 0)} |
| Scheduled | {status_counts.get('scheduled', 0)} |
| Sending | {status_counts.get('sending', 0)} |
| Errors | **{status_counts.get('error', 0)}** |

## SocialMarket → Scheduler Truth

| KPI | Value |
|---|---:|
| Approved jobs received this run | {outbox_jobs_received} |
| Pending approved preview | {scheduler.get('outbox_pending_preview_count', 'unknown')} |
| Outbox health | {scheduler.get('outbox_health_ok', 'unknown')} |
| Scheduler actions | `{json.dumps(counts, ensure_ascii=False)}` |

## Incident / Required Action

**{reason}**

- **GREEN only when:** queue fill = 100%, Buffer errors = 0, scheduler completed truthfully.
- SocialScheduler schedules only **SocialMarket-approved** content; it does not fabricate filler posts.
- Underfill caused by insufficient approved content is a **CRITICAL SUPPLY INCIDENT**.
- Admin source of truth: Buffer live state + SocialMarket publishing outbox + scheduler reconciliation.

## Next scheduled posts
"""
    next_rows = dashboard["next_scheduled"][:10]
    if next_rows:
        md += "\n| Due | Channel | Post ID |\n|---|---|---|\n"
        for row in next_rows:
            md += f"| {row.get('dueAt') or ''} | {row.get('service') or row.get('channelId') or ''} | {row.get('id') or ''} |\n"
    else:
        md += "\n_No next-scheduled detail available in this run._\n"
    (ARTIFACT_DIR / "admin-dashboard.md").write_text(md, encoding="utf-8")

    body_rows = "".join(
        f"<tr><td>{esc(k)}</td><td>{esc(v)}</td></tr>"
        for k, v in [
            ("Overall", overall),
            ("Active queue", f"{slo['active_queue']} / {slo['queue_limit']}"),
            ("Fill rate", f"{slo['fill_rate_pct']:.2f}%"),
            ("Missing slots", slo["missing_slots"]),
            ("Buffer errors", status_counts.get("error", 0)),
            ("Approved jobs received", outbox_jobs_received),
            ("Incident", reason),
        ]
    )
    page = f"""<!doctype html><html><head><meta charset='utf-8'><title>SocialScheduler Admin</title>
<style>body{{font-family:system-ui;margin:36px;max-width:900px}}.ok{{color:#067647}}.bad{{color:#b42318}}table{{border-collapse:collapse;width:100%}}td{{border-bottom:1px solid #ddd;padding:10px}}td:last-child{{font-weight:700;text-align:right}}code{{white-space:pre-wrap}}</style></head><body>
<h1>SocialScheduler Admin Dashboard</h1><h2 class='{'ok' if overall == 'HEALTHY' else 'bad'}'>{icon} {esc(overall)}</h2>
<p>Updated {esc(generated_at)} · Hard SLO: Buffer fill = 100%</p><table>{body_rows}</table>
<h3>Full truth JSON</h3><code>{esc(json.dumps(dashboard, ensure_ascii=False, indent=2))}</code></body></html>"""
    (ARTIFACT_DIR / "admin-dashboard.html").write_text(page, encoding="utf-8")

    output = os.getenv("GITHUB_OUTPUT", "").strip()
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(f"overall_status={overall}\n")
            handle.write(f"slo_met={'true' if slo['met'] else 'false'}\n")
            handle.write(f"fill_rate_pct={slo['fill_rate_pct']}\n")
            handle.write(f"missing_slots={slo['missing_slots']}\n")

    print(json.dumps(dashboard, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
