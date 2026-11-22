# AGENTS.md — Regras de Engenharia para IA no Repositório `radar-expansao`

## 1. Contexto Obrigatório
Antes de gerar ou alterar qualquer código neste repositório, leia obrigatoriamente `prd.md` e `spec.md` para garantir alinhamento com o cliente **Atlas Fitness** (modelos **Atlas Platinum** e **Atlas Smart**) e com os contratos das camadas Medalhão.

## 2. Convenções de Estrutura e Nomenclatura
* **Pastas:**
  * `src/config/`: Configurações e variáveis de ambiente.
  * `src/ingestion/`: Apenas extração HTTP e carga bruta na camada `bronze`.
  * `src/transformation/`: Queries SQL (DuckDB/Postgres) e regras de negócio (`silver` e `gold`).
  * `src/quality/`: Validações de schema, nulidade, unicidade, intervalos e geração de relatórios.
  * `src/app/`: Interface Streamlit (somente leitura da camada `gold`).
* **Nomenclatura:**
  * Arquivos e funções Python: `snake_case` com `type hints` obrigatórios e docstrings concisas.
  * Tabelas e colunas SQL: `snake_case` em português claro (`codigo_ibge`, `pib_per_capita`, `score_platinum`, `score_smart`).

## 3. Regras Invioláveis (O que NUNCA fazer)
1. **Nunca transformar dados na ingestão:** A camada `bronze` armazena o payload JSON bruto exato retornado pela API.
2. **Nunca fazer chamada única irrestrita ao IBGE:** Sempre fatiar requisições por UF (`N6[N3[uf]]`) e/ou período para evitar HTTP 500/timeout.
3. **Nunca ultrapassar janela de 10 anos por chamada na API SGS do Banco Central.**
4. **Nunca hardcodar credenciais, URLs de banco ou chaves de API:** Usar exclusivamente `os.getenv()` / `.env`.
5. **Nunca usar `print()` para telemetria do pipeline:** Utilizar o módulo `logging` estruturado.

## 4. Padrão de Commits (Conventional Commits)
* `docs: ...` para alterações em `prd.md`, `spec.md`, `agents.md`, `prompts/` e `README.md`.
* `feat(ingestion): ...` para extratores IBGE/BCB.
* `feat(transformation): ...` para pipelines SQL Silver/Gold.
* `feat(quality): ...` para regras de Data Quality e exportação Parquet.
* `feat(app): ...` para o dashboard Streamlit.
* `chore(automation): ...` para workflows n8n e scripts `run.sh`.
