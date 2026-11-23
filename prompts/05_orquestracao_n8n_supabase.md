# Prompt 05 — Orquestração n8n + Supabase + GitHub Actions

## Prompt Original

> Objetivo (Etapa 4 - Orquestração n8n + Supabase + GitHub Actions):
> 1. Crie o arquivo `.github/workflows/pipeline_radar.yml` com schedule mensal (dia 05 às 06:00 UTC), `workflow_dispatch` para execução manual via n8n, Python 3.11, upload de artefatos (quality report + Parquet gold), sumário no GitHub Step Summary.
> 2. Crie `n8n/workflow_atlas_fitness_radar.json` com 5 nós: Schedule Trigger (mensal) + Manual Trigger → HTTP Request (disparar workflow_dispatch) → Wait 90s → HTTP Request (checar status do run) → Postgres (auditoria `gold.ranking_expansao`) → IF (validação: GitHub conclusion=success E total_elegiveis > 0) → Set (resumo sucesso/falha).
> 3. Atualize `README.md` com: GitHub Secrets `DATABASE_URL`, instruções de importação n8n (localhost:5678), Supabase Session Pooler (IPv4, porta 6543), GitHub PAT (scopes repo+workflow).
> 4. Registre tudo em `prompts/05_orquestracao_n8n_supabase.md`.

---

## Resumo Técnico das Alterações

### 1. `.github/workflows/pipeline_radar.yml` — CI/CD Mensal

**Triggers:**
- `schedule`: `cron: '0 6 5 * *'` (dia 05, 06:00 UTC)
- `workflow_dispatch`: input `ref` (branch, default `main`)

**Job `build-and-run`:**
- `runs-on: ubuntu-latest`, timeout 60 min
- Env: `DATABASE_URL` (secret), `LOG_LEVEL=INFO`, `OUTPUT_DIR=output`, `REQUEST_TIMEOUT=30`, `RATE_LIMIT_SLEEP=0.35`
- Steps: Checkout → Setup Python 3.11 (cache pip) → Install deps → Run pipeline → Upload quality report → Upload Parquet Gold → Summary markdown

**Artefatos (retention 30 dias):**
- `quality-report`: `output/quality_report.json`
- `gold-parquet-outputs`: `output/gold_ranking_expansao/`, `output/gold_contexto_macro/`

**GitHub Step Summary:** Tabela markdown com métricas extraídas do `quality_report.json`.

---

### 2. `n8n/workflow_atlas_fitness_radar.json` — Workflow de Orquestração

**Nós (9 total):**

| ID | Nome | Tipo | Função |
|----|------|------|--------|
| 1 | Schedule Trigger | `n8n-nodes-base.scheduleTrigger` | Mensal dia 05 06:00 UTC |
| 2 | Manual Trigger | `n8n-nodes-base.manualTrigger` | Execução sob demanda |
| 3 | Disparar GitHub Actions | `n8n-nodes-base.httpRequest` | POST `/repos/{owner}/{repo}/actions/workflows/pipeline_radar.yml/dispatches` |
| 4 | Wait 90s | `n8n-nodes-base.wait` | Aguarda 90s para workflow iniciar |
| 5 | Checar Status Workflow | `n8n-nodes-base.httpRequest` | GET `/repos/{owner}/{repo}/actions/workflows/pipeline_radar.yml/runs?per_page=1` |
| 6 | Auditoria Gold (Postgres) | `n8n-nodes-base.postgres` | Query agregada em `gold.ranking_expansao` |
| 7 | Validar Sucesso | `n8n-nodes-base.if` | `conclusion=success` E `total_elegiveis > 0` |
| 8 | Resumo Sucesso | `n8n-nodes-base.set` | Payload estruturado de sucesso |
| 9 | Resumo Falha | `n8n-nodes-base.set` | Payload estruturado de falha |

**Credenciais n8n referenciadas:**
- `GitHub PAT` → HTTP Header Auth (Bearer token)
- `Supabase Session Pooler` → PostgreSQL connection

**Conexões:** Linear 1→3→4→5→6→7→(8|9)

---

### 3. Query de Auditoria Gold (Postgres)

```sql
SELECT COUNT(*) AS total_elegiveis,
       MAX(ano_pop) AS ano_pop_ref,
       MAX(ano_pib) AS ano_pib_ref,
       ROUND(AVG(score_platinum), 2) AS media_platinum,
       ROUND(AVG(score_smart), 2) AS media_smart
FROM gold.ranking_expansao;
```

Retorna contagem de municípios elegíveis (pop ≥ 50k), anos de referência de população/PIB e médias dos scores para validação de sanidade.

---

### 4. README.md — Documentação de Automação

Seções adicionadas:
- **GitHub Actions**: schedule, dispatch, secrets, artefatos, summary
- **n8n**: fluxo visual, importação, credenciais necessárias
- **Supabase Session Pooler**: host, porta 6543, IPv4, driver `psycopg2`, SSL require
- **GitHub PAT**: scopes `repo` + `workflow`, expiração 90 dias

---

### 5. Configuração Supabase (Produção)

**Session Pooler (IPv4) — Obrigatório:**
```
Host: aws-0-[REGION].pooler.supabase.com
Port: 6543
Database: postgres
User: postgres.[PROJECT_REF]
Password: [PASSWORD]
SSL Mode: require
```

**Connection String Python:**
```python
postgresql+psycopg2://postgres.[REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres
```

> ⚠️ **Não use** Transaction Pooler (porta 5432) nem driver `psycopg` (v3) — falha handshake SSL em CI Ubuntu.

**GitHub Secret `DATABASE_URL`:** String acima codificada (senha com URL encoding para caracteres especiais).

---

### 6. GitHub PAT — Criação e Uso

1. `Settings → Developer settings → Personal access tokens → Tokens (classic)`
2. `Generate new token (classic)`
3. Scopes: ✅ `repo` (full) ✅ `workflow`
4. Expiration: 90 dias
5. Copiar token → n8n Credential `GitHub PAT` (HTTP Header Auth)

**Header nas chamadas n8n:**
```
Authorization: Bearer <PAT>
Accept: application/vnd.github+json
X-GitHub-Api-Version: 2022-11-28
User-Agent: n8n-atlas-fitness-radar
```

---

### 7. Importação n8n (localhost:5678)

1. Acesse `http://localhost:5678`
2. Workflows → Import
3. Selecione `n8n/workflow_atlas_fitness_radar.json`
4. Configure credenciais:
   - `GitHub PAT` → HTTP Header Auth
   - `Supabase Session Pooler` → PostgreSQL
5. Ative workflow (toggle "Active" no canto superior direito)

---

### 8. Validação End-to-End

**Teste manual via n8n:**
1. Execute "Manual Trigger" no n8n
2. Aguarde ~2-3 min (pipeline GitHub Actions)
3. Verifique branch `Resumo Sucesso` ou `Resumo Falha`
4. Confira `github_run_url` para logs completos

**Teste agendado:**
- Próxima execução: dia 05 às 06:00 UTC
- Verificar no GitHub Actions → Workflow runs
- Artefatos disponíveis por 30 dias

---

### 9. Troubleshooting Comum

| Sintoma | Causa | Solução |
|---------|-------|---------|
| `401 Unauthorized` no dispatch | PAT inválido/expirado | Renovar PAT, scopes `repo`+`workflow` |
| `SSL SYSCALL error` no Postgres | Driver `psycopg` v3 | Usar `psycopg2-binary` + `postgresql+psycopg2://` |
| `connection timeout` Supabase | IPv6 no runner CI | Forçar IPv4 no host ou usar Session Pooler IPv4 |
| `workflow_dispatch` não encontrado | Workflow não no `main` | Push `.github/workflows/pipeline_radar.yml` para `main` |
| `total_elegiveis = 0` | PIB/pop não carregados | Verificar Bronze/Silver logs, re-rodar ingestão |

---

### 10. Arquivos Criados/Modificados

| Arquivo | Tipo | Descrição |
|---------|------|-----------|
| `.github/workflows/pipeline_radar.yml` | `chore(automation)` | GitHub Actions mensal + dispatch + artefatos + summary |
| `n8n/workflow_atlas_fitness_radar.json` | `chore(automation)` | Workflow n8n 9 nós (schedule+manual→dispatch→wait→status→auditoria→IF→resumo) |
| `README.md` | `docs` | Seção completa de automação (secrets, n8n import, Supabase pooler, PAT) |
| `prompts/05_orquestracao_n8n_supabase.md` | `docs` | Este documento |

---

### 11. Próximos Passos (Fase II+)

1. **Dashboard Streamlit**: `streamlit run src/app/streamlit_app.py` — validar filtros UF/Região, toggle Platinum/Smart, drill-down município
2. **Testes Automatizados**: Expandir `tests/` com pytest + fixtures de bronze mock + property-based tests para validações SQL
3. **API de Consulta**: FastAPI sobre `gold.ranking_expansao` com paginação, filtros, OpenAPI/Swagger
4. **Alertas n8n**: Adicionar nó `Slack`/`Email` nos branches Sucesso/Falha para notificação proativa
5. **Backfill Histórico**: Script para recalcular scores com janelas móveis (ex: últimos 5 anos PIB)
6. **Versionamento de Modelo**: MLflow para tracking de versões de scoring (pesos, features, thresholds)

---

### 12. Validação Final

```bash
# 1. Verificar workflow YAML sintaxe
gh workflow view pipeline_radar.yml --repo marcofpereira-ai/atlas-fitness-expansion-radar

# 2. Disparar manualmente via API (teste PAT)
gh workflow run pipeline_radar.yml --ref main --repo marcofpereira-ai/atlas-fitness-expansion-radar

# 3. Verificar execução
gh run list --workflow=pipeline_radar.yml --repo marcofpereira-ai/atlas-fitness-expansion-radar --limit 5

# 4. Baixar artefatos
gh run download <RUN_ID> --repo marcofpereira-ai/atlas-fitness-expansion-radar --dir ./artifacts

# 5. Validar n8n import (manual no localhost:5678)
# 6. Confirmar Supabase sync (DATABASE_URL ativo no .env)
python -m src.main
# ✅ Pipeline PASSED + tabelas bronze/silver/gold criadas no Supabase
```