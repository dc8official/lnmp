from __future__ import annotations

import os
from pathlib import Path
from typing import List, Literal, Optional, Tuple, Type

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)


class ConfigurationError(Exception):
    """Raised when application configuration is missing, invalid, or cannot be parsed."""
    pass


class DatabaseSettings(BaseModel):
    host: str = "localhost"
    port: int = Field(default=5432, ge=1, le=65535)
    name: str = "netmon"
    user: str = "postgres"
    password: str = "postgres"

    model_config = ConfigDict(extra="ignore")


class MonitoringSettings(BaseModel):
    interval_seconds: int = Field(default=60, ge=10, le=3600)
    ping_count: int = Field(default=10, ge=1, le=20)
    ping_interval_seconds: int = Field(default=6, ge=1, le=60)
    state_confirmation_cycles: int = Field(default=3, ge=1, le=10)
    retention_days: int = Field(default=730, ge=30, le=3650)

    model_config = ConfigDict(extra="ignore")


class ApiSettings(BaseModel):
    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)
    allowed_origins: List[str] = ["*"]

    model_config = ConfigDict(extra="ignore")


class SecuritySettings(BaseModel):
    session_timeout_minutes: int = Field(default=120, ge=1, le=1440)
    max_active_sessions_per_user: int = Field(default=2, ge=1, le=10)
    hsts_enabled: bool = False
    secret_key: str = Field(default="dev-secret-key-change-in-production-min-32-chars")

    model_config = ConfigDict(extra="ignore")


class LoggingSettings(BaseModel):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_dir: str = "/var/log/netmon"

    model_config = ConfigDict(extra="ignore")


class RedisSettings(BaseModel):
    host: str = "127.0.0.1"
    port: int = Field(default=6379, ge=1, le=65535)
    db: int = Field(default=0, ge=0, le=15)
    password: Optional[str] = None
    enabled: bool = True
    performance_mode: bool = False

    model_config = ConfigDict(extra="ignore")


def resolve_config_file() -> Optional[Path]:
    """Resolves configuration file path from environment or standard locations."""
    env_path_str = os.environ.get("NETMON_CONFIG_PATH")
    if env_path_str:
        p = Path(env_path_str)
        if not p.is_file():
            raise ConfigurationError(
                f"Config file specified by NETMON_CONFIG_PATH does not exist: {p}"
            )
        return p

    prod_path = Path("/etc/netmon/config.toml")
    if prod_path.is_file():
        return prod_path

    # Development fallback in repository deploy/
    repo_fallback = (
        Path(__file__).resolve().parent.parent.parent
        / "deploy"
        / "config.template.toml"
    )
    if repo_fallback.is_file():
        return repo_fallback

    local_toml = Path("config.toml")
    if local_toml.is_file():
        return local_toml

    return None


class Settings(BaseSettings):
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)
    api: ApiSettings = Field(default_factory=ApiSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)

    model_config = SettingsConfigDict(
        env_prefix="NETMON_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        cfg_file = resolve_config_file()
        if cfg_file is not None:
            try:
                toml_source = TomlConfigSettingsSource(
                    settings_cls,
                    toml_file=cfg_file,
                )
                return (
                    init_settings,
                    env_settings,
                    dotenv_settings,
                    toml_source,
                    file_secret_settings,
                )
            except Exception as e:
                raise ConfigurationError(
                    f"Failed to parse TOML configuration file at {cfg_file}: {e}"
                ) from e
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )

    @property
    def db_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.database.user}:{self.database.password}@"
            f"{self.database.host}:{self.database.port}/{self.database.name}"
        )

    @property
    def sync_db_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.database.user}:{self.database.password}@"
            f"{self.database.host}:{self.database.port}/{self.database.name}"
        )


def load_settings() -> Settings:
    """Load settings with environment variable fallbacks and validation."""
    try:
        loaded = Settings()
    except ValidationError as err:
        raise ConfigurationError(f"Configuration validation failed:\n{err}") from err
    except Exception as exc:
        if isinstance(exc, ConfigurationError):
            raise
        raise ConfigurationError(f"Error loading configuration: {exc}") from exc

    # Legacy environment variable compatibility overrides
    db_pass = os.environ.get("NETMON_DB_PASSWORD") or os.environ.get("POSTGRES_PASSWORD")
    if db_pass:
        loaded.database.password = db_pass

    db_user = os.environ.get("NETMON_DB_USER") or os.environ.get("POSTGRES_USER")
    if db_user:
        loaded.database.user = db_user

    db_host = os.environ.get("NETMON_DB_HOST") or os.environ.get("POSTGRES_HOST")
    if db_host:
        loaded.database.host = db_host

    db_port = os.environ.get("NETMON_DB_PORT") or os.environ.get("POSTGRES_PORT")
    if db_port:
        try:
            loaded.database.port = int(db_port)
        except ValueError:
            raise ConfigurationError(f"Invalid integer for database port: {db_port}")

    db_name = os.environ.get("NETMON_DB_NAME") or os.environ.get("POSTGRES_DB")
    if db_name:
        loaded.database.name = db_name

    secret_key = os.environ.get("NETMON_SECRET_KEY")
    if secret_key:
        loaded.security.secret_key = secret_key

    return loaded


settings = load_settings()
