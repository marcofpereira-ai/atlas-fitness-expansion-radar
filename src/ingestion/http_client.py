import logging
import time
from typing import Any
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger("radar_expansao.http")


class ResilientHTTPClient:
    """Cliente HTTP com retentativas exponenciais, timeout configurável e rate-limiting."""

    def __init__(
        self,
        timeout: int = 30,
        rate_limit_sleep: float = 0.35,
        max_retries: int = 4,
        backoff_factor: float = 1.5,
    ) -> None:
        self.timeout = timeout
        self.rate_limit_sleep = rate_limit_sleep
        self.backoff_factor = backoff_factor
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "AtlasFitness-RadarExpansao/1.0 (DataEngineeringPipeline)",
                "Accept": "application/json",
            }
        )

        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        """Executa GET com logging detalhado e tratamento de respostas vazias/instáveis."""
        time.sleep(self.rate_limit_sleep)
        log_params = params.copy() if params else {}
        # Redact sensitive params if any
        for key in log_params:
            if "key" in key.lower() or "token" in key.lower() or "secret" in key.lower():
                log_params[key] = "***"

        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            # Log status code and response size for observability
            response_size = len(response.content) if response.content else 0
            logger.debug(
                "HTTP GET %s | params=%s | status=%d | size=%d bytes",
                url, log_params, response.status_code, response_size
            )

            # Handle empty responses gracefully
            if response.status_code == 204 or response_size == 0:
                logger.warning("Resposta vazia (status=%d) para %s | params=%s", response.status_code, url, log_params)
                return []

            response.raise_for_status()

            data = response.json()
            # Validate JSON structure is not an error object
            if isinstance(data, dict) and "erro" in data:
                logger.error("API retornou objeto de erro: %s | params=%s", data, log_params)
                raise ValueError(f"API error response: {data}")

            return data

        except requests.exceptions.Timeout:
            logger.error("Timeout (%ds) na requisição GET %s | params=%s", self.timeout, url, log_params)
            raise
        except requests.exceptions.RequestException as exc:
            logger.error("Falha na requisição GET %s | params=%s | erro=%s", url, log_params, exc)
            raise
