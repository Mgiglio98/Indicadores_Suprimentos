# Tratamento_Indicadores.py
import pandas as pd
import numpy as np
from pathlib import Path

_BI_LABEL = {
    1:"Jan–Fev",2:"Jan–Fev",3:"Mar–Abr",4:"Mar–Abr",5:"Mai–Jun",6:"Mai–Jun",
    7:"Jul–Ago",8:"Jul–Ago",9:"Set–Out",10:"Set–Out",11:"Nov–Dez",12:"Nov–Dez"
}
def _format_brl(v): return f"R$ {v:,.2f}".replace(",", "_").replace(".", ",").replace("_",".")

def carregar_bases():
    base_dir = Path(__file__).parent
    df_erp = pd.read_excel(base_dir/"total_indicadores.xlsx", sheet_name="Planilha1", dtype={"INSUMO_CDG":"string"})
    df_bas = pd.read_excel(base_dir/"MateriaisBasicos.xlsx", sheet_name="Final", usecols=["Código"], dtype={"Código":"string"}).drop_duplicates()

    df_erp["REQ_DATA"] = pd.to_datetime(df_erp["REQ_DATA"], errors="coerce")
    df_erp["OF_DATA"]  = pd.to_datetime(df_erp["OF_DATA"],  errors="coerce")

    cod_basicos = set(df_bas["Código"].dropna())
    if "TIPO_MATERIAL" not in df_erp.columns:
        pos = df_erp.columns.get_loc("INSUMO_CDG")+1
        df_erp.insert(pos, "TIPO_MATERIAL", np.where(df_erp["INSUMO_CDG"].isin(cod_basicos), "BÁSICO", "ESPECÍFICO"))
    return df_erp

def fornecedor_top_por_uf(df, anos=10, ufs=("RJ","SP")):
    df = df.copy()
    df["OF_DATA_DT"] = pd.to_datetime(df["OF_DATA"], errors="coerce")
    limite = pd.Timestamp.today() - pd.DateOffset(years=anos)
    base = df[df["OF_DATA_DT"] >= limite]
    out = []
    for uf in ufs:
        top = (base[base["FORNECEDOR_UF"]==uf]
               .groupby(["FORNECEDOR_CDG","FORNECEDOR_DESC"], as_index=False)["PRCTTL_INSUMO"]
               .sum().sort_values("PRCTTL_INSUMO", ascending=False).head(1))
        if not top.empty:
            out.append({"UF": uf,
                        "FORNECEDOR_CDG": top.iloc[0]["FORNECEDOR_CDG"],
                        "FORNECEDOR_DESC": top.iloc[0]["FORNECEDOR_DESC"],
                        "VALOR": float(top.iloc[0]["PRCTTL_INSUMO"])})
    return pd.DataFrame(out)

def maior_ordem_fornecimento(df):
    df = df.copy()
    df["OF_DATA_DT"] = pd.to_datetime(df["OF_DATA"], errors="coerce")
    g = (df.groupby("OF_CDG")
         .agg(VALOR_TOTAL=("PRCTTL_INSUMO","sum"),
              EMPRD_DESC=("EMPRD_DESC","first"),
              FORNECEDOR_DESC=("FORNECEDOR_DESC","first"),
              DATA_OF=("OF_DATA_DT","first"),
              INSUMOS=("INSUMO_DESC", lambda x: ", ".join(sorted(set(x)))),
              TOTAL_ITENS=("INSUMO_CDG","nunique"))
         .reset_index().sort_values("VALOR_TOTAL", ascending=False).head(1))
    if g.empty: return g
    g["DATA_OF"] = pd.to_datetime(g["DATA_OF"]).dt.strftime("%d/%m/%Y")
    return g

def menor_ordem_fornecimento(df):
    df = df.copy()
    df["OF_DATA_DT"] = pd.to_datetime(df["OF_DATA"], errors="coerce")
    g = (df.groupby("OF_CDG")
         .agg(VALOR_TOTAL=("PRCTTL_INSUMO","sum"),
              EMPRD_DESC=("EMPRD_DESC","first"),
              FORNECEDOR_DESC=("FORNECEDOR_DESC","first"),
              DATA_OF=("OF_DATA_DT","first"),
              INSUMOS=("INSUMO_DESC", lambda x: ", ".join(sorted(set(x)))),
              TOTAL_ITENS=("INSUMO_CDG","nunique"))
         .reset_index().sort_values("VALOR_TOTAL", ascending=True).head(1))
    if g.empty: return g
    g["DATA_OF"] = pd.to_datetime(g["DATA_OF"]).dt.strftime("%d/%m/%Y")
    return g

def valor_medio_por_of(df):
    tot = df.groupby("OF_CDG")["PRCTTL_INSUMO"].sum().reset_index(name="VALOR_TOTAL_OF")
    media = float(tot["VALOR_TOTAL_OF"].mean()) if not tot.empty else 0.0
    return media, tot

def percentual_ofs_basicas_ultimo_ano(df):
    df = df.copy(); df["OF_DATA_DT"] = pd.to_datetime(df["OF_DATA"], errors="coerce")
    limite = pd.Timestamp.today() - pd.DateOffset(years=1)
    base = df[df["OF_DATA_DT"]>=limite].copy()
    if base.empty: return 0.0, pd.DataFrame(columns=["OF_CDG","TIPO_OF"])
    grp = (base.groupby("OF_CDG")["TIPO_MATERIAL"].apply(lambda x:"BÁSICO" if "BÁSICO" in set(x) else "ESPECÍFICO")
           .reset_index(name="TIPO_OF"))
    total = len(grp); bas = int((grp["TIPO_OF"]=="BÁSICO").sum())
    pct = (bas/total*100.0) if total else 0.0
    return pct, grp

def periodo_maior_volume_bimestre(df, anos=10):
    df = df.copy(); df["OF_DATA_DT"] = pd.to_datetime(df["OF_DATA"], errors="coerce")
    limite = pd.Timestamp.today() - pd.DateOffset(years=anos)
    base = df[df["OF_DATA_DT"]>=limite].copy()
    if base.empty: return pd.DataFrame(columns=["BIMESTRE_ROTULO","VALOR_TOTAL","QTDE_OFS"])
    base["BIMESTRE_ROTULO"] = base["OF_DATA_DT"].dt.month.map(_BI_LABEL)
    return (base.groupby("BIMESTRE_ROTULO")
            .agg(VALOR_TOTAL=("PRCTTL_INSUMO","sum"), QTDE_OFS=("OF_CDG","nunique"))
            .reset_index().sort_values("VALOR_TOTAL", ascending=False))

def mes_maior_volume_ultimo_ano(df):
    df = df.copy(); df["OF_DATA_DT"] = pd.to_datetime(df["OF_DATA"], errors="coerce")
    limite = pd.Timestamp.today() - pd.DateOffset(years=1)
    base = df[df["OF_DATA_DT"]>=limite].copy()
    if base.empty: return pd.DataFrame(columns=["ANO_MES","VALOR_TOTAL"])
    base["ANO_MES"] = base["OF_DATA_DT"].dt.to_period("M")
    return (base.groupby("ANO_MES")["PRCTTL_INSUMO"].sum()
            .reset_index(name="VALOR_TOTAL")
            .sort_values("VALOR_TOTAL", ascending=False))
