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

## Uso de Inteligência Artificial no Projeto
O desenvolvimento seguiu metodologia *Spec-Driven* documentada em `prd.md`, `spec.md`, `agents.md` e registrada na pasta `prompts/`, garantindo rastreabilidade das decisões arquiteturais e revisão humana de todas as regras SQL e métricas de negócio.
