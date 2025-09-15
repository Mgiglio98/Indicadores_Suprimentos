import pandas as pd
import altair as alt
import streamlit as st

def grafico_anomalias_por_mes_com_comentarios(df):
    if df.empty:
        st.info("Sem dados de anomalias.")
        return

    # --- Prepara dados ---
    df["ANO_MES"] = df["Data Anomalia"].dt.to_period("M").astype(str)

    # Contagem de anomalias por mês
    contagem = df.groupby("ANO_MES").size().reset_index(name="TOTAL_ANOMALIAS")

    # --- Gráfico de barras ---
    chart = (
        alt.Chart(contagem)
        .mark_bar()
        .encode(
            x=alt.X("ANO_MES:N", title="Mês", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("TOTAL_ANOMALIAS:Q", title="Total de Anomalias"),
            tooltip=["ANO_MES", "TOTAL_ANOMALIAS"],
        )
        .properties(title="Total de Anomalias por Mês", height=300)
    )

    st.altair_chart(chart, use_container_width=True)

    # --- Comentários abaixo ---
    st.markdown("### 📝 Detalhes por mês")
    for mes in contagem["ANO_MES"]:
        empreendimentos_mes = (
            df.loc[df["ANO_MES"] == mes, "Empreendimento"]
            .dropna()
            .astype(str)
            .unique()
        )

        if len(empreendimentos_mes) > 0:
            lista = ", ".join(sorted(empreendimentos_mes))
            st.markdown(f"🔎 **{mes}** — Obras com anomalias: {lista}")
        else:
            st.markdown(f"🔎 **{mes}** — Sem anomalias registradas.")