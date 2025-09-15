# Tratamento_Anomalias.py
import streamlit as st
import pandas as pd
import altair as alt
from pathlib import Path

def carregar_anomalias():
    base_dir = Path(__file__).parent
    csv_path = base_dir / "Controle_Anomalias(Controle).csv"
    xlsx_path = base_dir / "Empreendimentos.xlsx"

    df = pd.read_csv(csv_path, sep=";")
    df["Empreendimento"] = df["Empreendimento"].astype(str).str.strip()
    df["Data Anomalia"] = pd.to_datetime(df["Data Anomalia"], dayfirst=True, errors="coerce")

    df_emp = pd.read_excel(xlsx_path)
    df_emp["EMP_CODIGO"] = df_emp["EMPREENDIMENTO"].astype(str).str.split("-").str[0].str.strip()

    # Se não houver "-", cria NOME_CURTO igual ao código
    df_emp["NOME_CURTO"] = (
        df_emp["EMPREENDIMENTO"]
        .astype(str)
        .apply(lambda x: x.split("-")[1].strip().split()[0] if "-" in x else x.strip())
    )

    df_merged = df.merge(df_emp, how="left", left_on="Empreendimento", right_on="EMP_CODIGO")

    # Garante que NOME_CURTO existe mesmo se merge não achar correspondência
    if "NOME_CURTO" not in df_merged.columns:
        df_merged["NOME_CURTO"] = df_merged["Empreendimento"]

    return df_merged
    
def grafico_anomalias_por_mes_com_comentarios(df):
    df = df.copy()
    df["ANO_MES"] = df["Data Anomalia"].dt.to_period("M").astype(str)

    if "NOME_CURTO" not in df.columns:
        df["NOME_CURTO"] = df["Empreendimento"]

    contagem = df.groupby("ANO_MES").size().reset_index(name="TOTAL_ANOMALIAS")

    chart = (
        alt.Chart(contagem)
        .mark_bar()
        .encode(
            x=alt.X("ANO_MES:N", title="Mês", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("TOTAL_ANOMALIAS:Q", title="Total de Anomalias"),
            tooltip=["ANO_MES", "TOTAL_ANOMALIAS"]
        )
        .properties(title="Total de Anomalias por Mês", height=300)
    )

    comentarios = []
    for mes in contagem["ANO_MES"]:
        empreendimentos_mes = (
            df.loc[df["ANO_MES"] == mes, ["Empreendimento", "NOME_CURTO"]]
            .dropna()
            .drop_duplicates()
        )

        if len(empreendimentos_mes) > 0:
            lista = ", ".join(
                empreendimentos_mes.apply(lambda x: f"{x['Empreendimento']} ({x['NOME_CURTO']})", axis=1)
            )
            comentarios.append(f"🔎 **{mes}** — Obras com anomalias: {lista}")
        else:
            comentarios.append(f"🔎 **{mes}** — Sem anomalias registradas.")

    return chart, comentarios
