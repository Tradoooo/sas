"""`sas portail` — serve the portal and the API in one process.

The portal is static (no build step, no CDN) and the API is mounted on the same
origin, so `portal/app.js` can call `/health` and `/campagnes` with a relative
path. This is the "URL déployée" deliverable in local form; the CDK stack serves
the same files from S3 behind CloudFront.
"""

from __future__ import annotations

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
PORTAIL = RACINE / "portal"


def servir(*, port: int = 8123, hote: str = "127.0.0.1") -> int:
    """Serve the API and mount the static portal at `/`."""
    try:
        import uvicorn
        from fastapi.staticfiles import StaticFiles
    except ImportError:
        print(
            "le portail demande l'extra « api » : pip install -e '.[api]'",
            file=sys.stderr,
        )
        return 2

    if not PORTAIL.is_dir():
        print(f"portail introuvable: {PORTAIL}", file=sys.stderr)
        return 2

    from sas.api.app import creer_app

    app = creer_app()
    app.mount("/", StaticFiles(directory=str(PORTAIL), html=True), name="portail")
    print(f"Sas — portail sur http://{hote}:{port}/  (Ctrl-C pour arrêter)")
    uvicorn.run(app, host=hote, port=port, log_level="warning")
    return 0
