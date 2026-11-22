import logging
import time
from typing import Any
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger("radar_expansao.http")


class ResilientHTTPClient:
    """Cliente HTTP com retentativas exponenciais, timeout e rate-limiting."""

    def __init__(self, timeout: int = 30, rate_limit_sleep: float = 0.35, max_retries: int = 4) -> None:
        self.timeout = timeout
        self.rate_limit_sleep = rate_limit_sleep
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "AtlasFitness-RadarExpansao/1.0 (DataEngineeringPipeline)",
                "Accept": "application/json",
            }
        )

        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        time.sleep(self.rate_limit_sleep)
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as exc:
            logger.error("Falha na requisição GET %s | params=%s | erro=%s", url, params, exc)
            raise
