"""Public exports for platform-level services and shared ports."""

from src.platform.api.app_factory import build_fastapi_app
from src.platform.api.dependencies.container import (
    AppContainer,
    AppSettingsDep,
    DependencyContainerNotReadyError,
    get_app_container,
    get_app_settings,
    set_app_container,
)
from src.platform.api.error_handlers_app_exception import ApplicationHTTPException
from src.platform.config.settings import AppSettings, get_settings
from src.platform.persistence.lifecycle import ClosableResource
from src.platform.persistence.readiness import ReadinessProbe
from src.platform.persistence.sqlmodel.engine import build_engine
from src.platform.shared.adapters.system_clock import SystemClock
from src.platform.shared.adapters.uuid_id_generator import UUIDIdGenerator
from src.platform.shared.clock_port import ClockPort
from src.platform.shared.id_generator_port import IdGeneratorPort
from src.platform.shared.result import Err, Ok, Result

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
