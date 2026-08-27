import os
import sys
from pathlib import Path
from typing import List, Literal
import tomllib

from pydantic import BaseModel, Field, ValidationError


class DatabaseSettings(BaseModel):
    host: str
    port: int = Field(..., ge=1, le=65535)
    name: str
    user: str
    password: str


class MonitoringSettings(BaseModel):
    interval_seconds: int = Field(..., ge=10, le=3600)
    ping_count: int = Field(..., ge=1, le=20)
    ping_interval_seconds: int = Field(..., ge=1, le=60)
    state_confirmation_cycles: int = Field(..., ge=1, le=10)
    retention_days: int = Field(..., ge=30, le=3650)


class ApiSettings(BaseModel):
    host: str
    port: int = Field(..., ge=1, le=65535)
    allowed_origins: List[str]


class SecuritySettings(BaseModel):
    session_timeout_minutes: int = Field(default=120, ge=1, le=1440)
    max_active_sessions_per_user: int = Field(default=2, ge=1, le=10)
    hsts_enabled: bool
    secret_key: str


class LoggingSettings(BaseModel):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"]
    log_dir: str


class Settings(BaseModel):
    database: DatabaseSettings
    monitoring: MonitoringSettings
    api: ApiSettings
    security: SecuritySettings
    logging: LoggingSettings

    @property
    def db_url(self) -> str:
        return f"postgresql+asyncpg://{self.database.user}:{self.database.password}@{self.database.host}:{self.database.port}/{self.database.name}"

    @property
    def sync_db_url(self) -> str:
        return f"postgresql+psycopg2://{self.database.user}:{self.database.password}@{self.database.host}:{self.database.port}/{self.database.name}"


def load_settings() -> Settings:
    config_path = None

    # 1. Path specified in environment variable NETMON_CONFIG_PATH (if set)
    env_path_str = os.environ.get("NETMON_CONFIG_PATH")
    if env_path_str:
        config_path = Path(env_path_str)
        if not config_path.is_file():
            print(
                f"Error: Config file specified by NETMON_CONFIG_PATH does not exist: {config_path}",
                file=sys.stderr,
            )
            sys.exit(1)

    # 2. /etc/netmon/config.toml (production default)
    if not config_path:
        prod_path = Path("/etc/netmon/config.toml")
        if prod_path.is_file():
            config_path = prod_path

    # 3. deploy/config.template.toml relative to the project root (development fallback only)
    if not config_path:
        fallback_path = (
            Path(__file__).resolve().parent.parent.parent
            / "deploy"
            / "config.template.toml"
        )
        if fallback_path.is_file():
            config_path = fallback_path
            print(
                f"Warning: Configuration file not found at NETMON_CONFIG_PATH or /etc/netmon/config.toml. Falling back to development config: {config_path}"
            )
        else:
            print(
                "Error: No configuration file could be resolved.",
                file=sys.stderr,
            )
            sys.exit(1)

    try:
        with open(config_path, "rb") as f:
            config_data = tomllib.load(f)
    except Exception as e:
        print(
            f"Error: Failed to parse TOML configuration file at {config_path}: {e}",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        from dotenv import load_dotenv
        load_dotenv()
        backend_env = Path(__file__).resolve().parent.parent / ".env"
        if backend_env.is_file():
            load_dotenv(dotenv_path=backend_env)
    except Exception:
        pass

    db_password = os.environ.get("NETMON_DB_PASSWORD") or os.environ.get("POSTGRES_PASSWORD", "postgres")
    secret_key = os.environ.get("NETMON_SECRET_KEY") or config_data.get("security", {}).get("secret_key")

    if not db_password or not db_password.strip():
        db_password = "postgres"

    if not secret_key or not str(secret_key).strip():
        print(
            "CRITICAL SECURITY ERROR: NETMON_SECRET_KEY is missing or empty. "
            "Set NETMON_SECRET_KEY in environment or .env file before starting.",
            file=sys.stderr,
        )
        sys.exit(1)

    db_user = os.environ.get("NETMON_DB_USER") or os.environ.get("POSTGRES_USER")
    db_host = os.environ.get("NETMON_DB_HOST") or os.environ.get("POSTGRES_HOST")
    db_port = os.environ.get("NETMON_DB_PORT") or os.environ.get("POSTGRES_PORT")
    db_name = os.environ.get("NETMON_DB_NAME") or os.environ.get("POSTGRES_DB")

    if "database" not in config_data or not isinstance(config_data["database"], dict):
        config_data["database"] = {}

    if db_user:
        config_data["database"]["user"] = db_user
    if db_host:
        config_data["database"]["host"] = db_host
    if db_port:
        config_data["database"]["port"] = int(db_port)
    if db_name:
        config_data["database"]["name"] = db_name

    config_data["database"]["password"] = db_password

    if "security" not in config_data or not isinstance(config_data["security"], dict):
        config_data["security"] = {}
    config_data["security"]["secret_key"] = secret_key

    try:
        return Settings(**config_data)
    except ValidationError as e:
        print(
            f"Error: Configuration validation failed:\n{e}", file=sys.stderr
        )
        sys.exit(1)


settings = load_settings()
