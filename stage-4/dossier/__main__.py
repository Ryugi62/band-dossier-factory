"""Start the service: `python -m dossier` listens on 0.0.0.0:$PORT (default 8080)."""
import logging
import os

from aiohttp import web

from .http_app import build_app
from .persistence import Persistence
from .service import Service

STATE_PATH = os.environ.get("DOSSIER_STATE_PATH", "/var/lib/dossier/state.db")


def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"),
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    port = int(os.environ.get("PORT") or "8080")
    service = Service(persistence=Persistence(STATE_PATH))
    web.run_app(build_app(service), host="0.0.0.0", port=port, access_log=None, backlog=512)


if __name__ == "__main__":
    main()
