"""Public exports for platform-level services and shared ports."""

from app_platform.api.app_factory import build_fastapi_app
from app_platform.api.dependencies.container import (
    AppContainer,
    AppSettingsDep,
    DependencyContainerNotReadyError,
    get_app_container,
    get_app_settings,
    set_app_container,
)
from app_platform.api.error_handlers_app_exception import ApplicationHTTPException
from app_platform.config.settings import AppSettings, get_settings
from app_platform.persistence.lifecycle import ClosableResource
from app_platform.persistence.readiness import ReadinessProbe
from app_platform.persistence.sqlmodel.engine import build_engine
from app_platform.shared.adapters.system_clock import SystemClock
from app_platform.shared.adapters.uuid_id_generator import UUIDIdGenerator
from app_platform.shared.clock_port import ClockPort
from app_platform.shared.id_generator_port import IdGeneratorPort
from app_platform.shared.result import Err, Ok, Result

__all__ = [
    "AppContainer",
    "AppSettings",
    "AppSettingsDep",
    "ApplicationHTTPException",
    "ClockPort",
    "ClosableResource",
    "DependencyContainerNotReadyError",
    "Err",
    "IdGeneratorPort",
    "Ok",
    "ReadinessProbe",
    "Result",
    "SystemClock",
    "UUIDIdGenerator",
    "build_engine",
    "build_fastapi_app",
    "get_app_container",
    "get_app_settings",
    "get_settings",
    "set_app_container",
]
