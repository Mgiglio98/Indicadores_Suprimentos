# visualizacoes_recorrencia.py

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

# Paleta "corporativa" Osborne
OSBORNE_ORANGE = "#F58220"
OSBORNE_DARK = "#3A3A3A"
OSBORNE_LIGHT = "#D9D9D9"


def set_osborne_style():
    """Configura estilo padrão dos gráficos."""
    plt.rcParams.update({
        "figure.figsize": (10, 6),
        "axes.facecolor": "white",
        "axes.edgecolor": OSBORNE_DARK,
        "axes.labelcolor": OSBORNE_DARK,
        "xtick.color": OSBORNE_DARK,
        "ytick.color": OSBORNE_DARK,
        "text.color": OSBORNE_DARK,
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "axes.grid": True,
        "grid.color": OSBORNE_LIGHT,
        "grid.linestyle": "--",
        "grid.alpha": 0.4,
    })


# -------------------------------------------------------------------
# 1) Recorrência mensal (basicos_reqs_mes)
# -------------------------------------------------------------------
def plot_top_itens_recorrencia_mensal(df_mes: pd.DataFrame, top_n: int = 15):
    """
    df_mes: saída de basicos_reqs_mes
      EMPRD | EMPRD_DESC | ANO_MES | INSUMO_CDG | INSUMO_DESC | QTD_REQS_MES
    """
    set_osborne_style()
    fig, ax = plt.subplots()

    if df_mes is None or df_mes.empty:
        ax.text(0.5, 0.5, "Sem dados de recorrência mensal.",
                ha="center", va="center", fontsize=11)
        ax.axis("off")
        return fig

    # Soma recorrência por item (independente de obra/mês)
    agg = (
        df_mes.groupby(["INSUMO_CDG", "INSUMO_DESC"])["QTD_REQS_MES"]
        .sum()
        .reset_index()
        .sort_values("QTD_REQS_MES", ascending=False)
        .head(int(top_n))
    )

    if agg.empty:
        ax.text(0.5, 0.5, "Nenhum item com recorrência mensal atingindo o critério.",
                ha="center", va="center", fontsize=11)
        ax.axis("off")
        return fig

    agg = agg.sort_values("QTD_REQS_MES", ascending=True)  # para barra horizontal

    ax.barh(agg["INSUMO_DESC"], agg["QTD_REQS_MES"], color=OSBORNE_ORANGE)
    ax.set_xlabel("Quantidade de REQs com o item (mês)")
    ax.set_ylabel("Item básico")
    ax.set_title("Top itens básicos por recorrência mensal (soma geral)")

    for i, v in enumerate(agg["QTD_REQS_MES"]):
        ax.text(v + 0.2, i, str(int(v)), va="center", fontsize=9)

    fig.tight_layout()
    return fig


def plot_recorrencia_mensal_por_obra(df_mes: pd.DataFrame, obra: str | int):
    """
    Filtra df_mes para uma obra específica e mostra a recorrência por item.
    """
    set_osborne_style()
    fig, ax = plt.subplots()

    if df_mes is None or df_mes.empty:
        ax.text(0.5, 0.5, "Sem dados de recorrência mensal.",
                ha="center", va="center", fontsize=11)
        ax.axis("off")
        return fig

    base = df_mes[df_mes["EMPRD"] == obra]
    if base.empty:
        ax.text(0.5, 0.5, f"Sem dados para o empreendimento {obra}.",
                ha="center", va="center", fontsize=11)
        ax.axis("off")
        return fig

    # Nome da obra
    emprd_desc = base["EMPRD_DESC"].dropna().astype(str).iloc[0]

    # Soma por item
    agg = (
        base.groupby(["INSUMO_CDG", "INSUMO_DESC"])["QTD_REQS_MES"]
        .sum()
        .reset_index()
        .sort_values("QTD_REQS_MES", ascending=True)
    )

    ax.barh(agg["INSUMO_DESC"], agg["QTD_REQS_MES"], color=OSBORNE_ORANGE)
    ax.set_xlabel("Quantidade de REQs com o item (no ano)")
    ax.set_ylabel("Item básico")
    ax.set_title(f"Recorrência mensal de básicos - Obra {obra} ({emprd_desc})")

    for i, v in enumerate(agg["QTD_REQS_MES"]):
        ax.text(v + 0.1, i, str(int(v)), va="center", fontsize=9)

    fig.tight_layout()
    return fig


# -------------------------------------------------------------------
# 2) Requisições subsequentes (basicos_reqs_subsequentes)
# -------------------------------------------------------------------
def plot_itens_reqs_subsequentes(df_subseq: pd.DataFrame, top_n: int = 15):
    """
    df_subseq: saída de basicos_reqs_subsequentes
      EMPRD, EMPRD_DESC, INSUMO_CDG, INSUMO_DESC,
      TOTAL_REQS_ITEM, N_LIGACOES_SUBSEQ, MAX_SEQ_SUBSEQ
    """
    set_osborne_style()
    fig, ax = plt.subplots()

    if df_subseq is None or df_subseq.empty:
        ax.text(0.5, 0.5, "Sem dados de REQs subsequentes.",
                ha="center", va="center", fontsize=11)
        ax.axis("off")
        return fig

    # Ordenar pelos que mais têm ligações subsequentes
    agg = (
        df_subseq.copy()
        .sort_values(["N_LIGACOES_SUBSEQ", "MAX_SEQ_SUBSEQ"], ascending=[False, False])
        .head(int(top_n))
    )

    labels = agg["INSUMO_DESC"] + " | " + agg["EMPRD"].astype(str)
    y = np.arange(len(labels))

    ax.barh(y, agg["N_LIGACOES_SUBSEQ"], color=OSBORNE_ORANGE)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Nº de ligações subsequentes (REQ n -> REQ n+1)")
    ax.set_title("Itens básicos que aparecem em REQs subsequentes")

    for i, v in enumerate(agg["N_LIGACOES_SUBSEQ"]):
        ax.text(v + 0.1, i, f"{int(v)} | seq máx: {int(agg.iloc[i]['MAX_SEQ_SUBSEQ'])}",
                va="center", fontsize=8)

    fig.tight_layout()
    return fig


# -------------------------------------------------------------------
# 3) Recorrência semanal por obra (basicos_semanal_por_obra)
# -------------------------------------------------------------------
def plot_recorrencia_semanal_heatmap(df_semana: pd.DataFrame, top_itens: int = 10, top_obras: int = 10):
    """
    df_semana: saída de basicos_semanal_por_obra
      EMPRD | EMPRD_DESC | INSUMO_CDG | INSUMO_DESC
      | SEMANAS_DISTINTAS | MAX_SEQ_SEMANAS

    Cria um heatmap obra x item (limitado por top_itens e top_obras).
    """
    set_osborne_style()
    fig, ax = plt.subplots()

    if df_semana is None or df_semana.empty:
        ax.text(0.5, 0.5, "Sem dados de recorrência semanal.",
                ha="center", va="center", fontsize=11)
        ax.axis("off")
        return fig

    # rank itens por semanas distintas (global)
    itens_top = (
        df_semana.groupby(["INSUMO_CDG", "INSUMO_DESC"])["SEMANAS_DISTINTAS"]
        .sum()
        .reset_index()
        .sort_values("SEMANAS_DISTINTAS", ascending=False)
        .head(int(top_itens))
    )["INSUMO_CDG"].tolist()

    # rank obras por nº itens semanais
    obras_top = (
        df_semana[df_semana["INSUMO_CDG"].isin(itens_top)]
        .groupby(["EMPRD", "EMPRD_DESC"])["SEMANAS_DISTINTAS"]
        .sum()
        .reset_index()
        .sort_values("SEMANAS_DISTINTAS", ascending=False)
        .head(int(top_obras))
    )["EMPRD"].tolist()

    base = df_semana[
        df_semana["INSUMO_CDG"].isin(itens_top) &
        df_semana["EMPRD"].isin(obras_top)
    ].copy()

    if base.empty:
        ax.text(0.5, 0.5, "Sem interseção de itens/obras dentro dos tops definidos.",
                ha="center", va="center", fontsize=11)
        ax.axis("off")
        return fig

    # pivot obra x item
    pivot = base.pivot_table(
        index="EMPRD",
        columns="INSUMO_DESC",
        values="SEMANAS_DISTINTAS",
        aggfunc="sum",
        fill_value=0
    )

    obras_labels = []
    for emprd in pivot.index:
        desc = base.loc[base["EMPRD"] == emprd, "EMPRD_DESC"].dropna().astype(str).iloc[0]
        obras_labels.append(f"{emprd} - {desc.split()[0]}")

    im = ax.imshow(pivot.values, aspect="auto", cmap="Oranges")

    ax.set_xticks(np.arange(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns, rotation=45, ha="right")
    ax.set_yticks(np.arange(len(pivot.index)))
    ax.set_yticklabels(obras_labels)

    ax.set_title("Recorrência semanal de básicos (semanas distintas por obra x item)")
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("Nº de semanas com pedidos")

    fig.tight_layout()
    return fig


# -------------------------------------------------------------------
# 4) Intervalo médio entre pedidos (intervalo_medio_entre_pedidos)
# -------------------------------------------------------------------
def plot_intervalo_medio_scatter(df_int: pd.DataFrame):
    """
    df_int: saída de intervalo_medio_entre_pedidos_basicos
      EMPRD, EMPRD_DESC, INSUMO_CDG, INSUMO_DESC,
      TOTAL_REQS_ITEM, INTERVALO_MEDIO_DIAS, ...
    """
    set_osborne_style()
    fig, ax = plt.subplots()

    if df_int is None or df_int.empty:
        ax.text(0.5, 0.5, "Sem dados de intervalo médio entre pedidos.",
                ha="center", va="center", fontsize=11)
        ax.axis("off")
        return fig

    x = df_int["INTERVALO_MEDIO_DIAS"]
    y = df_int["TOTAL_REQS_ITEM"]

    ax.scatter(x, y, color=OSBORNE_ORANGE, alpha=0.7, edgecolors=OSBORNE_DARK)

    ax.set_xlabel("Intervalo médio entre pedidos (dias)")
    ax.set_ylabel("Total de REQs com o item (na obra)")
    ax.set_title("Intensidade de uso x Intervalo médio entre pedidos (básicos)")

    # linha de referência (ex.: 10 dias)
    ax.axvline(10, color=OSBORNE_LIGHT, linestyle="--")
    ax.text(10, ax.get_ylim()[1], "  10 dias", va="top", fontsize=8)

    fig.tight_layout()
    return fig


# -------------------------------------------------------------------
# 5) Itens pingados (itens pequenas qtds alta frequência)
# -------------------------------------------------------------------
def plot_itens_pingados(df_pingados: pd.DataFrame, top_n: int = 15):
    """
    df_pingados: saída de itens_basicos_pequenas_qtds_alta_frequencia
      INSUMO_CDG | INSUMO_DESC | pedidos | media_qtd | qtd_total | vezes_distintas
    """
    set_osborne_style()
    fig, ax = plt.subplots()

    if df_pingados is None or df_pingados.empty:
        ax.text(0.5, 0.5, "Sem itens pingados (alta frequência + baixa quantidade).",
                ha="center", va="center", fontsize=11)
        ax.axis("off")
        return fig

    base = (
        df_pingados.copy()
        .sort_values("pedidos", ascending=False)
        .head(int(top_n))
        .sort_values("pedidos", ascending=True)
    )

    ax.barh(base["INSUMO_DESC"], base["pedidos"], color=OSBORNE_ORANGE)
    ax.set_xlabel("Nº de REQs com o item")
    ax.set_ylabel("Item básico")
    ax.set_title("Itens básicos 'pingados' (alta frequência, baixa quantidade média)")

    for i, (n_ped, m_qtd) in enumerate(zip(base["pedidos"], base["media_qtd"])):
        ax.text(n_ped + 0.1, i, f"{int(n_ped)} REQs | média {m_qtd:.2f}", va="center", fontsize=8)

    fig.tight_layout()
    return fig