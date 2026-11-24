## 📋 Descrição
<!-- Descreva claramente o que este PR faz e por quê. Referencie issues relacionadas se houver. -->

**Tipo de mudança:**
- [ ] 🐛 Bug fix (correção que não quebra funcionalidade existente)
- [ ] ✨ Nova feature (funcionalidade que adiciona valor)
- [ ] 💥 Breaking change (correção/feature que quebra compatibilidade)
- [ ] 📝 Documentação (atualização de docs, README, spec, etc.)
- [ ] ♻️ Refatoração (mudança de código que não altera comportamento externo)
- [ ] ⚡ Performance (melhoria de velocidade/eficiência)
- [ ] ✅ Testes (adição/atualização de testes)
- [ ] 🔧 Chore (manutenção, deps, configs, CI/CD)

---

## 🎯 Contexto & Motivação
<!-- Explique o problema que resolve ou a oportunidade que captura. -->
- **Issue relacionada:** #<!-- número da issue -->
- **Decisão arquitetural:** <!-- link para ADR ou discussão no PRD/spec se aplicável -->

---

## 🧪 Como Testar
<!-- Passos para validar a mudança localmente. -->
```bash
# Exemplo:
cp .env.example .env
# configure DATABASE_URL se necessário
pip install -r requirements.txt
bash run.sh
streamlit run src/app/streamlit_app.py
```

**Checklist de validação:**
- [ ] Pipeline roda sem erros (`bash run.sh`)
- [ ] Dashboard abre e carrega dados (`streamlit run src/app/streamlit_app.py`)
- [ ] Testes existentes passam (`pytest` ou equivalente)
- [ ] Data Quality report gera `output/quality_report.json` com status PASSED
- [ ] Parquet exportado em `output/gold_*/` com partições ano/mes

---

## 📊 Impacto nos Dados / Pipeline
<!-- Se altera ingestão, transformação, qualidade ou schema: -->
- [ ] **Bronze:** Mudança em payload bruto / novas fontes / endpoints
- [ ] **Silver:** Mudança em star schema / dims / fatos / joins
- [ ] **Gold:** Mudança em scoring / ranking / métricas / normalização
- [ ] **Data Quality:** Novas validações / thresholds alterados
- [ ] **Parquet/Supabase:** Schema de saída alterado (requer migração)
- [ ] **Dashboard:** Novos filtros / visualizações / abas

**Migração de dados necessária?** ☐ Sim / ☐ Não
> Se sim, descreva a estratégia (backfill, dual-write, cutover, etc.)

---

## 🔒 Segurança & Segredos
- [ ] Nenhum segredo hardcodado (`.env`, `.streamlit/secrets.toml`, tokens, senhas)
- [ ] Variáveis sensíveis usam `os.getenv()` / GitHub Secrets / n8n Credentials
- [ ] `.gitignore` atualizado se novos padrões de arquivos sensíveis surgirem

---

## 📸 Evidências Visuais (se aplicável)
<!-- Screenshots do dashboard, logs de execução, diagramas atualizados, etc. -->

| Antes | Depois |
|-------|--------|
| ![antes](url) | ![depois](url) |

---

## ✅ Checklist de Qualidade (Conventional Commits)
- [ ] Título do PR segue **Conventional Commits** (`feat(ingestion): ...`, `fix(transformation): ...`, `docs: ...`, `chore(automation): ...`)
- [ ] Commits atômicos e mensagens claras
- [ ] Código segue padrões do `agents.md` (snake_case, type hints, docstrings, logging estruturado)
- [ ] Nenhum `print()` para telemetria — usa `logging`
- [ ] Nenhuma transformação na camada `ingestion/` (bronze = payload bruto)
- [ ] Requisições IBGE fatiadas por UF / períodos (sem chamada única irrestrita)
- [ ] Janelas BCB SGS ≤ 10 anos
- [ ] Documentação atualizada (`README.md`, `spec.md`, `prd.md` se regras de negócio mudaram)

---

## 👀 Revisão
**Revisores sugeridos:** @<!-- github handles -->
**Áreas de atenção:** <!-- lógica de scoring, SQL complexo, performance, segurança -->

---

> **Nota:** Este template segue as convenções do projeto definidas em `agents.md` e `spec.md`. Por favor, preencha todas as seções aplicáveis.