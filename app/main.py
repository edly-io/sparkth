from fastapi import FastAPI

from app.api.v1.api import api_router

app = FastAPI()

app.include_router(api_router, prefix="/api/v1")


@app.get("/")
def read_root() -> dict[str, str]:
    return {"message": "Welcome to the Sparkth API"}
