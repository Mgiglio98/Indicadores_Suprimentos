import pandas as pd
import numpy as np
from typing import Optional, Dict, Any


# ============================================================
# 1) Função base: filtrar só BÁSICOS em um ano
# ============================================================
def _filtrar_basicos_ano(df: pd.DataFrame, ano: Optional[int] = None) -> pd.DataFrame:
    base = df.copy()

    base["REQ_DATA"] = pd.to_datetime(base.get("REQ_DATA"), errors="coerce")

    if "TIPO_MATERIAL" in base.columns:
        base = base[base["TIPO_MATERIAL"].astype(str).str.upper() == "BÁSICO"]
    # Se não tiver TIPO_MATERIAL (caso raro), deixa passar tudo

    base = base.dropna(subset=["REQ_DATA"])

    if ano is not None:
        base = base[base["REQ_DATA"].dt.year == int(ano)]

    return base


def _mapa_empr_desc(base: pd.DataFrame) -> pd.DataFrame:
    if "EMPRD" not in base.columns:
        return pd.DataFrame(columns=["EMPRD", "EMPRD_DESC"])

    if "EMPRD_DESC" in base.columns:
        nomes = (
            base.groupby("EMPRD")["EMPRD_DESC"]
            .agg(lambda s: s.dropna().astype(str).iloc[0] if len(s.dropna()) > 0 else "")
            .reset_index()
        )
    else:
        nomes = base[["EMPRD"]].drop_duplicates()
        nomes["EMPRD_DESC"] = nomes["EMPRD"].astype(str)

    return nomes


def _mapa_insumo_desc(base: pd.DataFrame) -> pd.DataFrame:
    if "INSUMO_CDG" not in base.columns:
        return pd.DataFrame(columns=["INSUMO_CDG", "INSUMO_DESC"])

    if "INSUMO_DESC" in base.columns:
        nomes = (
            base.groupby("INSUMO_CDG")["INSUMO_DESC"]
            .agg(lambda s: s.dropna().astype(str).iloc[0] if len(s.dropna()) > 0 else "")
            .reset_index()
        )
    else:
        nomes = base[["INSUMO_CDG"]].drop_duplicates()
        nomes["INSUMO_DESC"] = nomes["INSUMO_CDG"].astype(str)

    return nomes


# ============================================================
# 2) Básicos com 2+ requisições no mesmo mês
# ============================================================
def basicos_reqs_mes(
    df: pd.DataFrame,
    ano: Optional[int] = None,
    min_reqs_mes: int = 2
) -> pd.DataFrame:
    """
    Itens básicos que aparecem em pelo menos `min_reqs_mes` requisições distintas
    no mesmo mês (por obra).

    Saída:
      EMPRD | EMPRD_DESC | ANO_MES | INSUMO_CDG | INSUMO_DESC | QTD_REQS_MES
    """
    base = _filtrar_basicos_ano(df, ano)

    if base.empty or "REQ_CDG" not in base.columns:
        return pd.DataFrame(columns=[
            "EMPRD", "EMPRD_DESC", "ANO_MES",
            "INSUMO_CDG", "INSUMO_DESC", "QTD_REQS_MES"
        ])

    base["REQ_DATA_DT"] = pd.to_datetime(base["REQ_DATA"], errors="coerce")
    base = base.dropna(subset=["REQ_DATA_DT", "EMPRD", "REQ_CDG", "INSUMO_CDG"])

    base["ANO_MES"] = base["REQ_DATA_DT"].dt.to_period("M")

    # Não contar duplicado mesmo insumo-requisição
    dedup = base.drop_duplicates(subset=["EMPRD", "REQ_CDG", "INSUMO_CDG"])

    g = (
        dedup.groupby(["EMPRD", "ANO_MES", "INSUMO_CDG"])["REQ_CDG"]
        .nunique()
        .reset_index(name="QTD_REQS_MES")
    )

    g = g[g["QTD_REQS_MES"] >= int(min_reqs_mes)]
    if g.empty:
        return pd.DataFrame(columns=[
            "EMPRD", "EMPRD_DESC", "ANO_MES",
            "INSUMO_CDG", "INSUMO_DESC", "QTD_REQS_MES"
        ])

    # Junta nomes
    nomes_empr = _mapa_empr_desc(base)
    nomes_insumo = _mapa_insumo_desc(base)

    out = (
        g.merge(nomes_empr, on="EMPRD", how="left")
         .merge(nomes_insumo, on="INSUMO_CDG", how="left")
    )

    out["ANO_MES"] = out["ANO_MES"].astype(str)
    out = out[[
        "EMPRD", "EMPRD_DESC", "ANO_MES",
        "INSUMO_CDG", "INSUMO_DESC", "QTD_REQS_MES"
    ]]

    return out.sort_values(["EMPRD", "ANO_MES", "QTD_REQS_MES"], ascending=[True, True, False]).reset_index(drop=True)


# ============================================================
# 3) Básicos em requisições subsequentes (REQs consecutivas)
# ============================================================
def basicos_reqs_subsequentes(
    df: pd.DataFrame,
    ano: Optional[int] = None,
    min_ligacoes: int = 1
) -> pd.DataFrame:
    """
    Identifica itens básicos que aparecem em REQ consecutivas de uma mesma obra.

    Por obra e insumo, calcula:
      - TOTAL_REQS_ITEM: quantas REQs tiveram o item
      - N_LIGACOES_SUBSEQ: quantas "ligações" de REQ consecutivas (REQ n e n+1)
      - MAX_SEQ_SUBSEQ: maior sequência contínua de REQs contendo o item

    Retorna apenas casos com N_LIGACOES_SUBSEQ >= min_ligacoes.
    """
    base = _filtrar_basicos_ano(df, ano)
    if base.empty or "REQ_CDG" not in base.columns or "EMPRD" not in base.columns:
        return pd.DataFrame(columns=[
            "EMPRD", "EMPRD_DESC", "INSUMO_CDG", "INSUMO_DESC",
            "TOTAL_REQS_ITEM", "N_LIGACOES_SUBSEQ", "MAX_SEQ_SUBSEQ"
        ])

    base["REQ_DATA_DT"] = pd.to_datetime(base["REQ_DATA"], errors="coerce")
    base = base.dropna(subset=["REQ_DATA_DT", "EMPRD", "REQ_CDG", "INSUMO_CDG"])

    # Mapa de ordem das REQs por obra
    reqs = (
        base[["EMPRD", "REQ_CDG", "REQ_DATA_DT"]]
        .drop_duplicates()
        .sort_values(["EMPRD", "REQ_DATA_DT", "REQ_CDG"])
    )
    reqs["ORD_REQ_OBRA"] = reqs.groupby("EMPRD").cumcount()

    base = base.merge(reqs[["EMPRD", "REQ_CDG", "ORD_REQ_OBRA"]], on=["EMPRD", "REQ_CDG"], how="left")

    nomes_empr = _mapa_empr_desc(base)
    nomes_insumo = _mapa_insumo_desc(base)

    resultados = []

    for (emprd, ins_cdg), g in base.groupby(["EMPRD", "INSUMO_CDG"]):
        ords = (
            g[["ORD_REQ_OBRA"]]
            .dropna()
            .drop_duplicates()
            .sort_values("ORD_REQ_OBRA")["ORD_REQ_OBRA"]
            .to_numpy()
        )
        if len(ords) < 2:
            continue

        diffs = np.diff(ords)
        n_links = int((diffs == 1).sum())

        # maior sequência contínua de REQs consecutivas
        max_seq = 1
        atual = 1
        for d in diffs:
            if d == 1:
                atual += 1
                if atual > max_seq:
                    max_seq = atual
            else:
                atual = 1

        if n_links >= int(min_ligacoes):
            resultados.append({
                "EMPRD": emprd,
                "INSUMO_CDG": ins_cdg,
                "TOTAL_REQS_ITEM": int(len(ords)),
                "N_LIGACOES_SUBSEQ": int(n_links),
                "MAX_SEQ_SUBSEQ": int(max_seq),
            })

    if not resultados:
        return pd.DataFrame(columns=[
            "EMPRD", "EMPRD_DESC", "INSUMO_CDG", "INSUMO_DESC",
            "TOTAL_REQS_ITEM", "N_LIGACOES_SUBSEQ", "MAX_SEQ_SUBSEQ"
        ])

    out = pd.DataFrame(resultados)
    out = (
        out.merge(nomes_empr, on="EMPRD", how="left")
           .merge(nomes_insumo, on="INSUMO_CDG", how="left")
    )

    cols = [
        "EMPRD", "EMPRD_DESC", "INSUMO_CDG", "INSUMO_DESC",
        "TOTAL_REQS_ITEM", "N_LIGACOES_SUBSEQ", "MAX_SEQ_SUBSEQ"
    ]
    return out[cols].sort_values(
        ["N_LIGACOES_SUBSEQ", "MAX_SEQ_SUBSEQ", "TOTAL_REQS_ITEM"],
        ascending=[False, False, False]
    ).reset_index(drop=True)


# ============================================================
# 4) Básicos com recorrência semanal por obra
# ============================================================
def basicos_semanal_por_obra(
    df: pd.DataFrame,
    ano: Optional[int] = None,
    min_semanas: int = 4,
    exigir_consecutivas: bool = False
) -> pd.DataFrame:
    """
    Itens básicos que aparecem em várias semanas do ano para a mesma obra.

    Se exigir_consecutivas=True, considera apenas aqueles com sequência
    de pelo menos `min_semanas` semanas consecutivas.
    Caso contrário, basta ter aparecido em >= min_semanas semanas distintas.

    Saída:
      EMPRD | EMPRD_DESC | INSUMO_CDG | INSUMO_DESC
      | SEMANAS_DISTINTAS | MAX_SEQ_SEMANAS
    """
    base = _filtrar_basicos_ano(df, ano)
    if base.empty:
        return pd.DataFrame(columns=[
            "EMPRD", "EMPRD_DESC", "INSUMO_CDG", "INSUMO_DESC",
            "SEMANAS_DISTINTAS", "MAX_SEQ_SEMANAS"
        ])

    base["REQ_DATA_DT"] = pd.to_datetime(base["REQ_DATA"], errors="coerce")
    base = base.dropna(subset=["REQ_DATA_DT", "EMPRD", "INSUMO_CDG"])

    # semana ISO
    iso = base["REQ_DATA_DT"].dt.isocalendar()
    base["ANO_ISO"] = iso.year
    base["SEMANA_ISO"] = iso.week

    if ano is not None:
        base = base[base["ANO_ISO"] == int(ano)]

    if base.empty:
        return pd.DataFrame(columns=[
            "EMPRD", "EMPRD_DESC", "INSUMO_CDG", "INSUMO_DESC",
            "SEMANAS_DISTINTAS", "MAX_SEQ_SEMANAS"
        ])

    dedup = base.drop_duplicates(subset=["EMPRD", "INSUMO_CDG", "SEMANA_ISO"])

    nomes_empr = _mapa_empr_desc(base)
    nomes_insumo = _mapa_insumo_desc(base)

    resultados = []
    for (emprd, ins_cdg), g in dedup.groupby(["EMPRD", "INSUMO_CDG"]):
        semanas = np.sort(g["SEMANA_ISO"].to_numpy())
        if len(semanas) == 0:
            continue

        semanas_distintas = int(len(semanas))

        # maior sequência consecutiva de semanas
        if len(semanas) == 1:
            max_seq = 1
        else:
            diffs = np.diff(semanas)
            max_seq = 1
            atual = 1
            for d in diffs:
                if d == 1:
                    atual += 1
                    if atual > max_seq:
                        max_seq = atual
                else:
                    atual = 1

        if exigir_consecutivas:
            if max_seq >= int(min_semanas):
                resultados.append({
                    "EMPRD": emprd,
                    "INSUMO_CDG": ins_cdg,
                    "SEMANAS_DISTINTAS": semanas_distintas,
                    "MAX_SEQ_SEMANAS": int(max_seq),
                })
        else:
            if semanas_distintas >= int(min_semanas):
                resultados.append({
                    "EMPRD": emprd,
                    "INSUMO_CDG": ins_cdg,
                    "SEMANAS_DISTINTAS": semanas_distintas,
                    "MAX_SEQ_SEMANAS": int(max_seq),
                })

    if not resultados:
        return pd.DataFrame(columns=[
            "EMPRD", "EMPRD_DESC", "INSUMO_CDG", "INSUMO_DESC",
            "SEMANAS_DISTINTAS", "MAX_SEQ_SEMANAS"
        ])

    out = pd.DataFrame(resultados)
    out = (
        out.merge(nomes_empr, on="EMPRD", how="left")
           .merge(nomes_insumo, on="INSUMO_CDG", how="left")
    )

    cols = [
        "EMPRD", "EMPRD_DESC", "INSUMO_CDG", "INSUMO_DESC",
        "SEMANAS_DISTINTAS", "MAX_SEQ_SEMANAS"
    ]
    return out[cols].sort_values(
        ["MAX_SEQ_SEMANAS", "SEMANAS_DISTINTAS"],
        ascending=[False, False]
    ).reset_index(drop=True)


# ============================================================
# 5) Intervalo médio entre pedidos de básicos (por obra + insumo)
# ============================================================
def intervalo_medio_entre_pedidos_basicos(
    df: pd.DataFrame,
    ano: Optional[int] = None,
    min_reqs: int = 2
) -> pd.DataFrame:
    """
    Para cada obra + insumo básico, calcula:
      - TOTAL_REQS_ITEM
      - INTERVALO_MEDIO_DIAS
      - INTERVALO_MIN_DIAS
      - INTERVALO_MAX_DIAS

    Considera datas de REQ (normalizadas em dia).
    """
    base = _filtrar_basicos_ano(df, ano)
    if base.empty or "REQ_CDG" not in base.columns:
        return pd.DataFrame(columns=[
            "EMPRD", "EMPRD_DESC", "INSUMO_CDG", "INSUMO_DESC",
            "TOTAL_REQS_ITEM", "INTERVALO_MEDIO_DIAS",
            "INTERVALO_MIN_DIAS", "INTERVALO_MAX_DIAS"
        ])

    base["REQ_DATA_DT"] = pd.to_datetime(base["REQ_DATA"], errors="coerce").dt.normalize()
    base = base.dropna(subset=["REQ_DATA_DT", "EMPRD", "INSUMO_CDG", "REQ_CDG"])

    # por obra + insumo, REQs distintas e ordenadas
    dedup = base.drop_duplicates(subset=["EMPRD", "INSUMO_CDG", "REQ_CDG"])

    nomes_empr = _mapa_empr_desc(base)
    nomes_insumo = _mapa_insumo_desc(base)

    resultados = []
    for (emprd, ins_cdg), g in dedup.groupby(["EMPRD", "INSUMO_CDG"]):
        datas = (
            g[["REQ_DATA_DT"]]
            .dropna()
            .drop_duplicates()
            .sort_values("REQ_DATA_DT")["REQ_DATA_DT"]
            .to_numpy()
        )
        if len(datas) < int(min_reqs):
            continue

        diffs = (datas[1:] - datas[:-1]).astype("timedelta64[D]").astype(int)
        if len(diffs) == 0:
            continue

        resultados.append({
            "EMPRD": emprd,
            "INSUMO_CDG": ins_cdg,
            "TOTAL_REQS_ITEM": int(len(datas)),
            "INTERVALO_MEDIO_DIAS": float(np.mean(diffs)),
            "INTERVALO_MIN_DIAS": int(np.min(diffs)),
            "INTERVALO_MAX_DIAS": int(np.max(diffs)),
        })

    if not resultados:
        return pd.DataFrame(columns=[
            "EMPRD", "EMPRD_DESC", "INSUMO_CDG", "INSUMO_DESC",
            "TOTAL_REQS_ITEM", "INTERVALO_MEDIO_DIAS",
            "INTERVALO_MIN_DIAS", "INTERVALO_MAX_DIAS"
        ])

    out = pd.DataFrame(resultados)
    out = (
        out.merge(nomes_empr, on="EMPRD", how="left")
           .merge(nomes_insumo, on="INSUMO_CDG", how="left")
    )

    cols = [
        "EMPRD", "EMPRD_DESC", "INSUMO_CDG", "INSUMO_DESC",
        "TOTAL_REQS_ITEM", "INTERVALO_MEDIO_DIAS",
        "INTERVALO_MIN_DIAS", "INTERVALO_MAX_DIAS"
    ]
    out["INTERVALO_MEDIO_DIAS"] = out["INTERVALO_MEDIO_DIAS"].round(2)

    return out[cols].sort_values(
        ["INTERVALO_MEDIO_DIAS", "TOTAL_REQS_ITEM"],
        ascending=[True, False]
    ).reset_index(drop=True)


# ============================================================
# 6) Itens básicos de pequena quantidade e alta frequência (geral)
#    (generalização da sua função 2025)
# ============================================================
def itens_basicos_pequenas_qtds_alta_frequencia(
    df: pd.DataFrame,
    ano: Optional[int] = None,
    min_pedidos: int = 5,
    max_media_qtd: float = 10.0
) -> pd.DataFrame:
    """
    Itens básicos comprados muitas vezes mas em pequena quantidade média.

    Parâmetros:
        ano          : filtra por ano da REQ (None = todos)
        min_pedidos  : mínimo de requisições com o item
        max_media_qtd: máximo da média de quantidade por pedido

    Saída:
        INSUMO_CDG | INSUMO_DESC | pedidos | media_qtd | qtd_total | vezes_distintas
    """
    base = _filtrar_basicos_ano(df, ano)
    if base.empty:
        return pd.DataFrame(columns=[
            "INSUMO_CDG", "INSUMO_DESC",
            "pedidos", "media_qtd", "qtd_total", "vezes_distintas"
        ])

    base["QTD_PED"] = pd.to_numeric(base.get("QTD_PED"), errors="coerce")
    base = base.dropna(subset=["QTD_PED", "INSUMO_CDG", "INSUMO_DESC"])

    g = (
        base.groupby(["INSUMO_CDG", "INSUMO_DESC"])
        .agg(
            pedidos=("REQ_CDG", "count"),
            media_qtd=("QTD_PED", "mean"),
            qtd_total=("QTD_PED", "sum"),
            vezes_distintas=("OF_CDG", pd.Series.nunique),
        )
        .reset_index()
    )

    out = g[
        (g["pedidos"] >= int(min_pedidos)) &
        (g["media_qtd"] <= float(max_media_qtd))
    ].copy()

    out["media_qtd"] = out["media_qtd"].round(3)

    return out.sort_values(["pedidos", "media_qtd"], ascending=[False, True]).reset_index(drop=True)


# ============================================================
# 7) Painel consolidado de recorrência de básicos
# ============================================================
def painel_recorrencia_basicos(
    df: pd.DataFrame,
    ano: Optional[int] = 2025
) -> Dict[str, Any]:
    """
    Orquestra as principais análises de recorrência de materiais básicos
    para um determinado ano.

    Retorna um dict com:
      - "basicos_reqs_mes"
      - "basicos_reqs_subsequentes"
      - "basicos_semanal_por_obra"
      - "intervalo_medio_entre_pedidos"
      - "itens_pequena_qtd_alta_freq"
      - "resumo_indicadores" (dicionário com números-chave)
    """
    df_mes = basicos_reqs_mes(df, ano=ano, min_reqs_mes=2)
    df_subseq = basicos_reqs_subsequentes(df, ano=ano, min_ligacoes=1)
    df_semana = basicos_semanal_por_obra(df, ano=ano, min_semanas=4, exigir_consecutivas=False)
    df_intervalos = intervalo_medio_entre_pedidos_basicos(df, ano=ano, min_reqs=2)
    df_pingados = itens_basicos_pequenas_qtds_alta_frequencia(df, ano=ano, min_pedidos=5, max_media_qtd=10.0)

    resumo = {
        "ano": int(ano) if ano is not None else None,
        "qtd_itens_2plus_reqs_mes": int(df_mes["INSUMO_CDG"].nunique()) if not df_mes.empty else 0,
        "qtd_itens_com_reqs_subsequentes": int(df_subseq["INSUMO_CDG"].nunique()) if not df_subseq.empty else 0,
        "qtd_itens_semanal_obra": int(df_semana["INSUMO_CDG"].nunique()) if not df_semana.empty else 0,
        "qtd_itens_com_intervalo_calculado": int(df_intervalos["INSUMO_CDG"].nunique()) if not df_intervalos.empty else 0,
        "qtd_itens_pequena_qtd_alta_freq": int(df_pingados["INSUMO_CDG"].nunique()) if not df_pingados.empty else 0,
    }

    return {
        "basicos_reqs_mes": df_mes,
        "basicos_reqs_subsequentes": df_subseq,
        "basicos_semanal_por_obra": df_semana,
        "intervalo_medio_entre_pedidos": df_intervalos,
        "itens_pequena_qtd_alta_freq": df_pingados,
        "resumo_indicadores": resumo,
    }