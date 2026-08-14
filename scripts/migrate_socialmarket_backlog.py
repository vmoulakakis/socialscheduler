from __future__ import annotations

import json
from pathlib import Path

from src.socialmarket_outbox import SocialMarketOutboxClient

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    campaigns = json.loads((ROOT / "config" / "backlog.json").read_text(encoding="utf-8"))
    client = SocialMarketOutboxClient.from_env()
    result = client.import_legacy(campaigns)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
