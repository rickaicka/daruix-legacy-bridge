from fastapi import Depends, FastAPI, HTTPException, Query, status

from app.dependencies import get_repository
from app.legacy.connection import LegacyDatabaseUnavailable
from app.legacy.repository import (
    LegacyColumnNotFound,
    LegacyRepository,
    LegacyResourceNotFound,
    LegacyTableNotFound,
)
from app.schemas import (
    AuthenticationRequest,
    AuthenticationResponse,
    ClientResponse,
    LegacyTableInfoResponse,
    LegacyTablePageResponse,
    WorkResponse,
)
from app.security import require_service_auth

app = FastAPI(title="Daruix Legacy Bridge", version="0.2.0", docs_url=None, redoc_url=None)


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


@app.get(
    "/v1/budgeting/tables",
    response_model=list[LegacyTableInfoResponse],
    dependencies=[Depends(require_service_auth)],
)
def budgeting_tables(repository: LegacyRepository = Depends(get_repository)):
    return repository.list_budgeting_tables()


@app.get(
    "/v1/budgeting/{resource}",
    response_model=LegacyTablePageResponse,
    dependencies=[Depends(require_service_auth)],
)
def budgeting_table(
    resource: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    search: str = Query(default="", max_length=255),
    filter_column: str = Query(default="", max_length=255),
    filter_value: str = Query(default="", max_length=500),
    repository: LegacyRepository = Depends(get_repository),
):
    if bool(filter_column.strip()) != bool(filter_value.strip()):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="filter_column e filter_value devem ser enviados juntos.",
        )

    try:
        return repository.list_budgeting_table(
            resource=resource.strip(),
            offset=offset,
            limit=limit,
            search=search.strip(),
            filter_column=filter_column.strip(),
            filter_value=filter_value.strip(),
        )
    except LegacyResourceNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except LegacyTableNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except LegacyColumnNotFound as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
