# Metadados para Configuração do Repositório GitHub

## 📝 Descrição Curta (Campo "About" — até 160 caracteres)

> Pipeline de dados Medalhão (Bronze→Silver→Gold) para expansão da **rede de academias Atlas Fitness** (Platinum premium & Smart low-cost), integrando IBGE + Banco Central com orquestração n8n/GitHub Actions e dashboard Streamlit.

**Contagem de caracteres:** ~158 (incluindo espaços)

---

## 🏷️ Topics / Tags Recomendadas

Copie e cole na seção "Topics" do GitHub (Settings → General → Topics):

```
data-engineering, medallion-architecture, fitness-industry, academias, duckdb, supabase, n8n, github-actions, streamlit, python
```

**Lista individual para clique rápido:**
- `data-engineering`
- `medallion-architecture`
- `fitness-industry`
- `academias`
- `duckdb`
- `supabase`
- `n8n`
- `github-actions`
- `streamlit`
- `python`

---

## 🛠️ Comando `gh repo edit` Pronto (GitHub CLI)

Execute no terminal (após `gh auth login`):

```bash
gh repo edit marcofpereira-ai/atlas-fitness-expansion-radar \
  --description "Pipeline de dados Medalhão (Bronze→Silver→Gold) para expansão da rede de academias Atlas Fitness (Platinum premium & Smart low-cost), integrando IBGE + Banco Central com orquestração n8n/GitHub Actions e dashboard Streamlit." \
  --add-topic data-engineering \
  --add-topic medallion-architecture \
  --add-topic fitness-industry \
  --add-topic academias \
  --add-topic duckdb \
  --add-topic supabase \
  --add-topic n8n \
  --add-topic github-actions \
  --add-topic streamlit \
  --add-topic python \
  --enable-issues \
  --enable-wiki=false \
  --enable-projects=false \
  --delete-branch-on-merge=true
```

> **Nota:** Substitua `marcofpereira-ai` pelo seu usuário/organização GitHub se diferente.

---

## ✅ Checklist Pós-Configuração

- [ ] Description atualizada no About do GitHub
- [ ] Topics adicionados (10 tags)
- [ ] Branch protection rules configuradas (main: require PR review, status checks)
- [ ] GitHub Secrets criados: `DATABASE_URL` (Supabase Session Pooler)
- [ ] GitHub Environments configurados se usar (ex: `production` para Supabase)
- [ ] Repository visibility confirmada (Private / Public)
- [ ] Social preview image uploadada (opcional — screenshot do dashboard)

---

## 🔗 Links Úteis

- **Repo:** https://github.com/marcofpereira-ai/atlas-fitness-expansion-radar
- **Actions:** https://github.com/marcofpereira-ai/atlas-fitness-expansion-radar/actions
- **n8n Workflow Import:** `n8n/workflow_atlas_fitness_radar.json`
- **Dashboard Local:** `streamlit run src/app/streamlit_app.py`