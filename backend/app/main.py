from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from .database import Base, engine
from .routers import upload, review, search, exploitants, stats

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Gestion des factures numerisees")

app.include_router(upload.router)
app.include_router(review.router)
app.include_router(search.router)
app.include_router(exploitants.router)
app.include_router(stats.router)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def racine():
    return RedirectResponse(url="/static/index.html")


@app.get("/api/sante")
def sante():
    return {"statut": "ok"}
