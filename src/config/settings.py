import logging
import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    database_url: str | None
    log_level: str
    output_dir: Path
    request_timeout: int
    rate_limit_sleep: float
    backoff_factor: float
    ibge_base_url: str = "https://servicodados.ibge.gov.br/api"
    bcb_base_url: str = "https://api.bcb.gov.br/dados/serie"


def get_settings() -> Settings:
    output_path = Path(os.getenv("OUTPUT_DIR", "output"))
    output_path.mkdir(parents=True, exist_ok=True)
    return Settings(
        database_url=os.getenv("DATABASE_URL") or None,
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        output_dir=output_path,
        request_timeout=int(os.getenv("REQUEST_TIMEOUT", "30")),
        rate_limit_sleep=float(os.getenv("RATE_LIMIT_SLEEP", "0.35")),
        backoff_factor=float(os.getenv("BACKOFF_FACTOR", "1.5")),
    )


def configure_logging(level: str = "INFO") -> logging.Logger:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger("radar_expansao")
