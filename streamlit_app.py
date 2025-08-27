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
    quantidade_empresas_que_venderam_ultimos_3_anos,
)

from fornecedores_core import (
    carregar_fornecedores,
    total_empresas_cadastradas,
    serie_fornecedores_ativos_ultimos_anos,
)

st.set_page_config(page_title="Suprimentos • Indicadores & Fornecedores", layout="wide")
st.title("Suprimentos • Indicadores e Fornecedores")

# ---------- Helpers ----------
def _col(df: pd.DataFrame, candidatos):
    """1ª coluna existente entre candidatos/aliases (case-insensitive)."""
    aliases = {
        "DATA_OF": ["OF_DATA", "PED_DT", "REQ_DATA", "DATA", "DT"],
        "EMPRD_UF": ["UF_OBRA", "OBRA_UF", "UF"],
        "FORNECEDOR_UF": ["FORN_UF", "UF_FORN", "UF"],
    }
    lista = []
    for c in candidatos:
        lista.append(c)
        lista.extend(aliases.get(c, []))
    up = {c.strip().upper(): c for c in df.columns}
    for cand in lista:
        k = cand.strip().upper()
        if k in up:
            return up[k]
    raise KeyError(f"Nenhuma dessas colunas: {lista}. Disponíveis: {list(df.columns)}")

def _safe(fn, *a, **k):
    try:
        return fn(*a, **k)
    except Exception as e:
        st.warning(f"Não consegui calcular **{fn.__name__}**: {e}")
        return None

def _round_cols(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    df = df.copy()
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").round(2)
    return df

@st.cache_data(ttl=3600, show_spinner=False)
def _load_df_erp():
    return carregar_bases()

@st.cache_data(ttl=3600, show_spinner=False)
def _load_df_forn():
    return carregar_fornecedores()

df_erp = _load_df_erp()
df_forn = _load_df_forn()
df = df_erp.copy()

# ---------- KPIs ----------
with st.container(border=True):
    st.subheader("📊 Resumo")
    k1, k2, k3, k4, k5 = st.columns(5)

    vm = _safe(valor_medio_por_of, df)
    if vm:
        media, _det = vm
        k1.metric("Valor médio por OF", _format_brl(round(media, 2)))

    pct_grp = _safe(percentual_ofs_basicas_ultimo_ano, df)
    if pct_grp:
        pct, _g = pct_grp
        k2.metric("% de OFs BÁSICAS (último ano)", f"{pct:.2f}%")

    try:
        total_cad = total_empresas_cadastradas(df_forn)
        k3.metric("Fornecedores cadastrados", f"{total_cad}")
    except Exception as e:
        k3.metric("Fornecedores cadastrados", "—")
        st.caption(f"Diagnóstico: {e}")

    qtd_vend = _safe(quantidade_empresas_que_venderam_ultimos_3_anos, df)
    k4.metric("Empresas que venderam (últimos 3 anos)", _format_int_br(qtd_vend if isinstance(qtd_vend, (int, float)) else 0))
    
    try:
        serie, resumo = serie_fornecedores_ativos_ultimos_anos(df, anos=10)
        if serie is not None and not serie.empty:
            var_txt = f"{resumo['var_abs']} ({resumo['var_pct']:.2f}%)"
            k5.metric(
                "Variação fornecedores ativos",
                var_txt,
                help=f"{resumo['primeiro_ano']} → {resumo['ultimo_ano']}",
            )
        else:
            k4.metric("Variação fornecedores ativos", "—")
    except Exception:
        k4.metric("Variação fornecedores ativos", "—")

# ---------- TOP fornecedores ----------
with st.container(border=True):
    st.subheader("🥇 TOP fornecedores por UF")
    c1, c2 = st.columns(2)

    with c1:
        st.caption("Últimos 10 anos")
        df_top10 = _safe(fornecedor_top_por_uf, df, anos=10)
        if isinstance(df_top10, pd.DataFrame) and not df_top10.empty:
            if "FORNECEDOR_CDG" in df_top10.columns:
                df_top10["FORNECEDOR_CDG"] = df_top10["FORNECEDOR_CDG"].astype("string")
            df_top10 = _round_cols(df_top10, ["VALOR"])
            st.dataframe(
                df_top10,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "VALOR": st.column_config.NumberColumn("VALOR", format="%.2f"),
                    "FORNECEDOR_CDG": st.column_config.TextColumn("FORNECEDOR_CDG"),
                },
            )
        else:
            st.info("Sem dados para exibir.")

    with c2:
        st.caption("Últimos 2 anos")
        df_top2 = _safe(fornecedor_top_por_uf, df, anos=2)
        if isinstance(df_top2, pd.DataFrame) and not df_top2.empty:
            if "FORNECEDOR_CDG" in df_top2.columns:
                df_top2["FORNECEDOR_CDG"] = df_top2["FORNECEDOR_CDG"].astype("string")
            df_top2 = _round_cols(df_top2, ["VALOR"])
            st.dataframe(
                df_top2,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "VALOR": st.column_config.NumberColumn("VALOR", format="%.2f"),
                    "FORNECEDOR_CDG": st.column_config.TextColumn("FORNECEDOR_CDG"),
                },
            )
        else:
            st.info("Sem dados para exibir.")

# ---------- OFs destaque ----------
with st.container(border=True):
    st.subheader("📎 OFs destaque")
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("**🏆 Maior OF**")
        df_max = _safe(maior_ordem_fornecimento, df)
        if isinstance(df_max, pd.DataFrame) and not df_max.empty:
            df_max = _round_cols(df_max, ["VALOR_TOTAL", "ITEM_PRCUNTPED", "PRCTTL_INSUMO", "TOTAL"])
            st.dataframe(
                df_max,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "VALOR_TOTAL": st.column_config.NumberColumn("VALOR_TOTAL", format="%.2f"),
                    "ITEM_PRCUNTPED": st.column_config.NumberColumn("ITEM_PRCUNTPED", format="%.2f"),
                    "PRCTTL_INSUMO": st.column_config.NumberColumn("PRCTTL_INSUMO", format="%.2f"),
                    "TOTAL": st.column_config.NumberColumn("TOTAL", format="%.2f"),
                },
            )
        else:
            st.info("Sem dados para exibir.")

    with c2:
        st.markdown("**🧩 Menor OF**")
        df_min = _safe(menor_ordem_fornecimento, df)
        if isinstance(df_min, pd.DataFrame) and not df_min.empty:
            df_min = _round_cols(df_min, ["VALOR_TOTAL", "ITEM_PRCUNTPED", "PRCTTL_INSUMO", "TOTAL"])
            st.dataframe(
                df_min,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "VALOR_TOTAL": st.column_config.NumberColumn("VALOR_TOTAL", format="%.2f"),
                    "ITEM_PRCUNTPED": st.column_config.NumberColumn("ITEM_PRCUNTPED", format="%.2f"),
                    "PRCTTL_INSUMO": st.column_config.NumberColumn("PRCTTL_INSUMO", format="%.2f"),
                    "TOTAL": st.column_config.NumberColumn("TOTAL", format="%.2f"),
                },
            )
        else:
            st.info("Sem dados para exibir.")

# ---------- Volumes por período ----------
with st.container(border=True):
    st.subheader("📈 Volumes por período")

    st.markdown("**Bimestre com maior volume (padrão: últimos 10 anos)**")
    df_bi = _safe(periodo_maior_volume_bimestre, df, anos=10)
    if isinstance(df_bi, pd.DataFrame) and not df_bi.empty:
        df_bi = _round_cols(df_bi, ["VALOR_TOTAL"])
        st.dataframe(
            df_bi,
            use_container_width=True,
            hide_index=True,
            column_config={
                "VALOR_TOTAL": st.column_config.NumberColumn("VALOR_TOTAL", format="%.2f"),
                "QTDE_OFS": st.column_config.NumberColumn("QTDE_OFS", format="%.0f"),
            },
        )
    else:
        st.info("Sem dados para exibir.")

    st.markdown("**Mês com maior volume (último ano)**")
    df_mes = _safe(mes_maior_volume_ultimo_ano, df)
    if isinstance(df_mes, pd.DataFrame) and not df_mes.empty:
        df_mes = _round_cols(df_mes, ["VALOR_TOTAL"])
        st.dataframe(
            df_mes,
            use_container_width=True,
            hide_index=True,
            column_config={
                "VALOR_TOTAL": st.column_config.NumberColumn("VALOR_TOTAL", format="%.2f"),
            },
        )
    else:
        st.info("Sem dados para exibir.")

# ---------- Série de Fornecedores Ativos ----------
with st.container(border=True):
    st.subheader("👥 Fornecedores ativos (série anual)")
    try:
        serie, _resumo = serie_fornecedores_ativos_ultimos_anos(df, anos=10)
        if isinstance(serie, pd.DataFrame) and not serie.empty:
            st.dataframe(
                serie,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "FORNECEDORES_ATIVOS": st.column_config.NumberColumn("FORNECEDORES_ATIVOS", format="%.0f")
                },
            )
            st.bar_chart(data=serie, x="ANO", y="FORNECEDORES_ATIVOS", use_container_width=True)
        else:
            st.info("Sem dados para exibir.")
    except Exception as e:
        st.warning(f"Não consegui gerar a série: {e}")

# ---------- Estilo ----------
st.markdown(
    """
<style>
[data-testid="stMetricValue"] { font-size: 1.6rem; }
section.main > div { padding-top: 0.25rem; }
</style>
""",
    unsafe_allow_html=True,
)



