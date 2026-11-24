# Radar de Expansão Territorial — Atlas Fitness

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![DuckDB](https://img.shields.io/badge/DuckDB-1.0%2B-FFFFFF?logo=duckdb&logoColor=yellow)](https://duckdb.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Supabase-4169E1?logo=postgresql&logoColor=white)](https://supabase.com/)
[![GitHub Actions](https://img.shields.io/badge/CI%2FCD-GitHub%20Actions-2088FF?logo=githubactions&logoColor=white)](https://github.com/features/actions)
[![n8n](https://img.shields.io/badge/Orchestration-n8n-EA4B71?logo=n8n&logoColor=white)](https://n8n.io/)
[![Streamlit](https://img.shields.io/badge/Dashboard-Streamlit-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Streamlit Cloud](https://img.shields.io/badge/Live%20Demo-Streamlit%20Cloud-FF4B4B?logo=streamlit&logoColor=white)](https://atlas-fitness-expansion-radar.streamlit.app/)
[![Architecture](https://img.shields.io/badge/Architecture-Medallion%20(Bronze%20→%20Silver%20→%20Gold)-8A2BE2)](https://www.databricks.com/glossary/medallion-architecture)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## 🌐 Demonstração ao Vivo

| Ambiente | Link | Status |
|----------|------|--------|
| **Streamlit Cloud** | [![Acessar Dashboard](https://img.shields.io/badge/🚀%20Acessar%20Dashboard-Atlas%20Fitness%20Radar-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://atlas-fitness-expansion-radar.streamlit.app/) | 🟢 Online |
| **GitHub Actions** | [Pipeline Runs](https://github.com/marcofpereira-ai/atlas-fitness-expansion-radar/actions) | 🟢 Ativo |

> **Pipeline resiliente de Engenharia de Dados e Lakehouse Medalhão** (`Bronze → Silver → Gold`) desenvolvido para apoiar a decisão de abertura de novas unidades da rede **Atlas Fitness** — setor de **Academias, Saúde e Bem-Estar / Fitness Retail** — em dois modelos de negócio distintos:
>
> * **Atlas Platinum** — academias de alto padrão / ticket premium (foco em renda per capita elevada e baixo custo de oportunidade).
> * **Atlas Smart** — academias de modelo smart/low-cost de alto volume (foco em escala populacional e adensamento urbano).

---

## 🏗️ Arquitetura End-to-End

```mermaid
flowchart LR
    subgraph FONTES["📡 Fontes Oficiais"]
        IBGE["IBGE API\nLocalidades · População (6579)\nPIB Municipal (5938) · IPCA (7060)"]
        BCB["Banco Central SGS\nSelic (432) · Dólar PTAX (10813)"]
    end

    subgraph INGESTION["🐍 Python Ingestion<br/>(src/ingestion/)"]
        HTTP["HTTP Resiliente\nRetry Exponencial + Rate-Limit\nFatiamento por UF / Janelas ≤ 10 anos"]
        BRONZE["Bronze Layer\nSupabase (JSONB)\nRaw Vault Imutável"]
    end

    subgraph TRANSFORM["🔄 Transformação SQL<br/>(src/transformation/)"]
        SILVER["Silver Layer\nStar Schema Normalizado\ndim_municipio · dim_calendario\nfato_indicadores_municipais · fato_macroeconomia"]
        GOLD["Gold Layer\nModelos Analíticos\nranking_expansao · contexto_macro"]
    end

    subgraph QUALITY["✅ Data Quality<br/>(src/quality/)"]
        DQ["Validações\nSchema · Nulidade · Unicidade · Intervalos\nRelatórios JSON/CSV"]
        PARQUET["Exportação Parquet (Snappy)\nParticionado ano/mes\noutput/gold_*/"]
    end

    subgraph AUTOMATION["⚙️ Automação & Orquestração"]
        GHA["GitHub Actions\nPipeline Mensal (cron 0 6 5 * *)"]
        N8N["n8n Self-Hosted\nSchedule + Manual Trigger\nDispara GHA → Auditoria Gold"]
        SUPABASE["Supabase Lakehouse\nSession Pooler IPv4 (porta 6543)"]
    end

    subgraph CONSUMPTION["📊 Consumo"]
        ST["Streamlit Dashboard\n4 Abas Executivas\nFiltro UF/Região · Platinum vs Smart"]
    end

    IBGE --> HTTP
    BCB --> HTTP
    HTTP --> BRONZE
    BRONZE --> SILVER
    SILVER --> GOLD
    GOLD --> DQ
    DQ --> PARQUET
    GOLD --> SUPABASE
    SUPABASE --> ST
    GHA --> SUPABASE
    N8N --> GHA
    N8N --> SUPABASE
```

---

## 📂 Estrutura do Projeto

```text
atlas-fitness-expansion-radar/
├── .github/
│   └── workflows/
│       └── pipeline_radar.yml       # GitHub Actions CI/CD mensal
├── n8n/
│   └── workflow_atlas_fitness_radar.json  # Workflow n8n (importável)
├── docs/
│   ├── images/
│   │   └── n8n_pipeline_sucesso.png       # Evidência visual da orquestração
│   └── GITHUB_ABOUT.md            # Metadados para About/Topics do GitHub
├── src/
│   ├── config/                    # Configurações e variáveis de ambiente
│   ├── ingestion/                 # Extração HTTP → Bronze (payload bruto)
│   ├── transformation/            # SQL DuckDB/Postgres → Silver & Gold
│   ├── quality/                   # Validações DQ + exportação Parquet
│   └── app/
│       └── streamlit_app.py       # Dashboard 4 abas (somente leitura Gold)
├── output/                        # Artefatos locais (Parquet, relatórios DQ)
├── prompts/                       # Histórico de prompts (rastreabilidade IA)
├── .env.example                   # Template de variáveis de ambiente
├── run.sh                         # Script de execução ponta a ponta
├── requirements.txt               # Dependências Python
├── pyproject.toml                 # Metadados do pacote
├── prd.md                         # Product Requirements Document
├── spec.md                        # Especificação Técnica
├── agents.md                      # Regras de engenharia para IA
└── LICENSE                        # Licença MIT
```

---

## 🧮 Dicionário de Dados — Camadas Medalhão

### Bronze (Raw Vault) — `bronze.raw_api_responses`
| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | BIGSERIAL | PK auto-incremento |
| `fonte` | VARCHAR | `'IBGE'` ou `'BCB'` |
| `entidade` | VARCHAR | `'localidades'`, `'populacao'`, `'pib'`, `'ipca'`, `'selic'`, `'dolar'` |
| `endpoint` | TEXT | URL completa chamada |
| `parametros` | JSONB | Parâmetros da requisição (UF, períodos, etc.) |
| `payload` | JSONB | **Resposta integral sem alterações** (regra inviolável) |
| `ingested_at` | TIMESTAMPTZ | Timestamp de ingestão |

### Silver (Star Schema Normalizado)

**`silver.dim_municipio`**
| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `codigo_ibge` | INT | PK — Código IBGE 7 dígitos |
| `nome_municipio` | VARCHAR | Nome oficial |
| `uf_sigla` | CHAR(2) | Sigla da UF |
| `uf_nome` | VARCHAR | Nome da UF |
| `regiao_nome` | VARCHAR | Região (Norte, Nordeste, etc.) |

**`silver.dim_calendario`**
| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `data_ref` | DATE | PK — Primeiro dia do mês |
| `ano` | INT | Ano |
| `mes` | INT | Mês (1-12) |
| `trimestre` | INT | Trimestre (1-4) |
| `ano_mes` | VARCHAR(7) | Formato `YYYY-MM` |

**`silver.fato_indicadores_municipais`**
| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `codigo_ibge` | INT | FK → dim_municipio |
| `ano` | INT | Ano de referência |
| `populacao_estimada` | BIGINT | População estimada (IBGE 6579) |
| `pib_mil_reais` | NUMERIC(18,2) | PIB em milhares de R$ (IBGE 5938) |
| **PK** | | `(codigo_ibge, ano)` |

**`silver.fato_macroeconomia`**
| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `data_ref` | DATE | PK — Primeiro dia do mês |
| `ano` | INT | Ano |
| `mes` | INT | Mês |
| `selic_meta` | NUMERIC(8,4) | Meta Selic (% a.a.) |
| `dolar_venda` | NUMERIC(10,4) | Dólar PTAX Venda (R$) |
| `ipca_mensal` | NUMERIC(8,4) | IPCA mensal (%) |

### Gold (Consumo Analítico)

**`gold.indicadores_municipio`** — Base consolidada por município (último ano válido)
| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `codigo_ibge` | INT | PK |
| `nome_municipio` | VARCHAR | |
| `uf_sigla` | CHAR(2) | |
| `regiao_nome` | VARCHAR | |
| `populacao_estimada` | BIGINT | Último ano disponível |
| `ano_pop` | INT | Ano da população |
| `crescimento_pop_pct` | NUMERIC(8,4) | Crescimento YoY ou CAGR (%) |
| `pib_total_reais` | NUMERIC(18,2) | PIB total em R$ |
| `pib_per_capita` | NUMERIC(14,2) | PIB per capita (R$) |
| `ano_pib` | INT | Ano do PIB |
| `porte` | VARCHAR | `Pequeno` / `Médio` / `Grande` |

**`gold.ranking_expansao`** — Ranking final com scores normalizados
| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `codigo_ibge` | INT | PK |
| `nome_municipio` | VARCHAR | |
| `uf_sigla` | CHAR(2) | |
| `regiao_nome` | VARCHAR | |
| `populacao_estimada` | BIGINT | |
| `pib_per_capita` | NUMERIC(14,2) | |
| `crescimento_pop_pct` | NUMERIC(8,4) | |
| `score_platinum` | NUMERIC(5,2) | **0–100** (Min-Max normalizado) |
| `rank_platinum` | INT | Ranking descendente |
| `score_smart` | NUMERIC(5,2) | **0–100** (Min-Max normalizado) |
| `rank_smart` | INT | Ranking descendente |
| `modelo_recomendado` | VARCHAR | `'Atlas Platinum'` ou `'Atlas Smart'` |

**`gold.contexto_macro`** — Série mensal consolidada
| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `data_ref` | DATE | PK |
| `selic_meta_media` | NUMERIC(8,4) | Média mensal Selic |
| `selic_meta_fechamento` | NUMERIC(8,4) | Último dia do mês |
| `dolar_venda_medio` | NUMERIC(10,4) | Média mensal Dólar |
| `dolar_venda_fechamento` | NUMERIC(10,4) | Último dia do mês |
| `ipca_mensal` | NUMERIC(8,4) | IPCA do mês (%) |
| `ipca_acumulado_12m_pct` | NUMERIC(8,4) | IPCA 12 meses (%) |

---

## 🎯 Regras de Negócio & Scoring

### Elegibilidade
- **Municípios com população ≥ 50.000 habitantes** (filtro aplicado em `gold.ranking_expansao`).
- Total mapeado: **5.570 municípios** (Brasil) → **687 elegíveis** no ranking.

### Fórmula — Atlas Platinum (Foco: Ticket Premium)
> **Score = 50% × PIB per capita (norm) + 30% × Crescimento Pop. (norm) + 20% × População (norm)**

| Peso | Indicador | Racional |
|------|-----------|----------|
| 50% | `pib_per_capita` | Proxy de capacidade de pagamento de ticket alto |
| 30% | `crescimento_pop_pct` | Expansão de demanda local futura |
| 20% | `populacao_estimada` | Garantia de escala mínima |

### Fórmula — Atlas Smart (Foco: Alto Giro / Volume)
> **Score = 50% × População (norm) + 35% × Crescimento Pop. (norm) + 15% × PIB per capita (norm)**

| Peso | Indicador | Racional |
|------|-----------|----------|
| 50% | `populacao_estimada` | Massa crítica e alto giro de alunos |
| 35% | `crescimento_pop_pct` | Cidades em adensamento urbano |
| 15% | `pib_per_capita` | Lastro econômico mínimo para consumo recorrente |

### Normalização
- Todos os indicadores normalizados via **Min-Max (0–100)** na camada Gold.
- `score_platinum` e `score_smart` variam entre **0 e 100**.

---

## ⚙️ Orquestração Automatizada (GitHub Actions + n8n)

### GitHub Actions — Pipeline Mensal
**Arquivo:** `.github/workflows/pipeline_radar.yml`

| Atributo | Valor |
|----------|-------|
| **Schedule** | Todo dia 05 às 06:00 UTC (`cron: '0 6 5 * *'`) |
| **Manual** | `workflow_dispatch` (disparável via n8n/API) |
| **Runtime** | Ubuntu-latest, Python 3.11, timeout 60 min |
| **Artefatos** | Quality Report JSON/CSV + Parquet Gold (retention 30 dias) |
| **Sumário** | Markdown no GitHub Step Summary com métricas-chave |

**GitHub Secrets necessários:**
| Secret | Descrição |
|--------|-----------|
| `DATABASE_URL` | Conexão Supabase (Session Pooler IPv4, porta 6543, driver `psycopg2`) |

> ⚠️ Use **Session Pooler (porta 6543)** com driver `psycopg2`. Não use Transaction Pooler (porta 5432) nem driver `psycopg` (v3) — causa erro de handshake SSL em CI.

### n8n — Workflow de Orquestração (Self-Hosted)
**Arquivo:** `n8n/workflow_atlas_fitness_radar.json`

**Fluxo (5 nós + 2 branches):**
```mermaid
flowchart LR
    A[Schedule Trigger<br/>Mensal dia 05 06:00 UTC] --> C[Disparar GitHub Actions<br/>workflow_dispatch]
    B[Manual Trigger] --> C
    C --> D[Wait 90s]
    D --> E[Checar Status Workflow<br/>GitHub API]
    E --> F[Auditoria Gold (Postgres)<br/>Contagem elegíveis + métricas]
    F --> G{Validar Sucesso}
    G -->|Conclusão success<br/>e elegíveis > 0| H[Resumo Sucesso]
    G -->|Caso contrário| I[Resumo Falha]
```

**Credenciais n8n necessárias:**
| Credencial | Tipo | Configuração |
|------------|------|--------------|
| `GitHub PAT` | HTTP Header Auth | `Authorization: Bearer <PAT>` — scopes `repo` + `workflow` |
| `Supabase Session Pooler` | PostgreSQL | Host: `aws-0-[REGION].pooler.supabase.com`, Porta: `6543`, Database: `postgres`, User: `postgres.[REF]`, SSL: `require` |

**Importar no n8n (localhost:5678):**
1. Acesse `http://localhost:5678` → Workflows → Import
2. Selecione `n8n/workflow_atlas_fitness_radar.json`
3. Configure as credenciais acima
4. Ative o workflow (toggle "Active")

### Evidência Visual — Execução Ponta a Ponta com Sucesso
![Orquestração n8n com Sucesso](docs/images/n8n_pipeline_sucesso.png)

---

## 🚀 Guia Rápido de Execução Local

### Pré-requisitos
- Python 3.11+
- (Opcional) Conta Supabase para persistência no Lakehouse
- (Opcional) n8n self-hosted para orquestração

### 1. Configure as variáveis de ambiente
```bash
cp .env.example .env
# Edite .env com sua DATABASE_URL se usar Supabase
```

### 2. Instale as dependências
```bash
pip install -r requirements.txt
```

### 3. Execute o pipeline completo
```bash
bash run.sh
```
> Executa: Ingestão → Transformação → Data Quality → Parquet (output/)

### 4. Abra o dashboard Streamlit
```bash
streamlit run src/app/streamlit_app.py
```

---

## ⚙️ Variáveis de Ambiente (`.env.example`)

```ini
# Conexão PostgreSQL / Supabase
# Opcional para execução local em DuckDB/Parquet
# Obrigatório para persistência no Lakehouse Supabase
DATABASE_URL=postgresql://postgres.[PROJECT_REF]:[PASSWORD]@aws-0-sa-east-1.pooler.supabase.com:6543/postgres

# Configurações do Pipeline
LOG_LEVEL=INFO
OUTPUT_DIR=output
REQUEST_TIMEOUT=30
RATE_LIMIT_SLEEP=0.35
```

---

## 📊 Resultados da Execução Real (Fase I — 2026-11-22)

| Métrica | Valor |
|---------|-------|
| **Total de municípios mapeados (Brasil)** | 5.570 |
| **Municípios com PIB válido** | 5.570 |
| **Municípios elegíveis no ranking (pop ≥ 50 mil)** | 687 |
| **Meses de histórico macroeconômico** | 59 (jan/2022 – nov/2026) |
| **Registros fato municipal (pop + PIB)** | 22.282 |
| **Registros fato macroeconomia (Selic, Dólar, IPCA)** | 59 |
| **Status Data Quality** | ✅ PASSED |

### Top 5 — Atlas Platinum (foco: PIB per capita + crescimento)
| Rank | Município | UF | PIB per capita (R$) | Score Platinum |
|------|-----------|----|---------------------|----------------|
| 1 | Saquarema | RJ | 678.529,08 | 58,98 |
| 2 | Maricá | RJ | 630.419,10 | 55,82 |
| 3 | Paulínia | SP | 570.523,33 | 53,49 |
| 4 | Extrema | MG | 332.970,77 | 41,06 |
| 5 | Louveira | SP | 364.367,28 | 38,21 |

> *Pesos: 50% PIB per capita + 30% Crescimento Pop. + 20% População*

### Top 5 — Atlas Smart (foco: População + crescimento)
| Rank | Município | UF | População | Score Smart |
|------|-----------|----|-----------|-------------|
| 1 | São Paulo | SP | 11.911.337 | 62,23 |
| 2 | Rio de Janeiro | RJ | 6.731.133 | 39,58 |
| 3 | Campo Verde | MT | 51.969 | 37,00 |
| 4 | Araquari | SC | 53.939 | 29,03 |
| 5 | Lucas do Rio Verde | MT | 99.291 | 27,30 |

> *Pesos: 50% População + 35% Crescimento Pop. + 15% PIB per capita*

### Exportação Parquet (Snappy) Particionada
```
output/
├── gold_ranking_expansao/
│   └── ano=2026/
│       └── mes=11/
│           └── data.parquet  (687 municípios × 19 colunas)
└── gold_contexto_macro/
    ├── ano=2022/ ... ano=2026/
    │   └── mes=01..12/
    │       └── data.parquet  (59 meses × 7 colunas)
```

---

## 🤖 Uso de Inteligência Artificial no Projeto
O desenvolvimento seguiu metodologia *Spec-Driven* documentada em `prd.md`, `spec.md`, `agents.md` e registrada na pasta `prompts/`, garantindo rastreabilidade das decisões arquiteturais e revisão humana de todas as regras SQL e métricas de negócio.

---

## 📄 Licença
Distribuído sob a licença **MIT**. Veja `LICENSE` para mais informações.

---

## 👥 Autor
**Marco Pereira** — Staff Data Engineer & Technical Writer  
Projeto executado para a rede **Atlas Fitness** (consultoria Bússola Pública).