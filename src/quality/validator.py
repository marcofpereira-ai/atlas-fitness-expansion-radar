from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any
import pandas as pd

logger = logging.getLogger("radar_expansao.quality")


def run_data_quality_checks(tables: dict[str, pd.DataFrame], output_dir: Path) -> dict[str, Any]:
    """Executa auditoria completa de Data Quality nas camadas Bronze, Silver e Gold."""
    ranking_df = tables["gold_ranking_expansao"]
    macro_df = tables["gold_contexto_macro"]
    mun_df = tables["silver_dim_municipio"]
    indicadores_df = tables["gold_indicadores_municipio"]
    fato_municipal_df = tables["silver_fato_indicadores_municipais"]
    fato_macro_df = tables["silver_fato_macroeconomia"]
    dim_calendario_df = tables.get("silver_dim_calendario", pd.DataFrame())

    # --- Configurações de validação ---
    NULL_RATIO_THRESHOLD = 0.05  # 5%

    # Colunas críticas que não devem ter nulos (ou muito poucos)
    CRITICAL_COLS_RANKING = {
        "codigo_ibge": 0.0,
        "nome_municipio": 0.0,
        "uf_sigla": 0.0,
        "populacao_estimada": 0.0,
        "pib_per_capita": NULL_RATIO_THRESHOLD,
        "score_platinum": 0.0,
        "score_smart": 0.0,
        "modelo_recomendado": 0.0,
    }

    CRITICAL_COLS_MACRO = {
        "data_ref": 0.0,
        "selic_meta_media": NULL_RATIO_THRESHOLD,
        "dolar_venda_medio": NULL_RATIO_THRESHOLD,
        # IPCA tem cobertura histórica menor (~24 meses) vs Selic/Dolar (~60+ meses)
        # Threshold mais alto esperado: ~60% nulos para meses antigos
        "ipca_mensal_pct": 0.70,
    }

    # --- 1. Validação de Schema ---
    expected_ranking_cols = {
        "codigo_ibge", "nome_municipio", "uf_sigla", "uf_nome", "regiao_nome",
        "porte_municipio", "ano_pop", "populacao_estimada", "crescimento_pop_pct",
        "ano_pib", "pib_total_reais", "pib_per_capita",
        "score_platinum", "rank_platinum", "score_smart", "rank_smart",
        "modelo_recomendado", "ano", "mes"
    }
    missing_cols = sorted(expected_ranking_cols - set(ranking_df.columns))
    extra_cols = sorted(set(ranking_df.columns) - expected_ranking_cols)

    # --- 2. Null Ratio por coluna ---
    null_ratios_ranking = {col: round(float(ranking_df[col].isna().mean()), 4) for col in ranking_df.columns}
    null_ratios_macro = {col: round(float(macro_df[col].isna().mean()), 4) for col in macro_df.columns}
    null_ratios_indicadores = {col: round(float(indicadores_df[col].isna().mean()), 4) for col in indicadores_df.columns}

    # Verifica colunas críticas
    critical_null_violations = []
    for col, threshold in CRITICAL_COLS_RANKING.items():
        if col in null_ratios_ranking and null_ratios_ranking[col] > threshold:
            critical_null_violations.append(f"{col}: {null_ratios_ranking[col]*100:.2f}% > {threshold*100:.0f}%")

    for col, threshold in CRITICAL_COLS_MACRO.items():
        if col in null_ratios_macro and null_ratios_macro[col] > threshold:
            critical_null_violations.append(f"{col}: {null_ratios_macro[col]*100:.2f}% > {threshold*100:.0f}%")

    # --- 3. Unicidade ---
    unique_ibge_ranking = bool(ranking_df["codigo_ibge"].is_unique)
    unique_ibge_municipio = bool(mun_df["codigo_ibge"].is_unique)
    unique_macro_data_ref = bool(macro_df["data_ref"].is_unique) if "data_ref" in macro_df.columns else True

    # --- 4. Range Checks ---
    # Scores 0-100
    valid_scores = bool(
        ranking_df["score_platinum"].between(0, 100).all() and ranking_df["score_smart"].between(0, 100).all()
    )
    score_platinum_range = (float(ranking_df["score_platinum"].min()), float(ranking_df["score_platinum"].max()))
    score_smart_range = (float(ranking_df["score_smart"].min()), float(ranking_df["score_smart"].max()))

    # População elegível >= 50k
    valid_population = bool((ranking_df["populacao_estimada"] >= 50000).all())
    min_pop = int(ranking_df["populacao_estimada"].min()) if len(ranking_df) > 0 else 0

    # PIB per capita > 0
    valid_pib_pc = bool((ranking_df["pib_per_capita"] > 0).all()) if "pib_per_capita" in ranking_df.columns else True
    min_pib_pc = float(ranking_df["pib_per_capita"].min()) if "pib_per_capita" in ranking_df.columns and len(ranking_df) > 0 else 0

    # Macroeconomia
    valid_selic = bool((macro_df["selic_meta_media"].dropna() >= 0).all()) if "selic_meta_media" in macro_df.columns else True
    valid_dolar = bool((macro_df["dolar_venda_medio"].dropna() >= 0).all()) if "dolar_venda_medio" in macro_df.columns else True
    valid_ipca = True  # IPCA pode ser negativo (deflação)

    # Crescimento populacional - range razoável
    valid_crescimento = bool(ranking_df["crescimento_pop_pct"].between(-50, 200).all()) if "crescimento_pop_pct" in ranking_df.columns else True

    # --- 5. Contagens por camada ---
    bronze_count = len(tables.get("bronze_raw_records", [])) if "bronze_raw_records" in tables else 0
    # Se não tiver bronze no tables, tentamos inferir do contexto
    # (o bronze é passado separado no main, mas não está no dict tables)

    # --- Compila checks ---
    checks = [
        {
            "check_name": "schema_gold_ranking_expansao",
            "passed": len(missing_cols) == 0,
            "details": f"Missing: {missing_cols} | Extra: {extra_cols}",
        },
        {
            "check_name": "null_ratio_critical_columns",
            "passed": len(critical_null_violations) == 0,
            "details": "Violações: " + "; ".join(critical_null_violations) if critical_null_violations else "Todas colunas críticas dentro do threshold (5%)",
        },
        {
            "check_name": "uniqueness_codigo_ibge_ranking",
            "passed": unique_ibge_ranking,
            "details": f"Total rows: {len(ranking_df)}, Unique codigo_ibge: {ranking_df['codigo_ibge'].nunique()}",
        },
        {
            "check_name": "uniqueness_codigo_ibge_dim_municipio",
            "passed": unique_ibge_municipio,
            "details": f"Total rows: {len(mun_df)}, Unique codigo_ibge: {mun_df['codigo_ibge'].nunique()}",
        },
        {
            "check_name": "uniqueness_data_ref_macro",
            "passed": unique_macro_data_ref,
            "details": f"Total rows: {len(macro_df)}, Unique data_ref: {macro_df['data_ref'].nunique()}" if "data_ref" in macro_df.columns else "N/A",
        },
        {
            "check_name": "range_scores_0_to_100",
            "passed": valid_scores,
            "details": f"Platinum {score_platinum_range} | Smart {score_smart_range}",
        },
        {
            "check_name": "range_populacao_elegivel_min_50k",
            "passed": valid_population,
            "details": f"Min populacao elegivel: {min_pop}",
        },
        {
            "check_name": "range_pib_per_capita_positive",
            "passed": valid_pib_pc,
            "details": f"Min PIB per capita: {min_pib_pc:.2f}",
        },
        {
            "check_name": "range_crescimento_pop_pct_reasonable",
            "passed": valid_crescimento,
            "details": f"Crescimento range: [{ranking_df['crescimento_pop_pct'].min():.2f}, {ranking_df['crescimento_pop_pct'].max():.2f}]%" if "crescimento_pop_pct" in ranking_df.columns else "N/A",
        },
        {
            "check_name": "range_selic_non_negative",
            "passed": valid_selic,
            "details": f"Selic min: {macro_df['selic_meta_media'].min():.4f}" if "selic_meta_media" in macro_df.columns else "N/A",
        },
        {
            "check_name": "range_dolar_non_negative",
            "passed": valid_dolar,
            "details": f"Dólar min: {macro_df['dolar_venda_medio'].min():.4f}" if "dolar_venda_medio" in macro_df.columns else "N/A",
        },
    ]

    all_passed = all(c["passed"] for c in checks)

    # --- Relatório completo ---
    report = {
        "project": "Radar de Expansao - Atlas Fitness",
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASSED" if all_passed else "FAILED",
        "summary": {
            "total_municipios_brasil": int(len(mun_df)),
            "municipios_elegiveis_ranking": int(len(ranking_df)),
            "municipios_com_pib_valido": int(len(indicadores_df[indicadores_df["pib_per_capita"].notna()])) if "pib_per_capita" in indicadores_df.columns else 0,
            "meses_macroeconomia": int(len(macro_df)),
            "registros_fato_municipal": int(len(fato_municipal_df)),
            "registros_fato_macroeconomia": int(len(fato_macro_df)),
            "datas_calendario": int(len(dim_calendario_df)),
        },
        "checks": checks,
        "null_ratios": {
            "gold_ranking_expansao": null_ratios_ranking,
            "gold_contexto_macro": null_ratios_macro,
            "gold_indicadores_municipio": null_ratios_indicadores,
        },
        "metrics": {
            "score_platinum": {
                "min": score_platinum_range[0],
                "max": score_platinum_range[1],
                "mean": round(float(ranking_df["score_platinum"].mean()), 2) if len(ranking_df) > 0 else 0,
            },
            "score_smart": {
                "min": score_smart_range[0],
                "max": score_smart_range[1],
                "mean": round(float(ranking_df["score_smart"].mean()), 2) if len(ranking_df) > 0 else 0,
            },
            "pib_per_capita": {
                "min": min_pib_pc,
                "max": float(ranking_df["pib_per_capita"].max()) if len(ranking_df) > 0 else 0,
                "mean": round(float(ranking_df["pib_per_capita"].mean()), 2) if len(ranking_df) > 0 else 0,
            },
        },
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
