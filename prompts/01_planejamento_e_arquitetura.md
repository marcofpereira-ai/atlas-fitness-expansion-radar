# Registro de Prompt 01 — Planejamento Unificado e Definição do Cliente

## Prompt Utilizado
> "Analise os requisitos do Desafio Python (FT03 - Projeto 1) e do Data Challenge Xperiun (Fase 2 - Radar de Expansão). Crie uma arquitetura unificada para o cliente Rede de Academias Atlas Fitness (com dois modelos: Atlas Platinum e Atlas Smart), gerando prd.md, spec.md e agents.md antes de escrever o código."

## O que a IA Entregou
* Mapeamento cruzado entre os requisitos de engenharia de software/dados (ingestão resiliente de 2 APIs, SQL unnesting, 5 transformações, Data Quality, Parquet Snappy particionado por ano/mês) e os entregáveis do Lakehouse Medalhão (Bronze, Silver, Gold, n8n e Streamlit).
* Definição matemática transparente dos scores de expansão (`score_platinum` e `score_smart`) normalizados de 0 a 100.

## Ajustes e Validações Realizadas pelo Autor
* Validação das séries oficiais do IBGE (Agregados 6579, 5938, 7060) e do Banco Central SGS (Séries 432 e 10813).
* Inclusão da regra de fatiamento por UF para contornar o limite de volume da API de Agregados do IBGE e particionamento temporal Hive (`ano=YYYY/mes=MM`) na pasta `output/`.
