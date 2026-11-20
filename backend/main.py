"""DroneLog - kisméretű, állapotmentes FastAPI-alkalmazás Docker Swarmhoz."""

import hmac
import logging
import os
import socket
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Path, Query, Request, Response
from fastapi.responses import JSONResponse

from backend.models import Mission, MissionCreate, MissionList, MissionPatch, MissionStats
from backend.repository import DatabaseUnavailable, MissionRepository, read_required_secret

VERSION = "1.0.0"
INSTANCE = socket.gethostname()
LOGGER = logging.getLogger("dronelog")

app = FastAPI(
    title="DroneLog API",
    description="Oktatási drónos feladatnapló. A feladatok lekérdezése nyilvános; az íráshoz X-Admin-Token kell.",
    version=VERSION,
    docs_url=None,
    redoc_url=None,
    openapi_url="/api/openapi.json",
)


def get_repository() -> MissionRepository:
    return MissionRepository()


def require_admin(x_admin_token: Annotated[str | None, Header(alias="X-Admin-Token", max_length=256)] = None) -> None:
    try:
        expected = read_required_secret(
            os.getenv("ADMIN_TOKEN_FILE", "/run/secrets/admin_token"), minimum_length=32
        )
    except (OSError, ValueError):
        LOGGER.error("A szerkesztői titok nincs megfelelően beállítva.")
        raise HTTPException(status_code=503, detail="A szerkesztés jelenleg nincs beállítva.") from None
    if not x_admin_token or not hmac.compare_digest(expected.encode("utf-8"), x_admin_token.encode("utf-8")):
        raise HTTPException(status_code=401, detail="A szerkesztéshez érvényes szerkesztői kulcs szükséges.")


@app.middleware("http")
async def response_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Instance-ID"] = INSTANCE
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.exception_handler(DatabaseUnavailable)
async def database_unavailable_handler(request: Request, error: DatabaseUnavailable):
    return JSONResponse(
        status_code=503,
        content={"detail": "Az adatbázis átmenetileg nem érhető el. Próbáld újra néhány másodperc múlva."},
        headers={"Retry-After": "5"},
    )


@app.get("/api/health", tags=["üzemeltetés"])
def health(repository: Annotated[MissionRepository, Depends(get_repository)]):
    try:
        repository.health()
    except DatabaseUnavailable:
        return JSONResponse(status_code=503, content={"status": "degraded", "database": "unavailable", "instance": INSTANCE, "version": VERSION})
    return {"status": "ok", "database": "ok", "instance": INSTANCE, "version": VERSION}


@app.get("/api/instance", tags=["üzemeltetés"])
def instance():
    """Melyik API-task szolgálta ki a kérést? Nem a teljes cluster leltára."""
    return {"instance": INSTANCE, "version": VERSION}


@app.get("/api/admin/check", dependencies=[Depends(require_admin)], tags=["üzemeltetés"])
def check_admin():
    """A szerkesztői kulcs ellenőrzése adatváltoztatás nélkül."""
    return {"authorized": True}


@app.get("/api/missions", response_model=MissionList, tags=["feladatok"])
def list_missions(
    repository: Annotated[MissionRepository, Depends(get_repository)],
    limit: Annotated[int, Query(ge=1, le=500)] = 500,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return repository.list(limit, offset)


@app.post("/api/missions", response_model=Mission, status_code=201, dependencies=[Depends(require_admin)], tags=["feladatok"])
def create_mission(payload: MissionCreate, repository: Annotated[MissionRepository, Depends(get_repository)]):
    return repository.create(payload.model_dump())


@app.patch("/api/missions/{mission_id}", response_model=Mission, dependencies=[Depends(require_admin)], tags=["feladatok"])
def update_mission(
    mission_id: Annotated[int, Path(ge=1)],
    payload: MissionPatch,
    repository: Annotated[MissionRepository, Depends(get_repository)],
):
    mission = repository.update(mission_id, payload.model_dump(exclude_unset=True))
    if mission is None:
        raise HTTPException(status_code=404, detail="A feladat nem található.")
    return mission


@app.delete("/api/missions/{mission_id}", status_code=204, dependencies=[Depends(require_admin)], tags=["feladatok"])
def delete_mission(
    mission_id: Annotated[int, Path(ge=1)],
    repository: Annotated[MissionRepository, Depends(get_repository)],
):
    if not repository.delete(mission_id):
        raise HTTPException(status_code=404, detail="A feladat nem található.")
    return Response(status_code=204)


@app.get("/api/stats", response_model=MissionStats, tags=["feladatok"])
def mission_stats(repository: Annotated[MissionRepository, Depends(get_repository)]):
    return repository.stats()
