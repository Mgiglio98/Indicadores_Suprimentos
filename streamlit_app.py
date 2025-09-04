import streamlit as st
import pandas as pd
import altair as alt
from pathlib import Path
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("America/Sao_Paulo")
except Exception:
    _TZ = None

from Tratamento_Indicadores import (
    carregar_bases,
    fornecedor_top_por_uf,
    maior_ordem_fornecimento,
    menor_ordem_fornecimento,
    valor_medio_por_of,
    percentual_ofs_basicas_ultimo_ano,
    mes_maior_volume_ultimo_ano,
    _format_brl,
    quantidade_empresas_que_venderam_ultimos_3_anos,
    meses_top3_volume_geral,
    maior_compra_item_unico,
    menor_compra_item_unico,
    valor_medio_por_item,
    categorias_mais_compradas_ultimos_anos,
    categorias_basicos_distintos,
    fornecedores_basicos_por_local_cadastro,
    itens_da_of,
    categorias_com_venda_continua_ultimos_anos,
    categorias_crescimento_desde_2015,
    compras_atrasadas,
    tempo_medio_geracao_of,
    tempos_medios_12m_5a,
)

from fornecedores_core import (
    carregar_fornecedores,
    total_empresas_cadastradas,
    serie_fornecedores_ativos_ultimos_anos,
    serie_fornecedores_cadastrados_por_ano,
)

st.set_page_config(page_title="Suprimentos • Indicadores & Fornecedores", layout="wide")
# ===== Topo com título à esquerda e logo à direita =====
from pathlib import Path

col1, col2 = st.columns([6,1], vertical_alignment="center")

with col1:
    st.title("Suprimentos • Indicadores e Fornecedores")

with col2:
    logo_path = Path(__file__).parent / "logo.png"
    if logo_path.exists():
        st.image(str(logo_path), use_container_width=True)

# ---------- Helpers ----------
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

def _format_pct_br(x) -> str:
    try:
        return f"{float(x):.2f}%".replace(".", ",")
    except Exception:
        return "0,00%"

def _fmt_df_brl(df: pd.DataFrame,
                money: list[str] | None = None,
                ints: list[str] | None = None,
                pcts: list[str] | None = None,
                decimals: list[str] | None = None) -> pd.DataFrame:
    out = df.copy()
    # Moeda
    if money:
        for c in money:
            if c in out.columns:
                out[c] = pd.to_numeric(out[c], errors="coerce").map(lambda v: _format_brl(v) if pd.notna(v) else "—")
    # Inteiros
    if ints:
        for c in ints:
            if c in out.columns:
                s = pd.to_numeric(out[c], errors="coerce").fillna(0)
                out[c] = s.astype(int).map(lambda n: f"{n:,}".replace(",", "."))
    # Percentuais
    if pcts:
        for c in pcts:
            if c in out.columns:
                out[c] = pd.to_numeric(out[c], errors="coerce").map(lambda v: _format_pct_br(v) if pd.notna(v) else "—")
    # Decimais gerais
    if decimals:
        for c in decimals:
            if c in out.columns:
                out[c] = pd.to_numeric(out[c], errors="coerce").map(
                    lambda v: f"{v:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".") if pd.notna(v) else "—"
                )
    return out

def _fill_last_n_years(df: pd.DataFrame, year_col: str = "ANO", y_col: str = "FORNECEDORES_ATIVOS", n: int = 10) -> pd.DataFrame:
    anos = list(range(pd.Timestamp.today().year - n + 1, pd.Timestamp.today().year + 1))
    base = pd.DataFrame({year_col: anos})
    out = base.merge(df[[year_col, y_col]], on=year_col, how="left")
    out[y_col] = pd.to_numeric(out[y_col], errors="coerce").fillna(0).astype(int)
    return out

def _fmt_dt_br(ts: float) -> str:
    try:
        dt = datetime.fromtimestamp(ts, tz=_TZ) if _TZ else datetime.fromtimestamp(ts)
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return "—"

@st.cache_data(ttl=300, show_spinner=False)
def _repo_files_info():
    base_dir = Path(__file__).parent
    files = [
        {"name": "total_indicadores.xlsx",  "path": base_dir / "total_indicadores.xlsx"},
        {"name": "FornecedoresAtivos.xlsx", "path": base_dir / "FornecedoresAtivos.xlsx"},
    ]
    out, mx = [], 0.0
    for f in files:
        p = f["path"]
        if p.exists():
            ts = p.stat().st_mtime
            mx = max(mx, ts)
            out.append({
                "name": f["name"],
                "path": str(p),
                "mtime": ts,
                "mtime_str": _fmt_dt_br(ts),
                "size": p.stat().st_size,
                "found": True,
            })
        else:
            out.append({
                "name": f["name"], "path": str(p), "mtime": None,
                "mtime_str": "—", "size": 0, "found": False
            })
    return {"files": out, "max_ts": mx, "max_str": _fmt_dt_br(mx) if mx else "—"}

@st.cache_data(ttl=3600, show_spinner=False)
def _read_file_bytes(path: str):
    try:
        return Path(path).read_bytes()
    except Exception:
        return None

@st.cache_data(ttl=3600, show_spinner=False)
def _load_df_erp():
    return carregar_bases()

@st.cache_data(ttl=3600, show_spinner=False)
def _load_df_forn():
    return carregar_fornecedores()

df_erp = _load_df_erp()
df_forn = _load_df_forn()
df = df_erp.copy()

# ——— Bases (carimbo + downloads em um único container) ———
info = _repo_files_info()

with st.container(border=False):
    st.subheader("🗓️ Atualização do Painel")
    st.markdown(f"**Atualizado em:** {info['max_str']}")

    f1, f2 = info["files"][0], info["files"][1]
    c1, c2, c3 = st.columns([1,1,4])  # espaço só no começo

    with c1:
        data1 = _read_file_bytes(f1["path"]) if f1["found"] else None
        st.download_button(
            "Baixar total_indicadores.xlsx",
            data=data1 if data1 is not None else b"",
            file_name="total_indicadores.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            disabled=(data1 is None),
        )
    
    with c2:
        data2 = _read_file_bytes(f2["path"]) if f2["found"] else None
        st.download_button(
            "Baixar FornecedoresAtivos.xlsx",
            data=data2 if data2 is not None else b"",
            file_name="FornecedoresAtivos.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            disabled=(data2 is None),
        )

# ---------- KPIs ----------
with st.container(border=True):
    st.subheader("📊 Resumo")

    # --------- Cálculos prévios (com fallback) ---------
    # Valor médio por OF
    try:
        vm = valor_medio_por_of(df)
        media_of = vm[0] if isinstance(vm, tuple) else 0
    except Exception:
        media_of = None

    # % OFs básicas (último ano)
    try:
        pct_grp = percentual_ofs_basicas_ultimo_ano(df)
        pct_bas = pct_grp[0] if isinstance(pct_grp, tuple) else 0.0
    except Exception:
        pct_bas = None

    # Fornecedores cadastrados (base de cadastro)
    try:
        total_cad = total_empresas_cadastradas(df_forn)
    except Exception:
        total_cad = None

    # Empresas que venderam (últimos 3 anos)
    try:
        qtd_vend = quantidade_empresas_que_venderam_ultimos_3_anos(df)
    except Exception:
        qtd_vend = None

    # Cadastrados no último ano
    try:
        cad_serie = serie_fornecedores_cadastrados_por_ano(df_forn, anos=1)
        cad_no_ano = int(cad_serie["FORNECEDORES_CADASTRADOS"].sum()) if not cad_serie.empty else 0
    except Exception:
        cad_no_ano = None

    # Ticket médio por ITEM (linha)
    try:
        vm_item = valor_medio_por_item(df)
        media_item = vm_item[0] if isinstance(vm_item, tuple) else 0
    except Exception:
        media_item = None

    # Compras com atraso (12m)
    df_atrasos = pd.DataFrame()
    try:
        taxa_atraso_pct, qtd_atrasadas, total_compras, df_atrasos = compras_atrasadas(
            df, dias_uteis_sla=3, meses_lookback=12
        )
    except Exception:
        taxa_atraso_pct = None

    # Tempos médios (12m e 5a, em dias úteis)
    try:
        m12, m5a = tempos_medios_12m_5a(df, considerar_dias_uteis=True)
    except Exception:
        m12, m5a = None, None

   # Linha 1 centralizada (5 KPIs)
    spacer1, r1c1, r1c2, r1c3, r1c4, r1c5, spacer2 = st.columns([1, 2, 2, 2, 2, 2, 1])
    
    r1c1.metric("Valor médio por OF", _format_brl(round(media_of, 2)) if media_of is not None else "—")
    r1c2.metric("% de OFs Básicas no último ano", _format_pct_br(pct_bas) if pct_bas is not None else "—")
    r1c3.metric("Fornecedores cadastrados", f"{total_cad}" if total_cad is not None else "—")
    r1c4.metric("Fornecedores nos últimos 3 anos", _format_int_br(qtd_vend) if qtd_vend is not None else "—")
    r1c5.metric("Cadastrados no último ano", f"{cad_no_ano}" if cad_no_ano is not None else "—")

    # Linha 2 centralizada (4 KPIs)
    spacer1, r2c1, r2c2, r2c3, r2c4, spacer2 = st.columns([1, 2, 2, 2, 2, 1])
    
    r2c1.metric("Valor médio por Insumo", _format_brl(round(media_item, 2)) if media_item is not None else "—")
    r2c2.metric("Compras com atraso (12m)", _format_pct_br(taxa_atraso_pct) if taxa_atraso_pct is not None else "—")
    r2c3.metric("Tempo médio p/ gerar OF (12m, úteis)", (f"{float(m12):.2f} dias".replace(".", ",")) if m12 is not None else "—")
    r2c4.metric("Tempo médio p/ gerar OF (5 anos, úteis)", (f"{float(m5a):.2f} dias".replace(".", ",")) if m5a is not None else "—")

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
            df_top10 = _round_cols(df_top10, ["VALOR"])  # mantém numérico p/ uso futuro
            df_top10_fmt = _fmt_df_brl(df_top10, money=["VALOR"])
        
            st.dataframe(
                df_top10_fmt,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "VALOR": st.column_config.TextColumn("VALOR"),
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
            df_top2_fmt = _fmt_df_brl(df_top2, money=["VALOR"])
        
            st.dataframe(
                df_top2_fmt,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "VALOR": st.column_config.TextColumn("VALOR"),
                    "FORNECEDOR_CDG": st.column_config.TextColumn("FORNECEDOR_CDG"),
                },
            )
        else:
            st.info("Sem dados para exibir.")

# ---------- OFs destaque ----------
with st.container(border=True):
    st.subheader("🛒 Principais Vendas")
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("**🏆 Maior OF**")
        df_max = _safe(maior_ordem_fornecimento, df)
        if isinstance(df_max, pd.DataFrame) and not df_max.empty:
            df_max = _round_cols(df_max, ["VALOR_TOTAL", "ITEM_PRCUNTPED", "PRCTTL_INSUMO", "TOTAL"])
            df_max_fmt = _fmt_df_brl(
                df_max,
                money=["VALOR_TOTAL", "ITEM_PRCUNTPED", "PRCTTL_INSUMO", "TOTAL"],
                ints=["TOTAL_ITENS"] if "TOTAL_ITENS" in df_max.columns else None
            )
            st.dataframe(
                df_max_fmt,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "VALOR_TOTAL":     st.column_config.TextColumn("VALOR_TOTAL"),
                    "ITEM_PRCUNTPED":  st.column_config.TextColumn("ITEM_PRCUNTPED"),
                    "PRCTTL_INSUMO":   st.column_config.TextColumn("PRCTTL_INSUMO"),
                    "TOTAL":           st.column_config.TextColumn("TOTAL"),
                    "TOTAL_ITENS":     st.column_config.TextColumn("TOTAL_ITENS") if "TOTAL_ITENS" in df_max.columns else None,
                },
            )
        else:
            st.info("Sem dados para exibir.")
        try:
            if isinstance(df_max, pd.DataFrame) and not df_max.empty and "OF_CDG" in df_max.columns:
                of_alvo = df_max.iloc[0]["OF_CDG"]
                with st.expander("Ver itens da OF (Top 5)"):
                    mostrar_todos = st.checkbox("Mostrar todos os itens", key="itens_maior_of_all", value=False)
                    top_n = None if mostrar_todos else 5
                    df_itens = itens_da_of(df, of_cdg=of_alvo, top_n=top_n)
        
                    if isinstance(df_itens, pd.DataFrame) and not df_itens.empty:
                        st.dataframe(
                            df_itens,
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "INSUMO_CDG":  st.column_config.TextColumn("CÓDIGO"),
                                "INSUMO_DESC": st.column_config.TextColumn("DESCRIÇÃO DO INSUMO"),
                                "QUANTIDADE":  st.column_config.NumberColumn("QTDE", format="%.2f"),
                                "PRECO_UNIT":  st.column_config.NumberColumn("PREÇO UNIT.", format="%.2f"),
                                "PRECO_TOTAL": st.column_config.NumberColumn("PREÇO TOTAL", format="%.2f"),
                            },
                        )
                    else:
                        st.caption("Sem itens para exibir.")
        except Exception as e:
            st.caption(f"Não consegui listar os itens da OF: {e}")

    with c2:
        st.markdown("**📉 Menor OF**")
        df_min = _safe(menor_ordem_fornecimento, df)
        if isinstance(df_min, pd.DataFrame) and not df_min.empty:
            df_min = _round_cols(df_min, ["VALOR_TOTAL", "ITEM_PRCUNTPED", "PRCTTL_INSUMO", "TOTAL"])
            df_min_fmt = _fmt_df_brl(
                df_min,
                money=["VALOR_TOTAL", "ITEM_PRCUNTPED", "PRCTTL_INSUMO", "TOTAL"],
                ints=["TOTAL_ITENS"] if "TOTAL_ITENS" in df_min.columns else None
            )
            st.dataframe(
                df_min_fmt,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "VALOR_TOTAL":     st.column_config.TextColumn("VALOR_TOTAL"),
                    "ITEM_PRCUNTPED":  st.column_config.TextColumn("ITEM_PRCUNTPED"),
                    "PRCTTL_INSUMO":   st.column_config.TextColumn("PRCTTL_INSUMO"),
                    "TOTAL":           st.column_config.TextColumn("TOTAL"),
                    "TOTAL_ITENS":     st.column_config.TextColumn("TOTAL_ITENS") if "TOTAL_ITENS" in df_min.columns else None,
                },
            )
        else:
            st.info("Sem dados para exibir.")
        # Expander: itens da Menor OF
        try:
            if isinstance(df_min, pd.DataFrame) and not df_min.empty and "OF_CDG" in df_min.columns:
                of_alvo = df_min.iloc[0]["OF_CDG"]
                with st.expander("Ver itens da OF (Top 5)"):
                    mostrar_todos = st.checkbox("Mostrar todos os itens", key="itens_menor_of_all", value=False)
                    top_n = None if mostrar_todos else 5
                    df_itens = itens_da_of(df, of_cdg=of_alvo, top_n=top_n)
        
                    if isinstance(df_itens, pd.DataFrame) and not df_itens.empty:
                        st.dataframe(
                            df_itens,
                            use_container_width=True,
                            hide_index=True,
                            column_config={
                                "INSUMO_CDG":  st.column_config.TextColumn("CÓDIGO"),
                                "INSUMO_DESC": st.column_config.TextColumn("DESCRIÇÃO DO INSUMO"),
                                "QUANTIDADE":  st.column_config.NumberColumn("QTDE", format="%.2f"),
                                "PRECO_UNIT":  st.column_config.NumberColumn("PREÇO UNIT.", format="%.2f"),
                                "PRECO_TOTAL": st.column_config.NumberColumn("PREÇO TOTAL", format="%.2f"),
                            },
                        )
                    else:
                        st.caption("Sem itens para exibir.")
        except Exception as e:
            st.caption(f"Não consegui listar os itens da OF: {e}")

    c3, c4 = st.columns(2)

    with c3:
        st.markdown("**🧱 Maior compra de um item**")   # fonte menor que subheader, igual ao "Maior OF"
        df_itemmax = _safe(maior_compra_item_unico, df)
        if isinstance(df_itemmax, pd.DataFrame) and not df_itemmax.empty:
            df_itemmax_fmt = _fmt_df_brl(df_itemmax, money=["PRECO_TOTAL"], decimals=["QUANTIDADE"])
            st.dataframe(df_itemmax_fmt, use_container_width=True, hide_index=True)
        else:
            st.info("Sem dados para exibir.")

    with c4:
        st.markdown("**🧱 Menor compra de um item**")
        df_itemmin = _safe(menor_compra_item_unico, df)
        if isinstance(df_itemmin, pd.DataFrame) and not df_itemmin.empty:
            df_itemmin_fmt = _fmt_df_brl(df_itemmin, money=["PRECO_TOTAL"], decimals=["QUANTIDADE"])
            st.dataframe(df_itemmin_fmt, use_container_width=True, hide_index=True)
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
            df_mes_12["ANO_MES"] = df_mes_12["ANO_MES"].astype(str)
            df_mes_12_fmt = _fmt_df_brl(df_mes_12, money=["VALOR_TOTAL"], pcts=["PART_%"])
            st.dataframe(
                df_mes_12_fmt,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "ANO_MES":     st.column_config.TextColumn("ANO/MÊS"),
                    "VALOR_TOTAL": st.column_config.TextColumn("VALOR_TOTAL"),
                    "PART_%":      st.column_config.TextColumn("PART_%"),
                },
            )
        else:
            st.info("Sem dados para exibir.")
            
    # Top 3 meses (geral, agregando todos os anos por mês-do-ano)
    with c2:
        st.markdown("**Top 3 meses (últimos 10 anos)**")
        df_mes_all = _safe(meses_top3_volume_geral, df, top_n=3)
        if isinstance(df_mes_all, pd.DataFrame) and not df_mes_all.empty:
            df_mes_all = _round_cols(df_mes_all, ["VALOR_TOTAL", "PART_%"])
            df_mes_all_fmt = _fmt_df_brl(df_mes_all, money=["VALOR_TOTAL"], pcts=["PART_%"])
            st.dataframe(
                df_mes_all_fmt,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "MES_ROTULO":  st.column_config.TextColumn("MÊS"),
                    "VALOR_TOTAL": st.column_config.TextColumn("VALOR_TOTAL"),
                    "PART_%":      st.column_config.TextColumn("PART_%"),
                },
            )
        else:
            st.info("Sem dados para exibir.")

# ---------- Série de Fornecedores Ativos ----------
with st.container(border=True):
    st.subheader("📊 Fornecedores ativos por ano")

    serie, resumo = serie_fornecedores_ativos_ultimos_anos(df, anos=10)
    if isinstance(serie, pd.DataFrame) and not serie.empty:
        serie_plot = _fill_last_n_years(serie, year_col="ANO", y_col="FORNECEDORES_ATIVOS", n=10)
        serie_plot_vis = serie_plot.copy()
        serie_plot_vis["ANO_TXT"] = serie_plot_vis["ANO"].astype(str)
        # rótulo BR
        serie_plot_vis["FORNECEDORES_ATIVOS_TXT"] = serie_plot_vis["FORNECEDORES_ATIVOS"].map(_format_int_br)
    
        bars = (
            alt.Chart(serie_plot_vis)
            .mark_bar()
            .encode(
                x=alt.X("ANO_TXT:N", title="ANO", axis=alt.Axis(labelAngle=0)),
                y=alt.Y("FORNECEDORES_ATIVOS:Q", title=None, axis=None),   # << remove eixo de valores
                tooltip=["ANO_TXT", "FORNECEDORES_ATIVOS"]
            )
            .properties(height=300)
        )
    
        labels = (
            alt.Chart(serie_plot_vis)
            .mark_text(dy=-5)  # acima da barra
            .encode(
                x="ANO_TXT:N",
                y="FORNECEDORES_ATIVOS:Q",
                text="FORNECEDORES_ATIVOS_TXT:N"
            )
        )
    
        chart_ativos = bars + labels
        st.altair_chart(chart_ativos, use_container_width=True)
    else:
        st.info("Sem dados para exibir nos últimos 10 anos.")

# ---------- Série de Categorias ----------
with st.container(border=True):
    st.subheader("📦 Volume por Categoria")

    st.markdown("**Mais compradas (últimos 5 anos)**")
    df_cat5 = _safe(categorias_mais_compradas_ultimos_anos, df, anos=5)
    if isinstance(df_cat5, pd.DataFrame) and not df_cat5.empty:
        df_cat5 = df_cat5.copy()
        df_cat5["VALOR_TOTAL"] = pd.to_numeric(df_cat5["VALOR_TOTAL"], errors="coerce")
    
        # ordena e pega top N
        toplot = df_cat5.sort_values("VALOR_TOTAL", ascending=False).head(8).reset_index(drop=True)
    
        # ordem explícita (maior → menor) para o eixo Y
        order_cats = toplot["CATEGORIA"].tolist()
    
        # rótulos em BRL
        toplot["VALOR_TOTAL_TXT"] = toplot["VALOR_TOTAL"].map(_format_brl)
    
        _altura = max(360, 36 * len(toplot))
    
        base = (
            alt.Chart(toplot)
            .encode(
                y=alt.Y(
                    "CATEGORIA:N",
                    sort=order_cats,                         # << força a ordem desejada
                    title="CATEGORIA",
                    axis=alt.Axis(labelAngle=0, labelLimit=0, labelPadding=6),
                ),
                x=alt.X("VALOR_TOTAL:Q", title=None, axis=None),
                tooltip=["CATEGORIA", "VALOR_TOTAL", "PART_%"],
            )
            .properties(height=_altura)
        )
    
        bars = base.mark_bar()
        labels = base.mark_text(align="left", dx=5).encode(text="VALOR_TOTAL_TXT:N")
    
        st.altair_chart(bars + labels, use_container_width=True)
    
        top = toplot.iloc[0]
        st.caption(f"Top: **{top['CATEGORIA']}** — {_format_brl(top['VALOR_TOTAL'])} ({float(top['PART_%']):.2f}%)")
    else:
        st.info("Sem dados para exibir.")

    # Maior crescimento desde 2015 (fixo 2015 → último ano, apenas categorias com vendas nos últimos 5 anos)
    try:
        col_cat_ref = "INSUMO_CATEGORIA_NORM" if "INSUMO_CATEGORIA_NORM" in df.columns else "INSUMO_CATEGORIA"
        res_g = categorias_crescimento_desde_2015(
            df,
            start_year=2015,
            col_cat=col_cat_ref,
            min_anos_validos=3,
            clip_pct=500.0,
            require_continuous_last_n=5,
        )
    
        if isinstance(res_g, pd.DataFrame) and not res_g.empty:
            # opcional: excluir categorias específicas
            res_g = res_g[res_g["CATEGORIA"].astype(str).str.upper() != "DESPESAS OPERACIONAIS"]
    
        # ... depois de calcular res_g e aplicar o filtro "DESPESAS OPERACIONAIS"
        if isinstance(res_g, pd.DataFrame) and not res_g.empty:
            top2 = res_g.head(2)
            partes = []
            for _, r in top2.iterrows():
                partes.append(
                    f"**{r['CATEGORIA']}** — {float(r['CRESC_AA_%']):.2f}% a.a. "
                    f"({int(r['ANO_INICIO'])}→{int(r['ANO_FIM'])})"
                )
            st.caption(
                "Categorias com maior crescimento ano a ano: "
                + " | ".join(partes) + "."
            )
        else:
            st.caption("Nenhuma categoria atende ao critério: vendas em TODOS os últimos 5 anos + base suficiente para cálculo.")
    except Exception as e:
        st.caption(f"Não foi possível calcular o crescimento desde 2015: {e}")
        
with st.container(border=True):
    st.subheader("🧱 Materiais Básicos — Fornecimento por local")

    # 1) Categorias dos básicos observadas no ERP
    with st.expander("Categorias dos materiais básicos"):
        df_cats = categorias_basicos_distintos(df)
        if isinstance(df_cats, pd.DataFrame) and not df_cats.empty:
            st.dataframe(df_cats, use_container_width=True, hide_index=True)
        else:
            st.info("Não encontrei categorias para TIPO_MATERIAL = 'BÁSICO'.")

    # 2) & 3) Fornecedores CADASTRADOS aptos a vender básico por local (UF)
    st.markdown("**Fornecedores aptos por UF**")
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
        k1.metric("Fornecedores RJ", _fmt(rj))
        k2.metric("Fornecedores SP", _fmt(sp))
        k3.metric("Fornecedores SC", _fmt(sc))

    else:
        st.info("Sem dados para compor os contadores por local.")

with st.expander("Listar fornecedores aptos por UF"):
    ufs = ["RJ", "SP", "SC"]
    for uf in ufs:
        st.markdown(f"**UF: {uf}**")
        df_list = df_forn[
            (df_forn["FORN_UF"].astype(str).str.upper() == uf)
            & (df_forn["_APTO_BASICO_"] == True)
        ].copy()

        if not df_list.empty:
            cols_to_show = ["FORNECEDOR_CDG", "FORN_FANTASIA", "CATEGORIAS"]  # ajuste conforme nomes reais
            cols_validas = [col for col in cols_to_show if col in df_list.columns]

            st.dataframe(
                df_list[cols_validas].sort_values("FORN_FANTASIA"),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("Nenhum fornecedor apto encontrado para esta UF.")
        
# ---------- Estilo ----------
st.markdown("""
<style>
/* margem menor no topo geral */
section.main > div { padding-top: 0.5rem; }

/* h1 compacto */
h1 { line-height: 1.25; }

/* cards: borda mais suave e menos espaço vertical */
div[data-testid="stMetric"] {
    background: rgba(255,255,255,0.02);
    padding: 0.75rem 0.75rem;
    border-radius: 12px;
}

/* valor do KPI um pouco maior */
[data-testid="stMetricValue"] { font-size: 1.55rem; }

/* subtítulo das seções */
.block-container h3, .block-container h2, .block-container h4 {
    letter-spacing: .2px;
}
</style>
""", unsafe_allow_html=True)
