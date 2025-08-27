# streamlit_app.py
import streamlit as st
import pandas as pd

from Tratamento_Indicadores import (
    carregar_bases,
    fornecedor_top_por_uf,
    maior_ordem_fornecimento,
    menor_ordem_fornecimento,
    valor_medio_por_of,
    percentual_ofs_basicas_ultimo_ano,
    periodo_maior_volume_bimestre,
    mes_maior_volume_ultimo_ano,
    _format_brl,
)

from fornecedores_core import (
    carregar_fornecedores,
    total_empresas_cadastradas,
    serie_fornecedores_ativos_ultimos_anos,
)

st.set_page_config(page_title="Suprimentos • Indicadores & Fornecedores", layout="wide")
st.title("Suprimentos • Indicadores e Fornecedores")

@st.cache_data
def _load_df_erp(): 
    return carregar_bases()

@st.cache_data
def _load_df_forn(): 
    return carregar_fornecedores()

df_erp  = _load_df_erp()
df_forn = _load_df_forn()

# =========================
# 📈 Indicadores de Suprimentos
# =========================
st.header("📈 Indicadores de Suprimentos")

col1, col2 = st.columns(2)
with col1:
    st.subheader("Fornecedor TOP (10 anos) – RJ/SP")
    st.dataframe(fornecedor_top_por_uf(df_erp, anos=10), use_container_width=True)
with col2:
    st.subheader("Fornecedor TOP (2 anos) – RJ/SP")
    st.dataframe(fornecedor_top_por_uf(df_erp, anos=2), use_container_width=True)

c1, c2 = st.columns(2)
with c1:
    st.subheader("🏆 Maior OF")
    st.dataframe(maior_ordem_fornecimento(df_erp), use_container_width=True)
with c2:
    st.subheader("📉 Menor OF")
    st.dataframe(menor_ordem_fornecimento(df_erp), use_container_width=True)

media, detalhado = valor_medio_por_of(df_erp)
st.metric("Valor médio por OF", _format_brl(media))
#with st.expander("OFs com total"):
    #st.dataframe(detalhado, use_container_width=True)

pct, grupo = percentual_ofs_basicas_ultimo_ano(df_erp)
st.metric("% de OFs BÁSICAS (último ano)", f"{pct:.2f}%")
#with st.expander("Classificação das OFs (último ano)"):
    #st.dataframe(grupo, use_container_width=True)

st.subheader("Bimestre com maior volume (padrão, últimos 10 anos)")
st.dataframe(periodo_maior_volume_bimestre(df_erp, anos=10), use_container_width=True)

st.subheader("Mês com maior volume (último ano)")
st.dataframe(mes_maior_volume_ultimo_ano(df_erp), use_container_width=True)

st.divider()

# =========================
# 🏷️ Fornecedores
# =========================
st.header("🏷️ Fornecedores")

st.subheader("Cadastro de Fornecedores")
total_cad = total_empresas_cadastradas(df_forn)
st.metric("Empresas cadastradas (total)", f"{total_cad}")

st.subheader("Fornecedores ativos por ano (últimos 10 anos)")
serie, resumo = serie_fornecedores_ativos_ultimos_anos(df_erp, anos=10)
st.dataframe(serie, use_container_width=True)
if not serie.empty:
    st.bar_chart(data=serie, x="ANO", y="FORNECEDORES_ATIVOS", use_container_width=True)
    st.caption(
        f"Variação {resumo['primeiro_ano']} → {resumo['ultimo_ano']}: "
        f"{resumo['var_abs']} fornecedores ({resumo['var_pct']:.2f}%)"
    )

