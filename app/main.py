from fastapi import Depends, FastAPI, HTTPException, Query, status

from app.dependencies import get_repository
from app.legacy.connection import LegacyDatabaseUnavailable
from app.legacy.repository import LegacyRepository
from app.schemas import AuthenticationRequest, AuthenticationResponse, ClientResponse, WorkResponse
from app.security import require_service_auth

app = FastAPI(title="Daruix Legacy Bridge", version="0.1.0", docs_url=None, redoc_url=None)


@app.exception_handler(LegacyDatabaseUnavailable)
async def database_unavailable_handler(_, error: LegacyDatabaseUnavailable):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=503, content={"detail": str(error), "code": "legacy_database_unavailable"})


@app.get("/health/live")
def liveness():
    return {"status": "ok"}


@app.get("/health/ready", dependencies=[Depends(require_service_auth)])
def readiness(repository: LegacyRepository = Depends(get_repository)):
    repository.ping()
    return {"status": "ok", "database": "reachable"}


@app.post("/v1/authenticate", response_model=AuthenticationResponse, dependencies=[Depends(require_service_auth)])
def authenticate(payload: AuthenticationRequest, repository: LegacyRepository = Depends(get_repository)):
    return repository.authenticate(payload.username, payload.password)


@app.get("/v1/clients", response_model=list[ClientResponse], dependencies=[Depends(require_service_auth)])
def clients(
    search: str = Query(default="", max_length=120),
    limit: int = Query(default=100, ge=1, le=500),
    repository: LegacyRepository = Depends(get_repository),
):
    return repository.list_clients(search.strip(), limit)


@app.get("/v1/works", response_model=list[WorkResponse], dependencies=[Depends(require_service_auth)])
def works(
    client_name: str = Query(default="", max_length=255),
    client_document: str = Query(default="", max_length=30),
    search: str = Query(default="", max_length=120),
    limit: int = Query(default=100, ge=1, le=500),
    repository: LegacyRepository = Depends(get_repository),
):
    return repository.list_works(client_name.strip(), client_document.strip(), search.strip(), limit)


@app.get("/v1/works/{work_id}", response_model=WorkResponse, dependencies=[Depends(require_service_auth)])
def work(work_id: int, repository: LegacyRepository = Depends(get_repository)):
    result = repository.get_work(work_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Obra não encontrada.")
    return result

