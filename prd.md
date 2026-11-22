# PRD — Radar de Expansão: Atlas Fitness

## 1. Cliente e Vertical
* **Cliente:** Rede de Academias **Atlas Fitness** (consultoria executada pela Bússola Pública).
* **Vertical:** Saúde, Bem-Estar e Fitness (varejo físico de serviços recorrentes).
* **Modelos de Negócio:**
  * **Atlas Platinum (Premium):** Unidades de alto padrão com ticket médio elevado, infraestrutura completa (musculação importada, recovery, estúdios coletivos) e foco em retenção de público de maior poder aquisitivo.
  * **Atlas Smart (Popular / Alto Giro):** Unidades enxutas de implantação rápida, mensalidade acessível e alta capacidade de absorção em centros urbanos densos.

## 2. Problema de Negócio
Atualmente, a expansão territorial da Atlas Fitness depende de análises subjetivas ("feeling" comercial, observação pontual de concorrentes e indicações locais), sem integração sistemática entre demografia municipal e cenário macroeconômico. Isso gera dois riscos:
1. Abrir unidades **Atlas Platinum** em cidades populosas, porém sem renda per capita suficiente para sustentar o ticket.
2. Perder oportunidades de expansão **Atlas Smart** em municípios de porte médio com forte crescimento populacional e massa crítica jovem/adulta.
3. Ignorar o impacto de juros (Selic) e câmbio (Dólar) no CAPEX de obras e importação de equipamentos.

## 3. Perguntas de Negócio
1. **Potencial por Modelo:** Quais são os top 10 municípios do Brasil (e por UF/Região) com maior potencial para **Atlas Platinum** vs. **Atlas Smart**?
2. **Renda vs. Volume:** Municípios de maior PIB per capita são sempre a melhor escolha, ou cidades de médio/grande porte com renda intermediária superam em retorno para o modelo **Atlas Smart**?
3. **Dinâmica de Crescimento:** Quais cidades médias (100 mil a 500 mil habitantes) apresentam maior aceleração populacional recente combinada com PIB per capita acima da média estadual?
4. **Timing Macroeconômico:** O comportamento recente de Selic, IPCA e Dólar favorece acelerar o CAPEX de novas unidades agora ou priorizar modelos mais enxutos (Atlas Smart)?

## 4. Critérios e Pesos do Ranking (Score 0 a 100)
Cada indicador municipal é normalizado via Min-Max (0 a 100) na camada Gold:
* **Score Atlas Platinum (`score_platinum`):**
  * **50%** PIB per capita municipal (`pib_per_capita`) — Proxy de capacidade de pagamento de ticket premium.
  * **30%** Crescimento populacional recente (`crescimento_pop_pct`) — Proxy de expansão de demanda local.
  * **20%** População total (`populacao_estimada`) — Garantia de escala mínima (filtro de elegibilidade: municípios com $\ge 50.000$ habitantes).
* **Score Atlas Smart (`score_smart`):**
  * **50%** População total (`populacao_estimada`) — Proxy de massa crítica e alto giro de alunos.
  * **35%** Crescimento populacional recente (`crescimento_pop_pct`) — Captura cidades em adensamento urbano.
  * **15%** PIB per capita municipal (`pib_per_capita`) — Garante lastro econômico mínimo para consumo recorrente.

## 5. Escopo
* **Dentro do Escopo:**
  * Ingestão automatizada via APIs oficiais do **IBGE** (Localidades, População Estimada, PIB Municipal, IPCA) e **Banco Central SGS** (Meta Selic, Câmbio Dólar).
  * Arquitetura Medalhão (`bronze`, `silver`, `gold`) no PostgreSQL (Supabase) + exportação local particionada em Parquet (Snappy) com auditoria de Data Quality.
  * Orquestração incremental via n8n e dashboard interativo no Streamlit Cloud.
* **Fora do Escopo (Fase 1):**
  * Mapeamento intraurbano por CEP/bairro, análise de aluguel comercial por metro quadrado e raspagem de preços de concorrentes locais.

## 6. Critérios de Sucesso
* Pipeline ponta a ponta executando sem falhas manuais e respeitando limites de requisições das APIs.
* 100% dos 5.570 municípios brasileiros mapeados com rastreabilidade completa da camada Gold até o JSON bruto na Bronze.
* Relatório de Data Quality sem violações críticas de unicidade, schema ou intervalos.
* Dashboard Streamlit publicado permitindo ao Diretor de Expansão filtrar UF/Região e alternar entre **Atlas Platinum** e **Atlas Smart** em menos de 30 segundos.
