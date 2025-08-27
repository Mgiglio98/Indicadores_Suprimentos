import pandas as pd
import numpy as np
from pathlib import Path

_BI_LABEL = {
    1: "Jan–Fev", 2: "Jan–Fev", 3: "Mar–Abr", 4: "Mar–Abr", 5: "Mai–Jun", 6: "Mai–Jun",
    7: "Jul–Ago", 8: "Jul–Ago", 9: "Set–Out", 10: "Set–Out", 11: "Nov–Dez", 12: "Nov–Dez"
}

def _format_brl(v):
    return f"R$ {v:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")

def carregar_bases():
    base_dir = Path(__file__).parent
    df_erp = pd.read_excel(
        base_dir / "total_indicadores.xlsx",
        sheet_name="Planilha1",
        dtype={"INSUMO_CDG": "string", "FORNECEDOR_CDG": "string"},
    )

    # Datas
    df_erp["REQ_DATA"] = pd.to_datetime(df_erp["REQ_DATA"], errors="coerce")
    df_erp["OF_DATA"] = pd.to_datetime(df_erp["OF_DATA"], errors="coerce")

    # Numéricos
    for col in ["PRCTTL_INSUMO", "ITEM_PRCUNTPED", "TOTAL"]:
        if col in df_erp.columns:
            df_erp[col] = pd.to_numeric(df_erp[col], errors="coerce")

    # Preservar zeros no código do fornecedor
    if "FORNECEDOR_CDG" in df_erp.columns:
        df_erp["FORNECEDOR_CDG"] = df_erp["FORNECEDOR_CDG"].astype("string")
        w = int(df_erp["FORNECEDOR_CDG"].dropna().astype(str).str.len().max())
        if w > 0:
            df_erp["FORNECEDOR_CDG"] = df_erp["FORNECEDOR_CDG"].str.zfill(w)

    # Classificação de básicos
    df_bas = pd.read_excel(
        base_dir / "MateriaisBasicos.xlsx",
        sheet_name="Final",
        usecols=["Código"],
        dtype={"Código": "string"},
    ).drop_duplicates()

    cod_basicos = set(df_bas["Código"].dropna())
    if "TIPO_MATERIAL" not in df_erp.columns:
        pos = df_erp.columns.get_loc("INSUMO_CDG") + 1
        df_erp.insert(
            pos,
            "TIPO_MATERIAL",
            np.where(df_erp["INSUMO_CDG"].isin(cod_basicos), "BÁSICO", "ESPECÍFICO"),
        )

    return df_erp

def fornecedor_top_por_uf(df, anos=10, ufs=("RJ", "SP")):
    df = df.copy()
    df["OF_DATA_DT"] = pd.to_datetime(df["OF_DATA"], errors="coerce")
    limite = pd.Timestamp.today() - pd.DateOffset(years=anos)
    base = df[df["OF_DATA_DT"] >= limite]
    out = []
    for uf in ufs:
        top = (
            base[base["FORNECEDOR_UF"] == uf]
            .groupby(["FORNECEDOR_CDG", "FORNECEDOR_DESC"], as_index=False)["PRCTTL_INSUMO"]
            .sum()
            .sort_values("PRCTTL_INSUMO", ascending=False)
            .head(1)
        )
        if not top.empty:
            out.append(
                {
                    "UF": uf,
                    "FORNECEDOR_CDG": top.iloc[0]["FORNECEDOR_CDG"],
                    "FORNECEDOR_DESC": top.iloc[0]["FORNECEDOR_DESC"],
                    "VALOR": float(top.iloc[0]["PRCTTL_INSUMO"]),
                }
            )
    out = pd.DataFrame(out)
    if not out.empty:
        out["FORNECEDOR_CDG"] = out["FORNECEDOR_CDG"].astype("string")
        w = int(out["FORNECEDOR_CDG"].dropna().astype(str).str.len().max())
        if w > 0:
            out["FORNECEDOR_CDG"] = out["FORNECEDOR_CDG"].str.zfill(w)
        out["VALOR"] = pd.to_numeric(out["VALOR"], errors="coerce").round(2)
    return out

def maior_ordem_fornecimento(df):
    df = df.copy()
    df["OF_DATA_DT"] = pd.to_datetime(df["OF_DATA"], errors="coerce")
    g = (
        df.groupby("OF_CDG")
        .agg(
            VALOR_TOTAL=("PRCTTL_INSUMO", "sum"),
            EMPRD_DESC=("EMPRD_DESC", "first"),
            FORNECEDOR_DESC=("FORNECEDOR_DESC", "first"),
            DATA_OF=("OF_DATA_DT", "first"),
            #INSUMOS=("INSUMO_DESC", lambda x: ", ".join(sorted(set(x)))),
            TOTAL_ITENS=("INSUMO_CDG", "nunique"),
        )
        .reset_index()
        .sort_values("VALOR_TOTAL", ascending=False)
        .head(1)
    )
    if g.empty:
        return g
    g["DATA_OF"] = pd.to_datetime(g["DATA_OF"]).dt.strftime("%d/%m/%Y")
    g["VALOR_TOTAL"] = pd.to_numeric(g["VALOR_TOTAL"], errors="coerce").round(2)
    return g

def menor_ordem_fornecimento(df):
    df = df.copy()
    df["OF_DATA_DT"] = pd.to_datetime(df["OF_DATA"], errors="coerce")
    g = (
        df.groupby("OF_CDG")
        .agg(
            VALOR_TOTAL=("PRCTTL_INSUMO", "sum"),
            EMPRD_DESC=("EMPRD_DESC", "first"),
            FORNECEDOR_DESC=("FORNECEDOR_DESC", "first"),
            DATA_OF=("OF_DATA_DT", "first"),
            #INSUMOS=("INSUMO_DESC", lambda x: ", ".join(sorted(set(x)))),
            TOTAL_ITENS=("INSUMO_CDG", "nunique"),
        )
        .reset_index()
        .sort_values("VALOR_TOTAL", ascending=True)
        .head(1)
    )
    if g.empty:
        return g
    g["DATA_OF"] = pd.to_datetime(g["DATA_OF"]).dt.strftime("%d/%m/%Y")
    g["VALOR_TOTAL"] = pd.to_numeric(g["VALOR_TOTAL"], errors="coerce").round(2)
    return g

def valor_medio_por_of(df):
    tot = df.groupby("OF_CDG")["PRCTTL_INSUMO"].sum().reset_index(name="VALOR_TOTAL_OF")
    tot["VALOR_TOTAL_OF"] = pd.to_numeric(tot["VALOR_TOTAL_OF"], errors="coerce").round(2)
    media = float(tot["VALOR_TOTAL_OF"].mean()) if not tot.empty else 0.0
    return media, tot

def percentual_ofs_basicas_ultimo_ano(df):
    df = df.copy()
    df["OF_DATA_DT"] = pd.to_datetime(df["OF_DATA"], errors="coerce")
    limite = pd.Timestamp.today() - pd.DateOffset(years=1)
    base = df[df["OF_DATA_DT"] >= limite].copy()
    if base.empty:
        return 0.0, pd.DataFrame(columns=["OF_CDG", "TIPO_OF"])
    grp = (
        base.groupby("OF_CDG")["TIPO_MATERIAL"]
        .apply(lambda x: "BÁSICO" if "BÁSICO" in set(x) else "ESPECÍFICO")
        .reset_index(name="TIPO_OF")
    )
    total = len(grp)
    bas = int((grp["TIPO_OF"] == "BÁSICO").sum())
    pct = (bas / total * 100.0) if total else 0.0
    return pct, grp

def periodo_maior_volume_bimestre(df, anos=10, top_n=None, estacionalidade=False):
    df = df.copy()
    df["OF_DATA_DT"] = pd.to_datetime(df["OF_DATA"], errors="coerce")
    limite = pd.Timestamp.today() - pd.DateOffset(years=anos)
    base = df[df["OF_DATA_DT"] >= limite].copy()
    if base.empty:
        cols = ["BIMESTRE_ROTULO", "VALOR_TOTAL", "QTDE_OFS", "PART_%"] if estacionalidade else ["BIMESTRE_ROTULO", "VALOR_TOTAL", "QTDE_OFS"]
        return pd.DataFrame(columns=cols)

    base["PRCTTL_INSUMO"] = pd.to_numeric(base["PRCTTL_INSUMO"], errors="coerce")
    base["BIMESTRE"] = np.ceil(base["OF_DATA_DT"].dt.month / 2).astype(int)
    base["BIMESTRE_ROTULO"] = base["OF_DATA_DT"].dt.month.map(_BI_LABEL)

    agg = (
        base.groupby(["BIMESTRE", "BIMESTRE_ROTULO"])
        .agg(VALOR_TOTAL=("PRCTTL_INSUMO", "sum"), QTDE_OFS=("OF_CDG", "nunique"))
        .reset_index()
    )
    agg["VALOR_TOTAL"] = pd.to_numeric(agg["VALOR_TOTAL"], errors="coerce")

    if estacionalidade:
        total = agg["VALOR_TOTAL"].sum()
        agg["PART_%"] = (agg["VALOR_TOTAL"] / total * 100).round(2) if total else 0.0
        out = agg.sort_values("BIMESTRE")[["BIMESTRE_ROTULO", "VALOR_TOTAL", "QTDE_OFS", "PART_%"]].copy()
    else:
        agg = agg.sort_values("VALOR_TOTAL", ascending=False)
        if top_n:
            agg = agg.head(int(top_n))
        out = agg[["BIMESTRE_ROTULO", "VALOR_TOTAL", "QTDE_OFS"]].copy()

    out["VALOR_TOTAL"] = out["VALOR_TOTAL"].round(2)
    return out

def mes_maior_volume_ultimo_ano(df, top_n=3):
    df = df.copy()
    df["OF_DATA_DT"] = pd.to_datetime(df["OF_DATA"], errors="coerce")
    limite = pd.Timestamp.today() - pd.DateOffset(years=1)
    base = df[df["OF_DATA_DT"] >= limite].copy()
    if base.empty:
        return pd.DataFrame(columns=["ANO_MES", "VALOR_TOTAL", "PART_%"])
    base["PRCTTL_INSUMO"] = pd.to_numeric(base["PRCTTL_INSUMO"], errors="coerce")
    base["ANO_MES"] = base["OF_DATA_DT"].dt.to_period("M")
    res = (base.groupby("ANO_MES")["PRCTTL_INSUMO"].sum()
           .reset_index(name="VALOR_TOTAL")
           .sort_values("VALOR_TOTAL", ascending=False))
    total = res["VALOR_TOTAL"].sum()
    res["PART_%"] = (res["VALOR_TOTAL"] / total * 100).round(2) if total else 0.0
    res["VALOR_TOTAL"] = pd.to_numeric(res["VALOR_TOTAL"], errors="coerce").round(2)
    return res.head(int(top_n))

def mes_maior_volume_geral(df, top_n=3):
    df = df.copy()
    df["OF_DATA_DT"] = pd.to_datetime(df["OF_DATA"], errors="coerce")
    base = df.dropna(subset=["OF_DATA_DT"]).copy()
    if base.empty:
        return pd.DataFrame(columns=["ANO_MES", "VALOR_TOTAL", "PART_%"])
    base["PRCTTL_INSUMO"] = pd.to_numeric(base["PRCTTL_INSUMO"], errors="coerce")
    base["ANO_MES"] = base["OF_DATA_DT"].dt.to_period("M")
    res = (base.groupby("ANO_MES")["PRCTTL_INSUMO"].sum()
           .reset_index(name="VALOR_TOTAL")
           .sort_values("VALOR_TOTAL", ascending=False))
    total = res["VALOR_TOTAL"].sum()
    res["PART_%"] = (res["VALOR_TOTAL"] / total * 100).round(2) if total else 0.0
    res["VALOR_TOTAL"] = pd.to_numeric(res["VALOR_TOTAL"], errors="coerce").round(2)
    return res.head(int(top_n))

def quantidade_empresas_que_venderam_ultimos_3_anos(df):
    df = df.copy()
    df["OF_DATA_DT"] = pd.to_datetime(df.get("OF_DATA"), errors="coerce")
    limite = pd.Timestamp.today() - pd.DateOffset(years=3)
    base = df[df["OF_DATA_DT"] >= limite].copy()
    if base.empty:
        return 0
    if "PRCTTL_INSUMO" in base.columns:
        v = pd.to_numeric(base["PRCTTL_INSUMO"], errors="coerce").fillna(0)
        base = base[v > 0]
        if base.empty:
            return 0
    candidatos = [
        "FORNECEDOR_CDG", "FORNECEDOR_ID", "COD_FORNECEDOR",
        "FORN_CNPJ", "CNPJ", "PED_FORNECEDOR", "FORNECEDOR"
    ]
    col_forn = next((c for c in candidatos if c in base.columns), None)
    if not col_forn:
        raise KeyError(
            f"Não encontrei coluna de fornecedor. Tente uma destas: {candidatos}. Disponíveis: {list(base.columns)}"
        )
    s = (
        base[col_forn]
        .astype("string")
        .str.strip()
        .replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
        .dropna()
    )
    return int(s.nunique())



