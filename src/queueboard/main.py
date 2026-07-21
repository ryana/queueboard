from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from queueboard import __version__
from queueboard.api import router as api_router
from queueboard.config import get_settings
from queueboard.web import router as web_router

settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description="A lightweight shared queue for tracking work from intake to completion.",
)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
app.include_router(api_router)
app.include_router(web_router)


@app.get("/health", tags=["operations"])
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "version": __version__,
        "revision": settings.build_revision,
        "environment": settings.app_env,
    }
