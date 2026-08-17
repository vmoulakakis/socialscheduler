from __future__ import annotations

# Keep the proven outbox executor semantics from openpost_main, but replace only
# the publisher client/service matrix. This avoids creating a second scheduler
# brain while adding LinkedIn and provider-native format validation.
from . import openpost_main as executor
from .openpost_native import OpenPostAPIError, OpenPostClient, SERVICES

executor.OpenPostAPIError = OpenPostAPIError
executor.OpenPostClient = OpenPostClient
executor.SERVICES = SERVICES

main = executor.main


if __name__ == "__main__":
    raise SystemExit(main())
