import json
import logging
from pathlib import Path
from typing import Any
import duckdb
import pandas as pd
from sqlalchemy import create_engine, text

logger = logging.getLogger("radar_expansao.transformation")


def build_silver_and_gold(bronze_records: list[dict[str, Any]], output_dir: Path, database_url: str | None = None) -> dict[str, pd.DataFrame]:
    """
    Executa desaninhamento SQL (UNNEST/JSON) via DuckDB, constrói Silver (Star Schema)
    e Gold (Atlas Fitness), persiste Parquet particionado por ano/mês e sincroniza no Supabase.
    """
    con = duckdb.connect(database=":memory:")

    # 1. Explode Localidades (IBGE)
    loc_payloads = [json.loads(r["payload"]) for r in bronze_records if r["entidade"] == "localidades"]
    municipios_flat = []
    for batch in loc_payloads:
        for m in batch:
            # Handle missing microrregiao/mesorregiao hierarchy gracefully
            microrregiao = m.get("microrregiao")
            if microrregiao and microrregiao.get("mesorregiao") and microrregiao["mesorregiao"].get("UF"):
                uf = microrregiao["mesorregiao"]["UF"]
                reg = uf.get("regiao", {})
                municipios_flat.append(
                    {
                        "codigo_ibge": int(m["id"]),
                        "nome_municipio": m["nome"],
                        "uf_sigla": uf.get("sigla", ""),
                        "uf_nome": uf.get("nome", ""),
                        "regiao_nome": reg.get("nome", ""),
                    }
                )
            else:
                logger.warning("Município %s (%s) sem hierarquia completa UF/Região, pulando", m.get("id"), m.get("nome"))
    con.register("raw_municipios_df", pd.DataFrame(municipios_flat))

    # 2. Explode Séries aninhadas do IBGE (População, PIB, IPCA)
    ibge_series_rows = []
    for r in bronze_records:
        if r["fonte"] == "IBGE" and r["entidade"] in {"populacao", "pib", "ipca"}:
            payload = json.loads(r["payload"])
            for item in payload:
                for res in item.get("resultados", []):
                    for s in res.get("series", []):
                        loc_id = str(s["localidade"]["id"])
                        for periodo, valor_str in s.get("serie", {}).items():
                            ibge_series_rows.append(
                                {
                                    "entidade": r["entidade"],
                                    "localidade_id": loc_id,
                                    "periodo": str(periodo),
                                    "valor_bruto": str(valor_str),
                                    "ingested_at": r["ingested_at"],
                                }
                            )
    con.register("raw_ibge_series_df", pd.DataFrame(ibge_series_rows))

    # 3. Explode Séries BCB (Selic, Dólar)
    bcb_rows = []
    for r in bronze_records:
        if r["fonte"] == "BCB":
            payload = json.loads(r["payload"])
            for row in payload:
                bcb_rows.append(
                    {
                        "entidade": r["entidade"],
                        "data_str": str(row["data"]),
                        "valor_str": str(row["valor"]),
                        "ingested_at": r["ingested_at"],
                    }
                )
    con.register("raw_bcb_df", pd.DataFrame(bcb_rows))

    # SQL Silver: Deduplicação, Tipagem e Tratamento de Nulos ('-', '...', '..', 'X', '')
    con.execute("""
        CREATE TABLE silver_dim_municipio AS
        SELECT DISTINCT
            CAST(codigo_ibge AS INTEGER) AS codigo_ibge,
            TRIM(nome_municipio) AS nome_municipio,
            UPPER(TRIM(uf_sigla)) AS uf_sigla,
            TRIM(uf_nome) AS uf_nome,
            TRIM(regiao_nome) AS regiao_nome
        FROM raw_municipios_df
        WHERE codigo_ibge IS NOT NULL;
    """)

    con.execute("""
        CREATE TABLE silver_ibge_limpo AS
        WITH dedup AS (
            SELECT
                entidade,
                localidade_id,
                periodo,
                CASE
                    WHEN TRIM(valor_bruto) IN ('-', '...', '..', 'X', '') THEN NULL
                    ELSE TRY_CAST(REPLACE(TRIM(valor_bruto), ',', '.') AS DOUBLE)
                END AS valor_num,
                ROW_NUMBER() OVER (PARTITION BY entidade, localidade_id, periodo ORDER BY ingested_at DESC) AS rn
            FROM raw_ibge_series_df
        )
        SELECT entidade, localidade_id, periodo, valor_num
        FROM dedup
        WHERE rn = 1;
    """)

    con.execute("""
        CREATE TABLE silver_fato_indicadores_municipais AS
        WITH pop AS (
            SELECT CAST(localidade_id AS INTEGER) AS codigo_ibge, CAST(periodo AS INTEGER) AS ano, CAST(valor_num AS BIGINT) AS populacao_estimada
            FROM silver_ibge_limpo
            WHERE entidade = 'populacao'
        ),
        pib AS (
            SELECT CAST(localidade_id AS INTEGER) AS codigo_ibge, CAST(periodo AS INTEGER) AS ano, CAST(valor_num AS DOUBLE) AS pib_mil_reais
            FROM silver_ibge_limpo
            WHERE entidade = 'pib'
        )
        SELECT
            COALESCE(pop.codigo_ibge, pib.codigo_ibge) AS codigo_ibge,
            COALESCE(pop.ano, pib.ano) AS ano,
            pop.populacao_estimada,
            pib.pib_mil_reais
        FROM pop
        FULL OUTER JOIN pib
            ON pop.codigo_ibge = pib.codigo_ibge AND pop.ano = pib.ano;
    """)

    # 4. Dimensão Calendário (silver_dim_calendario) - conforme spec.md
    con.execute("""
        CREATE TABLE silver_dim_calendario AS
        WITH datas AS (
            SELECT DISTINCT data_ref
            FROM (
                SELECT MAKE_DATE(b.ano, b.mes, 1) AS data_ref
                FROM (
                    SELECT
                        EXTRACT(YEAR FROM STRPTIME(data_str, '%d/%m/%Y'))::INT AS ano,
                        EXTRACT(MONTH FROM STRPTIME(data_str, '%d/%m/%Y'))::INT AS mes
                    FROM raw_bcb_df
                    UNION
                    SELECT
                        CAST(SUBSTR(periodo, 1, 4) AS INT) AS ano,
                        CAST(SUBSTR(periodo, 5, 2) AS INT) AS mes
                    FROM silver_ibge_limpo
                    WHERE entidade = 'ipca' AND LENGTH(periodo) = 6
                ) b
            )
        )
        SELECT
            data_ref,
            EXTRACT(YEAR FROM data_ref)::INT AS ano,
            EXTRACT(MONTH FROM data_ref)::INT AS mes,
            EXTRACT(QUARTER FROM data_ref)::INT AS trimestre,
            STRFTIME(data_ref, '%Y-%m') AS ano_mes
        FROM datas
        ORDER BY data_ref;
    """)

    con.execute("""
        CREATE TABLE silver_fato_macroeconomia AS
        WITH bcb_clean AS (
            SELECT
                entidade,
                STRPTIME(data_str, '%d/%m/%Y')::DATE AS data_ref,
                TRY_CAST(REPLACE(valor_str, ',', '.') AS DOUBLE) AS valor,
                ROW_NUMBER() OVER (PARTITION BY entidade, data_str ORDER BY ingested_at DESC) AS rn
            FROM raw_bcb_df
        ),
        bcb_mensal AS (
            SELECT
                EXTRACT(YEAR FROM data_ref)::INT AS ano,
                EXTRACT(MONTH FROM data_ref)::INT AS mes,
                AVG(CASE WHEN entidade = 'selic' THEN valor END) AS selic_meta_media,
                AVG(CASE WHEN entidade = 'dolar' THEN valor END) AS dolar_venda_medio
            FROM bcb_clean
            WHERE rn = 1
            GROUP BY 1, 2
        ),
        ipca_mensal AS (
            SELECT
                CAST(SUBSTR(periodo, 1, 4) AS INT) AS ano,
                CAST(SUBSTR(periodo, 5, 2) AS INT) AS mes,
                valor_num AS ipca_mensal_pct
            FROM silver_ibge_limpo
            WHERE entidade = 'ipca' AND LENGTH(periodo) = 6
        ),
        macro_base AS (
            SELECT
                MAKE_DATE(b.ano, b.mes, 1) AS data_ref,
                b.ano,
                b.mes,
                ROUND(b.selic_meta_media, 4) AS selic_meta_media,
                ROUND(b.dolar_venda_medio, 4) AS dolar_venda_medio,
                ROUND(i.ipca_mensal_pct, 4) AS ipca_mensal_pct
            FROM bcb_mensal b
            LEFT JOIN ipca_mensal i
                ON b.ano = i.ano AND b.mes = i.mes
        )
        SELECT
            m.data_ref,
            m.ano,
            m.mes,
            m.selic_meta_media,
            m.dolar_venda_medio,
            m.ipca_mensal_pct
        FROM macro_base m
        INNER JOIN silver_dim_calendario c
            ON m.data_ref = c.data_ref
        ORDER BY m.data_ref;
    """)

    # SQL Gold: Enriquecimento de Métricas e Ranking Atlas Fitness (Platinum vs Smart)
    con.execute("""
        CREATE TABLE gold_indicadores_municipio AS
        WITH pop_ranked AS (
            SELECT
                codigo_ibge,
                ano AS ano_pop,
                populacao_estimada,
                LAG(populacao_estimada) OVER (PARTITION BY codigo_ibge ORDER BY ano) AS pop_anterior,
                ROW_NUMBER() OVER (PARTITION BY codigo_ibge ORDER BY ano DESC) AS rn
            FROM silver_fato_indicadores_municipais
            WHERE populacao_estimada IS NOT NULL
        ),
        pib_ranked AS (
            SELECT
                codigo_ibge,
                ano AS ano_pib,
                pib_mil_reais,
                ROW_NUMBER() OVER (PARTITION BY codigo_ibge ORDER BY ano DESC) AS rn
            FROM silver_fato_indicadores_municipais
            WHERE pib_mil_reais IS NOT NULL
        )
        SELECT
            m.codigo_ibge,
            m.nome_municipio,
            m.uf_sigla,
            m.uf_nome,
            m.regiao_nome,
            p.ano_pop,
            p.populacao_estimada,
            ROUND(
                CASE WHEN p.pop_anterior > 0
                     THEN ((p.populacao_estimada - p.pop_anterior)::DOUBLE / p.pop_anterior) * 100.0
                     ELSE 0.0
                END, 4
            ) AS crescimento_pop_pct,
            b.ano_pib,
            ROUND(b.pib_mil_reais * 1000.0, 2) AS pib_total_reais,
            ROUND((b.pib_mil_reais * 1000.0) / NULLIF(p.populacao_estimada, 0), 2) AS pib_per_capita,
            CASE
                WHEN p.populacao_estimada >= 500000 THEN 'Grande Porte'
                WHEN p.populacao_estimada >= 100000 THEN 'Médio Porte'
                ELSE 'Pequeno Porte'
            END AS porte_municipio
        FROM silver_dim_municipio m
        INNER JOIN pop_ranked p ON m.codigo_ibge = p.codigo_ibge AND p.rn = 1
        LEFT JOIN pib_ranked b ON m.codigo_ibge = b.codigo_ibge AND b.rn = 1;
    """)

    con.execute("""
        CREATE TABLE gold_ranking_expansao AS
        WITH bounds AS (
            SELECT
                MIN(pib_per_capita) AS min_pib_pc, MAX(pib_per_capita) AS max_pib_pc,
                MIN(populacao_estimada) AS min_pop, MAX(populacao_estimada) AS max_pop,
                MIN(crescimento_pop_pct) AS min_cresc, MAX(crescimento_pop_pct) AS max_cresc
            FROM gold_indicadores_municipio
            WHERE populacao_estimada >= 50000 AND pib_per_capita IS NOT NULL
        ),
        norm AS (
            SELECT
                g.*,
                -- Min-Max normalization: handle min=max case by assigning 50 (midpoint)
                COALESCE(
                    ((g.pib_per_capita - b.min_pib_pc) / NULLIF(b.max_pib_pc - b.min_pib_pc, 0)) * 100.0,
                    50.0
                ) AS idx_pib_pc,
                COALESCE(
                    ((g.populacao_estimada - b.min_pop) / NULLIF(b.max_pop - b.min_pop, 0)) * 100.0,
                    50.0
                ) AS idx_pop,
                COALESCE(
                    ((g.crescimento_pop_pct - b.min_cresc) / NULLIF(b.max_cresc - b.min_cresc, 0)) * 100.0,
                    50.0
                ) AS idx_cresc
            FROM gold_indicadores_municipio g
            CROSS JOIN bounds b
            WHERE g.populacao_estimada >= 50000 AND g.pib_per_capita IS NOT NULL
        ),
        scored AS (
            SELECT
                *,
                ROUND(0.50 * idx_pib_pc + 0.30 * idx_cresc + 0.20 * idx_pop, 2) AS score_platinum,
                ROUND(0.50 * idx_pop + 0.35 * idx_cresc + 0.15 * idx_pib_pc, 2) AS score_smart
            FROM norm
        )
        SELECT
            codigo_ibge,
            nome_municipio,
            uf_sigla,
            uf_nome,
            regiao_nome,
            porte_municipio,
            ano_pop,
            populacao_estimada,
            crescimento_pop_pct,
            ano_pib,
            pib_total_reais,
            pib_per_capita,
            score_platinum,
            DENSE_RANK() OVER (ORDER BY score_platinum DESC) AS rank_platinum,
            score_smart,
            DENSE_RANK() OVER (ORDER BY score_smart DESC) AS rank_smart,
            CASE
                WHEN score_platinum >= score_smart THEN 'Atlas Platinum'
                ELSE 'Atlas Smart'
            END AS modelo_recomendado,
            EXTRACT(YEAR FROM CURRENT_DATE)::INT AS ano,
            EXTRACT(MONTH FROM CURRENT_DATE)::INT AS mes
        FROM scored;
    """)

    con.execute("""
        CREATE TABLE gold_contexto_macro AS
        SELECT
            data_ref,
            ano,
            mes,
            selic_meta_media,
            dolar_venda_medio,
            ipca_mensal_pct,
            ROUND(
                (EXP(SUM(LN(1 + COALESCE(ipca_mensal_pct, 0) / 100.0)) OVER (ORDER BY data_ref ROWS BETWEEN 11 PRECEDING AND CURRENT ROW)) - 1) * 100.0,
                4
            ) AS ipca_acumulado_12m_pct
        FROM silver_fato_macroeconomia
        ORDER BY data_ref;
    """)

    tables = {
        "silver_dim_municipio": con.execute("SELECT * FROM silver_dim_municipio").df(),
        "silver_dim_calendario": con.execute("SELECT * FROM silver_dim_calendario").df(),
        "silver_fato_indicadores_municipais": con.execute("SELECT * FROM silver_fato_indicadores_municipais").df(),
        "silver_fato_macroeconomia": con.execute("SELECT * FROM silver_fato_macroeconomia").df(),
        "gold_indicadores_municipio": con.execute("SELECT * FROM gold_indicadores_municipio").df(),
        "gold_ranking_expansao": con.execute("SELECT * FROM gold_ranking_expansao").df(),
        "gold_contexto_macro": con.execute("SELECT * FROM gold_contexto_macro").df(),
    }

    # Persistência Parquet (Snappy) particionada por ano/mês
    ranking_dir = output_dir / "gold_ranking_expansao"
    macro_dir = output_dir / "gold_contexto_macro"
    tables["gold_ranking_expansao"].to_parquet(
        ranking_dir, engine="pyarrow", compression="snappy", partition_cols=["ano", "mes"], index=False
    )
    tables["gold_contexto_macro"].to_parquet(
        macro_dir, engine="pyarrow", compression="snappy", partition_cols=["ano", "mes"], index=False
    )
    logger.info("Camada Gold exportada em Parquet (Snappy) particionada por ano/mes em %s", output_dir)

    if database_url:
        _sync_to_postgres(database_url, bronze_records, tables)

    return tables


def _sync_to_postgres(database_url: str, bronze_records: list[dict[str, Any]], tables: dict[str, pd.DataFrame]) -> None:
    logger.info("Sincronizando camadas bronze, silver e gold com PostgreSQL/Supabase...")
    engine = create_engine(database_url)
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS bronze;"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS silver;"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS gold;"))

    pd.DataFrame(bronze_records).to_sql("raw_api_responses", engine, schema="bronze", if_exists="append", index=False)

    schema_map = {
        "silver_dim_municipio": ("silver", "dim_municipio"),
        "silver_dim_calendario": ("silver", "dim_calendario"),
        "silver_fato_indicadores_municipais": ("silver", "fato_indicadores_municipais"),
        "silver_fato_macroeconomia": ("silver", "fato_macroeconomia"),
        "gold_indicadores_municipio": ("gold", "indicadores_municipio"),
        "gold_ranking_expansao": ("gold", "ranking_expansao"),
        "gold_contexto_macro": ("gold", "contexto_macro"),
    }
    for key, (schema, table_name) in schema_map.items():
        tables[key].to_sql(table_name, engine, schema=schema, if_exists="replace", index=False)
    logger.info("Sincronização concluída no Supabase.")
