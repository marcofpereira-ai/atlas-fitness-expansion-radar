"""
Teste de fumaça (smoke test) para validar conectividade das APIs IBGE e BCB SGS.

Executa extração mínima com:
- 1 UF (São Paulo, ID 35) para IBGE (População e PIB)
- 1 janela recente (ano atual) para BCB SGS (Selic série 432 e Dólar série 10813)
- 1 mês para IPCA

Uso:
    python -m tests.test_ingestion_smoke
    # ou via CLI principal:
    python -m src.main --dry-run
"""
import sys
from pathlib import Path

# Adiciona src ao path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.config.settings import configure_logging, get_settings
from src.ingestion.extractors import run_ingestion


def test_ibge_connectivity() -> bool:
    """Testa conectividade básica com API IBGE (Localidades + 1 UF)."""
    settings = get_settings()
    logger = configure_logging("DEBUG")

    logger.info("=== SMOKE TEST: Conectividade IBGE ===")
    bronze_records = run_ingestion(settings, dry_run=True, dry_run_uf_id=35)

    # Validações
    ibge_records = [r for r in bronze_records if r["fonte"] == "IBGE"]
    bcb_records = [r for r in bronze_records if r["fonte"] == "BCB"]

    assert len(ibge_records) >= 4, f"Esperado >=4 registros IBGE, obtido {len(ibge_records)}"
    assert len(bcb_records) >= 2, f"Esperado >=2 registros BCB, obtido {len(bcb_records)}"

    # Verifica entidades esperadas
    ibge_entidades = {r["entidade"] for r in ibge_records}
    expected_ibge = {"localidades", "populacao", "pib", "ipca"}
    assert expected_ibge.issubset(ibge_entidades), f"Entidades IBGE faltando: {expected_ibge - ibge_entidades}"

    # Verifica BCB
    bcb_entidades = {r["entidade"] for r in bcb_records}
    expected_bcb = {"selic", "dolar"}
    assert expected_bcb.issubset(bcb_entidades), f"Entidades BCB faltando: {expected_bcb - bcb_entidades}"

    # Valida payloads não estão vazios
    for r in bronze_records:
        import json
        payload = json.loads(r["payload"])
        # Não deve ser um objeto de erro
        if isinstance(payload, dict) and "erro" in payload:
            raise AssertionError(f"Payload contém erro da API: {payload}")
        # Lista não deve estar vazia (exceto IPCA que pode ter 1 item)
        if isinstance(payload, list) and r["entidade"] != "ipca" and len(payload) == 0:
            raise AssertionError(f"Payload vazio para {r['entidade']}")

    logger.info("✓ Smoke test IBGE/BCB passou: %d registros IBGE, %d registros BCB", len(ibge_records), len(bcb_records))
    return True


def main() -> int:
    try:
        test_ibge_connectivity()
        print("\n[OK] SMOKE TEST PASSOU - APIs IBGE e BCB acessiveis e retornando payloads validos")
        return 0
    except Exception as e:
        print(f"\n[ERRO] SMOKE TEST FALHOU: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())