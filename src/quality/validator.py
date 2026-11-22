from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any
import pandas as pd

logger = logging.getLogger("radar_expansao.quality")


def run_data_quality_checks(tables: dict[str, pd.DataFrame], output_dir: Path) -> dict[str, Any]:
    """Executa auditoria de schema, null ratio, unicidade e intervalos nas camadas Silver/Gold."""
    ranking_df = tables["gold_ranking_expansao"]
    macro_df = tables["gold_contexto_macro"]
    mun_df = tables["silver_dim_municipio"]

    expected_ranking_cols = {
        "codigo_ibge",
        "nome_municipio",
        "uf_sigla",
        "populacao_estimada",
        "pib_per_capita",
        "score_platinum",
        "score_smart",
        "modelo_recomendado",
    }
    missing_cols = sorted(expected_ranking_cols - set(ranking_df.columns))

    null_ratios = {col: round(float(ranking_df[col].isna().mean()), 4) for col in ranking_df.columns}
    unique_ibge = bool(ranking_df["codigo_ibge"].is_unique)
    valid_scores = bool(
        ranking_df["score_platinum"].between(0, 100).all() and ranking_df["score_smart"].between(0, 100).all()
    )
    valid_population = bool((ranking_df["populacao_estimada"] >= 50000).all())
    valid_macro = bool((macro_df["selic_meta_media"].dropna() >= 0).all())

    checks = [
        {
            "check_name": "schema_gold_ranking_expansao",
            "passed": len(missing_cols) == 0,
            "details": f"Missing columns: {missing_cols}",
        },
        {
            "check_name": "uniqueness_codigo_ibge",
            "passed": unique_ibge,
            "details": f"Total rows: {len(ranking_df)}, Unique codigo_ibge: {ranking_df['codigo_ibge'].nunique()}",
        },
        {
            "check_name": "range_scores_0_to_100",
            "passed": valid_scores,
            "details": f"Platinum [{ranking_df['score_platinum'].min()}, {ranking_df['score_platinum'].max()}] | Smart [{ranking_df['score_smart'].min()}, {ranking_df['score_smart'].max()}]",
        },
        {
            "check_name": "range_populacao_elegivel_min_50k",
            "passed": valid_population,
            "details": f"Min populacao elegivel: {int(ranking_df['populacao_estimada'].min())}",
        },
        {
            "check_name": "range_selic_non_negative",
            "passed": valid_macro,
            "details": f"Macro rows: {len(macro_df)}",
        },
    ]

    all_passed = all(c["passed"] for c in checks)
    report = {
        "project": "Radar de Expansao - Atlas Fitness",
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASSED" if all_passed else "FAILED",
        "summary": {
            "total_municipios_brasil": int(len(mun_df)),
            "municipios_elegiveis_ranking": int(len(ranking_df)),
            "meses_macroeconomia": int(len(macro_df)),
        },
        "checks": checks,
        "null_ratio_gold_ranking": null_ratios,
    }

    json_path = output_dir / "quality_report.json"
    csv_path = output_dir / "quality_report.csv"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    pd.DataFrame(checks).to_csv(csv_path, index=False)
    logger.info("Relatório de Data Quality salvo em %s (Status: %s)", json_path, report["status"])

    if not all_passed:
        raise ValueError("Falha crítica nas regras de Data Quality. Verifique output/quality_report.json.")

    return report
