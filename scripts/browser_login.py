from __future__ import annotations

import argparse
import json
import os

from src.direct_browser import start_login_session


def main() -> int:
    p = argparse.ArgumentParser(description="Start a Browserbase Live View for manual social login")
    p.add_argument("platform", choices=["meta", "tiktok", "linkedin"])
    p.add_argument("--context-id", default=None)
    args = p.parse_args()

    result = start_login_session(args.platform, args.context_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("\nOPEN THIS LIVE VIEW AND LOGIN YOURSELF:")
    print(result["live_view_url"])
    print("\nThen visit/open the platform login URL inside the session:")
    print(result["login_url"])
    print("\nSave the context_id as a GitHub Actions secret for later dry-runs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
