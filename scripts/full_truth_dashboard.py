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
        or 30
    )
    active = int(
        (scheduler.get("queue_slo") or {}).get("active_queue")
        or scheduler.get("active_queue")
        or preflight.get("active_queue")
        or 0
    )
    slo = queue_slo(active, queue_limit)
    reported_slo = scheduler.get("queue_slo") or {}
    if reported_slo:
        slo.update(reported_slo)

    channel_slo = scheduler.get("channel_queue_slo") or {}
    if not channel_slo:
        for row in preflight.get("channel_queue") or []:
            service = str(row.get("service") or "unknown")
            channel_slo[service] = queue_slo(int(row.get("active_queue") or 0), int(row.get("queue_limit") or 10))

    actions = list(scheduler.get("actions") or [])
    counts = action_counts(actions)
    status_counts = scheduler.get("post_write_status_counts") or preflight.get("status_counts") or {}
    buffer_errors = int(status_counts.get("error") or 0)
    outbox_jobs_received = int(scheduler.get("outbox_jobs_received") or 0)
    reason = incident_reason(
        missing_slots=int(slo.get("missing_slots") or 0),
        outbox_jobs_received=outbox_jobs_received,
        blocked_actions=int(counts.get("blocked") or 0),
        buffer_errors=buffer_errors,
    )

    channel_truth_met = bool(channel_slo) and all(bool(item.get("met")) for item in channel_slo.values())
    overall = "HEALTHY" if channel_truth_met and buffer_errors == 0 and scheduler.get("ok", True) else "CRITICAL"
    generated_at = datetime.now(TZ).isoformat(timespec="seconds")
    dashboard = {
        "generated_at": generated_at,
        "overall_status": overall,
        "hard_slo": "BUFFER_FILL_RATE_100_PERCENT_PER_CHANNEL",
        "queue_slo": slo,
        "channel_queue_slo": channel_slo,
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
            "jobs_received_by_platform": scheduler.get("outbox_jobs_received_by_platform") or {},
            "pending_preview_count": scheduler.get("outbox_pending_preview_count"),
            "pending_by_platform": scheduler.get("outbox_pending_by_platform") or {},
            "health_ok": scheduler.get("outbox_health_ok"),
            "refill": scheduler.get("outbox_refill") or {},
            "sync": scheduler.get("outbox_sync") or {},
        },
        "scheduler": {
            "mode": scheduler.get("mode"),
            "content_source": scheduler.get("content_source"),
            "action_counts": counts,
            "preclaim_active_queue": scheduler.get("preclaim_active_queue"),
            "preclaim_free_slots": scheduler.get("preclaim_free_slots"),
            "preclaim_active_by_service": scheduler.get("preclaim_active_by_service") or {},
            "preclaim_capacity_by_service": scheduler.get("preclaim_capacity_by_service") or {},
            "scheduled_created": scheduler.get("scheduled_created", 0),
        },
        "next_scheduled": scheduler.get("next_scheduled") or [],
        "truth_notes": [
            "Healthy requires 100% fill on every connected Buffer channel, not just total queue count.",
            "SocialScheduler schedules only SocialMarket-approved jobs; it never fabricates filler content.",
            "Before claiming, SocialMarket runs a rolling refill so seasonal and pain-solver content can enter the 72-hour window.",
        ],
    }

    (ARTIFACT_DIR / "full-truth.json").write_text(json.dumps(dashboard, ensure_ascii=False, indent=2), encoding="utf-8")

    icon = "✅" if overall == "HEALTHY" else "🚨"
    md = f"""# {icon} SocialScheduler Admin Dashboard

**Updated:** {generated_at}  
**Overall:** **{overall}**  
**Hard SLO:** Buffer fill = **100% on every connected channel**

## Buffer Truth

| Channel | Active | Limit | Fill | Missing | Status |
|---|---:|---:|---:|---:|---|
"""
    for service in ("facebook", "instagram", "tiktok"):
        item = channel_slo.get(service) or queue_slo(0, 10)
        state = "✅" if item.get("met") else "🚨"
        md += f"| {service.title()} | **{item.get('active_queue', 0)}** | {item.get('queue_limit', 10)} | **{float(item.get('fill_rate_pct', 0)):.2f}%** | {item.get('missing_slots', 0)} | {state} |\n"

    md += f"""
**TOTAL:** **{slo.get('active_queue', 0)} / {slo.get('queue_limit', 30)}** · Fill **{float(slo.get('fill_rate_pct', 0)):.2f}%** · Missing **{slo.get('missing_slots', 0)}**

| Buffer status | Count |
|---|---:|
| Sent | {status_counts.get('sent', 0)} |
| Scheduled | {status_counts.get('scheduled', 0)} |
| Sending | {status_counts.get('sending', 0)} |
| Errors | **{status_counts.get('error', 0)}** |

## SocialMarket → Scheduler

| KPI | Value |
|---|---|
| Jobs claimed this run | **{outbox_jobs_received}** |
| Claimed by platform | `{json.dumps(scheduler.get('outbox_jobs_received_by_platform') or {}, ensure_ascii=False)}` |
| Pending approved preview | {scheduler.get('outbox_pending_preview_count', 'unknown')} |
| Pending by platform | `{json.dumps(scheduler.get('outbox_pending_by_platform') or {}, ensure_ascii=False)}` |
| Outbox health | {scheduler.get('outbox_health_ok', 'unknown')} |
| Rolling refill | `{json.dumps(scheduler.get('outbox_refill') or {}, ensure_ascii=False)}` |
| Created in Buffer | **{scheduler.get('scheduled_created', 0)}** |

## Incident / Required Action

**{reason}**

- **GREEN only when:** Facebook 10/10, Instagram 10/10, TikTok 10/10 and Buffer errors = 0.
- Underfill is never hidden by workflow success.
- If SocialMarket has insufficient approved content for a channel, the dashboard stays **CRITICAL** until supply/refill is fixed.

## Next scheduled posts
"""
    next_rows = dashboard["next_scheduled"][:30]
    if next_rows:
        md += "\n| Due | Channel | Post ID |\n|---|---|---|\n"
        for row in next_rows:
            md += f"| {row.get('dueAt') or ''} | {row.get('service') or row.get('channelId') or ''} | {row.get('id') or ''} |\n"
    else:
        md += "\n_No next-scheduled detail available in this run._\n"
    (ARTIFACT_DIR / "admin-dashboard.md").write_text(md, encoding="utf-8")

    channel_rows = "".join(
        f"<tr><td>{esc(service.title())}</td><td>{esc(item.get('active_queue', 0))}/{esc(item.get('queue_limit', 10))}</td><td>{esc(item.get('fill_rate_pct', 0))}%</td><td>{'OK' if item.get('met') else 'CRITICAL'}</td></tr>"
        for service, item in ((s, channel_slo.get(s) or queue_slo(0, 10)) for s in ("facebook", "instagram", "tiktok"))
    )
    page = f"""<!doctype html><html><head><meta charset='utf-8'><title>SocialScheduler Admin</title>
<style>body{{font-family:system-ui;margin:36px;max-width:980px}}.ok{{color:#067647}}.bad{{color:#b42318}}table{{border-collapse:collapse;width:100%}}td,th{{border-bottom:1px solid #ddd;padding:10px;text-align:left}}td:nth-child(n+2){{font-weight:700}}code{{white-space:pre-wrap}}</style></head><body>
<h1>SocialScheduler Admin Dashboard</h1><h2 class='{'ok' if overall == 'HEALTHY' else 'bad'}'>{icon} {esc(overall)}</h2>
<p>Updated {esc(generated_at)} · Hard SLO: 100% per channel</p>
<table><thead><tr><th>Channel</th><th>Queue</th><th>Fill</th><th>Status</th></tr></thead><tbody>{channel_rows}</tbody></table>
<h3>Full truth</h3><code>{esc(json.dumps(dashboard, ensure_ascii=False, indent=2))}</code></body></html>"""
    (ARTIFACT_DIR / "admin-dashboard.html").write_text(page, encoding="utf-8")

    output = os.getenv("GITHUB_OUTPUT", "").strip()
    if output:
        with open(output, "a", encoding="utf-8") as handle:
            handle.write(f"overall_status={overall}\n")
            handle.write(f"slo_met={'true' if channel_truth_met else 'false'}\n")
            handle.write(f"fill_rate_pct={slo.get('fill_rate_pct', 0)}\n")
            handle.write(f"missing_slots={slo.get('missing_slots', 0)}\n")

    print(json.dumps(dashboard, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
