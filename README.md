# Radar de Expansão Territorial — Atlas Fitness

Pipeline resiliente de Engenharia de Dados e Lakehouse Medalhão (`Bronze -> Silver -> Gold`) desenvolvido para apoiar a decisão de abertura de novas unidades da rede **Atlas Fitness** em dois formatos de negócio: **Atlas Platinum** (alto ticket) e **Atlas Smart** (alto giro e escala).

## Arquitetura da Solução
1. **Ingestão (`src/ingestion/`):** Consumo automatizado via HTTP resiliente (`Retry` exponencial + *rate-limiting*) das APIs oficiais do **IBGE** (Localidades, População Estimada `6579`, PIB Municipal `5938`, IPCA `7060`) e do **Banco Central SGS** (Selic `432`, Dólar `10813`).
2. **Transformação & SQL (`src/transformation/`):** Desaninhamento de estruturas JSON via SQL (DuckDB / PostgreSQL), saneamento de nulos (`-`, `...`), deduplicação, cruzamento demográfico-macroeconômico e cálculo dos scores normalizados (0–100).
3. **Data Quality & Persistência (`src/quality/`):** Validação automatizada de schema, *null ratio*, unicidade e intervalos, exportando `output/quality_report.json` e datasets colunares **Parquet (Snappy)** particionados por `ano/mes`, além da sincronização no **Supabase (PostgreSQL)**.
4. **Consumo & Automação:** Dashboard interativo em **Streamlit** (`src/app/streamlit_app.py`) e orquestração incremental via **n8n** (`n8n/`).

## Como Executar Ponta a Ponta
```bash
# 1. Configure as variáveis de ambiente (opcional DATABASE_URL para Supabase)
cp .env.example .env

# 2. Instale as dependências
pip install -r requirements.txt

# 3. Execute o pipeline completo (Ingestão -> Transformação -> Data Quality -> Parquet)
bash run.sh
```

Para abrir o painel analítico localmente:
```bash
streamlit run src/app/streamlit_app.py
```

## Resultados da Execução Real (Fase I — 2026-11-22)

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

## Automação & Orquestração (GitHub Actions + n8n + Supabase)

### GitHub Actions — Pipeline Mensal
Workflow em `.github/workflows/pipeline_radar.yml`:
- **Schedule**: Todo dia 05 às 06:00 UTC (`cron: '0 6 5 * *'`)
- **Manual**: `workflow_dispatch` (disparável via n8n/API)
- **Runtime**: Ubuntu-latest, Python 3.11, timeout 60 min
- **Artefatos**: Quality Report JSON/CSV + Parquet Gold (retention 30 dias)
- **Sumário**: Markdown no GitHub Step Summary com métricas-chave

**GitHub Secrets necessários:**
| Secret | Descrição | Exemplo |
|--------|-----------|---------|
| `DATABASE_URL` | Conexão Supabase (Session Pooler IPv4) | `postgresql+psycopg2://postgres.[REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres` |

> ⚠️ Use **Session Pooler (porta 6543)** com driver `psycopg2` no Windows. Não use Transaction Pooler (porta 5432) nem driver `psycopg` (v3) — causa erro de handshake SSL em CI.

### n8n — Workflow de Orquestração (Self-Hosted)
Arquivo: `n8n/workflow_atlas_fitness_radar.json`

**Fluxo (5 nós + 2 branches):**
```
Schedule Trigger (mensal) ──┐
                            ├──▶ Disparar GitHub Actions (workflow_dispatch) ──▶ Wait 90s ──▶ Checar Status Workflow ──▶ Auditoria Gold (Postgres) ──▶ Validar Sucesso (IF) ──▶ Resumo Sucesso / Resumo Falha
Manual Trigger ─────────────┘
```

**Credenciais n8n necessárias:**
| Credencial | Tipo | Configuração |
|------------|------|--------------|
| `GitHub PAT` | HTTP Header Auth | `Authorization: Bearer <PAT>` — scope `repo` + `workflow` |
| `Supabase Session Pooler` | PostgreSQL | Host: `aws-0-[REGION].pooler.supabase.com`, Porta: `6543`, Database: `postgres`, User: `postgres.[REF]`, Password: `[PASSWORD]`, SSL: `require` |

**Importar no n8n (localhost:5678):**
1. Acesse `http://localhost:5678` → Workflows → Import
2. Selecione `n8n/workflow_atlas_fitness_radar.json`
3. Configure as credenciais acima
4. Ative o workflow (toggle "Active")

### Supabase — Session Pooler (IPv4)
- **Host**: `aws-0-[REGION].pooler.supabase.com` (ex: `aws-0-us-east-1.pooler.supabase.com`)
- **Porta**: `6543` (Session Pooler)
- **Database**: `postgres`
- **User**: `postgres.[PROJECT_REF]`
- **SSL Mode**: `require`
- **Driver Python**: `psycopg2-binary` → connection string `postgresql+psycopg2://...`

> ⚠️ O Supabase exige IPv4 no pooler. Se o runner GitHub Actions resolver IPv6, force IPv4 no `DATABASE_URL` ou configure `host` como IPv4 literal.

### GitHub PAT — Permissões
Crie em `Settings → Developer settings → Personal access tokens → Tokens (classic)`:
- **Scopes**: `repo` (full) + `workflow`
- **Expiration**: 90 dias (renovar periodicamente)
- **Usage**: Header `Authorization: Bearer <PAT>` nas chamadas HTTP do n8n

---

## Uso de Inteligência Artificial no Projeto
O desenvolvimento seguiu metodologia *Spec-Driven* documentada em `prd.md`, `spec.md`, `agents.md` e registrada na pasta `prompts/`, garantindo rastreabilidade das decisões arquiteturais e revisão humana de todas as regras SQL e métricas de negócio.
