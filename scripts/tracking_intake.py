from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

ATHENS = ZoneInfo("Europe/Athens")


def parse_form(body: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    pattern = re.compile(r"^###\s+(.+?)\s*$\n+(.*?)(?=^###\s+|\Z)", re.MULTILINE | re.DOTALL)
    for match in pattern.finditer(body or ""):
        label = match.group(1).strip()
        value = match.group(2).strip()
        if value == "_No response_":
            value = ""
        sections[label] = value
    return sections


def require_https(url: str) -> str:
    value = url.strip()
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("Tracking URL must be a valid https:// URL")
    return value


def parse_target(value: str) -> str:
    local = datetime.strptime(value.strip(), "%Y-%m-%d %H:%M").replace(tzinfo=ATHENS)
    return local.isoformat(timespec="seconds")


def parse_platforms(value: str) -> list[str]:
    allowed = {"instagram", "facebook", "tiktok"}
    raw = [part.strip().lower() for part in value.split(",") if part.strip()]
    result: list[str] = []
    for item in raw:
        if item not in allowed:
            raise ValueError(f"Unsupported platform: {item}")
        if item not in result:
            result.append(item)
    if not result:
        raise ValueError("At least one platform is required")
    return result


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize a GitHub Tracking URL issue into a safe repo intake record")
    parser.add_argument("--issue-number", required=True, type=int)
    parser.add_argument("--issue-url", required=True)
    parser.add_argument("--issue-body", required=True)
    parser.add_argument("--registry", default="config/tracking_sources.json")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    fields = parse_form(args.issue_body)
    tracking_url = require_https(fields.get("Tracking URL", ""))
    brand = fields.get("Brand", "").strip()
    angle = fields.get("Campaign angle / hook", "").strip()
    target_at = parse_target(fields.get("Target date/time (Europe/Athens)", ""))
    platforms = parse_platforms(fields.get("Platforms", ""))
    asset_mode = fields.get("Asset mode", "").strip()
    asset_reference = fields.get("Existing asset filename (optional)", "").strip()
    claim_sensitivity = fields.get("Claim sensitivity", "normal").strip()
    notes = fields.get("Notes / asset attachments", "").strip()

    if not brand or not angle:
        raise ValueError("Brand and campaign angle are required")
    if asset_mode not in {"auto-card", "existing-file", "manual-review"}:
        raise ValueError("Invalid asset mode")
    if asset_mode == "existing-file" and not asset_reference:
        raise ValueError("existing-file asset mode requires an asset filename")
    if claim_sensitivity not in {"normal", "current-claim-sensitive"}:
        raise ValueError("Invalid claim sensitivity")

    registry_path = Path(args.registry)
    registry = load_json(registry_path, [])
    source = next((x for x in registry if x.get("url") == tracking_url and x.get("brand") == brand), None)
    if source is None:
        source_hash = hashlib.sha256(f"{brand}|{tracking_url}".encode("utf-8")).hexdigest()[:12]
        source = {
            "source_id": f"trk-{source_hash}",
            "brand": brand,
            "url": tracking_url,
            "mode": "opaque",
            "active": True,
            "created_from_issue": args.issue_number,
            "created_at": datetime.now(ATHENS).isoformat(timespec="seconds"),
        }
        registry.append(source)
        dump_json(registry_path, registry)

    request_hash = hashlib.sha256(f"{args.issue_number}|{brand}|{tracking_url}".encode("utf-8")).hexdigest()[:10]
    request = {
        "request_id": f"req-{args.issue_number}-{request_hash}",
        "issue_number": args.issue_number,
        "issue_url": args.issue_url,
        "tracking_source_id": source["source_id"],
        "tracking_url": tracking_url,
        "tracking_mode": "opaque",
        "brand": brand,
        "angle": angle,
        "target_at": target_at,
        "platforms": platforms,
        "asset_mode": asset_mode,
        "asset_reference": asset_reference or None,
        "claim_sensitivity": claim_sensitivity,
        "notes": notes,
        "status": "normalized",
        "updated_at": datetime.now(ATHENS).isoformat(timespec="seconds"),
    }
    dump_json(Path(args.output), request)

    print(json.dumps({
        "request_id": request["request_id"],
        "source_id": source["source_id"],
        "output": args.output,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
