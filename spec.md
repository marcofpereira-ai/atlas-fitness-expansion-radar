# SPEC — Especificação Técnica: Radar de Expansão (Atlas Fitness)

## 1. Arquitetura Geral
```text
[API IBGE] ──────┐
                 ├──> [Python Ingestion (Lotes + Retry)] ──> [Supabase: bronze (JSONB)]
[API BCB SGS] ───┘                                                   │
                                                                     ▼
[Streamlit Cloud] <── [Supabase: gold] <── [SQL/DuckDB Flattening & Star Schema: silver]
                                │
                                └──> [Data Quality + Parquet (Snappy, ano/mes) + quality_report.json]
```

## 2. Fontes e Endpoints de APIs
### 2.1 API do IBGE (`https://servicodados.ibge.gov.br/api`)
* **Localidades:** `/v1/localidades/municipios` (Dimensões de Município, UF e Região).
* **População Estimada (Agregado 6579, Variável 9324):** `/v3/agregados/6579/periodos/{anos}/variaveis/9324?localidades=N6[N3[{uf_id}]]`
  * *Estratégia de lote:* Consulta paginada por UF (`27` chamadas por lote de períodos disponíveis via `/v3/agregados/6579/periodos`) para evitar timeout/erro 500.
* **PIB dos Municípios (Agregado 5938, Variável 37 - mil R$):** `/v3/agregados/5938/periodos/{anos}/variaveis/37?localidades=N6[N3[{uf_id}]]`
  * *Nota temporal:* O PIB municipal possui defasagem de ~2 anos em relação à população; o cruzamento na Gold utiliza o último ano disponível de cada série com metadado explícito (`ano_pop`, `ano_pib`).
* **IPCA Mensal Brasil (Agregado 7060, Variável 63):** `/v3/agregados/7060/periodos/{ultimos_24_meses}/variaveis/63?localidades=N1[all]`

### 2.2 API do Banco Central SGS (`https://api.bcb.gov.br/dados/serie`)
* **Meta Selic (Série 432):** `/bcdata.sgs.432/dados?formato=json&dataInicial={dd/MM/aaaa}&dataFinal={dd/MM/aaaa}`
* **Taxa de Câmbio Dólar PTAX/Venda (Série 10813):** `/bcdata.sgs.10813/dados?formato=json&dataInicial={dd/MM/aaaa}&dataFinal={dd/MM/aaaa}`
* *Estratégia de janela:* Intervalos fatiados em janelas $\le 10$ anos conforme restrição da API do BCB.

## 3. Modelo de Dados (Camadas Medalhão)
### 3.1 Camada `bronze` (Raw Vault)
* `bronze.raw_api_responses`:
  * `id` (BIGSERIAL PK)
  * `fonte` (VARCHAR: `'IBGE'` | `'BCB'`)
  * `entidade` (VARCHAR: `'localidades'`, `'populacao'`, `'pib'`, `'ipca'`, `'selic'`, `'dolar'`)
  * `endpoint` (TEXT)
  * `parametros` (JSONB)
  * `payload` (JSONB — resposta integral sem alterações)
  * `ingested_at` (TIMESTAMPTZ DEFAULT NOW())

### 3.2 Camada `silver` (Star Schema Normalizado)
* **Dimensões:**
  * `silver.dim_municipio` (`codigo_ibge` PK INT, `nome_municipio` VARCHAR, `uf_sigla` CHAR(2), `uf_nome` VARCHAR, `regiao_nome` VARCHAR)
  * `silver.dim_calendario` (`data_ref` DATE PK, `ano` INT, `mes` INT, `trimestre` INT, `ano_mes` VARCHAR(7))
* **Fatos:**
  * `silver.fato_indicadores_municipais` (`codigo_ibge` INT, `ano` INT, `populacao_estimada` BIGINT, `pib_mil_reais` NUMERIC(18,2), PK `(codigo_ibge, ano)`)
  * `silver.fato_macroeconomia` (`data_ref` DATE PK, `ano` INT, `mes` INT, `selic_meta` NUMERIC(8,4), `dolar_venda` NUMERIC(10,4), `ipca_mensal` NUMERIC(8,4))

### 3.3 Camada `gold` (Consumo Analítico & Exportação)
* `gold.indicadores_municipio`: Consolida último ano válido de população, crescimento populacional (YoY / CAGR), PIB total em reais, PIB per capita e classificação de porte (`Pequeno`, `Médio`, `Grande`).
* `gold.ranking_expansao`: Aplica normalização Min-Max (0–100) e calcula `score_platinum`, `rank_platinum`, `score_smart`, `rank_smart` e `modelo_recomendado` (`Atlas Platinum` vs. `Atlas Smart`).
* `gold.contexto_macro`: Série mensal consolidada de Selic média/fechamento, Dólar médio/fechamento, IPCA mensal e acumulado 12 meses.

## 4. Regras de Transformação & SQL
1. **Desaninhamento SQL (`UNNEST` / `jsonb_array_elements`):** Extração via DuckDB (local/Parquet) e PostgreSQL (`jsonb_array_elements`) das estruturas aninhadas `resultados -> series -> serie` do IBGE.
2. **Saneamento de Nulos:** Valores `"-"` e `"..."` convertidos explicitamente para `NULL` antes do cast numérico.
3. **Deduplicação:** `ROW_NUMBER() OVER (PARTITION BY chave ORDER BY ingested_at DESC) = 1`.
4. **Cruzamento (JOIN):** Integração de `fato_indicadores_municipais` com `dim_municipio` e agregação temporal com `fato_macroeconomia`.
5. **Enriquecimento:** Cálculo de `pib_per_capita = (pib_mil_reais * 1000) / NULLIF(populacao_estimada, 0)`, variação percentual populacional e scores ponderados.

## 5. Data Quality & Persistência
* **Validações Automatizadas:** Verificação de schema/colunas obrigatórias, *null ratio* ($\le 5\%$ em colunas críticas), unicidade de chaves primárias e *range checks* (`populacao_estimada > 0`, `pib_per_capita > 0`, `score` entre `0` e `100`).
* **Saídas Persistidas:**
  * Tabelas `bronze`, `silver` e `gold` no PostgreSQL (Supabase).
  * Arquivos colunares Parquet com compressão `snappy` em `output/gold_ranking_expansao/ano=YYYY/mes=MM/` e `output/gold_contexto_macro/ano=YYYY/mes=MM/`.
  * Auditoria em `output/quality_report.json` e `output/quality_report.csv`.

## 6. Como Executar
```bash
cp .env.example .env
pip install -r requirements.txt
bash run.sh
```
