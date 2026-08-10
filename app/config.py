from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    bridge_service_token: SecretStr
    bridge_allowed_clients: str = "127.0.0.1, 172.19.0.1, 172.18.0.1"
    legacy_db_path: Path = Path("/legacy-db/SGO.accdb")
    legacy_db_password: SecretStr = SecretStr("")
    ucanaccess_classpath: str = "/opt/ucanaccess/*"
    db_connect_timeout_seconds: int = 10

    def allowed_client_list(self) -> list[str]:
        return [item.strip() for item in self.bridge_allowed_clients.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
