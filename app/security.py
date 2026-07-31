import hmac

from fastapi import Depends, Header, HTTPException, Request, status

from app.config import Settings, get_settings


def require_service_auth(
    request: Request,
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    client_ip = request.client.host if request.client else ""
    if client_ip not in settings.allowed_client_list():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cliente não autorizado.")

    scheme, _, supplied_token = (authorization or "").partition(" ")
    expected_token = settings.bridge_service_token.get_secret_value()
    if scheme.lower() != "bearer" or not hmac.compare_digest(supplied_token, expected_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token de serviço inválido.")
