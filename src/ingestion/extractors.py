from datetime import date, datetime, timezone
import json
import logging
from typing import Any
from src.config.settings import Settings
from src.ingestion.http_client import ResilientHTTPClient

logger = logging.getLogger("radar_expansao.ingestion")


def _build_bronze_record(fonte: str, entidade: str, endpoint: str, parametros: dict[str, Any], payload: Any) -> dict[str, Any]:
    return {
        "fonte": fonte,
        "entidade": entidade,
        "endpoint": endpoint,
        "parametros": json.dumps(parametros, ensure_ascii=False),
        "payload": json.dumps(payload, ensure_ascii=False),
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    }


def extract_ibge_localidades(client: ResilientHTTPClient, settings: Settings) -> list[dict[str, Any]]:
    endpoint = f"{settings.ibge_base_url}/v1/localidades/municipios"
    logger.info("Extraindo localidades municipais do IBGE...")
    payload = client.get_json(endpoint)
    return [_build_bronze_record("IBGE", "localidades", endpoint, {}, payload)]


def _get_available_periods(client: ResilientHTTPClient, settings: Settings, agregado: int, limit: int = 3) -> list[str]:
    endpoint = f"{settings.ibge_base_url}/v3/agregados/{agregado}/periodos"
    periods_data = client.get_json(endpoint)
    ids = [str(item["id"]) for item in periods_data if "id" in item]
    return ids[-limit:]


def extract_ibge_agregado_por_uf(
    client: ResilientHTTPClient,
    settings: Settings,
    agregado: int,
    variavel: int,
    entidade: str,
    uf_ids: list[int],
    n_periodos: int = 2,
) -> list[dict[str, Any]]:
    periodos = _get_available_periods(client, settings, agregado, limit=n_periodos)
    periodos_str = "|".join(periodos)
    records: list[dict[str, Any]] = []

    logger.info("Extraindo IBGE agregado=%s variavel=%s periodos=%s em %d lotes (UFs)...", agregado, variavel, periodos_str, len(uf_ids))
    for uf_id in uf_ids:
        endpoint = f"{settings.ibge_base_url}/v3/agregados/{agregado}/periodos/{periodos_str}/variaveis/{variavel}"
        params = {"localidades": f"N6[N3[{uf_id}]]"}
        payload = client.get_json(endpoint, params=params)
        records.append(_build_bronze_record("IBGE", entidade, endpoint, params, payload))

    return records


def extract_ibge_ipca(client: ResilientHTTPClient, settings: Settings, n_meses: int = 24) -> list[dict[str, Any]]:
    periodos = _get_available_periods(client, settings, agregado=7060, limit=n_meses)
    periodos_str = "|".join(periodos)
    endpoint = f"{settings.ibge_base_url}/v3/agregados/7060/periodos/{periodos_str}/variaveis/63"
    params = {"localidades": "N1[all]"}
    logger.info("Extraindo IPCA mensal do IBGE (%d meses)...", len(periodos))
    payload = client.get_json(endpoint, params=params)
    return [_build_bronze_record("IBGE", "ipca", endpoint, params, payload)]


def extract_bcb_serie(
    client: ResilientHTTPClient,
    settings: Settings,
    serie_codigo: int,
    entidade: str,
    start_year: int = 2022,
) -> list[dict[str, Any]]:
    """Extrai série diária do BCB SGS respeitando o limite máximo de 10 anos por janela."""
    current_year = date.today().year
    records: list[dict[str, Any]] = []
    endpoint = f"{settings.bcb_base_url}/bcdata.sgs.{serie_codigo}/dados"

    y = start_year
    while y <= current_year:
        end_y = min(y + 9, current_year)
        data_ini = f"01/01/{y}"
        data_fim = f"31/12/{end_y}" if end_y < current_year else date.today().strftime("%d/%m/%Y")
        params = {"formato": "json", "dataInicial": data_ini, "dataFinal": data_fim}
        logger.info("Extraindo BCB SGS serie=%s (%s) janela %s a %s...", serie_codigo, entidade, data_ini, data_fim)
        payload = client.get_json(endpoint, params=params)
        records.append(_build_bronze_record("BCB", entidade, endpoint, params, payload))
        y = end_y + 1

    return records


def run_ingestion(settings: Settings) -> list[dict[str, Any]]:
    client = ResilientHTTPClient(timeout=settings.request_timeout, rate_limit_sleep=settings.rate_limit_sleep)
    bronze_records: list[dict[str, Any]] = []

    loc_records = extract_ibge_localidades(client, settings)
    bronze_records.extend(loc_records)

    raw_municipios = json.loads(loc_records[0]["payload"])
    uf_ids = sorted({int(m["microrregiao"]["mesorregiao"]["UF"]["id"]) for m in raw_municipios if m.get("microrregiao")})

    bronze_records.extend(
        extract_ibge_agregado_por_uf(client, settings, agregado=6579, variavel=9324, entidade="populacao", uf_ids=uf_ids, n_periodos=2)
    )
    bronze_records.extend(
        extract_ibge_agregado_por_uf(client, settings, agregado=5938, variavel=37, entidade="pib", uf_ids=uf_ids, n_periodos=2)
    )
    bronze_records.extend(extract_ibge_ipca(client, settings, n_meses=24))
    bronze_records.extend(extract_bcb_serie(client, settings, serie_codigo=432, entidade="selic", start_year=2022))
    bronze_records.extend(extract_bcb_serie(client, settings, serie_codigo=10813, entidade="dolar", start_year=2022))

    logger.info("Ingestão concluída: %d payloads brutos capturados na camada Bronze.", len(bronze_records))
    return bronze_records
