import streamlit as st
import pandas as pd
import altair as alt
import io
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
    categorias_mais_compradas_ultimos_anos,
    categorias_basicos_distintos,
    fornecedores_basicos_por_local_cadastro,
    itens_da_of,
    categorias_com_venda_continua_ultimos_anos,
    categorias_crescimento_desde_2015,
    compras_atrasadas,
    tempo_medio_geracao_of,
    tempos_medios_12m_5a,
    quantidade_ofs_ate_300_2025_2026,
    total_ofs_por_ano,
    fornecedor_top_por_uf_emp,
    tabela_ofs_atrasadas,
    recorrencia_materiais_basicos_2026,
    itens_basicos_pequenas_qtds_alta_frequencia_2026,
    ofs_basico_vs_nao_ultimos_12m,
    requisicoes_ofs_ultimos_12m,
    media_requisicoes_por_empreendimento_ultimos_12m,
    tempo_medio_req_para_of_ultimos_12m
)

from fornecedores_core import (
    carregar_fornecedores,
    total_empresas_cadastradas,
    serie_fornecedores_ativos_ultimos_anos,
    serie_fornecedores_cadastrados_por_ano,
    carregar_movimentacao,
    resumo_movimentacao_fornecedores
)

from Tratamento_Anomalias import (
    carregar_anomalias, 
    grafico_anomalias_por_mes_com_comentarios
)

st.set_page_config(page_title="Suprimentos • Indicadores & Fornecedores", layout="wide")
# ===== Topo com título à esquerda e logo à direita =====
from pathlib import Path

col1, col2 = st.columns([6,1], vertical_alignment="center")

with col1:
    st.title("Suprimentos • Indicadores e Fornecedores")
    st.caption(
        "Painel consolidado para análise de indicadores, considerando apenas Requisições e OFs Aprovadas"
    )

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
def _load_df_mov():
    """Carrega planilha FornecedoresMovimentacao.xlsx"""
    return carregar_movimentacao()

df_mov = _load_df_mov()

@st.cache_data(ttl=3600, show_spinner=False)
def _load_df_forn():
    return carregar_fornecedores()

df_erp = _load_df_erp()
df_forn = _load_df_forn()
df = df_erp.copy()

# Geração do Excel com KPIs detalhados (Fornecedores Últimos 3 anos + OFs básicas Último ano)
try:
    # 🔄 Igual à função do KPI
    data_limite = pd.Timestamp.today() - pd.DateOffset(years=3)
    df_3anos = df.copy()
    df_3anos["OF_DATA_DT"] = pd.to_datetime(df_3anos.get("OF_DATA"), errors="coerce")
    df_3anos = df_3anos[df_3anos["OF_DATA_DT"] >= data_limite]
    
    # Filtro de valor total > 0, igual no KPI
    if "PRCTTL_INSUMO" in df_3anos.columns:
        v = pd.to_numeric(df_3anos["PRCTTL_INSUMO"], errors="coerce").fillna(0)
        df_3anos = df_3anos[v > 0]
    
    # Coluna de fornecedor com os mesmos critérios
    candidatos = [
        "FORNECEDOR_CDG", "FORNECEDOR_ID", "COD_FORNECEDOR",
        "FORN_CNPJ", "CNPJ", "PED_FORNECEDOR", "FORNECEDOR"
    ]
    col_forn = next((c for c in candidatos if c in df_3anos.columns), None)
    if not col_forn:
        raise KeyError(f"Não encontrei coluna de fornecedor entre: {candidatos}")
    
    # Limpeza dos dados
    df_3anos[col_forn] = (
        df_3anos[col_forn]
        .astype("string")
        .str.strip()
        .replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
    )

    # Deduplicar e manter nome (assumindo "FORNECEDOR_DESC" como nome fantasia)
    df_forn_3anos = (
        df_3anos
        .dropna(subset=[col_forn, "FORNECEDOR_DESC"])
        .drop_duplicates(subset=[col_forn])
        [[col_forn, "FORNECEDOR_DESC"]]
        .rename(columns={col_forn: "FORNECEDOR_CDG"})
        .sort_values("FORNECEDOR_DESC")
    )

    # OFs básicas do Último ano
    _, df_of_basicas = percentual_ofs_basicas_ultimo_ano(df)

    # Gera Excel com as duas abas
    hoje_str = datetime.today().strftime("%Y-%m-%d")
    nome_arquivo_kpi = f"KPIs_Suprimentos_{hoje_str}.xlsx"
    path_kpi = Path(nome_arquivo_kpi)

    with pd.ExcelWriter(path_kpi, engine="openpyxl") as writer:
        df_forn_3anos.to_excel(writer, sheet_name="Fornecedores_3_anos", index=False)
        df_of_basicas.to_excel(writer, sheet_name="OFs_Basicas_12m", index=False)

    # Lê o conteúdo do arquivo para o botão de download
    data_kpi = path_kpi.read_bytes() if path_kpi.exists() else None

except Exception as e:
    data_kpi = None
    st.warning(f"Erro ao gerar o arquivo de KPIs: {e}")

# ——— Bases (carimbo + downloads em um único container) ———
info = _repo_files_info()

with st.container(border=False):

    f1, f2 = info["files"][0], info["files"][1]
    c1, c2, c3 = st.columns([1,1,4])  # espaço só no começo

    with c1:
        data1 = _read_file_bytes(f1["path"]) if f1["found"] else None
        st.download_button(
            "📥 Baixar total_indicadores.xlsx",
            data=data1 if data1 is not None else b"",
            file_name="total_indicadores.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            disabled=(data1 is None),
        )
    
    with c2:
        data2 = _read_file_bytes(f2["path"]) if f2["found"] else None
        st.download_button(
            "📥 Baixar FornecedoresAtivos.xlsx",
            data=data2 if data2 is not None else b"",
            file_name="FornecedoresAtivos.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            disabled=(data2 is None),
        )

    with c3:
        st.download_button(
            "📥 Baixar KPIs de Suprimentos",
            data=data_kpi if data_kpi is not None else b"",
            file_name=nome_arquivo_kpi,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            disabled=(data_kpi is None),
        )
    
# ---------- KPIs ----------
with st.container(border=True):
    st.subheader("📊 Resumo")

    # --------- Cálculos prévios (com fallback) ---------
    # Valor médio por OF
    media_of = valor_medio_por_of(df)
    valor_txt = _format_brl(round(media_of, 2)) if pd.notna(media_of) else "—"

    # % OFs básicas (Último ano)
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

    # Empresas que venderam (Últimos 3 anos)
    try:
        qtd_vend = quantidade_empresas_que_venderam_ultimos_3_anos(df)
    except Exception:
        qtd_vend = None

    # Cadastrados no Último ano
    # Filtrar apenas fornecedores cadastrados por VANDERLEI.SOUZA
    df_forn_vanderlei = df_forn[df_forn["FORN_QUEMCADASTROU"] == "VANDERLEI.SOUZA"]
    
    try:
        cad_serie = serie_fornecedores_cadastrados_por_ano(df_forn_vanderlei, anos=1)
        cad_no_ano = int(cad_serie["FORNECEDORES_CADASTRADOS"].sum()) if not cad_serie.empty else 0
    except Exception:
        cad_no_ano = None

    # Compras com atraso (12m)
    df_atrasos = pd.DataFrame()
    try:
        taxa_atraso_pct, qtd_atrasadas, total_compras, df_atrasos = compras_atrasadas(
            df, dias_uteis_sla=3, Meses_lookback=12
        )
    except Exception:
        taxa_atraso_pct = None

    # Tempos médios (12m e 5a, em dias úteis)
    try:
        m12, m5a = tempos_medios_12m_5a(df, considerar_dias_uteis=True)
    except Exception:
        m12, m5a = None, None

    try:
        resumo_baratas, df_ofs_baratas = quantidade_ofs_ate_300_2025_2026(df)
        kpi_ofs_2025 = int(resumo_baratas.get("2025", 0))
        kpi_ofs_2026 = int(resumo_baratas.get("2026", 0))
    except Exception:
        kpi_ofs_2025, kpi_ofs_2026 = None, None
        df_ofs_baratas = pd.DataFrame()

    try:
        totais_ano = total_ofs_por_ano(df, anos=(2025, 2026))
        total_ofs_2025 = totais_ano.get("2025", 0)
        total_ofs_2026 = totais_ano.get("2026", 0)
    except Exception:
        total_ofs_2025 = total_ofs_2026 = None

   # Linha 1 centralizada (5 KPIs)
    spacer1, r1c1, r1c2, r1c3, r1c4, spacer2 = st.columns([1, 2, 2, 2, 2, 1])

    r1c1.metric("Valor médio OF (12m)", valor_txt)
    r1c2.metric("% de OFs Básicas (12m)", _format_pct_br(pct_bas) if pct_bas is not None else "—")
    r1c3.metric("Tempo médio OF (12m)", (f"{int(round(m12))} dias") if m12 is not None else "—")
    r1c4.metric("Tempo médio OF (5a)", (f"{int(round(m5a))} dias") if m5a is not None else "—")
    
    # Linha 2 centralizada (4 KPIs)
    spacer1, r2c1, r2c2, r2c3, r2c4, r2c5, spacer2 = st.columns([1, 2, 2, 2, 2, 2, 1])

    r2c1.metric("Compras com atraso (12m)", _format_pct_br(taxa_atraso_pct) if taxa_atraso_pct is not None else "—")
    r2c2.metric("OFs < R$ 300 - 2025", _format_int_br(kpi_ofs_2025) if kpi_ofs_2025 is not None else "—")
    r2c3.metric("Total de OFs 2025", _format_int_br(total_ofs_2025) if total_ofs_2025 is not None else "—")
    r2c4.metric("OFs < R$ 300 - 2026", _format_int_br(kpi_ofs_2026) if kpi_ofs_2026 is not None else "—")
    r2c5.metric("Total de OFs 2026", _format_int_br(total_ofs_2026) if total_ofs_2026 is not None else "—")

with st.container(border=True):
    st.subheader("Visão Geral de Fornecedores — Cadastro × Utilização (Materiais + Serviços)")

    try:
        resumo, df_nunca = resumo_movimentacao_fornecedores(df_mov, anos=2)

        spacer1, c1, c2, c3, c4, c5, spacer2 = st.columns([1, 2, 2, 2, 2, 2, 1])
        c1.metric("Total cadastrados", _format_int_br(resumo["total_cadastrados"]))
        c2.metric("Cadastrados (Últimos 2 anos)", _format_int_br(resumo["cadastrados_ult2a"]))
        c3.metric("Utilizados (Últimos 2 anos)", _format_int_br(resumo["utilizados_ult2a"]))
        c4.metric("Nunca utilizados", _format_int_br(resumo["nunca_utilizados"]))
        c5.metric("Cadastrados e utilizados (Últimos 2 anos)", _format_int_br(resumo["cadastrados_e_utilizados"]))

        with st.expander("🔎 Ver lista de fornecedores nunca utilizados"):
            if not df_nunca.empty:
                st.dataframe(df_nunca, use_container_width=True, hide_index=True)
            else:
                st.caption("Nenhum fornecedor na condição 'nunca utilizado'.")
    except Exception as e:
        st.warning(f"Não foi possível gerar a visão de fornecedores: {e}")

with st.container(border=True):
    st.subheader("OFs Básicas vs Específicas — Últimos 12 Meses")

    df_basicos = ofs_basico_vs_nao_ultimos_12m(df_erp)

    if df_basicos.empty:
        st.info("Nenhuma OF registrada nos Últimos 12 Meses.")
    else:
        df_long = df_basicos.melt(
            id_vars=["ANO_MES_PERIOD", "ANO_MES_LABEL", "TOTAL"],
            value_vars=["BASICO", "ESPECIFICO"],
            var_name="TIPO",
            value_name="QTD"
        )
        
        # Nome bonito na legenda
        df_long["TIPO"] = df_long["TIPO"].replace({
            "BASICO": "Básico",
            "ESPECIFICO": "Específico"
        })

        chart_base = (
            alt.Chart(df_long)
            .transform_stack(
                stack="QTD",
                groupby=["ANO_MES_LABEL"],
                as_=["y0","y1"],
                offset="normalize"
            )
            .transform_calculate(
                y_mid="(datum.y0 + datum.y1) / 2"
            )
        )
        
        bars = chart_base.mark_bar().encode(
            x=alt.X(
                "ANO_MES_LABEL:N",
                sort=alt.SortField("ANO_MES_PERIOD"),
                title=None,
                axis=alt.Axis(labelAngle=0)
            ),
            y=alt.Y(
                "y0:Q",
                title=None,
                axis=alt.Axis(labels=False, ticks=False, domain=False, grid=False)
            ),
            y2="y1:Q",
            color=alt.Color(
                "TIPO:N",
                title="Tipo",
                sort=["Específico", "Básico"],
                legend=alt.Legend(
                    orient="right",
                    direction="vertical"
                )
            )
        )

        labels = chart_base.mark_text(
            baseline="middle",
            align="center",
            fontWeight="bold",
            color="white"
        ).encode(
            x=alt.X("ANO_MES_LABEL:N", sort=alt.SortField("ANO_MES_PERIOD")),
            y=alt.Y("y_mid:Q"),
            text=alt.Text("QTD:Q", format=".0f")
        )

        chart = (
            (bars + labels)
            .properties(height=360, padding={"top": 30})
            .configure_view(clip=False)
        )

        st.altair_chart(chart, use_container_width=True)

with st.container(border=True):
    st.subheader("Materiais Básicos — Fornecimento por local")

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

# ---------- TOP fornecedores ----------
with st.container(border=True):
    st.subheader("TOP fornecedores por UF")
    c1, c2 = st.columns(2)

    with c1:
        st.caption("Últimos 10 anos")
        df_top10 = _safe(fornecedor_top_por_uf_emp, df, anos=10)
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
        df_top2 = _safe(fornecedor_top_por_uf_emp, df, anos=2)
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

# ---------- Série de Fornecedores Ativos ----------
with st.container(border=True):
    st.subheader("Fornecedores ativos por ano")

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
                x=alt.X("ANO_TXT:N", title=None, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("FORNECEDORES_ATIVOS:Q", title=None, axis=None),
                tooltip=["ANO_TXT", "FORNECEDORES_ATIVOS"]
            )
            .properties(height=300)
        )
    
        labels = (
            alt.Chart(serie_plot_vis)
            .mark_text(
                baseline="top",
                align="center",
                dy=8,
                color="white",
                fontWeight="bold"
            )
            .encode(
                x=alt.X("ANO_TXT:N"),
                y=alt.Y("FORNECEDORES_ATIVOS:Q"),
                text=alt.Text("FORNECEDORES_ATIVOS_TXT:N")
            )
        )
    
        chart_ativos = bars + labels
        st.altair_chart(chart_ativos, use_container_width=True)
    else:
        st.info("Sem dados para exibir nos Últimos 10 anos.")

# ---------- OFs destaque ----------
with st.container(border=True):
    st.subheader("Principais Compras - Últimos 10 anos")
    c1, c2 = st.columns(2)

    with c1:
        st.markdown("**Maior OF**")
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
        st.markdown("**Menor OF**")
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

# ---------- Volumes por período ----------
with st.container(border=True):
    st.subheader("Volumes por período")

    c1, c2 = st.columns(2)
    # Top 3 Meses (Últimos 12 Meses)
    with c1:
        st.markdown("**Top 3 Meses (Últimos 12 Meses)**")
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
            
    # Top 3 Meses (geral, agregando todos os anos por mês-do-ano)
    with c2:
    st.markdown("**Top 3 Meses (Últimos 5 anos)**")

    df_mes_all = _safe(meses_top3_volume_geral, df, top_n=3, anos=5)

    if isinstance(df_mes_all, pd.DataFrame) and not df_mes_all.empty:
        df_mes_all = _round_cols(df_mes_all, ["VALOR_TOTAL", "PART_%"])
        df_mes_all_fmt = _fmt_df_brl(df_mes_all, money=["VALOR_TOTAL"], pcts=["PART_%"])

        st.dataframe(
            df_mes_all_fmt,
            use_container_width=True,
            hide_index=True,
            column_config={
                "MES_ROTULO":  st.column_config.TextColumn("MÊS"),
                "VALOR_TOTAL": st.column_config.TextColumn("VALOR TOTAL"),
                "PART_%":      st.column_config.TextColumn("PARTICIPAÇÃO"),
            },
        )
    else:
        st.info("Sem dados para exibir.")

# ---------- Série de Categorias ----------
with st.container(border=True):
    st.subheader("Volume por Categoria")

    st.markdown("**Mais compradas - Últimos 12 meses**")
    df_cat5 = _safe(categorias_mais_compradas_ultimos_anos, df, meses=12)
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
                    sort=order_cats,
                    title=None,
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

    # Maior crescimento desde 2015 (fixo 2015 → Último ano, apenas categorias com vendas nos Últimos 5 anos)
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
            st.caption("Nenhuma categoria atende ao critério: vendas em TODOS os Últimos 5 anos + base suficiente para cálculo.")
    except Exception as e:
        st.caption(f"Não foi possível calcular o crescimento desde 2015: {e}")

# ---------- Gráfico 1: Requisições x OFs ----------
with st.container(border=True):
    st.subheader("Requisições e OFs — Últimos 12 Meses")

    df_mes = _safe(requisicoes_ofs_ultimos_12m, df)

    if isinstance(df_mes, pd.DataFrame) and not df_mes.empty:
        df_long = df_mes.melt(
            id_vars=["ANO_MES_PERIOD", "ANO_MES_LABEL"],
            value_vars=["REQUISICOES", "OFS"],
            var_name="TIPO",
            value_name="QTD"
        )
        df_long["QTD"] = pd.to_numeric(df_long["QTD"], errors="coerce").fillna(0).astype(int)

        bars = (
            alt.Chart(df_long)
            .mark_bar()
            .encode(
                x=alt.X(
                    "ANO_MES_LABEL:N",
                    sort=alt.SortField("ANO_MES_PERIOD"),
                    title=None,
                    axis=alt.Axis(labelAngle=0)
                ),
                xOffset=alt.XOffset("TIPO:N", sort=["REQUISICOES", "OFS"]),
                y=alt.Y("QTD:Q", title=None, axis=alt.Axis(labels=False, ticks=False, domain=False, grid=False)),
                color=alt.Color("TIPO:N", title="Tipo"),
                tooltip=[
                    alt.Tooltip("ANO_MES_LABEL:N", title="Mês"),
                    alt.Tooltip("TIPO:N", title="Tipo"),
                    alt.Tooltip("QTD:Q", title="Qtd", format=".0f"),
                ],
            )
            .properties(height=300)
        )

        labels = (
            alt.Chart(df_long)
            .mark_text(align="center", baseline="bottom", dy=-2)
            .encode(
                x=alt.X("ANO_MES_LABEL:N", sort=alt.SortField("ANO_MES_PERIOD")),
                xOffset=alt.XOffset("TIPO:N", sort=["REQUISICOES", "OFS"]),
                y=alt.Y("QTD:Q"),
                text=alt.Text("QTD:Q", format=".0f"),
                detail="TIPO:N",
            )
        )

        st.altair_chart(alt.layer(bars, labels).resolve_scale(y="shared"), use_container_width=True)
    else:
        st.info("Sem dados de REQ ou OF nos Últimos 12 Meses.")

# ---------- Gráfico 2: Média de Requisições por Empreendimento ----------
with st.container(border=True):
    st.subheader("Média de Requisições por Empreendimento — Últimos 12 Meses")

    df_media = _safe(media_requisicoes_por_empreendimento_ultimos_12m, df)

    if isinstance(df_media, pd.DataFrame) and not df_media.empty:
        df_plot = df_media.copy()

        # ✅ valor inteiro para plotar e rotular
        df_plot["MEDIA_REQ_INT"] = pd.to_numeric(df_plot["MEDIA_REQ_POR_EMPR"], errors="coerce").round(0).astype("Int64")

        base = alt.Chart(df_plot).encode(
            x=alt.X(
                "ANO_MES_LABEL:N",
                sort=alt.SortField("ANO_MES_PERIOD"),
                title=None,
                axis=alt.Axis(labelAngle=0)
            ),
            y=alt.Y(
                "MEDIA_REQ_INT:Q",
                title=None,
                axis=alt.Axis(labels=False, ticks=False, domain=False, grid=True)
            ),
            tooltip=[
                alt.Tooltip("ANO_MES_LABEL:N", title="Mês"),
                alt.Tooltip("MEDIA_REQ_INT:Q", title="Média (req)", format=".0f"),
                alt.Tooltip("TOTAL_REQ:Q", title="Total de REQs", format=".0f"),
                alt.Tooltip("EMPREENDIMENTOS:Q", title="Empreendimentos", format=".0f"),
            ]
        )

        line = base.mark_line(point=True)

        labels = base.mark_text(dy=-8).encode(
            text=alt.Text("MEDIA_REQ_INT:Q", format=".0f")
        )

        meta_line = alt.Chart(pd.DataFrame({"y": [4]})).mark_rule(
            color="red", strokeDash=[4, 4]
        ).encode(y="y:Q")

        st.altair_chart(line + labels + meta_line, use_container_width=True)

        with st.expander("🔎 Ver obras com mais de 4 requisições por mês (Últimos 12 Meses)"):
            for _, row in df_plot.iterrows():
                if pd.notna(row.get("TOP_EMPREENDIMENTOS")):
                    st.markdown(f"**{row['ANO_MES_LABEL']}** — {row['TOP_EMPREENDIMENTOS']}")
    else:
        st.info("Sem dados de requisições nos Últimos 12 Meses.")

# ---------- Gráfico 3: Tempo médio REQ → OF ----------
with st.container(border=True):
    st.subheader("Tempo médio em dias úteis: REQ → OF — Últimos 12 Meses")

    df_tempo = _safe(tempo_medio_req_para_of_ultimos_12m, df, dias_uteis_sla=3)

    if isinstance(df_tempo, pd.DataFrame) and not df_tempo.empty:
        df_plot = df_tempo.copy()

        # ✅ arredonda para inteiro e usa isso NO GRÁFICO
        df_plot["MEDIA_DIAS_INT"] = df_plot["MEDIA_DIAS_UTEIS"].round(0).astype("Int64")

        base = alt.Chart(df_plot).encode(
            x=alt.X(
                "ANO_MES_LABEL:N",
                sort=alt.SortField("ANO_MES_PERIOD"),
                title=None,
                axis=alt.Axis(labelAngle=0)
            ),
            y=alt.Y(
                "MEDIA_DIAS_INT:Q",
                title=None,
                axis=alt.Axis(labels=False, ticks=False, domain=False, grid=True)
            ),
            tooltip=[
                alt.Tooltip("ANO_MES_LABEL:N", title="Mês"),
                alt.Tooltip("MEDIA_DIAS_INT:Q", title="Média (dias)", format=".0f"),
                alt.Tooltip("TOTAL_OFS:Q", title="Total de OFs", format=".0f"),
                alt.Tooltip("ULTRAPASSARAM_SLA:Q", title="Acima do SLA", format=".0f"),
            ],
        )

        line = base.mark_line(point=True)

        labels = base.mark_text(dy=-8).encode(
            text=alt.Text("MEDIA_DIAS_INT:Q", format=".0f")
        )

        sla_line = alt.Chart(pd.DataFrame({"y": [3]})).mark_rule(
            color="red", strokeDash=[4, 4]
        ).encode(y="y:Q")

        st.altair_chart(line + labels + sla_line, use_container_width=True)
    else:
        st.info("Sem dados de REQ → OF nos Últimos 12 Meses.")
        
with st.container(border=True):
    st.subheader("OFs que ultrapassaram o SLA — Últimos 12 meses")

    if isinstance(df, pd.DataFrame) and not df.empty:

        df_ofs_atrasadas = tabela_ofs_atrasadas(df)

        if not df_ofs_atrasadas.empty:

            st.dataframe(
                df_ofs_atrasadas,
                use_container_width=True,
                hide_index=True
            )

            # --- Download ---
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                df_ofs_atrasadas.to_excel(
                    writer,
                    index=False,
                    sheet_name="OFs_Atrasadas"
                )

            buffer.seek(0)

            nome_arquivo = (
                f"OFs_Atrasadas_12M_"
                f"{datetime.today().strftime('%Y-%m-%d')}.xlsx"
            )

            st.download_button(
                label="📥 Baixar tabela de OFs atrasadas (Excel)",
                data=buffer,
                file_name=nome_arquivo,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        else:
            st.success("✅ Nenhuma OF ultrapassou o SLA nos últimos 12 meses.")
    else:
        st.warning("Base de dados vazia ou inválida.")

# Carrega apenas uma vez
if "df_anomalias" not in st.session_state:
    st.session_state["df_anomalias"] = carregar_anomalias(Path(__file__).parent)

with st.container(border=True):
    st.subheader("Anomalias por Mês")

    df_anomalias = st.session_state["df_anomalias"].copy()

    # Garante datetime
    df_anomalias["Data Anomalia"] = pd.to_datetime(
        df_anomalias["Data Anomalia"], errors="coerce"
    )

    # Excluir março/2026
    df_anomalias = df_anomalias[
        df_anomalias["Data Anomalia"].dt.to_period("M").astype(str) != "2026-03"
    ]

    # Gráfico + comentários
    chart, comentarios = grafico_anomalias_por_mes_com_comentarios(df_anomalias)

    if chart:
        st.altair_chart(chart, use_container_width=True)
        with st.expander("🔎 Ver obras com anomalias por mês"):
            for c in comentarios:
                st.markdown(c)
    else:
        st.info(comentarios[0])
        
# ---------- Estilo ----------
st.markdown("""
<style>
/* margem menor no topo geral */
section.main > div { padding-top: 0.5rem; }

/* h1 compacto */
h1 { line-height: 1.25; }

/* forçar cor preta para todo o texto */
html, body, [class*="css"] {
    color: black !important;}

/* cards: borda mais suave e menos espaço vertical */
div[data-testid="stMetric"] {
    background: rgba(255,255,255,0.02);
    padding: 0.75rem 0.75rem;
    border-radius: 12px;}

/* valor do KPI um pouco maior */
[data-testid="stMetricValue"] { font-size: 1.55rem; }

/* subtítulo das seções */
.block-container h3, .block-container h2, .block-container h4 {
    letter-spacing: .2px;}
</style>
""", unsafe_allow_html=True)













