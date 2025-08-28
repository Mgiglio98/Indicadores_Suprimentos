import streamlit as st
import pandas as pd
import altair as alt
from pathlib import Path
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("America/Sao_Paulo")  # fuso BR
except Exception:
    _TZ = None

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
    menor_compra_item_unico,
    valor_medio_por_item,
    itens_da_of,
    categorias_yoy_series,
    categorias_cagr_desde_inicio,
    categoria_top_cagr,
    categorias_crescimento_desde_2015,
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
    """
    Converte colunas numéricas para strings PT-BR:
      - money:    "R$ 1.234,56"
      - ints:     "1.234"
      - pcts:     "12,34%"
      - decimals: "1.234,56" (sem "R$")
    Obs.: usar APENAS em tabelas (st.dataframe). Para gráficos, manter numérico.
    """
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

with st.container(border=True):
    st.subheader("🗓️ Atualização das bases (repositório)")
    st.markdown(f"**Atualizado em:** {info['max_str']}")

    # arquivos esperados (na ordem definida no helper)
    f1, f2 = info["files"][0], info["files"][1]
    c1, c2 = st.columns(2)

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
    k1, k2, k3, k4, k5, k6 = st.columns(6)

    # Valor médio por OF
    vm = _safe(valor_medio_por_of, df)
    media = vm[0] if vm and isinstance(vm, tuple) else 0
    k1.metric("Valor médio por OF", _format_brl(round(media, 2)))

    # % OFs básicas (último ano)
    pct_grp = _safe(percentual_ofs_basicas_ultimo_ano, df)
    pct = pct_grp[0] if pct_grp and isinstance(pct_grp, tuple) else 0.0
    k2.metric("% de OFs BÁSICAS (último ano)", _format_pct_br(pct))

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

    # Ticket médio por ITEM (linha)
    try:
        vm_item = _safe(valor_medio_por_item, df)
        media_item = vm_item[0] if vm_item and isinstance(vm_item, tuple) else 0
        k6.metric("Ticket médio por ITEM", _format_brl(round(media_item, 2)))
    except Exception:
        k6.metric("Ticket médio por ITEM", "—")

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
    st.subheader("📎 OFs destaque")
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
        st.markdown("**🧩 Menor OF**")
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

    with st.container(border=True):
        st.subheader("🧱 Maior compra de um item (única linha)")
        df_itemmax = _safe(maior_compra_item_unico, df)
        if isinstance(df_itemmax, pd.DataFrame) and not df_itemmax.empty:
            df_itemmax_fmt = _fmt_df_brl(
                df_itemmax,
                money=["PRECO_TOTAL"],
                decimals=["QUANTIDADE"]
            )
            st.dataframe(
                df_itemmax_fmt,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "INSUMO_CDG":  st.column_config.TextColumn("CÓDIGO"),
                    "INSUMO_DESC": st.column_config.TextColumn("DESCRIÇÃO DO INSUMO"),
                    "QUANTIDADE":  st.column_config.TextColumn("QTDE"),
                    "PRECO_TOTAL": st.column_config.TextColumn("PREÇO TOTAL"),
                },
            )
        else:
            st.info("Sem dados para exibir.")

    with st.container(border=True):
        st.subheader("🧱 Menor compra de um item (única linha)")
        df_itemmin = _safe(menor_compra_item_unico, df)
        if isinstance(df_itemmin, pd.DataFrame) and not df_itemmin.empty:
            df_itemmin_fmt = _fmt_df_brl(
                df_itemmin,
                money=["PRECO_TOTAL"],
                decimals=["QUANTIDADE"]
            )
            st.dataframe(
                df_itemmin_fmt,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "INSUMO_CDG":  st.column_config.TextColumn("CÓDIGO"),
                    "INSUMO_DESC": st.column_config.TextColumn("DESCRIÇÃO DO INSUMO"),
                    "QUANTIDADE":  st.column_config.TextColumn("QTDE"),
                    "PRECO_TOTAL": st.column_config.TextColumn("PREÇO TOTAL"),
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
        st.markdown("**Top 3 meses (geral)**")
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
    st.subheader("👥 Fornecedores cadastrados por ano")
    try:
        serie_cad = serie_fornecedores_cadastrados_por_ano(df_forn, anos=10)
        if isinstance(serie_cad, pd.DataFrame) and not serie_cad.empty:
            serie_cad_vis = serie_cad.copy()
            serie_cad_vis["ANO_TXT"] = serie_cad_vis["ANO"].astype(str)
            
            chart_cad = (
                alt.Chart(serie_cad_vis)
                .mark_line(point=True)
                .encode(
                    x=alt.X("ANO_TXT:N", title="ANO", axis=alt.Axis(labelAngle=0)),  # horizontal, sem separadores
                    y=alt.Y("FORNECEDORES_CADASTRADOS:Q", title="FORNECEDORES CADASTRADOS"),
                )
                .properties(height=300)
            )
            st.altair_chart(chart_cad, use_container_width=True)
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

        serie_plot_vis = serie_plot.copy()
        serie_plot_vis["ANO_TXT"] = serie_plot_vis["ANO"].astype(str)
        
        chart_ativos = (
            alt.Chart(serie_plot_vis)
            .mark_bar()
            .encode(
                x=alt.X("ANO_TXT:N", title="ANO", axis=alt.Axis(labelAngle=0)),
                y=alt.Y("FORNECEDORES_ATIVOS:Q", title="FORNECEDORES ATIVOS"),
                tooltip=["ANO_TXT", "FORNECEDORES_ATIVOS"]
            )
            .properties(height=300)
        )
        st.altair_chart(chart_ativos, use_container_width=True)

        st.caption(
            f"Variação {resumo['primeiro_ano']} → {resumo['ultimo_ano']}: "
            f"{resumo['var_abs']} fornecedores ({resumo['var_pct']:.2f}%)."
        )
    else:
        st.info("Sem dados para exibir nos últimos 10 anos.")

# ---------- Série de Categorias ----------
with st.container(border=True):
    st.subheader("📦 Categorias de materiais")

    # --- Mais compradas (últimos 5 anos) — gráfico único, largura total ---
    st.markdown("**Mais compradas (últimos 5 anos)**")
    df_cat5 = _safe(categorias_mais_compradas_ultimos_anos, df, anos=5)
    if isinstance(df_cat5, pd.DataFrame) and not df_cat5.empty:
        df_cat5 = df_cat5.copy()
        df_cat5["VALOR_TOTAL"] = pd.to_numeric(df_cat5["VALOR_TOTAL"], errors="coerce")

        # ordena do maior para o menor e limita (ajuste o .head(N) se quiser mostrar mais/menos)
        toplot = df_cat5.sort_values("VALOR_TOTAL", ascending=False).head(8)

        # altura maior para caber rótulos completos
        _altura = max(360, 36 * len(toplot))
        chart_cat = (
            alt.Chart(toplot)
            .mark_bar()
            .encode(
                y=alt.Y(
                    "CATEGORIA:N",
                    title="CATEGORIA",
                    sort=alt.SortField(field="VALOR_TOTAL", order="descending"),
                    axis=alt.Axis(labelAngle=0, labelLimit=0, labelPadding=6),  # nomes completos
                ),
                x=alt.X("VALOR_TOTAL:Q", title="VALOR TOTAL"),
                tooltip=["CATEGORIA", "VALOR_TOTAL", "PART_%"],
            )
            .properties(height=_altura)
        )
        st.altair_chart(chart_cat, use_container_width=True)

        # caption do Top
        top = toplot.iloc[0]
        st.caption(
            f"Top: **{top['CATEGORIA']}** — {_format_brl(top['VALOR_TOTAL'])} ({float(top['PART_%']):.2f}%)"
        )
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
            require_continuous_last_n=5,   # <<< aqui está o filtro
        )
    
        if isinstance(res_g, pd.DataFrame) and not res_g.empty:
            # opcional: excluir categorias específicas
            res_g = res_g[res_g["CATEGORIA"].astype(str).str.upper() != "DESPESAS OPERACIONAIS"]
    
        if isinstance(res_g, pd.DataFrame) and not res_g.empty:
            topg = res_g.iloc[0]
            st.caption(
                "Maior crescimento desde 2015 (apenas categorias com vendas em todos os últimos 5 anos): "
                f"**{topg['CATEGORIA']}** — {float(topg['CRESC_AA_%']):.2f}% a.a. "
                f"({int(topg['ANO_INICIO'])}→{int(topg['ANO_FIM'])}, método: {topg['METODO']})."
            )
        else:
            st.caption("Nenhuma categoria atende ao critério: vendas em TODOS os últimos 5 anos + base suficiente para cálculo.")
    except Exception as e:
        st.caption(f"Não foi possível calcular o crescimento desde 2015: {e}")
        
with st.container(border=True):
    st.subheader("🧱 Materiais BÁSICOS — cobertura de cadastro por local")

    # 1) Categorias dos básicos observadas no ERP
    with st.expander("Categorias dos materiais básicos (observadas no ERP)"):
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
