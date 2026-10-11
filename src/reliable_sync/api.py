from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="Reliable RPA Sync Engine", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy", "mode": "portfolio-reference"}
