import sys
import traceback
from pathlib import Path

# Add root directory to sys.path so app module can be imported
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

try:
    from app.main import app
except Exception as e:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse

    app = FastAPI()
    tb = traceback.format_exc()

    @app.api_route("/{full_path:path}", methods=["GET", "POST", "HEAD"])
    async def catch_all_err(full_path: str):
        return HTMLResponse(
            f"<h1>Inkgauge Serverless Initialization Error</h1><pre style='background:#f4f4f4;padding:1em;border-radius:4px;'>{tb}</pre>",
            status_code=500
        )
