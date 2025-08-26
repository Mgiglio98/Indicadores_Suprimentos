import pandas as pd
import numpy as np

ARQ_ERP = r"C:\Users\Matheus\Desktop\RelatoriosSiecon\total_indicadores.xlsx"
ABA_ERP = "Planilha1"
ARQ_BASICOS = r"C:\Users\Matheus\Desktop\AutomatizaReq\MateriaisBasicos.xlsx"
ABA_BASICOS = "Final"
COL_ERP = "INSUMO_CDG"
COL_BASIC = "Código"

hoje = pd.Timestamp.today()
limite_10_anos = hoje - pd.DateOffset(years=10)
limite_2_anos = hoje - pd.DateOffset(years=2)
limite_1_ano = hoje - pd.DateOffset(years=1)

_BI_LABEL = {
    1: "Jan–Fev", 2: "Jan–Fev",
    3: "Mar–Abr", 4: "Mar–Abr",
    5: "Mai–Jun", 6: "Mai–Jun",
    7: "Jul–Ago", 8: "Jul–Ago",
    9: "Set–Out", 10: "Set–Out",
    11: "Nov–Dez", 12: "Nov–Dez"
}

# Leitura das planilhas
df_erp = pd.read_excel(ARQ_ERP, sheet_name=ABA_ERP, dtype={COL_ERP: "string"})
df_bas = pd.read_excel(ARQ_BASICOS, sheet_name=ABA_BASICOS, usecols=[COL_BASIC], dtype={COL_BASIC: "string"}).drop_duplicates()

df_erp["REQ_DATA"] = pd.to_datetime(df_erp["REQ_DATA"], errors="coerce").dt.strftime("%d/%m/%Y")
df_erp["OF_DATA"] = pd.to_datetime(df_erp["OF_DATA"], errors="coerce").dt.strftime("%d/%m/%Y")

# Conjunto de códigos básicos
cod_basicos = set(df_bas[COL_BASIC].dropna())

# Criar coluna TIPO_MATERIAL e inserir depois da coluna INSUMO_CDG
mask_basico = df_erp[COL_ERP].isin(cod_basicos)
col_nova = np.where(mask_basico, "BÁSICO", "ESPECÍFICO")
pos = df_erp.columns.get_loc(COL_ERP) + 1
df_erp.insert(pos, "TIPO_MATERIAL", col_nova)

def fornecedor_top_10_anos_por_uf(df):
    df = df.copy()
    df["OF_DATA_DT"] = pd.to_datetime(df["OF_DATA"], format="%d/%m/%Y", errors="coerce")
    df_filtrado = df[df["OF_DATA_DT"] >= limite_10_anos]
    for uf in ["RJ", "SP"]:
        df_uf = df_filtrado[df_filtrado["FORNECEDOR_UF"] == uf]
        top = (
            df_uf.groupby("FORNECEDOR_DESC", as_index=False)["PRCTTL_INSUMO"]
            .sum()
            .sort_values(by="PRCTTL_INSUMO", ascending=False)
            .head(1))
        fornecedor = top.iloc[0]["FORNECEDOR_DESC"]
        valor = top.iloc[0]["PRCTTL_INSUMO"]
        print(f"Nos últimos 10 anos para {uf}, o fornecedor com maior volume de compras foi '{fornecedor}', com R$ {valor:,.2f}.")

def fornecedor_top_2_anos_por_uf(df):
    df = df.copy()
    df["OF_DATA_DT"] = pd.to_datetime(df["OF_DATA"], format="%d/%m/%Y", errors="coerce")
    df_filtrado = df[df["OF_DATA_DT"] >= limite_2_anos]
    for uf in ["RJ", "SP"]:
        df_uf = df_filtrado[df_filtrado["FORNECEDOR_UF"] == uf]
        top = (
            df_uf.groupby("FORNECEDOR_DESC", as_index=False)["PRCTTL_INSUMO"]
            .sum()
            .sort_values(by="PRCTTL_INSUMO", ascending=False)
            .head(1))
        fornecedor = top.iloc[0]["FORNECEDOR_DESC"]
        valor = top.iloc[0]["PRCTTL_INSUMO"]
        print(f"Nos últimos 2 anos para {uf}, o fornecedor com maior volume de compras foi '{fornecedor}', com R$ {valor:,.2f}.")

def maior_ordem_fornecimento(df):
    df = df.copy()
    df["OF_DATA_DT"] = pd.to_datetime(df["OF_DATA"], format="%d/%m/%Y", errors="coerce")
    grupo = (
        df.groupby("OF_CDG")
        .agg({
            "PRCTTL_INSUMO": "sum",
            "EMPRD_DESC": "first",
            "FORNECEDOR_DESC": "first",
            "OF_DATA_DT": "first",
            "INSUMO_DESC": lambda x: ", ".join(sorted(set(x))),
            "INSUMO_CDG": "count"
        })
        .rename(columns={
            "PRCTTL_INSUMO": "VALOR_TOTAL",
            "INSUMO_DESC": "INSUMOS",
            "INSUMO_CDG": "TOTAL_ITENS",
            "OF_DATA_DT": "DATA_OF"
        })
        .reset_index())
    maior_of = grupo.sort_values(by="VALOR_TOTAL", ascending=False).head(1)
    if pd.notnull(maior_of.iloc[0]["DATA_OF"]):
        data_formatada = maior_of.iloc[0]["DATA_OF"].strftime("%d/%m/%Y")
        maior_of.at[maior_of.index[0], "DATA_OF"] = data_formatada
    return maior_of

def menor_ordem_fornecimento(df):
    df = df.copy()
    df["OF_DATA_DT"] = pd.to_datetime(df["OF_DATA"], format="%d/%m/%Y", errors="coerce")
    grupo = (
        df.groupby("OF_CDG")
        .agg({
            "PRCTTL_INSUMO": "sum",
            "EMPRD_DESC": "first",
            "FORNECEDOR_DESC": "first",
            "OF_DATA_DT": "first",
            "INSUMO_DESC": lambda x: ", ".join(sorted(set(x))),
            "INSUMO_CDG": "count"
        })
        .rename(columns={
            "PRCTTL_INSUMO": "VALOR_TOTAL",
            "INSUMO_DESC": "INSUMOS",
            "INSUMO_CDG": "TOTAL_ITENS",
            "OF_DATA_DT": "DATA_OF"
        })
        .reset_index())
    menor_of = grupo.sort_values(by="VALOR_TOTAL", ascending=True).head(1)
    if pd.notnull(menor_of.iloc[0]["DATA_OF"]):
        data_formatada = menor_of.iloc[0]["DATA_OF"].strftime("%d/%m/%Y")
        menor_of.at[menor_of.index[0], "DATA_OF"] = data_formatada
    return menor_of

def valor_medio_por_of(df):
    df = df.copy()
    df["OF_DATA_DT"] = pd.to_datetime(df["OF_DATA"], format="%d/%m/%Y", errors="coerce")
    total_por_of = (
        df.groupby("OF_CDG")["PRCTTL_INSUMO"]
        .sum()
        .reset_index(name="VALOR_TOTAL_OF"))
    valor_medio = total_por_of["VALOR_TOTAL_OF"].mean()
    print(f"Valor médio das compras por OF: R$ {valor_medio:,.2f}")
    return valor_medio, total_por_of

def percentual_ofs_basicas_ultimo_ano(df):
    df = df.copy()
    df["OF_DATA_DT"] = pd.to_datetime(df["OF_DATA"], format="%d/%m/%Y", errors="coerce")
    df_periodo = df[df["OF_DATA_DT"] >= limite_1_ano]
    grupo = (
        df_periodo.groupby("OF_CDG")["TIPO_MATERIAL"]
        .apply(lambda x: "BÁSICO" if "BÁSICO" in set(x) else "ESPECÍFICO")
        .reset_index(name="TIPO_OF"))
    total = len(grupo)
    basicos = (grupo["TIPO_OF"] == "BÁSICO").sum()
    percentual = (basicos / total) * 100
    print(f"📊 No último ano, {percentual:.2f}% das OFs foram de materiais básicos")
    return percentual, grupo

def _format_brl(v):
    return f"R$ {v:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")

def periodo_maior_volume_bimestre(df, imprimir=True):
    df = df.copy()
    df["OF_DATA_DT"] = pd.to_datetime(df["OF_DATA"], format="%d/%m/%Y", errors="coerce")
    recorte = df[df["OF_DATA_DT"] >= limite_10_anos].copy()
    recorte["BIMESTRE_ROTULO"] = recorte["OF_DATA_DT"].dt.month.map(_BI_LABEL)
    ranking = (
        recorte.groupby("BIMESTRE_ROTULO")
               .agg(VALOR_TOTAL=("PRCTTL_INSUMO", "sum"), QTDE_OFS=("OF_CDG", "nunique"))
               .reset_index()
               .sort_values("VALOR_TOTAL", ascending=False))
    if imprimir and not ranking.empty:
        top = ranking.iloc[0]
        print(f"🏆 Bimestre com maior volume: "f"{top['BIMESTRE_ROTULO']} ({_format_brl(top['VALOR_TOTAL'])}) — {int(top['QTDE_OFS'])} OFs")
    return ranking

def mes_maior_volume_ultimo_ano(df, imprimir=True):
    df = df.copy()
    df["OF_DATA_DT"] = pd.to_datetime(df["OF_DATA"], format="%d/%m/%Y", errors="coerce")
    recorte = df[df["OF_DATA_DT"] >= limite_1_ano].copy()
    recorte["ANO_MES"] = recorte["OF_DATA_DT"].dt.to_period("M")
    tot_por_mes = (
        recorte.groupby("ANO_MES")["PRCTTL_INSUMO"]
               .sum()
               .reset_index(name="VALOR_TOTAL")
               .sort_values("VALOR_TOTAL", ascending=False))
    if imprimir and not tot_por_mes.empty:
        topo = tot_por_mes.iloc[0]
        mes_pt = topo["ANO_MES"].strftime("%B/%Y").capitalize()
        print(f"📅 Mês de maior volume (último ano): {mes_pt} ({_format_brl(topo['VALOR_TOTAL'])})")
    return tot_por_mes

fornecedor_top_10_anos_por_uf(df_erp)
fornecedor_top_2_anos_por_uf(df_erp)
print(maior_ordem_fornecimento(df_erp))
print(menor_ordem_fornecimento(df_erp))
valor_medio_por_of(df_erp)
percentual_ofs_basicas_ultimo_ano(df_erp)
periodo_maior_volume_bimestre(df_erp)
mes_maior_volume_ultimo_ano(df_erp)