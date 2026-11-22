import os
from pathlib import Path
import pandas as pd
import plotly.express as px
from sqlalchemy import create_engine
import streamlit as st

st.set_page_config(page_title="Radar de Expansão | Atlas Fitness", layout="wide")


@st.cache_data(ttl=3600)
def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        engine = create_engine(db_url)
        ranking = pd.read_sql("SELECT * FROM gold.ranking_expansao", engine)
        macro = pd.read_sql("SELECT * FROM gold.contexto_macro ORDER BY data_ref", engine)
        return ranking, macro

    ranking = pd.read_parquet(Path("output/gold_ranking_expansao"))
    macro = pd.read_parquet(Path("output/gold_contexto_macro"))
    return ranking, macro


st.title("Radar de Expansão Territorial — Atlas Fitness")
st.caption("Inteligência demográfica (IBGE) e macroeconômica (Banco Central) para decisão de abertura de unidades.")

ranking_df, macro_df = load_data()

col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
with col_f1:
    modelo = st.radio(
        "Modelo de Negócio Atlas Fitness:",
        options=["Atlas Platinum (Alto Ticket)", "Atlas Smart (Alto Giro / Volume)"],
        horizontal=True,
    )
with col_f2:
    regioes = ["Todas"] + sorted(ranking_df["regiao_nome"].dropna().unique().tolist())
    regiao_sel = st.selectbox("Região:", regioes)
with col_f3:
    df_temp = ranking_df if regiao_sel == "Todas" else ranking_df[ranking_df["regiao_nome"] == regiao_sel]
    ufs = ["Todas"] + sorted(df_temp["uf_sigla"].dropna().unique().tolist())
    uf_sel = st.selectbox("UF:", ufs)

df_view = df_temp if uf_sel == "Todas" else df_temp[df_temp["uf_sigla"] == uf_sel]
is_platinum = "Platinum" in modelo
score_col = "score_platinum" if is_platinum else "score_smart"
df_view = df_view.sort_values(score_col, ascending=False).reset_index(drop=True)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Municípios Elegíveis (>=50k hab.)", f"{len(df_view):,}".replace(",", "."))
if not df_view.empty:
    top_city = df_view.iloc[0]
    m2.metric("Cidade #1 Recomendada", f"{top_city['nome_municipio']} - {top_city['uf_sigla']}", f"Score {top_city[score_col]:.1f}")
    m3.metric("PIB per Capita Médio (Filtro)", f"R$ {df_view['pib_per_capita'].mean():,.2f}")
if not macro_df.empty:
    last_macro = macro_df.sort_values("data_ref").iloc[-1]
    m4.metric("Selic Média Recente", f"{last_macro['selic_meta_media']:.2f}% a.a.", f"Dólar R$ {last_macro['dolar_venda_medio']:.2f}")

st.divider()
c_left, c_right = st.columns(2)

with c_left:
    st.subheader(f"Top 10 Municípios — {modelo}")
    top10 = df_view.head(10).sort_values(score_col, ascending=True)
    fig_bar = px.bar(
        top10,
        x=score_col,
        y=top10["nome_municipio"] + " (" + top10["uf_sigla"] + ")",
        orientation="h",
        color=score_col,
        color_continuous_scale="Tealgrn" if not is_platinum else "YlOrRd",
        labels={score_col: "Score (0-100)", "y": "Município"},
    )
    st.plotly_chart(fig_bar, use_container_width=True)

with c_right:
    st.subheader("Matriz Renda (PIB per Capita) vs. Volume Populacional")
    fig_scatter = px.scatter(
        df_view,
        x="pib_per_capita",
        y="populacao_estimada",
        size=score_col,
        color="modelo_recomendado",
        hover_name="nome_municipio",
        hover_data=["uf_sigla", "crescimento_pop_pct", "score_platinum", "score_smart"],
        log_x=True,
        log_y=True,
        labels={"pib_per_capita": "PIB per Capita (R$ - escala log)", "populacao_estimada": "População Estimada (escala log)"},
    )
    st.plotly_chart(fig_scatter, use_container_width=True)

st.subheader("Cenário Macroeconômico (Custo de Capital e Equipamentos)")
fig_macro = px.line(
    macro_df,
    x="data_ref",
    y=["selic_meta_media", "dolar_venda_medio", "ipca_acumulado_12m_pct"],
    labels={"data_ref": "Mês", "value": "Valor / Taxa", "variable": "Indicador"},
)
st.plotly_chart(fig_macro, use_container_width=True)

with st.expander("Metodologia do Score e Tabela Completa"):
    st.markdown(
        """
        * **Atlas Platinum:** `50% PIB per Capita + 30% Crescimento Populacional + 20% População Total` (foco em ticket alto e poder aquisitivo).
        * **Atlas Smart:** `50% População Total + 35% Crescimento Populacional + 15% PIB per Capita` (foco em escala, giro e adensamento urbano).
        """
    )
    st.dataframe(df_view, use_container_width=True)
