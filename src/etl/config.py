"""Configuration helpers for the local SalesLens ETL."""

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    """Runtime paths and PostgreSQL settings loaded from the local .env file."""

    processed_dir: Path
    database: str
    user: str
    password: str
    host: str
    port: int

    @property
    def connection_kwargs(self) -> dict[str, str | int]:
        return {
            "dbname": self.database,
            "user": self.user,
            "password": self.password,
            "host": self.host,
            "port": self.port,
            "connect_timeout": 5,
        }


def get_settings() -> Settings:
    """Load required local settings without exposing credentials in logs."""
    load_dotenv(PROJECT_ROOT / ".env")

    values = {
        "database": os.getenv("POSTGRES_DB"),
        "user": os.getenv("POSTGRES_USER"),
        "password": os.getenv("POSTGRES_PASSWORD"),
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": os.getenv("POSTGRES_PORT", "5432"),
    }
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise RuntimeError(
            "Missing required PostgreSQL settings in .env: " + ", ".join(missing)
        )

    return Settings(
        processed_dir=PROJECT_ROOT / "data" / "processed",
        database=str(values["database"]),
        user=str(values["user"]),
        password=str(values["password"]),
        host=str(values["host"]),
        port=int(str(values["port"])),
    )
