# Entrega Executiva — Radar de Expansão Atlas Fitness

**Projeto:** Radar de Expansão Territorial — Atlas Fitness  
**Cliente:** Rede de Academias Atlas Fitness (consultoria Bússola Pública)  
**Autor:** Marco Pereira — Staff Data Engineer & Technical Writer  
**Data:** Novembro 2026  
**Repositório:** https://github.com/marcofpereira-ai/atlas-fitness-expansion-radar  
**Dashboard Online:** https://atlas-fitness-expansion-radar.streamlit.app/

---

## 1. Resumo Executivo

O **Radar de Expansão Atlas Fitness** é uma plataforma de inteligência de dados end-to-end, projetada para apoiar a diretoria de expansão da rede de academias **Atlas Fitness** na decisão de abertura de novas unidades físicas em dois modelos de negócio complementares:

| Modelo | Posicionamento | Foco Estratégico | Score Principal |
|--------|----------------|------------------|-----------------|
| **Atlas Platinum** | Alto padrão / Ticket premium | Renda per capita elevada + baixo custo de oportunidade | `score_platinum` (50% PIB pc + 30% Cresc. Pop + 20% Pop) |
| **Atlas Smart** | Smart/Low-cost / Alto volume | Escala populacional + adensamento urbano | `score_smart` (50% Pop + 35% Cresc. Pop + 15% PIB pc) |

A solução integra **dados oficiais do IBGE** (5.570 municípios: população estimada, PIB municipal, localidades) e **Banco Central do Brasil** (Selic, Dólar PTAX, IPCA) em uma arquitetura **Medalhão (Bronze → Silver → Gold)** com orquestração automatizada via **GitHub Actions + n8n**, persistência em **Supabase (PostgreSQL)** e visualização executiva em **Streamlit Cloud**.

---

## 2. Critérios de Arquitetura Escalável Atendidos

### 2.1 Arquitetura Medalhão (Bronze / Silver / Gold)

| Camada | Tecnologia | Finalidade | Garantias |
|--------|------------|------------|-----------|
| **Bronze** | Supabase (JSONB) / DuckDB | Raw Vault imutável — payload bruto das APIs sem transformação | Rastreabilidade total, reprocessabilidade, auditoria |
| **Silver** | PostgreSQL / DuckDB | Star Schema normalizado (dims + fatos) com saneamento de nulos, deduplicação, joins | Qualidade estrutural, modelo dimensional pronto para BI |
| **Gold** | PostgreSQL / Parquet (Snappy) | Modelos analíticos prontos para consumo: `ranking_expansao`, `contexto_macro`, `indicadores_municipio` | Performance de leitura, particionamento ano/mês, exportação colunar |

**Evidência:** 5.570 municípios mapeados → 687 elegíveis (pop ≥ 50k) → 19 colunas no ranking Gold + 7 colunas no contexto macro.

### 2.2 Resiliência de Ingestão

- **Rate-limiting adaptativo** (0.35s entre requisições) + **Retry exponencial** (máx. 5 tentativas)
- **Fatiamento obrigatório por UF** (`N6[N3[uf]]`) nas APIs IBGE — evita HTTP 500/timeout em chamadas únicas irrestritas
- **Janelas ≤ 10 anos** na API SGS do Banco Central — conformidade com restrição oficial
- **Idempotência** via `ROW_NUMBER() OVER (PARTITION BY chave ORDER BY ingested_at DESC) = 1`

### 2.3 Orquestração Automatizada Dual

| Camada | Ferramenta | Trigger | Ações |
|--------|------------|---------|-------|
| **CI/CD** | GitHub Actions | `cron: '0 6 5 * *'` (mensal) + `workflow_dispatch` | Pipeline completo → Artefatos Parquet + Quality Report (30 dias retention) |
| **Orquestração** | n8n Self-Hosted | Schedule (dia 05 06:00 UTC) + Manual | Dispara GHA → Wait 90s → Checa status → Auditoria Gold (Postgres) → Valida sucesso/falha → Notificação |

**Evidência visual:** ![n8n Success](docs/images/n8n_pipeline_sucesso.png)

### 2.4 Data Quality Automatizado

Validações executadas a cada run (relatório em `output/quality_report.json`):

- ✅ Schema conformidade (colunas obrigatórias)
- ✅ Null ratio ≤ 5% em colunas críticas
- ✅ Unicidade de PKs (`codigo_ibge`, `data_ref`)
- ✅ Range checks: `população > 0`, `PIB per capita > 0`, `scores 0–100`, `elegíveis ≥ 50k hab`
- ✅ Status geral: **PASSED** (Fase I — 2026-11-22)

### 2.5 Persistência Híbrida & Portabilidade

- **Supabase (PostgreSQL):** Lakehouse de produção com Session Pooler IPv4 (porta 6543, driver `psycopg2`)
- **Parquet (Snappy) particionado:** `output/gold_*/ano=YYYY/mes=MM/` — portável, versionável, custo near-zero
- **Fallback automático:** Dashboard lê do banco se `DATABASE_URL` disponível; caso contrário, lê Parquet local

### 2.6 Observabilidade & Governança

- **Logging estruturado** (módulo `logging`, níveis configuráveis via `LOG_LEVEL`)
- **GitHub Step Summary** com métricas-chave a cada execução
- **Linhagem de dados** rastreável: Gold → Silver → Bronze (JSON bruto) → API origem
- **Spec-Driven Development:** `prd.md`, `spec.md`, `agents.md` versionados; prompts em `prompts/`

---

## 3. Atendimento ao "Desafio Python – FT03"

| Requisito FT03 | Implementação no Projeto | Evidência |
|----------------|--------------------------|-----------|
| **Extração de dados de APIs públicas** | IBGE (4 endpoints: localidades, população 6579, PIB 5938, IPCA 7060) + BCB SGS (Selic 432, Dólar 10813) | `src/ingestion/` — `ibge_client.py`, `bcb_client.py` |
| **Tratamento de paginação e rate limiting** | Paginação por UF (27 chamadas/lote); `RATE_LIMIT_SLEEP=0.35`; retry exponencial | `src/ingestion/http_client.py` |
| **Armazenamento em banco relacional** | Supabase (PostgreSQL) — schemas `bronze`, `silver`, `gold` | `src/transformation/sql/` — `01_bronze_to_silver.sql`, `02_silver_to_gold.sql` |
| **Transformação e modelagem de dados** | Star Schema (dims + fatos) → Gold com scoring normalizado Min-Max (0–100) | `spec.md` Seção 3; `gold.ranking_expansao` |
| **Exportação para formato analítico (Parquet)** | Snappy comprimido, particionado `ano/mes` em `output/gold_*/` | `src/quality/exporter.py`; árvore em `README.md` |
| **Dashboard interativo** | Streamlit 4 abas: Visão Executiva, Comparador Platinum vs Smart, Simulador What-If, Contexto Macro + DQ | `src/app/streamlit_app.py`; **Live:** https://atlas-fitness-expansion-radar.streamlit.app/ |
| **Automação de pipeline** | GitHub Actions (mensal) + n8n (orquestração + validação) | `.github/workflows/pipeline_radar.yml`; `n8n/workflow_atlas_fitness_radar.json` |
| **Testes e validação de qualidade** | Data Quality automatizado (schema, nulidade, unicidade, ranges) + relatório JSON/CSV | `src/quality/validator.py`; `output/quality_report.json` |
| **Documentação técnica** | PRD, SPEC, AGENTS, README com badges, Mermaid, dicionário de dados, guia execução | `prd.md`, `spec.md`, `agents.md`, `README.md` |
| **Variáveis de ambiente / Segredos** | `.env.example` template; `DATABASE_URL` via GitHub Secrets / `st.secrets` / `.env`; `.gitignore` protege segredos | `.env.example`, `.gitignore`, `docs/GITHUB_ABOUT.md` |

---

## 4. Métricas de Entrega (Fase I — 2026-11-22)

| KPI | Valor |
|-----|-------|
| Municípios mapeados (Brasil) | 5.570 |
| Municípios com PIB válido | 5.570 |
| Municípios elegíveis ranking (pop ≥ 50k) | 687 |
| Meses histórico macroeconômico | 59 (jan/2022 – nov/2026) |
| Registros fato municipal (pop + PIB) | 22.282 |
| Registros fato macroeconomia | 59 |
| Status Data Quality | ✅ **PASSED** |
| Top 1 Platinum — Saquarema/RJ | PIB pc: R$ 678.529 | Score: 58.98 |
| Top 1 Smart — São Paulo/SP | Pop: 11.9M | Score: 62.23 |

---

## 5. Próximos Passos (Roadmap)

| Fase | Escopo | Status |
|------|--------|--------|
| **Fase I** | Pipeline core + Dashboard 4 abas + Orquestração dual + DQ | ✅ Concluída |
| **Fase II** | Mapeamento intraurbano (CEP/setor censitário), aluguel comercial m², concorrentes | 📋 Planejada |
| **Fase III** | ML: previsão de demanda, churn risk, cannibalização; alertas automáticos Slack/Email | 📋 Planejada |
| **Fase IV** | Multi-tenant para outras redes; API REST para integração com CRM/Expansão | 📋 Visão futura |

---

## 6. Acesso Rápido

| Artefato | Link |
|----------|------|
| **Repositório GitHub** | https://github.com/marcofpereira-ai/atlas-fitness-expansion-radar |
| **Dashboard Streamlit Cloud** | https://atlas-fitness-expansion-radar.streamlit.app/ |
| **GitHub Actions (Pipeline)** | https://github.com/marcofpereira-ai/atlas-fitness-expansion-radar/actions |
| **n8n Workflow (Import)** | `n8n/workflow_atlas_fitness_radar.json` |
| **PRD** | `prd.md` |
| **SPEC Técnica** | `spec.md` |
| **Regras de Engenharia (IA)** | `agents.md` |
| **Configuração GitHub (About/Topics)** | `docs/GITHUB_ABOUT.md` |
| **Licença** | `LICENSE` (MIT) |

---

> **Assinatura Digital**  
> Marco Pereira — Staff Data Engineer & Technical Writer  
> Entregue em conformidade com `agents.md`, `spec.md`, `prd.md` e requisitos do Desafio Python FT03.