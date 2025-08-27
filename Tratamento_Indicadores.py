import pandas as pd
import numpy as np
from pathlib import Path
import unicodedata
from typing import Optional, List, Tuple

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

def _norm_txt(s: str) -> str:
    if s is None:
        return ""
    t = unicodedata.normalize("NFKD", str(s))
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return t.strip().lower()

def _split_tokens(text: str) -> set:
    if text is None:
        return set()
    t = _norm_txt(text)
    for sep in [",", ";", "/", "|", "&", "+"]:
        t = t.replace(sep, ",")
    parts = [p.strip() for p in t.split(",") if p.strip()]
    return {p for p in parts if len(p) > 1}

def _pick_col(df: pd.DataFrame, candidatos: List[str]) -> Optional[str]:
    up = {c.strip().upper(): c for c in df.columns}
    for cand in candidatos:
        k = cand.strip().upper()
        if k in up:
            return up[k]
        # fallback por substring
        for K, orig in up.items():
            if k in K:
                return orig
    return None

def categorias_basicos_distintos(df: pd.DataFrame, col_cat: str = "INSUMO_CATEGORIA") -> pd.DataFrame:
    base = df.copy()
    if "TIPO_MATERIAL" not in base.columns:
        return pd.DataFrame(columns=["CATEGORIA"])
    base = base[base["TIPO_MATERIAL"] == "BÁSICO"].copy()
    if base.empty or col_cat not in base.columns:
        return pd.DataFrame(columns=["CATEGORIA"])
    out = (base[col_cat].dropna().astype("string").str.strip().drop_duplicates()
           .to_frame(name="CATEGORIA").sort_values("CATEGORIA"))
    return out.reset_index(drop=True)

def _set_categorias_basicos(df_erp: pd.DataFrame, col_cat: str = "INSUMO_CATEGORIA") -> set:
    if "TIPO_MATERIAL" not in df_erp.columns or col_cat not in df_erp.columns:
        return set()
    base = df_erp[df_erp["TIPO_MATERIAL"] == "BÁSICO"]
    cats = base[col_cat].dropna().astype("string").unique().tolist()
    return {_norm_txt(c) for c in cats if str(c).strip()}

def fornecedores_basicos_por_local_cadastro(
    df_forn: pd.DataFrame,
    df_erp: pd.DataFrame,
    locais: Tuple[str, ...] = ("RJ","SP","SC"),
    candidatos_col_cat_forn: Tuple[str, ...] = (
        "CATEGORIAS", "CATEGORIA", "SEGMENTOS", "LINHA", "LINHAS",
        "LINHA_PRODUTO", "AREAS", "ATIVIDADES", "MATERIAIS", "GRUPOS",
        "FAMILIA", "FAMÍLIA"
    )
) -> pd.DataFrame:
    cat_bas = _set_categorias_basicos(df_erp, col_cat="INSUMO_CATEGORIA")
    if not cat_bas:
        return pd.DataFrame(columns=["LOCAL","FORNECEDORES_BÁSICO_CAD"])

    df = df_forn.copy()
    col_id = _pick_col(df, ["FORNECEDOR_CDG","FORNECEDOR_ID","COD_FORNECEDOR","FORN_ID","FORN_CDG","FORN_CNPJ","CNPJ","FORNECEDOR"])
    if not col_id:
        raise KeyError("Cadastro: não encontrei coluna de ID do fornecedor.")
    col_uf = _pick_col(df, ["FORNECEDOR_UF","FORN_UF","UF"])
    col_cidade = _pick_col(df, ["FORNECEDOR_MUN","FORNECEDOR_CIDADE","MUNICIPIO","CIDADE", "FORN_UF"])

    col_cat_forn = None
    for c in candidatos_col_cat_forn:
        col_cat_forn = _pick_col(df, [c])
        if col_cat_forn:
            break
    if not col_cat_forn:
        return pd.DataFrame(columns=["LOCAL","FORNECEDORES_BÁSICO_CAD"])

    df[col_id] = df[col_id].astype("string").str.strip()
    if col_uf: df[col_uf] = df[col_uf].astype("string").str.upper().str.strip()
    if col_cidade: df[col_cidade] = df[col_cidade].astype("string").map(_norm_txt)

    def _is_apto(cel) -> bool:
        toks = _split_tokens(cel)
        if not toks:
            return False
        for t in toks:
            for b in cat_bas:
                if t in b or b in t:
                    return True
        return False

    df["_APTO_BASICO_"] = df[col_cat_forn].apply(_is_apto)

    def _count(loc: str) -> int:
        loc_up = loc.upper()
        loc_norm = _norm_txt(loc)
        m = df["_APTO_BASICO_"] == True
        if loc_up in {"RJ","SP","SC","ES","MG","PR","RS","BA","PE","CE"} and col_uf:
            m &= (df[col_uf] == loc_up)
        elif col_cidade:
            m &= (df[col_cidade] == loc_norm)
        else:
            return 0
        return int(df.loc[m, col_id].dropna().nunique())

    out = pd.DataFrame([{"LOCAL": loc, "FORNECEDORES_BÁSICO_CAD": _count(loc)} for loc in locais])
    return out.sort_values("LOCAL").reset_index(drop=True)

