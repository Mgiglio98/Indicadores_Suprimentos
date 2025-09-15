# Tratamento_Anomalias.py
from __future__ import annotations
from pathlib import Path
import pandas as pd
import altair as alt
import re

# --- helpers ---------------------------------------------------------------
def _read_csv_ok(path: Path) -> pd.DataFrame:
    # tenta utf-8-sig e latin1 (CSV vindo do Excel/Windows cai num desses)
    last_err = None
    for enc in ("utf-8-sig", "latin1"):
        try:
            df = pd.read_csv(path, sep=";", encoding=enc)
            break
        except Exception as e:
            last_err = e
    else:
        raise last_err

    # normaliza nomes de colunas (espaços, NBSP)
    df.columns = (
        df.columns.astype(str)
        .str.replace("\xa0", " ", regex=False)
        .str.strip()
    )
    return df

def _only_digits(s: str) -> str:
    s = str(s)
    m = re.findall(r"\d+", s)
    return m[0].lstrip("0") if m else s.strip()

# --- carga e tratamento ----------------------------------------------------
def carregar_anomalias(
    base_dir: Path | None = None,
    csv_name: str = "Controle_Anomalias(Controle).csv",
    xlsx_name: str = "Empreendimentos.xlsx",
) -> pd.DataFrame:
    base_dir = base_dir or Path(__file__).parent

    # CSV de anomalias
    df = _read_csv_ok(base_dir / csv_name)
    # tenta localizar as colunas mesmo que venham com variação de espaço/underscore
    cols_lower = {c.lower().strip(): c for c in df.columns}
    col_emp = cols_lower.get("empreendimento")
    col_dt  = cols_lower.get("data anomalia") or cols_lower.get("data_anomalia")
    if not col_emp or not col_dt:
        raise KeyError(f"Esperava 'Empreendimento' e 'Data Anomalia'. Encontrei: {list(df.columns)}")

    df = df.rename(columns={col_emp: "Empreendimento", col_dt: "Data Anomalia"})
    df["Empreendimento"] = df["Empreendimento"].astype(str).str.strip()
    df["Empreendimento_cod"] = df["Empreendimento"].map(_only_digits)
    # datas (robusto contra espaços/lixo)
    df["Data Anomalia"] = pd.to_datetime(
        df["Data Anomalia"].astype(str).str.replace("\xa0", " ", regex=False).str.strip(),
        dayfirst=True,
        errors="coerce",
    )
    # remove linhas sem data válida para não gerar barra "NaT"
    df = df.dropna(subset=["Data Anomalia"]).copy()
    if df.empty:
        return df  # deixa o chamador tratar

    # Excel de empreendimentos
    df_emp = pd.read_excel(base_dir / xlsx_name)
    df_emp.columns = df_emp.columns.astype(str).str.replace("\xa0", " ", regex=False).str.strip()
    emp_col = "EMPREENDIMENTO" if "EMPREENDIMENTO" in df_emp.columns else "Empreendimento"
    if emp_col not in df_emp.columns:
        raise KeyError(f"Coluna 'EMPREENDIMENTO' não encontrada no {xlsx_name}. Colunas: {list(df_emp.columns)}")

    # quebra "2316 - MARCO"
    df_emp["EMP_CODIGO"]  = df_emp[emp_col].astype(str).str.split("-", n=1).str[0].map(_only_digits)
    df_emp["NOME_CURTO"]  = (
        df_emp[emp_col].astype(str)
        .apply(lambda x: x.split("-", 1)[1].strip() if "-" in x else x.strip())
        .str.split().str[0]
    )

    # merge pelo código
    out = df.merge(
        df_emp[["EMP_CODIGO", "NOME_CURTO"]],
        how="left",
        left_on="Empreendimento_cod",
        right_on="EMP_CODIGO",
    )
    return out

# --- gráfico + comentários -------------------------------------------------
def grafico_anomalias_por_mes_com_comentarios(df: pd.DataFrame):
    if df is None or df.empty:
        return None, ["Sem dados válidos de anomalias."]

    df = df.copy()
    df["ANO_MES"] = df["Data Anomalia"].dt.to_period("M").astype(str)
    if "NOME_CURTO" not in df.columns:
        df["NOME_CURTO"] = pd.NA
    if "Empreendimento_cod" not in df.columns:
        # fallback: extrai dígitos e remove zeros à esquerda
        df["Empreendimento_cod"] = (
            df["Empreendimento"].astype(str)
              .str.extract(r"(\d+)", expand=False)
              .fillna(df["Empreendimento"].astype(str))
              .str.lstrip("0")
        )

    contagem = (
        df.groupby("ANO_MES", dropna=True)
          .size()
          .reset_index(name="TOTAL_ANOMALIAS")
          .sort_values("ANO_MES")
    )
    if contagem.empty:
        return None, ["Sem datas válidas na coluna 'Data Anomalia'."]

    # --- barras ---
    bars = (
        alt.Chart(contagem)
        .mark_bar()
        .encode(
            x=alt.X("ANO_MES:N", title="Mês", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("TOTAL_ANOMALIAS:Q", title="Total de Anomalias"),
            tooltip=[alt.Tooltip("ANO_MES:N", title="Mês"),
                     alt.Tooltip("TOTAL_ANOMALIAS:Q", title="Total", format=".0f")]
        )
    )

    # --- rótulos em cima das barras (sem decimais) ---
    labels = (
        alt.Chart(contagem)
        .mark_text(align="center", baseline="bottom", dy=-2)
        .encode(
            x=alt.X("ANO_MES:N"),
            y=alt.Y("TOTAL_ANOMALIAS:Q"),
            text=alt.Text("TOTAL_ANOMALIAS:Q", format=".0f")
        )
    )

    chart = alt.layer(bars, labels).properties(
        title="Total de Anomalias por Mês",
        height=300
    )

    # --- comentários por mês (código sem .0) ---
    comentarios = []
    for mes in contagem["ANO_MES"]:
        dfm = df[df["ANO_MES"] == mes]
        cods  = dfm["Empreendimento_cod"].astype(str).str.strip()
        nomes = dfm["NOME_CURTO"]
        pares = {f"{c} ({n})" if pd.notna(n) and str(n).strip() else c
                 for c, n in zip(cods, nomes)}
        lista = ", ".join(sorted(pares)) if pares else "—"
        comentarios.append(f"🔎 **{mes}** — Obras com anomalias: {lista}")

    return chart, comentarios
