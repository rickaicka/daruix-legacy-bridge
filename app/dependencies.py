from fastapi import Depends

from app.config import Settings, get_settings
from app.legacy.connection import AccessConnectionFactory
from app.legacy.repository import LegacyRepository


def get_repository(settings: Settings = Depends(get_settings)) -> LegacyRepository:
    return LegacyRepository(AccessConnectionFactory(settings))

