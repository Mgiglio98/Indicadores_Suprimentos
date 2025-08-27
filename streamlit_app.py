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
    mes_maior_volume_geral,
    meses_top3_volume_geral,
    maior_compra_item_unico,
    categorias_mais_compradas_ultimos_anos,
    categorias_crescimento_yoy,
    categorias_basicos_distintos,
    fornecedores_basicos_por_local_cadastro,
)

from fornecedores_core import (
    carregar_fornecedores,
    total_empresas_cadastradas,
    serie_fornecedores_ativos_ultimos_anos,
    serie_fornecedores_cadastrados_por_ano,
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
    
def _format_int_br(n) -> str:
    try:
        return f"{int(n):,}".replace(",", ".")
    except Exception:
        return "0"

def _fill_last_n_years(df: pd.DataFrame, year_col: str = "ANO", y_col: str = "FORNECEDORES_ATIVOS", n: int = 10) -> pd.DataFrame:
    anos = list(range(pd.Timestamp.today().year - n + 1, pd.Timestamp.today().year + 1))
    base = pd.DataFrame({year_col: anos})
    out = base.merge(df[[year_col, y_col]], on=year_col, how="left")
    out[y_col] = pd.to_numeric(out[y_col], errors="coerce").fillna(0).astype(int)
    return out

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

    # Valor médio por OF
    vm = _safe(valor_medio_por_of, df)
    media = vm[0] if vm and isinstance(vm, tuple) else 0
    k1.metric("Valor médio por OF", _format_brl(round(media, 2)))

    # % OFs básicas (último ano)
    pct_grp = _safe(percentual_ofs_basicas_ultimo_ano, df)
    pct = pct_grp[0] if pct_grp and isinstance(pct_grp, tuple) else 0.0
    k2.metric("% de OFs BÁSICAS (último ano)", f"{pct:.2f}%")

    # Fornecedores cadastrados (base de cadastro)
    try:
        total_cad = total_empresas_cadastradas(df_forn)
        k3.metric("Fornecedores cadastrados", f"{total_cad}")
    except Exception as e:
        k3.metric("Fornecedores cadastrados", "—")
        st.caption(f"Diagnóstico: {e}")

    # NOVO KPI: Empresas que venderam (últimos 3 anos)
    qtd_vend = _safe(quantidade_empresas_que_venderam_ultimos_3_anos, df)
    qtd_vend = qtd_vend if isinstance(qtd_vend, (int, float)) else 0
    k4.metric("Empresas que venderam (últimos 3 anos)", _format_int_br(qtd_vend))

    # Cadastrados no último ano
    try:
        cad_serie = serie_fornecedores_cadastrados_por_ano(df_forn, anos=1)
        cad_no_ano = int(cad_serie["FORNECEDORES_CADASTRADOS"].sum()) if not cad_serie.empty else 0
        k5.metric("Cadastrados no último ano", f"{cad_no_ano}")
    except Exception:
        pass
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

    with st.container(border=True):
        st.subheader("🧱 Maior compra de um item (única linha)")
        df_itemmax = _safe(maior_compra_item_unico, df)
        if isinstance(df_itemmax, pd.DataFrame) and not df_itemmax.empty:
            st.dataframe(
                df_itemmax,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "INSUMO_CDG":  st.column_config.TextColumn("CÓDIGO"),
                    "INSUMO_DESC": st.column_config.TextColumn("DESCRIÇÃO DO INSUMO"),
                    "QUANTIDADE":  st.column_config.NumberColumn("QTDE", format="%.2f"),
                    "PRECO_TOTAL": st.column_config.NumberColumn("PREÇO TOTAL", format="%.2f"),
                },
            )
        else:
            st.info("Sem dados para exibir.")

# ---------- Volumes por período ----------
with st.container(border=True):
    st.subheader("📈 Volumes por período")

    c1, c2 = st.columns(2)

    # Top 3 meses (últimos 12 meses)
    with c1:
        st.markdown("**Top 3 meses (últimos 12 meses)**")
        df_mes_12 = _safe(mes_maior_volume_ultimo_ano, df, top_n=3)
        if isinstance(df_mes_12, pd.DataFrame) and not df_mes_12.empty:
            df_mes_12 = _round_cols(df_mes_12, ["VALOR_TOTAL", "PART_%"])
            st.dataframe(
                df_mes_12,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "VALOR_TOTAL": st.column_config.NumberColumn("VALOR_TOTAL", format="%.2f"),
                    "PART_%":      st.column_config.NumberColumn("PART_%",      format="%.2f"),
                },
            )
        else:
            st.info("Sem dados para exibir.")

    # Top 3 meses (geral, agregando todos os anos por mês-do-ano)
    with c2:
        st.markdown("**Top 3 meses (geral)**")
        df_mes_all = _safe(meses_top3_volume_geral, df, top_n=3)
        if isinstance(df_mes_all, pd.DataFrame) and not df_mes_all.empty:
            df_mes_all = _round_cols(df_mes_all, ["VALOR_TOTAL", "PART_%"])
            st.dataframe(
                df_mes_all,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "MES_ROTULO":  st.column_config.TextColumn("MÊS"),
                    "VALOR_TOTAL": st.column_config.NumberColumn("VALOR_TOTAL", format="%.2f"),
                    "PART_%":      st.column_config.NumberColumn("PART_%",      format="%.2f"),
                },
            )
        else:
            st.info("Sem dados para exibir.")

# ---------- Série de Fornecedores Ativos ----------
with st.container(border=True):
    st.subheader("👥 Fornecedores cadastrados por ano")
    try:
        serie_cad = serie_fornecedores_cadastrados_por_ano(df_forn, anos=10)
        if isinstance(serie_cad, pd.DataFrame) and not serie_cad.empty:
            st.line_chart(
                data=serie_cad,
                x="ANO",
                y="FORNECEDORES_CADASTRADOS",
                use_container_width=True,
            )
        else:
            st.info("Sem dados para exibir.")
    except Exception as e:
        st.warning(f"Não consegui gerar a série: {e}")

with st.container(border=True):
    st.subheader("📊 Fornecedores ativos por ano (últimos 10 anos)")

    serie, resumo = serie_fornecedores_ativos_ultimos_anos(df, anos=10)
    if isinstance(serie, pd.DataFrame) and not serie.empty:
        # garante anos contínuos (0 quando não teve fornecedor ativo)
        serie_plot = _fill_last_n_years(serie, year_col="ANO", y_col="FORNECEDORES_ATIVOS", n=10)

        st.bar_chart(
            data=serie_plot,
            x="ANO",
            y="FORNECEDORES_ATIVOS",
            use_container_width=True,
        )

        st.caption(
            f"Variação {resumo['primeiro_ano']} → {resumo['ultimo_ano']}: "
            f"{resumo['var_abs']} fornecedores ({resumo['var_pct']:.2f}%)."
        )
    else:
        st.info("Sem dados para exibir nos últimos 10 anos.")

# ---------- Série de Categorias ----------
with st.container(border=True):
    st.subheader("📦 Categorias de materiais")

    c1, c2 = st.columns(2)

    # Top categorias (últimos 5 anos)
    with c1:
        st.markdown("**Mais compradas (últimos 5 anos)**")
        df_cat5 = _safe(categorias_mais_compradas_ultimos_anos, df, anos=5)
        if isinstance(df_cat5, pd.DataFrame) and not df_cat5.empty:
            # exibe top 8 para não poluir
            toplot = df_cat5.head(8).copy()
            st.bar_chart(data=toplot, x="CATEGORIA", y="VALOR_TOTAL", use_container_width=True)
            top = df_cat5.iloc[0]
            st.caption(f"Top: **{top['CATEGORIA']}** — {_format_brl(top['VALOR_TOTAL'])} ({top['PART_%']:.2f}%)")
        else:
            st.info("Sem dados para exibir.")

    # Maior crescimento YoY (média) por categoria (últimos 5 anos)
    with c2:
        st.markdown("**Maior crescimento YoY (média, últimos 5 anos)**")
        df_yoy = _safe(categorias_crescimento_yoy, df, anos=5)
        if isinstance(df_yoy, pd.DataFrame) and not df_yoy.empty:
            toplot = df_yoy.head(8).copy()
            st.bar_chart(data=toplot, x="CATEGORIA", y="MEDIA_YOY_PCT", use_container_width=True)
            topg = df_yoy.iloc[0]
            st.caption(
                f"Top crescimento: **{topg['CATEGORIA']}** — {topg['MEDIA_YOY_PCT']:.2f}% a.a. "
                f"(último YoY: {topg['ULTIMO_YOY_PCT']:.2f}%; período {int(topg['PRIMEIRO_ANO'])}–{int(topg['ULTIMO_ANO'])})"
            )
        else:
            st.info("Sem dados para exibir.")

with st.container(border=True):
    st.subheader("🧱 Materiais BÁSICOS — cobertura de cadastro por local")

    # 1) Categorias dos básicos observadas no ERP
    st.markdown("**Categorias dos materiais básicos (observadas no ERP):**")
    df_cats = categorias_basicos_distintos(df)
    if isinstance(df_cats, pd.DataFrame) and not df_cats.empty:
        st.dataframe(df_cats, use_container_width=True, hide_index=True)
    else:
        st.info("Não encontrei categorias para TIPO_MATERIAL = 'BÁSICO'.")

    # 2) & 3) Fornecedores CADASTRADOS aptos a vender básico por local (UF)
    st.markdown("**Fornecedores cadastrados aptos (básico) por local**")
    df_res = fornecedores_basicos_por_local_cadastro(df_forn, df, locais=("RJ","SP","SC"))

    if isinstance(df_res, pd.DataFrame) and not df_res.empty:
        # normaliza chave para evitar case/acentos
        df_res = df_res.copy()
        df_res["LOCAL_NORM"] = df_res["LOCAL"].astype(str).str.upper()
        mapa = df_res.set_index("LOCAL_NORM")["FORNECEDORES_BÁSICO_CAD"].to_dict()

        k1, k2, k3 = st.columns(3)
        rj = int(mapa.get("RJ", 0))
        sp = int(mapa.get("SP", 0))
        sc = int(mapa.get("SC", 0))

        _fmt = lambda n: f"{int(n):,}".replace(",", ".")
        k1.metric("RJ — fornecedores básicos (cad.)", _fmt(rj))
        k2.metric("SP — fornecedores básicos (cad.)", _fmt(sp))
        k3.metric("SC — fornecedores básicos (cad.)", _fmt(sc))

        with st.expander("Ver detalhes"):
            st.dataframe(
                df_res[["LOCAL","FORNECEDORES_BÁSICO_CAD"]].sort_values("LOCAL"),
                use_container_width=True, hide_index=True,
                column_config={"FORNECEDORES_BÁSICO_CAD": st.column_config.NumberColumn(format="%.0f")}
            )
    else:
        st.info("Sem dados para compor os contadores por local.")
        
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



