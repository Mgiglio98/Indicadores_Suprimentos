# Tratamento_Anomalias.py
import pandas as pd
import altair as alt
from pathlib import Path

def carregar_anomalias():
    """
    Lê os arquivos de anomalias e empreendimentos do diretório atual.
    """
    base_dir = Path(__file__).parent
    csv_path = base_dir / "Controle_Anomalias(Controle).csv"
    xlsx_path = base_dir / "Empreendimentos.xlsx"

    # Leitura e tratamento
    df = pd.read_csv(csv_path, sep=";")
    df["Data Anomalia"] = pd.to_datetime(df["Data Anomalia"], dayfirst=True, errors="coerce")
    df_emp = pd.read_excel(xlsx_path)

    # Faz merge para enriquecer os dados
    df_merged = df.merge(df_emp, how="left", left_on="Empreendimento", right_on="EMPREENDIMENTO")

    return df_merged


def grafico_anomalias_por_mes_com_comentarios(df):
    if df.empty:
        return None, []

    df = df.copy()
    df["ANO_MES"] = df["Data Anomalia"].dt.to_period("M").astype(str)
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

    # Gera os comentários para exibir no Streamlit
    comentarios = []
    for mes in contagem["ANO_MES"]:
        empreendimentos_mes = (
            df.loc[df["ANO_MES"] == mes, "Empreendimento"]
            .dropna()
            .astype(str)
            .unique()
        )
        if len(empreendimentos_mes) > 0:
            lista = ", ".join(sorted(empreendimentos_mes))
            comentarios.append(f"🔎 **{mes}** — Obras com anomalias: {lista}")
        else:
            comentarios.append(f"🔎 **{mes}** — Sem anomalias registradas.")

    return chart, comentarios
