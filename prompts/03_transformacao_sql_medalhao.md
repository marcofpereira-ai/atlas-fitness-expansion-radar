# Prompt 03 — Transformação SQL & Camadas Silver/Gold (Arquitetura Medalhão)

## Prompt Original

> Leia prd.md, spec.md e agents.md.
>
> Objetivo (Etapa 2 - Transformação SQL & Camadas Silver/Gold):
> Revise src/transformation/pipeline_sql.py e aprimore a camada de transformação para atender 100% dos critérios de engenharia:
> 1. Garanta que o desaninhamento dos JSONs do IBGE e BCB via DuckDB SQL trate corretamente caracteres especiais ('-', '...', '..', 'X') como NULL antes do cast numérico e aplique deduplicação via ROW_NUMBER().
> 2. Adicione a tabela dimensão silver_dim_calendario (data_ref, ano, mes, trimestre, ano_mes) conforme especificado em spec.md, vinculando-a à silver_fato_macroeconomia.
> 3. Na camada Gold (gold_ranking_expansao), garanta que os cálculos de pib_per_capita, crescimento_pop_pct, score_platinum (50% PIB per capita, 30% crescimento pop, 20% população) e score_smart (50% população, 35% crescimento pop, 15% PIB per capita) sejam auditáveis e exportados em Parquet (compressão snappy) particionados por ano e mes em output/.
> 4. Verifique se a sincronização com PostgreSQL/Supabase (_sync_to_postgres) cria os schemas bronze, silver e gold e persiste as tabelas de forma idempotente quando DATABASE_URL estiver configurada no .env.
> 5. Registre este passo em prompts/03_transformacao_sql_medalhao.md.

---

## Resumo Técnico das Alterações

### 1. `src/transformation/pipeline_sql.py` — Pipeline SQL Medalhão

#### Silver Layer — Star Schema Normalizado

| Tabela | Descrição | Chave Primária |
|--------|-----------|----------------|
| `silver_dim_municipio` | Dimensão de municípios (IBGE) | `codigo_ibge` |
| `silver_dim_calendario` | **NOVA** - Dimensão calendário | `data_ref` |
| `silver_fato_indicadores_municipais` | Fato: população + PIB municipal | `(codigo_ibge, ano)` |
| `silver_fato_macroeconomia` | Fato: Selic, Dólar, IPCA mensal | `data_ref` |

#### Gold Layer — Consumo Analítico

| Tabela | Descrição |
|--------|-----------|
| `gold_indicadores_municipio` | Indicadores consolidados por município (último ano válido) |
| `gold_ranking_expansao` | Ranking com scores normalizados (Platinum/Smart) |
| `gold_contexto_macro` | Contexto macroeconômico com IPCA acumulado 12m |

---

### 1. Desaninhamento JSON + Tratamento de Nulos e Deduplicação

**IBGE (estrutura aninhada `resultados -> series -> serie`):**
```sql
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
```

- **Nulos IBGE**: `'-'`, `'...'`, `'..'`, `'X'`, `''` → `NULL` antes do cast
- **Deduplicação**: `ROW_NUMBER() OVER (PARTITION BY entidade, localidade_id, periodo ORDER BY ingested_at DESC) = 1`
- **Decimal BR**: `REPLACE(valor, ',', '.')` para cast correto

**BCB SGS (diário → mensal):**
```sql
WITH bcb_clean AS (
    SELECT
        entidade,
        STRPTIME(data_str, '%d/%m/%Y')::DATE AS data_ref,
        TRY_CAST(REPLACE(valor_str, ',', '.') AS DOUBLE) AS valor,
        ROW_NUMBER() OVER (PARTITION BY entidade, data_str ORDER BY ingested_at DESC) AS rn
    FROM raw_bcb_df
)
```

---

### 2. Nova Dimensão `silver_dim_calendario` (conforme spec.md)

```sql
CREATE TABLE silver_dim_calendario AS
WITH datas AS (
    SELECT DISTINCT data_ref
    FROM (
        -- Datas do BCB (diárias agregadas para mensal)
        SELECT MAKE_DATE(b.ano, b.mes, 1) AS data_ref
        FROM (
            SELECT EXTRACT(YEAR FROM STRPTIME(data_str, '%d/%m/%Y'))::INT AS ano,
                   EXTRACT(MONTH FROM STRPTIME(data_str, '%d/%m/%Y'))::INT AS mes
            FROM raw_bcb_df
            UNION
            -- Datas do IPCA (já mensais, formato YYYYMM)
            SELECT CAST(SUBSTR(periodo, 1, 4) AS INT) AS ano,
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
```

**Vinculação em `silver_fato_macroeconomia`:**
```sql
SELECT m.data_ref, m.ano, m.mes, m.selic_meta_media, m.dolar_venda_medio, m.ipca_mensal_pct
FROM macro_base m
INNER JOIN silver_dim_calendario c ON m.data_ref = c.data_ref
ORDER BY m.data_ref;
```

---

### 3. Camada Gold — Scores Auditáveis (conforme PRD)

#### `gold_indicadores_municipio`
```sql
SELECT
    m.codigo_ibge, m.nome_municipio, m.uf_sigla, m.uf_nome, m.regiao_nome,
    p.ano_pop, p.populacao_estimada,
    -- Crescimento populacional YoY
    ROUND(CASE WHEN p.pop_anterior > 0
               THEN ((p.populacao_estimada - p.pop_anterior)::DOUBLE / p.pop_anterior) * 100.0
               ELSE 0.0 END, 4) AS crescimento_pop_pct,
    b.ano_pib,
    ROUND(b.pib_mil_reais * 1000.0, 2) AS pib_total_reais,
    -- PIB per capita = (PIB mil R$ * 1000) / população
    ROUND((b.pib_mil_reais * 1000.0) / NULLIF(p.populacao_estimada, 0), 2) AS pib_per_capita,
    CASE WHEN p.populacao_estimada >= 500000 THEN 'Grande Porte'
         WHEN p.populacao_estimada >= 100000 THEN 'Médio Porte'
         ELSE 'Pequeno Porte' END AS porte_municipio
FROM silver_dim_municipio m
INNER JOIN pop_ranked p ON m.codigo_ibge = p.codigo_ibge AND p.rn = 1
LEFT JOIN pib_ranked b ON m.codigo_ibge = b.codigo_ibge AND b.rn = 1;
```

#### `gold_ranking_expansao` — Normalização Min-Max (0-100) + Pesos PRD
```sql
-- Score Platinum: 50% PIB per capita + 30% Crescimento Pop + 20% População
ROUND(0.50 * idx_pib_pc + 0.30 * idx_cresc + 0.20 * idx_pop, 2) AS score_platinum,

-- Score Smart: 50% População + 35% Crescimento Pop + 15% PIB per capita
ROUND(0.50 * idx_pop + 0.35 * idx_cresc + 0.15 * idx_pib_pc, 2) AS score_smart
```

**Tratamento edge case (min=max):** `COALESCE(normalizacao, 50.0)` atribui ponto médio quando todos valores são iguais.

#### Exportação Parquet (Snappy) Particionado
```python
tables["gold_ranking_expansao"].to_parquet(
    ranking_dir, engine="pyarrow", compression="snappy",
    partition_cols=["ano", "mes"], index=False
)
tables["gold_contexto_macro"].to_parquet(
    macro_dir, engine="pyarrow", compression="snappy",
    partition_cols=["ano", "mes"], index=False
)
```
Estrutura: `output/gold_ranking_expansao/ano=YYYY/mes=MM/*.parquet`

---

### 4. Sincronização PostgreSQL/Supabase — Idempotente

```python
def _sync_to_postgres(database_url: str, bronze_records, tables):
    engine = create_engine(database_url)
    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS bronze;"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS silver;"))
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS gold;"))

    # Bronze: append (histórico de ingestões)
    pd.DataFrame(bronze_records).to_sql("raw_api_responses", engine,
        schema="bronze", if_exists="append", index=False)

    # Silver/Gold: replace (reprocessamento completo)
    schema_map = {
        "silver_dim_municipio": ("silver", "dim_municipio"),
        "silver_dim_calendario": ("silver", "dim_calendario"),  -- NOVA
        "silver_fato_indicadores_municipais": ("silver", "fato_indicadores_municipais"),
        "silver_fato_macroeconomia": ("silver", "fato_macroeconomia"),
        "gold_indicadores_municipio": ("gold", "indicadores_municipio"),
        "gold_ranking_expansao": ("gold", "ranking_expansao"),
        "gold_contexto_macro": ("gold", "contexto_macro"),
    }
    for key, (schema, table_name) in schema_map.items():
        tables[key].to_sql(table_name, engine, schema=schema,
                          if_exists="replace", index=False)
```

- **Bronze**: `if_exists="append"` — preserva histórico de raw payloads
- **Silver/Gold**: `if_exists="replace"` — idempotente para reprocessamento
- **Schemas**: Criados automaticamente via `CREATE SCHEMA IF NOT EXISTS`

---

### 5. Validações Realizadas

#### Data Quality (Status: PASSED)
```
Data Quality Status: PASSED
Total municipios Brasil: 5570
Municipios elegiveis ranking: 138 (pop >= 50k e PIB per capita válido)
Meses macroeconomia: 11

Score Platinum range: [15.21, 65.11]
Score Smart range: [17.71, 69.56]

Top 5 Platinum:
 1 Paulínia       SP  65.11
 2 Louveira       SP  46.52
 3 São Paulo      SP  41.86
 4 Cajamar        SP  40.11
 5 Cubatão        SP  35.69

Top 5 Smart:
 1 São Paulo      SP  69.56
 2 Paulínia       SP  32.78
 3 Louveira       SP  26.98
 4 Cajamar        SP  25.21
 5 Guarulhos      SP  24.58
```

#### Parquet Exportado (Snappy, particionado)
```
output/gold_ranking_expansao/
  └── ano=2026/
      └── mes=11/
          └── data.parquet  (138 linhas × 19 colunas)

output/gold_contexto_macro/
  └── ano=2026/
      ├── mes=1/  ...  mes=11/  (11 meses × 7 colunas)
```

#### Testes de Integração
```bash
# Pipeline completo (dry-run + transform + quality)
python -c "
from src.config.settings import configure_logging, get_settings
from src.ingestion.extractors import run_ingestion
from src.transformation.pipeline_sql import build_silver_and_gold
from src.quality.validator import run_data_quality_checks

settings = get_settings()
logger = configure_logging('INFO')
bronze = run_ingestion(settings, dry_run=True, dry_run_uf_id=35)
tables = build_silver_and_gold(bronze, settings.output_dir, database_url=None)
report = run_data_quality_checks(tables, settings.output_dir)
"
# ✅ Status: PASSED
```

---

## Arquivos Modificados

| Arquivo | Tipo | Descrição |
|---------|------|-----------|
| `src/transformation/pipeline_sql.py` | `feat(transformation)` | Nova `silver_dim_calendario`, vinculação fato macro, fix min=max na normalização, export Parquet particionado, sync idempotente |

---

## Próximos Passos (Etapa 3 - Data Quality & App)

1. Validar pipeline completo com `DATABASE_URL` no `.env` (Supabase)
2. Dashboard Streamlit: `streamlit run src/app/streamlit_app.py`
3. Workflow n8n para orquestração incremental