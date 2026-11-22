from src.config.settings import configure_logging, get_settings
from src.ingestion.extractors import run_ingestion
from src.quality.validator import run_data_quality_checks
from src.transformation.pipeline_sql import build_silver_and_gold


def main() -> None:
    settings = get_settings()
    logger = configure_logging(settings.log_level)

    logger.info("Iniciando pipeline Radar de Expansão — Atlas Fitness...")
    bronze_records = run_ingestion(settings)
    tables = build_silver_and_gold(
        bronze_records=bronze_records,
        output_dir=settings.output_dir,
        database_url=settings.database_url,
    )
    report = run_data_quality_checks(tables=tables, output_dir=settings.output_dir)

    top_platinum = tables["gold_ranking_expansao"].sort_values("rank_platinum").head(5)
    top_smart = tables["gold_ranking_expansao"].sort_values("rank_smart").head(5)

    logger.info("Top 5 Atlas Platinum:
%s", top_platinum[["rank_platinum", "nome_municipio", "uf_sigla", "pib_per_capita", "score_platinum"]].to_string(index=False))
    logger.info("Top 5 Atlas Smart:
%s", top_smart[["rank_smart", "nome_municipio", "uf_sigla", "populacao_estimada", "score_smart"]].to_string(index=False))
    logger.info("Pipeline finalizado com status: %s", report["status"])


if __name__ == "__main__":
    main()
