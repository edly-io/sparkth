from importlib.metadata import version

from fastapi import FastAPI

from app.api.v1.api import api_router
from app.mcp.server import mcp

__version__ = version("sparkth")

# Note: Using path="/" causes connection issues with Claude
mcp_app = mcp.http_app(path="/mcp")

app = FastAPI(lifespan=mcp_app.lifespan)

app.include_router(api_router, prefix="/api/v1")

app.mount("/sparkth-mcp", mcp_app)


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Welcome to Sparkth", "version": __version__}
