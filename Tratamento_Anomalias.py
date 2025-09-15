# Tratamento_Anomalias.py
import streamlit as st
import pandas as pd
import altair as alt
from pathlib import Path

def carregar_anomalias():
    base_dir = Path(__file__).parent
    csv_path = base_dir / "Controle_Anomalias(Controle).csv"
    xlsx_path = base_dir / "Empreendimentos.xlsx"

    # --- CSV de anomalias ---
    df = pd.read_csv(csv_path, sep=";")
    if "Empreendimento" not in df.columns or "Data Anomalia" not in df.columns:
        raise KeyError(f"Colunas esperadas ('Empreendimento', 'Data Anomalia') não encontradas. Encontradas: {list(df.columns)}")

    df["Empreendimento"] = df["Empreendimento"].astype(str).str.strip()
    df["Data Anomalia"] = pd.to_datetime(df["Data Anomalia"], dayfirst=True, errors="coerce")

    # --- Excel de empreendimentos ---
    df_emp = pd.read_excel(xlsx_path)
    if "EMPREENDIMENTO" not in df_emp.columns:
        raise KeyError(f"Coluna 'EMPREENDIMENTO' não encontrada no Excel. Colunas: {list(df_emp.columns)}")

    # Quebra o texto "2316 - MARCO" em código e nome
    df_emp["EMP_CODIGO"] = df_emp["EMPREENDIMENTO"].astype(str).str.split("-").str[0].str.strip()
    df_emp["NOME_CURTO"] = df_emp["EMPREENDIMENTO"].astype(str).str.split("-").str[1].str.strip().str.split().str[0]

    # Merge usando EMP_CODIGO
    df_merged = df.merge(df_emp, how="left", left_on="Empreendimento", right_on="EMP_CODIGO")
    return df_merged
    
def grafico_anomalias_por_mes_com_comentarios(df):
    if df.empty:
        st.info("Sem dados de anomalias.")
        return

    df["ANO_MES"] = df["Data Anomalia"].dt.to_period("M").astype(str)
    contagem = df.groupby("ANO_MES").size().reset_index(name="TOTAL_ANOMALIAS")

    # Gráfico de barras
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

    st.altair_chart(chart, use_container_width=True)

    # Comentários com nomes curtos
    st.markdown("### 📝 Detalhes por mês")
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
            st.markdown(f"🔎 **{mes}** — Obras com anomalias: {lista}")
        else:
            st.markdown(f"🔎 **{mes}** — Sem anomalias registradas.")

