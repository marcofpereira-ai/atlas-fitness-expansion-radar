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
    logger.info("Localidades extraídas: %d municípios", len(payload) if isinstance(payload, list) else 0)
    return [_build_bronze_record("IBGE", "localidades", endpoint, {}, payload)]


def _get_available_periods(client: ResilientHTTPClient, settings: Settings, agregado: int, limit: int = 3) -> list[str]:
    endpoint = f"{settings.ibge_base_url}/v3/agregados/{agregado}/periodos"
    periods_data = client.get_json(endpoint)
    ids = [str(item["id"]) for item in periods_data if "id" in item]
    logger.debug("Agregado %s: %d períodos disponíveis, usando últimos %d: %s", agregado, len(ids), limit, ids[-limit:])
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

    logger.info(
        "Extraindo IBGE agregado=%s variavel=%s periodos=%s em %d lotes (UFs)...",
        agregado, variavel, periodos_str, len(uf_ids)
    )
    for uf_id in uf_ids:
        endpoint = f"{settings.ibge_base_url}/v3/agregados/{agregado}/periodos/{periodos_str}/variaveis/{variavel}"
        params = {"localidades": f"N6[N3[{uf_id}]]"}
        logger.debug("Lote UF %s: requisição para %s", uf_id, endpoint)
        try:
            payload = client.get_json(endpoint, params=params)
            # Log response structure for observability
            if isinstance(payload, list) and payload:
                first_item = payload[0]
                num_results = len(first_item.get("resultados", [])) if isinstance(first_item, dict) else 0
                logger.info(
                    "Lote UF %s: OK | resultados=%d | tamanho payload=%d chars",
                    uf_id, num_results, len(json.dumps(payload, ensure_ascii=False))
                )
            elif isinstance(payload, list) and not payload:
                logger.warning("Lote UF %s: resposta vazia (lista vazia)", uf_id)
            else:
                logger.warning("Lote UF %s: estrutura inesperada: %s", uf_id, type(payload).__name__)
            records.append(_build_bronze_record("IBGE", entidade, endpoint, params, payload))
        except Exception as exc:
            logger.error("Lote UF %s: FALHA | erro=%s", uf_id, exc)
            # Still record the failure in bronze for auditability
            records.append(_build_bronze_record("IBGE", entidade, endpoint, params, {"error": str(exc)}))

    return records


def extract_ibge_ipca(client: ResilientHTTPClient, settings: Settings, n_meses: int = 24) -> list[dict[str, Any]]:
    periodos = _get_available_periods(client, settings, agregado=7060, limit=n_meses)
    periodos_str = "|".join(periodos)
    endpoint = f"{settings.ibge_base_url}/v3/agregados/7060/periodos/{periodos_str}/variaveis/63"
    params = {"localidades": "N1[all]"}
    logger.info("Extraindo IPCA mensal do IBGE (%d meses)...", len(periodos))
    payload = client.get_json(endpoint, params=params)
    logger.info("IPCA extraído: %d séries", len(payload) if isinstance(payload, list) else 0)
    return [_build_bronze_record("IBGE", "ipca", endpoint, params, payload)]


def _validate_bcb_response(payload: Any, serie_codigo: int, entidade: str, data_ini: str, data_fim: str) -> list:
    """
    Valida que a resposta do BCB SGS é uma lista JSON válida (não um objeto de erro).
    A API BCB retorna lista em caso de sucesso, ou objeto {"erro": "..."} em caso de falha.
    """
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        # Check for BCB error object format
        if "erro" in payload or "error" in payload or "mensagem" in payload:
            raise ValueError(f"BCB SGS serie {serie_codigo} ({entidade}) retornou erro: {payload}")
        # Some endpoints might wrap the list in a dict
        for key, value in payload.items():
            if isinstance(value, list):
                logger.warning("BCB SGS serie %s: resposta wrapada em dict com chave '%s', extraindo lista", serie_codigo, key)
                return value
    raise ValueError(
        f"BCB SGS serie {serie_codigo} ({entidade}) janela {data_ini} a {data_fim}: "
        f"resposta não é uma lista JSON válida. Tipo: {type(payload).__name__}, Conteúdo: {payload}"
    )


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
        end_y = min(y + 9, current_year)  # Janela máxima de 10 anos (y a y+9 inclusive = 10 anos)
        data_ini = f"01/01/{y}"
        data_fim = f"31/12/{end_y}" if end_y < current_year else date.today().strftime("%d/%m/%Y")
        params = {"formato": "json", "dataInicial": data_ini, "dataFinal": data_fim}
        logger.info("Extraindo BCB SGS serie=%s (%s) janela %s a %s...", serie_codigo, entidade, data_ini, data_fim)
        payload = client.get_json(endpoint, params=params)
        # Validate response is a proper JSON list
        validated_payload = _validate_bcb_response(payload, serie_codigo, entidade, data_ini, data_fim)
        logger.info("BCB SGS serie=%s (%s) janela %s-%s: %d registros", serie_codigo, entidade, data_ini, data_fim, len(validated_payload))
        records.append(_build_bronze_record("BCB", entidade, endpoint, params, validated_payload))
        y = end_y + 1

    return records


def run_ingestion(settings: Settings, dry_run: bool = False, dry_run_uf_id: int = 35) -> list[dict[str, Any]]:
    """
    Executa ingestão completa ou modo dry-run (teste de conectividade com 1 UF e 1 janela BCB).

    Args:
        settings: Configurações do pipeline
        dry_run: Se True, executa apenas teste de conectividade
        dry_run_uf_id: UF ID para teste (padrão: 35 = São Paulo)
    """
    client = ResilientHTTPClient(
        timeout=settings.request_timeout,
        rate_limit_sleep=settings.rate_limit_sleep,
        backoff_factor=1.5,
    )
    bronze_records: list[dict[str, Any]] = []

    if dry_run:
        logger.info("=== MODO DRY-RUN: Teste de conectividade com UF=%s e janela BCB recente ===", dry_run_uf_id)
        # Teste 1: Localidades (sempre necessário para obter UFs)
        loc_records = extract_ibge_localidades(client, settings)
        bronze_records.extend(loc_records)

        # Teste 2: População para 1 UF (SP = 35), 1 período
        logger.info("Dry-run: testando extração de População (agregado 6579) para UF %s...", dry_run_uf_id)
        bronze_records.extend(
            extract_ibge_agregado_por_uf(client, settings, agregado=6579, variavel=9324, entidade="populacao", uf_ids=[dry_run_uf_id], n_periodos=1)
        )

        # Teste 3: PIB para 1 UF, 1 período
        logger.info("Dry-run: testando extração de PIB (agregado 5938) para UF %s...", dry_run_uf_id)
        bronze_records.extend(
            extract_ibge_agregado_por_uf(client, settings, agregado=5938, variavel=37, entidade="pib", uf_ids=[dry_run_uf_id], n_periodos=1)
        )

        # Teste 4: IPCA (1 mês recente)
        logger.info("Dry-run: testando extração de IPCA (agregado 7060)...")
        bronze_records.extend(extract_ibge_ipca(client, settings, n_meses=1))

        # Teste 5: BCB Selic (janela de 1 ano recente)
        current_year = date.today().year
        logger.info("Dry-run: testando extração de Selic (serie 432) ano %s...", current_year)
        bronze_records.extend(extract_bcb_serie(client, settings, serie_codigo=432, entidade="selic", start_year=current_year))

        # Teste 6: BCB Dólar (janela de 1 ano recente)
        logger.info("Dry-run: testando extração de Dólar (serie 10813) ano %s...", current_year)
        bronze_records.extend(extract_bcb_serie(client, settings, serie_codigo=10813, entidade="dolar", start_year=current_year))

        logger.info("Dry-run concluído: %d payloads brutos capturados.", len(bronze_records))
        return bronze_records

    # Ingestão completa
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
