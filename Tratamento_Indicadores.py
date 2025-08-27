import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, List, Tuple
import unicodedata

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

def meses_top3_volume_geral(df, top_n=3):
    """
    Top N meses do ano (Jan..Dez) com maior volume somando TODOS os anos.
    Retorna colunas: MES_ROTULO | VALOR_TOTAL | PART_%
    """
    df = df.copy()
    df["OF_DATA_DT"] = pd.to_datetime(df["OF_DATA"], errors="coerce")
    base = df.dropna(subset=["OF_DATA_DT"]).copy()
    if base.empty:
        return pd.DataFrame(columns=["MES_ROTULO", "VALOR_TOTAL", "PART_%"])

    base["PRCTTL_INSUMO"] = pd.to_numeric(base["PRCTTL_INSUMO"], errors="coerce")
    base["MES"] = base["OF_DATA_DT"].dt.month

    _MES_LABEL = {1:"Jan",2:"Fev",3:"Mar",4:"Abr",5:"Mai",6:"Jun",7:"Jul",8:"Ago",9:"Set",10:"Out",11:"Nov",12:"Dez"}

    agg = (base.groupby("MES")["PRCTTL_INSUMO"]
               .sum()
               .reset_index(name="VALOR_TOTAL"))
    total = agg["VALOR_TOTAL"].sum()
    agg["PART_%"] = (agg["VALOR_TOTAL"]/total*100).round(2) if total else 0.0
    agg["MES_ROTULO"] = agg["MES"].map(_MES_LABEL)
    agg["VALOR_TOTAL"] = pd.to_numeric(agg["VALOR_TOTAL"], errors="coerce").round(2)

    out = agg.sort_values("VALOR_TOTAL", ascending=False).head(int(top_n))
    return out[["MES_ROTULO", "VALOR_TOTAL", "PART_%"]]

def maior_compra_item_unico(df):
    """
    Retorna a linha (1 registro) com o MAIOR VALOR TOTAL de uma compra de item.
    Colunas no retorno: INSUMO_CDG | INSUMO_DESC | QUANTIDADE | PRECO_TOTAL
    - Tenta usar PRCTTL_INSUMO como total; se não existir, calcula QTDE * PRECO_UNIT.
    - É tolerante a aliases comuns de quantidade e preço unitário.
    """
    import pandas as pd

    def _pick(colnames, dfcols):
        for c in colnames:
            if c in dfcols:
                return c
        return None

    base = df.copy()

    # Colunas de interesse
    col_cod  = _pick(["INSUMO_CDG", "COD_INSUMO", "INSUMO_COD", "ITEM_CDG", "ITEM_CODIGO"], base.columns)
    col_desc = _pick(["INSUMO_DESC", "ITEM_DESC", "DESCRICAO_INSUMO", "DESCRICAO"], base.columns)
    col_qtd  = _pick(["ITEM_QTDSOLIC", "QTD_SOLIC", "QTDE_SOLICITADA", "QTDE", "QUANTIDADE", "ITEM_QTDE", "QTD"], base.columns)
    col_tot  = _pick(["PRCTTL_INSUMO", "VALOR_TOTAL_ITEM", "TOTAL", "VLR_TOTAL", "VL_TOTAL"], base.columns)
    col_pu   = _pick(["ITEM_PRCUNTPED", "PRECO_UNIT", "VLR_UNITARIO", "VL_UNIT", "PRECO_UNITARIO"], base.columns)

    if not (col_cod and col_desc):
        raise KeyError("Não encontrei colunas de código/descrição do insumo (esperado algo como INSUMO_CDG e INSUMO_DESC).")

    # Garante tipos numéricos
    if col_qtd:
        base[col_qtd] = pd.to_numeric(base[col_qtd], errors="coerce")
    if col_tot:
        base[col_tot] = pd.to_numeric(base[col_tot], errors="coerce")
    if col_pu:
        base[col_pu]  = pd.to_numeric(base[col_pu], errors="coerce")

    # Define total por linha
    if col_tot:
        base["_TOTAL_ITEM_"] = base[col_tot]
    elif col_qtd and col_pu:
        base["_TOTAL_ITEM_"] = base[col_qtd] * base[col_pu]
    else:
        raise KeyError("Não encontrei total do item (PRCTTL_INSUMO/TOTAL) nem consigo calcular via QTDE*PREÇO_UNIT.")

    base = base.dropna(subset=["_TOTAL_ITEM_"]).copy()
    if base.empty:
        return pd.DataFrame(columns=["INSUMO_CDG", "INSUMO_DESC", "QUANTIDADE", "PRECO_TOTAL"])

    # Ordena por maior total e seleciona 1
    top = base.sort_values("_TOTAL_ITEM_", ascending=False).head(1)

    # Monta saída
    out = pd.DataFrame({
        "INSUMO_CDG":  top[col_cod].astype("string"),
        "INSUMO_DESC": top[col_desc].astype("string"),
        "QUANTIDADE":  top[col_qtd] if col_qtd else pd.Series([pd.NA]),
        "PRECO_TOTAL": top["_TOTAL_ITEM_"],
    })

    # Arredonda
    out["PRECO_TOTAL"] = pd.to_numeric(out["PRECO_TOTAL"], errors="coerce").round(2)
    if "QUANTIDADE" in out.columns:
        out["QUANTIDADE"] = pd.to_numeric(out["QUANTIDADE"], errors="coerce")

    return out

def categorias_mais_compradas_ultimos_anos(df, anos=5, col_cat="INSUMO_CATEGORIA"):
    """
    Top de categorias por valor total nos últimos `anos`.
    Retorna: CATEGORIA | VALOR_TOTAL | PART_%
    """
    import pandas as pd
    df = df.copy()
    df["OF_DATA_DT"] = pd.to_datetime(df["OF_DATA"], errors="coerce")
    base = df[df["OF_DATA_DT"] >= pd.Timestamp.today() - pd.DateOffset(years=anos)].copy()
    if base.empty or col_cat not in base.columns:
        return pd.DataFrame(columns=["CATEGORIA", "VALOR_TOTAL", "PART_%"])

    base["PRCTTL_INSUMO"] = pd.to_numeric(base["PRCTTL_INSUMO"], errors="coerce")
    grp = (base.groupby(col_cat)["PRCTTL_INSUMO"].sum()
           .reset_index(name="VALOR_TOTAL")
           .rename(columns={col_cat: "CATEGORIA"}))
    tot = float(grp["VALOR_TOTAL"].sum()) if not grp.empty else 0.0
    grp["PART_%"] = (grp["VALOR_TOTAL"] / tot * 100).round(2) if tot else 0.0
    grp["VALOR_TOTAL"] = grp["VALOR_TOTAL"].round(2)
    return grp.sort_values("VALOR_TOTAL", ascending=False)


def categorias_crescimento_yoy(df, anos=5, col_cat="INSUMO_CATEGORIA"):
    """
    Crescimento médio YoY por categoria nos últimos `anos`.
    Retorna: CATEGORIA | MEDIA_YOY_PCT | ULTIMO_YOY_PCT | PRIMEIRO_ANO | ULTIMO_ANO
    """
    import pandas as pd
    df = df.copy()
    df["OF_DATA_DT"] = pd.to_datetime(df["OF_DATA"], errors="coerce")
    base = df[df["OF_DATA_DT"] >= pd.Timestamp.today() - pd.DateOffset(years=anos)].copy()
    if base.empty or col_cat not in base.columns:
        return pd.DataFrame(columns=["CATEGORIA", "MEDIA_YOY_PCT", "ULTIMO_YOY_PCT", "PRIMEIRO_ANO", "ULTIMO_ANO"])

    base["PRCTTL_INSUMO"] = pd.to_numeric(base["PRCTTL_INSUMO"], errors="coerce")
    base["ANO"] = base["OF_DATA_DT"].dt.year
    agg = (base.groupby([col_cat, "ANO"])["PRCTTL_INSUMO"].sum()
           .reset_index()
           .sort_values([col_cat, "ANO"]))

    # YoY por categoria
    agg["YOY_PCT"] = agg.groupby(col_cat)["PRCTTL_INSUMO"].pct_change() * 100

    def _avg(s): 
        s = s.dropna()
        return float(s.mean()) if not s.empty else 0.0

    def _last(s):
        s = s.dropna()
        return float(s.iloc[-1]) if not s.empty else 0.0

    res = (agg.groupby(col_cat)
           .agg(MEDIA_YOY_PCT=("YOY_PCT", _avg),
                ULTIMO_YOY_PCT=("YOY_PCT", _last),
                PRIMEIRO_ANO=("ANO", "min"),
                ULTIMO_ANO=("ANO", "max"))
           .reset_index()
           .rename(columns={col_cat: "CATEGORIA"}))
    res["MEDIA_YOY_PCT"] = res["MEDIA_YOY_PCT"].round(2)
    res["ULTIMO_YOY_PCT"] = res["ULTIMO_YOY_PCT"].round(2)
    return res.sort_values("MEDIA_YOY_PCT", ascending=False)

def _pick_col(df: pd.DataFrame, candidatos: List[str]) -> Optional[str]:
    up = {c.strip().upper(): c for c in df.columns}
    for cand in candidatos:
        k = cand.strip().upper()
        if k in up:
            return up[k]
        for kk, orig in up.items():  # substring fallback
            if k in kk:
                return orig
    return None

def _strip_accents_lower(s: pd.Series) -> pd.Series:
    def _norm(x):
        if pd.isna(x): return x
        t = unicodedata.normalize("NFKD", str(x))
        t = "".join(ch for ch in t if not unicodedata.combining(ch))
        return t.strip().lower()
    return s.astype("string").map(_norm)

def categorias_basicos_distintos(df: pd.DataFrame, col_cat: str = "INSUMO_CATEGORIA") -> pd.DataFrame:
    """
    Retorna as categorias (distintas) de materiais marcados como BÁSICO.
    Coluna esperada: TIPO_MATERIAL == 'BÁSICO'. Se não existir, assume vazio.
    """
    base = df.copy()
    if "TIPO_MATERIAL" not in base.columns:
        return pd.DataFrame(columns=["CATEGORIA"])
    base = base[base["TIPO_MATERIAL"] == "BÁSICO"].copy()
    if base.empty or col_cat not in base.columns:
        return pd.DataFrame(columns=["CATEGORIA"])
    out = (base[col_cat].dropna().astype("string").str.strip().drop_duplicates()
           .to_frame(name="CATEGORIA").sort_values("CATEGORIA"))
    return out.reset_index(drop=True)

def fornecedores_basicos_por_local(df_erp: pd.DataFrame,
                                   df_forn: Optional[pd.DataFrame] = None,
                                   locais: Tuple[str, ...] = ("RJ","SP","Itajaí")) -> pd.DataFrame:
    """
    Quantidade de empresas CADASTRADAS aptas (observadas vendendo BÁSICO no ERP) por local:
      - RJ/SP: compara por UF (obra OU fornecedor)
      - Itajaí: compara por município (obra OU fornecedor), normalizado
    Considera como 'cadastrada' se o FORNECEDOR_ID aparecer em df_forn (quando df_forn é fornecido).
    Retorna: LOCAL | FORNECEDORES_BÁSICO_CAD
    """
    df = df_erp.copy()

    # detecta colunas
    col_forn_id = _pick_col(df, [
        "FORNECEDOR_CDG","FORNECEDOR_ID","COD_FORNECEDOR","FORN_ID","FORN_CDG",
        "FORN_CNPJ","CNPJ","PED_FORNECEDOR","FORNECEDOR"
    ])
    if not col_forn_id:
        raise KeyError("Não encontrei coluna de identificador do fornecedor no ERP.")

    col_uf_obra = _pick_col(df, ["EMPRD_UF","OBRA_UF","UF_OBRA","UF"])
    col_uf_forn = _pick_col(df, ["FORNECEDOR_UF","FORN_UF","UF_FORN","UF"])

    col_cidade_obra = _pick_col(df, ["EMPRD_MUN","EMPRD_CIDADE","OBRA_MUNICIPIO","OBRA_CIDADE","CIDADE_OBRA","MUNICIPIO_OBRA","MUNICIPIO","CIDADE"])
    col_cidade_forn = _pick_col(df, ["FORNECEDOR_MUN","FORNECEDOR_CIDADE","CIDADE_FORN","MUNICIPIO_FORN","CIDADE","MUNICIPIO"])

    # filtra básicos
    if "TIPO_MATERIAL" not in df.columns:
        return pd.DataFrame(columns=["LOCAL","FORNECEDORES_BÁSICO_CAD"])
    base = df[df["TIPO_MATERIAL"] == "BÁSICO"].copy()
    if base.empty:
        return pd.DataFrame(columns=["LOCAL","FORNECEDORES_BÁSICO_CAD"])

    # normaliza campos
    base[col_forn_id] = base[col_forn_id].astype("string").str.strip()
    if col_uf_obra: base[col_uf_obra] = base[col_uf_obra].astype("string").str.upper().str.strip()
    if col_uf_forn: base[col_uf_forn] = base[col_uf_forn].astype("string").str.upper().str.strip()
    if col_cidade_obra: base[col_cidade_obra] = _strip_accents_lower(base[col_cidade_obra])
    if col_cidade_forn: base[col_cidade_forn] = _strip_accents_lower(base[col_cidade_forn])

    # conjunto de fornecedores cadastrados (interseção)
    regist: set[str] = set()
    if df_forn is not None and not df_forn.empty:
        col_forn_cad = _pick_col(df_forn, ["FORNECEDOR_CDG","FORNECEDOR_ID","COD_FORNECEDOR","FORN_ID","FORN_CDG","FORN_CNPJ","CNPJ","FORNECEDOR"])
        if col_forn_cad:
            regist = set(df_forn[col_forn_cad].astype("string").str.strip().dropna().unique().tolist())

    def _count_for(loc: str) -> int:
        loc_norm = unicodedata.normalize("NFKD", loc).encode("ascii","ignore").decode("ascii").strip().lower()
        mask = pd.Series(False, index=base.index)
        if loc.upper() in {"RJ","SP","SC","ES","MG","PR","RS","BA","PE","CE"}:  # UF
            if col_uf_obra: mask |= base[col_uf_obra] == loc.upper()
            if col_uf_forn: mask |= base[col_uf_forn] == loc.upper()
        else:  # município
            if col_cidade_obra: mask |= base[col_cidade_obra] == loc_norm
            if col_cidade_forn: mask |= base[col_cidade_forn] == loc_norm

        sub = base[mask].copy()
        if sub.empty: return 0
        ids = set(sub[col_forn_id].dropna().unique().tolist())
        if regist:
            ids = ids & regist  # mantém só cadastrados
        return int(len(ids))

    rows = [{"LOCAL": loc, "FORNECEDORES_BÁSICO_CAD": _count_for(loc)} for loc in locais]
    out = pd.DataFrame(rows)
    return out.sort_values("LOCAL").reset_index(drop=True)
