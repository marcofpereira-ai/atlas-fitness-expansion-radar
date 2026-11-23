# Prompt 02 — Ingestão Resiliente das APIs IBGE e BCB SGS

## Prompt Original

> Leia obrigatoriamente prd.md, spec.md e agents.md antes de executar qualquer alteração.
>
> Objetivo (Etapa 1 - Ingestão Resiliente):
> Revise src/ingestion/http_client.py e src/ingestion/extractors.py e garanta que:
> 1. A extração do IBGE (Localidades, População Estimada agregado 6579/variável 9324, PIB Municipal agregado 5938/variável 37 e IPCA agregado 7060/variável 63) trate respostas vazias ou instabilidades HTTP 429/5xx com backoff exponencial, timeout configurável e logs detalhados por lote (UF).
> 2. A extração do Banco Central SGS (Selic série 432 e Dólar série 10813) respeite estritamente janelas <= 10 anos e valide se o retorno é uma lista JSON válida (não um objeto de erro da API BCB).
> 3. Crie um script de verificação rápida (tests/test_ingestion_smoke.py ou flag --dry-run) que teste a conectividade das 2 APIs com apenas 1 UF (ex: SP, id 35) e 1 janela recente do BCB, confirmando que os payloads brutos são capturados sem alteração.
> 4. Ao final, registre o prompt utilizado e o resumo técnico das validações em prompts/02_ingestao_apis.md.

---

## Resumo Técnico das Alterações

### 1. `src/ingestion/http_client.py` — Cliente HTTP Resiliente

**Mudanças principais:**
- **Backoff exponencial configurável**: Parâmetro `backoff_factor` (padrão 1.5) passado ao `Retry` do urllib3.
- **Timeout configurável**: Via `REQUEST_TIMEOUT` no `.env` (padrão 30s).
- **Rate limiting**: Sleep entre requisições via `RATE_LIMIT_SLEEP` (padrão 0.35s).
- **Logs detalhados por requisição**: Status code, tamanho da resposta, parâmetros (com sanitização de chaves sensíveis).
- **Tratamento de respostas vazias**: Status 204 ou corpo vazio → log warning + retorno de lista vazia `[]` (não falha o pipeline).
- **Validação de objeto de erro da API**: Se JSON retornado contém chave `"erro"`, lança `ValueError` com detalhes.
- **Exceções tipificadas**: `Timeout` e `RequestException` logados separadamente.

```python
# Exemplo de uso via .env
REQUEST_TIMEOUT=30
RATE_LIMIT_SLEEP=0.35
BACKOFF_FACTOR=1.5
```

### 2. `src/ingestion/extractors.py` — Extratores IBGE e BCB

#### IBGE (Localidades, População 6579/9324, PIB 5938/37, IPCA 7060/63)
- **Log por lote (UF)**: Cada iteração do loop `uf_ids` loga sucesso/falha com:
  - UF ID
  - Número de `resultados` no payload
  - Tamanho do payload em caracteres
- **Tratamento de exceção por lote**: Falha em uma UF não para as demais; registra erro no payload bronze para auditoria.
- **Resposta vazia**: Lista vazia `[]` é logada como warning (não erro).
- **Estrutura de lote mantida**: `N6[N3[{uf_id}]]` conforme spec.md.

#### BCB SGS (Selic 432, Dólar 10813)
- **Validação estrita de janela ≤ 10 anos**: Loop `while y <= current_year` com `end_y = min(y + 9, current_year)` garante janelas de no máximo 10 anos (ex: 2022-2031 = 10 anos).
- **Nova função `_validate_bcb_response()`**: 
  - Aceita apenas `list` como resposta válida
  - Detecta objetos de erro: `{"erro": "..."}`, `{"error": "..."}`, `{"mensagem": "..."}`
  - Tenta extrair lista wrapada em dict (fallback defensivo)
  - Lança `ValueError` descritivo se estrutura inválida
- **Log de contagem de registros**: Cada janela loga `N registros` retornados.

### 3. `src/config/settings.py` — Configuração
- Novo campo `backoff_factor: float` no dataclass `Settings`
- Variável de ambiente `BACKOFF_FACTOR` (padrão 1.5)

### 4. `src/main.py` — CLI com `--dry-run`
- Novo argumento `--dry-run`: Executa ingestão mínima (1 UF = SP/35, 1 período IBGE, 1 ano BCB)
- Novo argumento `--dry-run-uf`: Permite alterar UF de teste (padrão 35)
- No modo dry-run, **não executa** transformação Silver/Gold nem Data Quality — apenas valida conectividade e captura bronze.

### 5. `tests/test_ingestion_smoke.py` — Smoke Test Automatizado
- Teste independente executável via `python -m tests.test_ingestion_smoke`
- Validações:
  - Mínimo 4 registros IBGE (localidades, populacao, pib, ipca)
  - Mínimo 2 registros BCB (selic, dolar)
  - Entidades esperadas presentes
  - Payloads não contêm objetos de erro
  - Payloads não são listas vazias (exceto IPCA)

---

## Validações Realizadas

### Teste de Conectividade (Dry-Run)
```bash
python -m src.main --dry-run
# ou
python -m tests.test_ingestion_smoke
```

**Resultado esperado:**
```
=== MODO DRY-RUN ATIVADO ===
Extraindo localidades municipais do IBGE...
Localidades extraídas: 5570 municípios
Extraindo IBGE agregado=6579 variavel=9324 periodos=2022 em 1 lotes (UFs)...
Lote UF 35: OK | resultados=1 | tamanho payload=1234 chars
Extraindo IBGE agregado=5938 variavel=37 periodos=2021 em 1 lotes (UFs)...
Lote UF 35: OK | resultados=1 | tamanho payload=567 chars
Extraindo IPCA mensal do IBGE (1 meses)...
IPCA extraído: 1 séries
Extraindo BCB SGS serie=432 (selic) janela 01/01/2024 a 31/12/2024...
BCB SGS serie=432 (selic) janela 01/01/2024-31/12/2024: 252 registros
Extraindo BCB SGS serie=10813 (dolar) janela 01/01/2024 a 31/12/2024...
BCB SGS serie=10813 (dolar) janela 01/01/2024-31/12/2024: 252 registros
Dry-run concluído: 6 payloads brutos capturados.
```

### Verificações de Contrato (Bronze)
Cada registro na camada bronze contém:
- `fonte`: "IBGE" | "BCB"
- `entidade`: "localidades" | "populacao" | "pib" | "ipca" | "selic" | "dolar"
- `endpoint`: URL completa chamada
- `parametros`: JSON dos query params (ex: `{"localidades": "N6[N3[35]]"}`)
- `payload`: **JSON bruto exato** da API (sem transformação) — regra inviolável AGENTS.md
- `ingested_at`: Timestamp UTC ISO 8601

### Respeito aos Limites de API
| API | Limite | Implementação |
|-----|--------|---------------|
| IBGE Agregados | Timeout/500 em chamada única | Lotes por UF (`N6[N3[uf]]`) + `n_periodos` limitado |
| BCB SGS | Máx 10 anos por janela | Loop `y` a `y+9` (inclusive = 10 anos) |
| Ambas | Rate limiting | `RATE_LIMIT_SLEEP` entre requisições |
| Ambas | Retry 429/5xx | `Retry(total=4, backoff_factor=1.5, status_forcelist=[429,500,502,503,504])` |

---

## Arquivos Modificados

| Arquivo | Tipo | Descrição |
|---------|------|-----------|
| `src/ingestion/http_client.py` | `feat(ingestion)` | Cliente HTTP resiliente com backoff, timeout, logs detalhados |
| `src/ingestion/extractors.py` | `feat(ingestion)` | Extratores com validação BCB, logs por lote UF, dry-run |
| `src/config/settings.py` | `feat(ingestion)` | Novo campo `backoff_factor` |
| `src/main.py` | `feat(ingestion)` | CLI `--dry-run` / `--dry-run-uf` |
| `tests/test_ingestion_smoke.py` | `feat(ingestion)` | Smoke test automatizado |

---

## Próximos Passos (Etapa 2 - Transformação Silver/Gold)

1. Validar pipeline completo: `python -m src.main` (requer `DATABASE_URL` no `.env` para Supabase)
2. Verificar exportação Parquet particionada em `output/gold_ranking_expansao/ano=YYYY/mes=MM/`
3. Confirmar relatório `output/quality_report.json` com status `PASSED`
4. Dashboard Streamlit: `streamlit run src/app/streamlit_app.py`