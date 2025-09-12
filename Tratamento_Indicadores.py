import pandas as pd
import numpy as np
from pathlib import Path
import unicodedata
from typing import Optional, List, Tuple

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
            EMPRD_CDG = ("EMPRD", "first"), 
            EMPRD_DESC=("EMPRD_DESC", "first"),
            FORNECEDOR_DESC=("FORNECEDOR_DESC", "first"),
            DATA_OF=("OF_DATA_DT", "first"),
            #INSUMOS=("INSUMO_DESC", lambda x: ", ".join(sorted(set(x)))),
            TOTAL_ITENS=("INSUMO_CDG", "nunique"),
        )
        .reset_index()
    )
    # >>> NOVO: excluir OFs com total <= 0 (ou NaN)
    g["VALOR_TOTAL"] = pd.to_numeric(g["VALOR_TOTAL"], errors="coerce")
    g = g[g["VALOR_TOTAL"] > 0]

    if g.empty:
        return g

    g = g.sort_values("VALOR_TOTAL", ascending=False).head(1)
    g["DATA_OF"] = pd.to_datetime(g["DATA_OF"]).dt.strftime("%d/%m/%Y")
    g["VALOR_TOTAL"] = pd.to_numeric(g["VALOR_TOTAL"], errors="coerce").round(2)
    return g

def menor_ordem_fornecimento(
    df: pd.DataFrame,
    min_total: float = 10.0,                 # <<< piso mínimo da OF (R$)
    excluir_itens_nao_positivos: bool = True # <<< ignora itens <= 0 ao somar
) -> pd.DataFrame:
    df = df.copy()
    df = df[df.get("INSUMO_CATEGORIA") != "CAÇAMBAS E RETIRADAS DE RESÍDUOS"]
    df["QTD_PED"] = pd.to_numeric(df.get("QTD_PED"), errors="coerce")
    df = df[df["QTD_PED"] >= 1]
    df["OF_DATA_DT"] = pd.to_datetime(df.get("OF_DATA"), errors="coerce")
    df["PRCTTL_INSUMO"] = pd.to_numeric(df.get("PRCTTL_INSUMO"), errors="coerce")

    # Opcional: remove itens zero/negativos para não "artificializar" o total da OF
    if excluir_itens_nao_positivos:
        df = df[df["PRCTTL_INSUMO"] > 0]

    g = (
        df.groupby("OF_CDG", dropna=True)
          .agg(
              VALOR_TOTAL=("PRCTTL_INSUMO", "sum"),
              EMPRD_CDG=("EMPRD", "first"),
              EMPRD_DESC=("EMPRD_DESC", "first"),
              FORNECEDOR_DESC=("FORNECEDOR_DESC", "first"),
              DATA_OF=("OF_DATA_DT", "first"),
              TOTAL_ITENS=("INSUMO_CDG", "nunique"),
          )
          .reset_index()
    )

    # Mantém só OFs com total > 0
    g["VALOR_TOTAL"] = pd.to_numeric(g["VALOR_TOTAL"], errors="coerce")

    # 1) Tenta com piso mínimo (ex.: R$ 1,00)
    g_valid = g[g["VALOR_TOTAL"] >= float(min_total)]

    # 2) Se não houver nenhuma >= piso, faz fallback para a menor > 0
    if g_valid.empty:
        g_valid = g[g["VALOR_TOTAL"] > 0]

    if g_valid.empty:
        return g_valid  # sem dados válidos

    out = g_valid.sort_values("VALOR_TOTAL", ascending=True).head(1).copy()
    out["DATA_OF"] = pd.to_datetime(out["DATA_OF"]).dt.strftime("%d/%m/%Y")
    out["VALOR_TOTAL"] = pd.to_numeric(out["VALOR_TOTAL"], errors="coerce").round(2)
    return out

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
    def _pick(cands, cols):
        for c in cands:
            if c in cols: return c
        return None

    base = df.copy()
    cols = base.columns

    col_cod  = _pick(["INSUMO_CDG","COD_INSUMO","INSUMO_COD","ITEM_CDG","ITEM_CODIGO"], cols)
    col_desc = _pick(["INSUMO_DESC","ITEM_DESC","DESCRICAO_INSUMO","DESCRICAO"], cols)
    col_qtd  = _pick([
        "ITEM_QTDSOLIC","QTD_SOLIC","QTDE_SOLICITADA","QTDE","QUANTIDADE",
        "ITEM_QTDE","QTD","QTD_ITEM","QTD_PEDIDA","QTD_REQUISITADA"
    ], cols)
    col_tot  = _pick(["PRCTTL_INSUMO","VALOR_TOTAL_ITEM","TOTAL","VLR_TOTAL","VL_TOTAL"], cols)
    col_pu   = _pick(["ITEM_PRCUNTPED","PRECO_UNIT","VLR_UNITARIO","VL_UNIT","PRECO_UNITARIO"], cols)

    if not (col_cod and col_desc):
        raise KeyError("Faltam colunas de código/descrição do item (ex.: INSUMO_CDG / INSUMO_DESC).")

    # numéricos
    if col_qtd: base[col_qtd] = pd.to_numeric(base[col_qtd], errors="coerce")
    if col_tot: base[col_tot] = pd.to_numeric(base[col_tot], errors="coerce")
    if col_pu:  base[col_pu]  = pd.to_numeric(base[col_pu],  errors="coerce")

    # total por linha
    if col_tot:
        base["_TOTAL_ITEM_"] = base[col_tot]
    elif col_qtd and col_pu:
        base["_TOTAL_ITEM_"] = base[col_qtd] * base[col_pu]
    else:
        raise KeyError("Não encontrei TOTAL do item e não consigo calcular via QTDE*PREÇO_UNIT.")

    base = base.dropna(subset=["_TOTAL_ITEM_"]).copy()
    if base.empty:
        return pd.DataFrame(columns=["INSUMO_CDG","INSUMO_DESC","QUANTIDADE","PRECO_TOTAL"])

    # pega o maior e alinha índice
    top = base.sort_values("_TOTAL_ITEM_", ascending=False).head(1).reset_index(drop=True)

    # calcula QTDE se não houver coluna
    quantidade = None
    if col_qtd and pd.notna(top.at[0, col_qtd]):
        quantidade = float(top.at[0, col_qtd])
    elif col_pu and pd.notna(top.at[0, col_pu]) and float(top.at[0, col_pu]) != 0:
        quantidade = float(top.at[0, "_TOTAL_ITEM_"]) / float(top.at[0, col_pu])

    out = pd.DataFrame([{
        "INSUMO_CDG":  str(top.at[0, col_cod]) if col_cod else None,
        "INSUMO_DESC": str(top.at[0, col_desc]) if col_desc else None,
        "QUANTIDADE":  quantidade,
        "PRECO_TOTAL": float(top.at[0, "_TOTAL_ITEM_"]),
    }])

    out["PRECO_TOTAL"] = pd.to_numeric(out["PRECO_TOTAL"], errors="coerce").round(2)
    if "QUANTIDADE" in out.columns:
        out["QUANTIDADE"] = pd.to_numeric(out["QUANTIDADE"], errors="coerce").round(2)

    return out

def menor_compra_item_unico(
    df: pd.DataFrame,
    min_total: float = 10.0,                 # piso mínimo do total do item (R$)
    excluir_itens_nao_positivos: bool = True # ignora itens com total <= 0
) -> pd.DataFrame:
    def _pick(cands, cols):
        for c in cands:
            if c in cols:
                return c
        return None

    base = df.copy()
    cols = base.columns

    col_cod  = _pick(["INSUMO_CDG","COD_INSUMO","INSUMO_COD","ITEM_CDG","ITEM_CODIGO"], cols)
    col_desc = _pick(["INSUMO_DESC","ITEM_DESC","DESCRICAO_INSUMO","DESCRICAO"], cols)
    col_qtd  = _pick([
        "ITEM_QTDSOLIC","QTD_SOLIC","QTDE_SOLICITADA","QTDE","QUANTIDADE",
        "ITEM_QTDE","QTD","QTD_ITEM","QTD_PEDIDA","QTD_REQUISITADA"
    ], cols)
    col_tot  = _pick(["PRCTTL_INSUMO","VALOR_TOTAL_ITEM","TOTAL","VLR_TOTAL","VL_TOTAL"], cols)
    col_pu   = _pick(["ITEM_PRCUNTPED","PRECO_UNIT","VLR_UNITARIO","VL_UNIT","PRECO_UNITARIO"], cols)

    if not (col_cod and col_desc):
        raise KeyError("Faltam colunas de código/descrição do item (ex.: INSUMO_CDG / INSUMO_DESC).")

    # Numéricos
    if col_qtd: base[col_qtd] = pd.to_numeric(base[col_qtd], errors="coerce")
    if col_tot: base[col_tot] = pd.to_numeric(base[col_tot], errors="coerce")
    if col_pu:  base[col_pu]  = pd.to_numeric(base[col_pu],  errors="coerce")

    # Total por linha
    if col_tot:
        base["_TOTAL_ITEM_"] = base[col_tot]
    elif col_qtd and col_pu:
        base["_TOTAL_ITEM_"] = base[col_qtd] * base[col_pu]
    else:
        raise KeyError("Não encontrei TOTAL do item e não consigo calcular via QTDE*PREÇO_UNIT.")

    base = base.dropna(subset=["_TOTAL_ITEM_"]).copy()
    if base.empty:
        return pd.DataFrame(columns=["INSUMO_CDG","INSUMO_DESC","QUANTIDADE","PRECO_TOTAL"])

    # Ignora totais <= 0 se solicitado
    if excluir_itens_nao_positivos:
        base = base[base["_TOTAL_ITEM_"] > 0]

    if base.empty:
        return pd.DataFrame(columns=["INSUMO_CDG","INSUMO_DESC","QUANTIDADE","PRECO_TOTAL"])

    # Aplica piso mínimo; se nada atingir, usa o menor > 0 (fallback)
    cand = base[base["_TOTAL_ITEM_"] >= float(min_total)]
    if cand.empty:
        cand = base[base["_TOTAL_ITEM_"] > 0]
        if cand.empty:
            return pd.DataFrame(columns=["INSUMO_CDG","INSUMO_DESC","QUANTIDADE","PRECO_TOTAL"])

    top = cand.sort_values("_TOTAL_ITEM_", ascending=True).head(1).reset_index(drop=True)

    # Calcula QTDE se não houver coluna
    quantidade = None
    if col_qtd and pd.notna(top.at[0, col_qtd]):
        quantidade = float(top.at[0, col_qtd])
    elif col_pu and pd.notna(top.at[0, col_pu]) and float(top.at[0, col_pu]) != 0:
        quantidade = float(top.at[0, "_TOTAL_ITEM_"]) / float(top.at[0, col_pu])

    out = pd.DataFrame([{
        "INSUMO_CDG":  str(top.at[0, col_cod]) if col_cod else None,
        "INSUMO_DESC": str(top.at[0, col_desc]) if col_desc else None,
        "QUANTIDADE":  quantidade,
        "PRECO_TOTAL": float(top.at[0, "_TOTAL_ITEM_"]),
    }])

    out["PRECO_TOTAL"] = pd.to_numeric(out["PRECO_TOTAL"], errors="coerce").round(2)
    if "QUANTIDADE" in out.columns:
        out["QUANTIDADE"] = pd.to_numeric(out["QUANTIDADE"], errors="coerce").round(2)

    return out

def valor_medio_por_item(df):
    if "PRCTTL_INSUMO" not in df.columns:
        return 0.0, pd.DataFrame(columns=["PRECO_TOTAL_ITEM"])

    s = pd.to_numeric(df["PRCTTL_INSUMO"], errors="coerce").dropna()
    # opcional: considerar apenas positivos
    s = s[s > 0]
    if s.empty:
        return 0.0, pd.DataFrame(columns=["PRECO_TOTAL_ITEM"])

    media = float(s.mean())
    out = pd.DataFrame({"PRECO_TOTAL_ITEM": s.round(2)})
    return round(media, 2), out
    
def categorias_mais_compradas_ultimos_anos(df, anos=5, col_cat="INSUMO_CATEGORIA"):
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
    locais: tuple[str, ...] = ("RJ", "SP", "SC"),
) -> pd.DataFrame:
    # categorias "básico" observadas no ERP (INSUMO_CATEGORIA)
    cat_bas = _set_categorias_basicos(df_erp, col_cat="INSUMO_CATEGORIA")
    if not cat_bas:
        return pd.DataFrame(columns=["LOCAL", "FORNECEDORES_BÁSICO_CAD"])

    # exigidos no cadastro
    if "FORN_UF" not in df_forn.columns or "CATEGORIAS" not in df_forn.columns:
        raise KeyError("No cadastro preciso das colunas FORN_UF e CATEGORIAS.")

    df = df_forn.copy()
    # tenta achar um ID p/ contar distintos; se não achar, conta linhas
    col_id = _pick_col(df, [
        "FORNECEDOR_CDG","FORNECEDOR_ID","COD_FORNECEDOR",
        "FORN_CNPJ","CNPJ","FORNECEDOR"
    ])

    df["FORN_UF"]   = df["FORN_UF"].astype("string").str.upper().str.strip()
    df["CATEGORIAS"] = df["CATEGORIAS"].astype("string")

    def _is_apto(cel) -> bool:
        toks = _split_tokens(cel)        # já separa por vírgula/;//|/&/+
        if not toks: return False
        # match aproximado: token dentro da categoria básica (ou vice-versa)
        return any(any(t in b or b in t for b in cat_bas) for t in toks)

    df["_APTO_BASICO_"] = df["CATEGORIAS"].apply(_is_apto)

    out = []
    for uf in locais:
        m = (df["_APTO_BASICO_"]) & (df["FORN_UF"] == uf.upper())
        if col_id:
            q = int(df.loc[m, col_id].astype("string").dropna().nunique())
        else:
            q = int(m.sum())  # fallback: conta linhas
        out.append({"LOCAL": uf, "FORNECEDORES_BÁSICO_CAD": q})

    return pd.DataFrame(out).sort_values("LOCAL").reset_index(drop=True)

def itens_da_of(df, of_cdg, top_n: int | None = 5):
    def _pick(cands, cols):
        for c in cands:
            if c in cols:
                return c
        return None

    base = df.copy()
    cols = base.columns

    col_of   = _pick(["OF_CDG","PED_CDG","OF","PED"], cols)
    col_cod  = _pick(["INSUMO_CDG","COD_INSUMO","INSUMO_COD","ITEM_CDG","ITEM_CODIGO"], cols)
    col_desc = _pick(["INSUMO_DESC","ITEM_DESC","DESCRICAO_INSUMO","DESCRICAO"], cols)
    col_qtd  = _pick(["QTD_PED","ITEM_QTDSOLIC","QTD_SOLIC","QTDE_SOLICITADA","QTDE","QUANTIDADE",
                      "ITEM_QTDE","QTD","QTD_ITEM","QTD_PEDIDA","QTD_REQUISITADA"], cols)
    col_pu   = _pick(["ITEM_PRCUNTPED","PRECO_UNIT","VLR_UNITARIO","VL_UNIT","PRECO_UNITARIO"], cols)
    col_tot  = _pick(["PRCTTL_INSUMO","VALOR_TOTAL_ITEM","TOTAL","VLR_TOTAL","VL_TOTAL"], cols)

    if not col_of:
        raise KeyError("Não encontrei a coluna da OF (ex.: OF_CDG).")
    if not (col_cod and col_desc):
        raise KeyError("Faltam colunas de item (ex.: INSUMO_CDG / INSUMO_DESC).")

    # Filtra a OF alvo
    alvo = base[base[col_of] == of_cdg].copy()
    if alvo.empty:
        return pd.DataFrame(columns=["INSUMO_CDG","INSUMO_DESC","QUANTIDADE","PRECO_UNIT","PRECO_TOTAL"])

    # Numéricos
    if col_qtd: alvo[col_qtd] = pd.to_numeric(alvo[col_qtd], errors="coerce")
    if col_pu:  alvo[col_pu]  = pd.to_numeric(alvo[col_pu],  errors="coerce")
    if col_tot: alvo[col_tot] = pd.to_numeric(alvo[col_tot], errors="coerce")

    # Total por linha
    if col_tot:
        alvo["_TOTAL_ITEM_"] = alvo[col_tot]
    elif col_qtd and col_pu:
        alvo["_TOTAL_ITEM_"] = alvo[col_qtd] * alvo[col_pu]
    else:
        alvo["_TOTAL_ITEM_"] = pd.NA  # sem total; retornará vazio

    alvo = alvo.dropna(subset=["_TOTAL_ITEM_"]).copy()
    if alvo.empty:
        return pd.DataFrame(columns=["INSUMO_CDG","INSUMO_DESC","QUANTIDADE","PRECO_UNIT","PRECO_TOTAL"])

    # Quantidade (fallback por total / PU)
    qtd = None
    if col_qtd:
        qtd = alvo[col_qtd]
    elif col_pu:
        with pd.option_context("mode.use_inf_as_na", True):
            qtd = alvo["_TOTAL_ITEM_"] / alvo[col_pu]
    else:
        qtd = pd.Series([pd.NA] * len(alvo), index=alvo.index)

    out = pd.DataFrame({
        "INSUMO_CDG":  alvo[col_cod].astype("string"),
        "INSUMO_DESC": alvo[col_desc].astype("string"),
        "QUANTIDADE":  pd.to_numeric(qtd, errors="coerce"),
        "PRECO_UNIT":  pd.to_numeric(alvo[col_pu], errors="coerce") if col_pu else pd.NA,
        "PRECO_TOTAL": pd.to_numeric(alvo["_TOTAL_ITEM_"], errors="coerce"),
    })

    out = out.sort_values("PRECO_TOTAL", ascending=False)
    if top_n:
        out = out.head(int(top_n))

    # Arredondamentos finais
    for c in ["QUANTIDADE","PRECO_UNIT","PRECO_TOTAL"]:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce").round(2)

    return out.reset_index(drop=True)

def categorias_com_venda_continua_ultimos_anos(
    df,
    anos: int = 5,
    col_cat: str = "INSUMO_CATEGORIA",
    col_data: str = "OF_DATA",
    col_val: str = "PRCTTL_INSUMO",
):
    base = df.copy()
    base[col_data] = pd.to_datetime(base[col_data], errors="coerce")
    base[col_val]  = pd.to_numeric(base[col_val], errors="coerce")
    base = base.dropna(subset=[col_data, col_val])

    if col_cat not in base.columns or base.empty:
        return set()

    base["ANO"] = base[col_data].dt.year
    ultimo_ano = int(base["ANO"].max())
    janela = list(range(ultimo_ano - anos + 1, ultimo_ano + 1))

    anuais = (
        base.groupby([col_cat, "ANO"])[col_val]
            .sum()
            .reset_index(name="VALOR_ANO")
    )

    # pivot -> garante todas as colunas (anos) e preenche ausentes com 0
    wide = (anuais.pivot(index=col_cat, columns="ANO", values="VALOR_ANO")
                  .reindex(columns=janela)
                  .fillna(0))

    mask = (wide > 0).all(axis=1)
    return set(wide.index[mask])

def categorias_crescimento_desde_2015(
    df,
    start_year: int = 2015,
    col_cat: str = "INSUMO_CATEGORIA",
    col_data: str = "OF_DATA",
    col_val: str = "PRCTTL_INSUMO",
    min_anos_validos: int = 3,
    clip_pct: float | None = 500.0,
    require_continuous_last_n: int | None = None,  # <<< novo
) -> pd.DataFrame:

    base = df.copy()
    if col_cat not in base.columns:
        return pd.DataFrame(columns=[
            "CATEGORIA","ANO_INICIO","ANO_FIM","VALOR_INICIO","VALOR_FIM","ANOS","METODO","CRESC_AA_%"
        ])

    base[col_data] = pd.to_datetime(base[col_data], errors="coerce")
    base[col_val]  = pd.to_numeric(base[col_val], errors="coerce")
    base = base.dropna(subset=[col_data, col_val])
    base["ANO"] = base[col_data].dt.year

    anuais = (base.groupby([col_cat, "ANO"])[col_val]
                 .sum()
                 .reset_index(name="VALOR_ANO"))

    # >>> filtro: apenas categorias com venda contínua nos últimos N anos
    if require_continuous_last_n and require_continuous_last_n > 0:
        cats_ok = categorias_com_venda_continua_ultimos_anos(
            df=base,
            anos=require_continuous_last_n,
            col_cat=col_cat,
            col_data=col_data,
            col_val=col_val,
        )
        if not cats_ok:
            return pd.DataFrame(columns=[
                "CATEGORIA","ANO_INICIO","ANO_FIM","VALOR_INICIO","VALOR_FIM","ANOS","METODO","CRESC_AA_%"
            ])
        anuais = anuais[anuais[col_cat].isin(cats_ok)]

    ano_max_global = int(anuais["ANO"].max()) if not anuais.empty else start_year
    out = []

    for cat, g in anuais.groupby(col_cat):
        g = g.sort_values("ANO")
        if g["ANO"].max() < start_year:
            continue

        anos_range = list(range(int(start_year), int(ano_max_global) + 1))
        full = (pd.DataFrame({"ANO": anos_range})
                .merge(g[["ANO","VALOR_ANO"]], on="ANO", how="left")
                .fillna(0)
                .sort_values("ANO"))

        anos_pos = full[full["VALOR_ANO"] > 0]
        if anos_pos["ANO"].nunique() < int(min_anos_validos):
            continue

        y0 = int(start_year)
        y1 = int(ano_max_global)
        v0 = float(full.loc[full["ANO"] == y0, "VALOR_ANO"].iloc[0])
        v1 = float(full.loc[full["ANO"] == y1, "VALOR_ANO"].iloc[0])
        anos = y1 - y0
        if anos <= 0:
            continue

        if v0 > 0:
            if v1 > 0:
                cresc = (v1 / v0) ** (1.0 / anos) - 1.0
            else:
                cresc = -1.0
            metodo = "CAGR"
        else:
            sub = full[full["VALOR_ANO"] > 0].copy()
            if sub["ANO"].nunique() >= int(min_anos_validos):
                x = sub["ANO"].astype(float).values
                y = np.log(sub["VALOR_ANO"].astype(float).values)
                slope, _ = np.polyfit(x, y, 1)
                cresc = np.exp(slope) - 1.0
                metodo = "LOGTREND"
            else:
                continue

        if clip_pct is not None:
            cresc = float(np.clip(cresc, -clip_pct/100.0, clip_pct/100.0))

        out.append({
            "CATEGORIA": cat,
            "ANO_INICIO": y0,
            "ANO_FIM": y1,
            "VALOR_INICIO": round(v0, 2),
            "VALOR_FIM": round(v1, 2),
            "ANOS": anos,
            "METODO": metodo,
            "CRESC_AA_%": round(cresc * 100.0, 2),
        })

    res = pd.DataFrame(out)
    if res.empty:
        return res
    return res.sort_values("CRESC_AA_%", ascending=False).reset_index(drop=True)

def compras_atrasadas(
    df: pd.DataFrame,
    dias_uteis_sla: int = 3,
    meses_lookback: int = 12,
    feriados: Optional[List[str]] = None,
) -> tuple[float, int, int, pd.DataFrame]:
    """
    Calcula atrasos de compra com base em 3 dias úteis a partir da REQ até a OF.
    Considera atraso quando DIAS_UTEIS > dias_uteis_sla.
    Filtra por padrão os últimos `meses_lookback` meses pela OF_DATA.

    Retorna:
      (taxa_atraso_pct, qtd_atrasadas, total_compras, df_atrasos)
    onde df_atrasos tem colunas:
      OF_CDG | REQ_DATA | OF_DATA | DIAS_UTEIS | DIAS_EXCEDIDOS | VALOR_TOTAL_OF | EMPRD_DESC | FORNECEDOR_DESC
    """
    base = df.copy()

    # Garantir datetime
    base["REQ_DATA"] = pd.to_datetime(base.get("REQ_DATA"), errors="coerce")
    base["OF_DATA"]  = pd.to_datetime(base.get("OF_DATA"),  errors="coerce")

    # Somente linhas com datas válidas
    base = base.dropna(subset=["REQ_DATA", "OF_DATA"]).copy()

    # Janela de análise (por OF_DATA)
    if meses_lookback and meses_lookback > 0:
        limite = pd.Timestamp.today().normalize() - pd.DateOffset(months=meses_lookback)
        base = base[base["OF_DATA"] >= limite]

    if base.empty:
        return 0.0, 0, 0, pd.DataFrame(columns=[
            "OF_CDG","REQ_DATA","OF_DATA","DIAS_UTEIS","DIAS_EXCEDIDOS",
            "VALOR_TOTAL_OF","EMPRD_DESC","FORNECEDOR_DESC"
        ])

    # Numéricos para somatório de valor da OF
    if "PRCTTL_INSUMO" in base.columns:
        base["PRCTTL_INSUMO"] = pd.to_numeric(base["PRCTTL_INSUMO"], errors="coerce").fillna(0)
    else:
        base["PRCTTL_INSUMO"] = 0.0

    # Agregar por OF
    agg = (base
           .groupby("OF_CDG", dropna=True)
           .agg(
               REQ_DATA_MIN=("REQ_DATA", "min"),
               OF_DATA_REF=("OF_DATA", "min"),
               VALOR_TOTAL_OF=("PRCTTL_INSUMO", "sum"),
               EMPRD_DESC=("EMPRD_DESC", "first"),
               FORNECEDOR_DESC=("FORNECEDOR_DESC", "first"),
           )
           .reset_index())

    # Remover casos inconsistentes (OF antes da REQ)
    agg = agg[agg["OF_DATA_REF"] >= agg["REQ_DATA_MIN"]].copy()
    if agg.empty:
        return 0.0, 0, 0, pd.DataFrame(columns=[
            "OF_CDG","REQ_DATA","OF_DATA","DIAS_UTEIS","DIAS_EXCEDIDOS",
            "VALOR_TOTAL_OF","EMPRD_DESC","FORNECEDOR_DESC"
        ])

    # --- Cálculo de dias úteis ---
    weekmask = "1111100"  # seg..sex

    hol = None
    if feriados:
        try:
            hol_list = [pd.to_datetime(d).date() for d in list(feriados) if pd.notna(d)]
            if len(hol_list) > 0:
                hol = np.asarray(hol_list, dtype="datetime64[D]").ravel()  # garante 1-D
        except Exception:
            hol = None

    start = agg["REQ_DATA_MIN"].dt.date.values.astype("datetime64[D]")
    end   = agg["OF_DATA_REF"].dt.date.values.astype("datetime64[D]")

    if hol is not None and hol.size > 0:
        dias_uteis = np.busday_count(begindates=start, enddates=end, weekmask=weekmask, holidays=hol)
    else:
        dias_uteis = np.busday_count(begindates=start, enddates=end, weekmask=weekmask)

    agg["DIAS_UTEIS"] = dias_uteis.astype(int)

    # Atraso: > SLA
    agg["DIAS_EXCEDIDOS"] = (agg["DIAS_UTEIS"] - int(dias_uteis_sla)).clip(lower=0).astype(int)
    agg["ATRASO"] = agg["DIAS_UTEIS"] > int(dias_uteis_sla)

    total = int(len(agg))
    atrasadas = int(agg["ATRASO"].sum())
    taxa = (atrasadas / total * 100.0) if total else 0.0

    # DataFrame de atrasos ordenado
    df_atrasos = (agg[agg["ATRASO"]]
                  .sort_values(["DIAS_EXCEDIDOS", "VALOR_TOTAL_OF"], ascending=[False, False])
                  .rename(columns={
                      "REQ_DATA_MIN": "REQ_DATA",
                      "OF_DATA_REF": "OF_DATA"
                  })[[
                      "OF_CDG","REQ_DATA","OF_DATA","DIAS_UTEIS","DIAS_EXCEDIDOS",
                      "VALOR_TOTAL_OF","EMPRD_DESC","FORNECEDOR_DESC"
                  ]]
                 )

    df_atrasos["VALOR_TOTAL_OF"] = pd.to_numeric(df_atrasos["VALOR_TOTAL_OF"], errors="coerce").round(2)

    return round(float(taxa), 2), atrasadas, total, df_atrasos

def tempo_medio_geracao_of(
    df: pd.DataFrame,
    considerar_dias_uteis: bool = True,
    meses_lookback: int = 12,
    feriados: Optional[List[str]] = None,
) -> tuple[float, float, float, pd.DataFrame]:
    """
    Calcula o tempo entre a data da REQ (primeira) e a data da OF (primeira) por OF,
    e retorna métricas agregadas.

    Parâmetros:
      - considerar_dias_uteis: se True, usa dias úteis (seg-sex, com feriados).
                               se False, usa dias corridos.
      - meses_lookback: janela de análise (filtra por OF_DATA).
      - feriados: lista opcional de strings de datas (ex.: '2025-09-07') a excluir como dias úteis.

    Retorna:
      (media, mediana, p90, df_duracoes)
      onde df_duracoes contém:
        OF_CDG | REQ_DATA | OF_DATA | DIAS_UTEIS | DIAS_CORRIDOS | VALOR_TOTAL_OF | EMPRD_DESC | FORNECEDOR_DESC
    """
    base = df.copy()

    # Garantir datetime
    base["REQ_DATA"] = pd.to_datetime(base.get("REQ_DATA"), errors="coerce")
    base["OF_DATA"]  = pd.to_datetime(base.get("OF_DATA"),  errors="coerce")

    # Manter apenas pares válidos
    base = base.dropna(subset=["REQ_DATA", "OF_DATA"]).copy()

    # Janela (por OF_DATA), consistente com 'compras_atrasadas'
    if meses_lookback and meses_lookback > 0:
        limite = pd.Timestamp.today().normalize() - pd.DateOffset(months=meses_lookback)
        base = base[base["OF_DATA"] >= limite]

    if base.empty:
        cols = ["OF_CDG","REQ_DATA","OF_DATA","DIAS_UTEIS","DIAS_CORRIDOS",
                "VALOR_TOTAL_OF","EMPRD_DESC","FORNECEDOR_DESC"]
        return 0.0, 0.0, 0.0, pd.DataFrame(columns=cols)

    # Preparar numéricos para somar valor por OF
    if "PRCTTL_INSUMO" in base.columns:
        base["PRCTTL_INSUMO"] = pd.to_numeric(base["PRCTTL_INSUMO"], errors="coerce").fillna(0)
    else:
        base["PRCTTL_INSUMO"] = 0.0

    # Agregação por OF: primeira REQ, primeira OF, soma de valor e metadados
    agg = (base
           .groupby("OF_CDG", dropna=True)
           .agg(
               REQ_DATA_MIN=("REQ_DATA", "min"),
               OF_DATA_REF=("OF_DATA", "min"),
               VALOR_TOTAL_OF=("PRCTTL_INSUMO", "sum"),
               EMPRD_DESC=("EMPRD_DESC", "first"),
               FORNECEDOR_DESC=("FORNECEDOR_DESC", "first"),
           )
           .reset_index())

    # Remover inconsistências (OF antes da REQ)
    agg = agg[agg["OF_DATA_REF"] >= agg["REQ_DATA_MIN"]].copy()
    if agg.empty:
        cols = ["OF_CDG","REQ_DATA","OF_DATA","DIAS_UTEIS","DIAS_CORRIDOS",
                "VALOR_TOTAL_OF","EMPRD_DESC","FORNECEDOR_DESC"]
        return 0.0, 0.0, 0.0, pd.DataFrame(columns=cols)

    # Dias corridos
    agg["DIAS_CORRIDOS"] = (agg["OF_DATA_REF"] - agg["REQ_DATA_MIN"]).dt.days.astype(int)

    # Dias úteis (seg-sex) com feriados opcionais
    weekmask = "1111100"
    start = agg["REQ_DATA_MIN"].dt.date.values.astype("datetime64[D]")
    end   = agg["OF_DATA_REF"].dt.date.values.astype("datetime64[D]")

    hol = None
    if feriados:
        try:
            hol_list = [pd.to_datetime(d).date() for d in list(feriados) if pd.notna(d)]
            if len(hol_list) > 0:
                hol = np.asarray(hol_list, dtype="datetime64[D]").ravel()
        except Exception:
            hol = None

    if hol is not None and hol.size > 0:
        dias_uteis = np.busday_count(begindates=start, enddates=end, weekmask=weekmask, holidays=hol)
    else:
        dias_uteis = np.busday_count(begindates=start, enddates=end, weekmask=weekmask)

    agg["DIAS_UTEIS"] = dias_uteis.astype(int)

    # Série alvo conforme parâmetro
    col = "DIAS_UTEIS" if considerar_dias_uteis else "DIAS_CORRIDOS"
    serie = pd.to_numeric(agg[col], errors="coerce").dropna()

    if serie.empty:
        cols = ["OF_CDG","REQ_DATA","OF_DATA","DIAS_UTEIS","DIAS_CORRIDOS",
                "VALOR_TOTAL_OF","EMPRD_DESC","FORNECEDOR_DESC"]
        return 0.0, 0.0, 0.0, pd.DataFrame(columns=cols)

    media = float(serie.mean())
    mediana = float(serie.median())
    p90 = float(np.percentile(serie.to_numpy(), 90))

    # DataFrame detalhado para exploração/visualização
    df_duracoes = (agg
                   .rename(columns={"REQ_DATA_MIN": "REQ_DATA", "OF_DATA_REF": "OF_DATA"})
                   [["OF_CDG","REQ_DATA","OF_DATA","DIAS_UTEIS","DIAS_CORRIDOS",
                     "VALOR_TOTAL_OF","EMPRD_DESC","FORNECEDOR_DESC"]]
                   .sort_values(col, ascending=False)
                   .reset_index(drop=True))

    return round(media, 2), round(mediana, 2), round(p90, 2), df_duracoes

def tempos_medios_12m_5a(
    df: pd.DataFrame,
    considerar_dias_uteis: bool = True,
    feriados: Optional[List[str]] = None,
) -> Tuple[float, float]:
    """
    Retorna o tempo médio de geração de OF:
      - últimos 12 meses
      - últimos 5 anos (60 meses)

    Usa REQ_DATA -> OF_DATA e a lógica já existente em tempo_medio_geracao_of.
    considerar_dias_uteis=True utiliza dias úteis (seg-sex, com feriados opcionais).
    """
    media_12m, _, _, _ = tempo_medio_geracao_of(
        df,
        considerar_dias_uteis=considerar_dias_uteis,
        meses_lookback=12,
        feriados=feriados,
    )
    media_5a, _, _, _ = tempo_medio_geracao_of(
        df,
        considerar_dias_uteis=considerar_dias_uteis,
        meses_lookback=60,  # 5 anos
        feriados=feriados,
    )
    return round(float(media_12m), 2), round(float(media_5a), 2)

def quantidade_ofs_ate_300_2024_2025(
    df: pd.DataFrame,
    limite: float = 300.0,
    anos: tuple[int, ...] = (2024, 2025),
    excluir_itens_nao_positivos: bool = True,  # True = ignora linhas com total <= 0
) -> tuple[dict, pd.DataFrame]:
    """
    Conta OFs distintas com valor total < limite nos anos especificados (padrão: 2024 e 2025).

    Retorna:
      - resumo (dict): {"2024": X, "2025": Y, "TOTAL_2024_2025": Z}
      - df_ofs (DataFrame): detalhes por OF (OF_CDG, ANO, VALOR_TOTAL_OF, OF_DATA, EMPRD_DESC, FORNECEDOR_DESC)
    """
    base = df.copy()

    # Datas e valores
    base["OF_DATA_DT"] = pd.to_datetime(base.get("OF_DATA"), errors="coerce")
    base["PRCTTL_INSUMO"] = pd.to_numeric(base.get("PRCTTL_INSUMO"), errors="coerce")

    # Mantém linhas válidas
    base = base.dropna(subset=["OF_DATA_DT", "OF_CDG"]).copy()

    # Opcional: ignorar itens com total <= 0 para não "puxar" OF pra baixo artificialmente
    if excluir_itens_nao_positivos:
        base = base[base["PRCTTL_INSUMO"] > 0]

    if base.empty:
        return {str(a): 0 for a in anos} | {f"TOTAL_{'_'.join(map(str, anos))}": 0}, \
               pd.DataFrame(columns=["OF_CDG","ANO","VALOR_TOTAL_OF","OF_DATA","EMPRD_DESC","FORNECEDOR_DESC"])

    # Agrega por OF (soma dos itens e pega a primeira data da OF)
    agg = (
        base.groupby("OF_CDG", dropna=True)
            .agg(
                VALOR_TOTAL_OF=("PRCTTL_INSUMO", "sum"),
                OF_DATA=("OF_DATA_DT", "min"),
                EMPRD_DESC=("EMPRD_DESC", "first"),
                FORNECEDOR_DESC=("FORNECEDOR_DESC", "first"),
            )
            .reset_index()
    )

    # Normaliza tipos
    agg["VALOR_TOTAL_OF"] = pd.to_numeric(agg["VALOR_TOTAL_OF"], errors="coerce")
    agg["ANO"] = agg["OF_DATA"].dt.year

    # Filtro: anos alvo e total < limite (estritamente menor que 300, como pedido)
    sel = agg[(agg["ANO"].isin(anos)) & (agg["VALOR_TOTAL_OF"] < float(limite))].copy()

    if sel.empty:
        return {str(a): 0 for a in anos} | {f"TOTAL_{'_'.join(map(str, anos))}": 0}, \
               pd.DataFrame(columns=["OF_CDG","ANO","VALOR_TOTAL_OF","OF_DATA","EMPRD_DESC","FORNECEDOR_DESC"])

    # Contagens por ano
    counts_por_ano = sel["ANO"].value_counts().reindex(anos, fill_value=0).to_dict()
    resumo = {str(a): int(counts_por_ano.get(a, 0)) for a in anos}
    resumo[f"TOTAL_{'_'.join(map(str, anos))}"] = int(len(sel))

    # Ajustes finais de output
    sel["VALOR_TOTAL_OF"] = sel["VALOR_TOTAL_OF"].round(2)
    sel = sel.sort_values(["ANO", "VALOR_TOTAL_OF", "OF_CDG"]).reset_index(drop=True)

    return resumo, sel[["OF_CDG","ANO","VALOR_TOTAL_OF","OF_DATA","EMPRD_DESC","FORNECEDOR_DESC"]]

def requisicoes_ofs_por_mes(
    df: pd.DataFrame,
    ano: int = 2025,
    col_req: str = "REQ_CDG",
    col_of: str = "OF_CDG",
    col_empr: str = "EMPRD",
) -> pd.DataFrame:
    """
    Conta REQUISIÇÕES e OFs distintas por mês, considerando apenas datas dentro do ano escolhido.
    REQ = chave (REQ_CDG, EMPRD)
    OF  = chave (OF_CDG)
    """
    base = df.copy()

    # Garantir datetime
    base["REQ_DATA_DT"] = pd.to_datetime(base.get("REQ_DATA"), errors="coerce")
    base["OF_DATA_DT"]  = pd.to_datetime(base.get("OF_DATA"),  errors="coerce")

    # --- Contagem de REQ (apenas ano selecionado pela própria REQ_DATA)
    df_req = (
        base[(base["REQ_DATA_DT"].dt.year == ano)]
        .dropna(subset=["REQ_DATA_DT", col_req, col_empr])
        .drop_duplicates(subset=[col_req, col_empr])
    )

    if not df_req.empty:
        df_req["ANO_MES"] = df_req["REQ_DATA_DT"].dt.to_period("M")
        df_req = df_req.groupby("ANO_MES")[col_req].count().reset_index(name="REQUISICOES")
    else:
        df_req = pd.DataFrame(columns=["ANO_MES", "REQUISICOES"])

    # --- Contagem de OF (apenas ano selecionado pela própria OF_DATA)
    df_of = (
        base[(base["OF_DATA_DT"].dt.year == ano)]
        .dropna(subset=["OF_DATA_DT", col_of])
        .drop_duplicates(subset=[col_of])
    )

    if not df_of.empty:
        df_of["ANO_MES"] = df_of["OF_DATA_DT"].dt.to_period("M")
        df_of = df_of.groupby("ANO_MES")[col_of].count().reset_index(name="OFS")
    else:
        df_of = pd.DataFrame(columns=["ANO_MES", "OFS"])

    # Mescla resultados e garante ordem
    df_mes = pd.merge(df_req, df_of, on="ANO_MES", how="outer").fillna(0)
    df_mes["ANO_MES"] = df_mes["ANO_MES"].astype(str)
    df_mes["REQUISICOES"] = df_mes["REQUISICOES"].astype(int)
    df_mes["OFS"] = df_mes["OFS"].astype(int)

    return df_mes.sort_values("ANO_MES").reset_index(drop=True)

def media_requisicoes_por_empreendimento_mes(
    df: pd.DataFrame,
    ano: int = 2025,
    col_req: str = "REQ_CDG",
    col_empr: str = "EMPRD",
    col_empr_desc: str = "EMPRD_DESC",
    col_req_data: str = "REQ_DATA",
    limite_top: int = 4
) -> pd.DataFrame:
    """
    Calcula a média mensal de requisições por empreendimento e lista empreendimentos
    que tiveram mais de `limite_top` requisições no mês, incluindo o nome resumido da obra.
    """
    base = df.copy()
    base["REQ_DATA_DT"] = pd.to_datetime(base.get(col_req_data), errors="coerce")
    base = base[base["REQ_DATA_DT"].dt.year == ano].copy()
    if base.empty:
        return pd.DataFrame(columns=["ANO_MES","TOTAL_REQ","EMPREENDIMENTOS","MEDIA_REQ_POR_EMPR","TOP_EMPREENDIMENTOS"])

    base = base.dropna(subset=["REQ_DATA_DT", col_req, col_empr])
    base = base.drop_duplicates(subset=[col_req, col_empr])
    base["ANO_MES"] = base["REQ_DATA_DT"].dt.to_period("M")

    # Se houver coluna de descrição de empreendimento, usa ela
    if col_empr_desc in base.columns:
        base[col_empr_desc] = base[col_empr_desc].astype(str)
    else:
        base[col_empr_desc] = base[col_empr].astype(str)  # fallback para código

    # Contagem geral
    req_counts = base.groupby("ANO_MES")[col_req].count().reset_index(name="TOTAL_REQ")
    empr_counts = base.groupby("ANO_MES")[col_empr].nunique().reset_index(name="EMPREENDIMENTOS")

    # Identificação dos top empreendimentos (mais de limite_top REQs)
    top_por_mes = (
        base.groupby(["ANO_MES", col_empr, col_empr_desc])[col_req]
        .count()
        .reset_index(name="QTD_REQ")
    )
    top_por_mes = top_por_mes[top_por_mes["QTD_REQ"] > limite_top]

    # Monta string com nome resumido (primeira palavra)
    top_por_mes["NOME_CURTO"] = top_por_mes[col_empr_desc].str.split().str[0]
    top_agg = (
        top_por_mes.groupby("ANO_MES")["NOME_CURTO"]
        .apply(lambda x: ", ".join(sorted(set(x))))
        .reset_index(name="TOP_EMPREENDIMENTOS")
    )

    df_out = req_counts.merge(empr_counts, on="ANO_MES", how="outer").merge(top_agg, on="ANO_MES", how="left")
    df_out["MEDIA_REQ_POR_EMPR"] = df_out["TOTAL_REQ"] / df_out["EMPREENDIMENTOS"].replace({0: pd.NA})
    df_out["ANO_MES"] = df_out["ANO_MES"].astype(str)
    return df_out.sort_values("ANO_MES").reset_index(drop=True)

def tempo_medio_req_para_of_por_mes(
    df: pd.DataFrame,
    ano: int = 2025,
    dias_uteis_sla: int = 3,
    col_req: str = "REQ_CDG",
    col_req_data: str = "REQ_DATA",
    col_of_data: str = "OF_DATA"
) -> pd.DataFrame:
    """
    Calcula o tempo médio (em dias úteis) entre REQ_DATA e OF_DATA, por mês de 2025.
    Também conta quantas ultrapassaram o SLA (dias_uteis_sla).

    Retorna DataFrame com:
      ANO_MES | MEDIA_DIAS_UTEIS | TOTAL_OFS | ULTRAPASSARAM_SLA
    """
    base = df.copy()
    base["REQ_DATA_DT"] = pd.to_datetime(base.get(col_req_data), errors="coerce")
    base["OF_DATA_DT"] = pd.to_datetime(base.get(col_of_data), errors="coerce")

    # Manter apenas linhas válidas e do ano desejado (considerando OF_DATA para agrupar por mês)
    base = base.dropna(subset=["REQ_DATA_DT", "OF_DATA_DT"]).copy()
    base = base[base["OF_DATA_DT"].dt.year == ano]

    if base.empty:
        return pd.DataFrame(columns=["ANO_MES", "MEDIA_DIAS_UTEIS", "TOTAL_OFS", "ULTRAPASSARAM_SLA"])

    # Agregar por OF para não duplicar cálculo
    agg = (
        base.groupby("OF_CDG", dropna=True)
        .agg(
            REQ_DATA_MIN=("REQ_DATA_DT", "min"),
            OF_DATA_REF=("OF_DATA_DT", "min")
        )
        .reset_index()
    )

    # Remove OFs inconsistentes
    agg = agg[agg["OF_DATA_REF"] >= agg["REQ_DATA_MIN"]].copy()
    if agg.empty:
        return pd.DataFrame(columns=["ANO_MES", "MEDIA_DIAS_UTEIS", "TOTAL_OFS", "ULTRAPASSARAM_SLA"])

    # Calcula dias úteis
    start = agg["REQ_DATA_MIN"].dt.date.values.astype("datetime64[D]")
    end   = agg["OF_DATA_REF"].dt.date.values.astype("datetime64[D]")
    weekmask = "1111100"  # seg..sex
    dias_uteis = np.busday_count(begindates=start, enddates=end, weekmask=weekmask)

    agg["DIAS_UTEIS"] = dias_uteis.astype(int)
    agg["ANO_MES"] = agg["OF_DATA_REF"].dt.to_period("M")

    # Agrupa por mês
    res = (
        agg.groupby("ANO_MES")
        .agg(
            MEDIA_DIAS_UTEIS=("DIAS_UTEIS", "mean"),
            TOTAL_OFS=("OF_CDG", "count"),
            ULTRAPASSARAM_SLA=("DIAS_UTEIS", lambda x: (x > dias_uteis_sla).sum()))
        .reset_index())

    res["MEDIA_DIAS_UTEIS"] = res["MEDIA_DIAS_UTEIS"].round(2)
    res["ANO_MES"] = res["ANO_MES"].astype(str)
    return res.sort_values("ANO_MES").reset_index(drop=True)

def total_ofs_por_ano(
    df: pd.DataFrame,
    anos: tuple[int, ...] = (2024, 2025),
    col_of: str = "OF_CDG",
    col_of_data: str = "OF_DATA"
) -> dict:
    """
    Conta OFs distintas para os anos informados.
    Retorna dict com {"2024": X, "2025": Y}
    """
    base = df.copy()
    base["OF_DATA_DT"] = pd.to_datetime(base.get(col_of_data), errors="coerce")
    base = base.dropna(subset=["OF_DATA_DT", col_of])
    base["ANO"] = base["OF_DATA_DT"].dt.year

    # conta OFs distintas por ano
    contagens = (
        base.groupby("ANO")[col_of]
        .nunique()
        .reindex(anos, fill_value=0)
        .to_dict())
    return {str(k): int(v) for k, v in contagens.items()}

def total_ofs_basico_vs_nao(
    df: pd.DataFrame,
    ano: int = 2025,
    mes: int = 8,
    col_tipo: str = "TIPO_MATERIAL",
    col_of: str = "OF_CDG",
    col_data: str = "OF_DATA"
) -> dict:
    """
    Conta OFs distintas no mês/ano informado, separando:
    - OFs que tiveram ao menos 1 item básico
    - OFs que não tiveram nenhum item básico

    Retorna dict com {"BÁSICO": X, "ESPECÍFICO": Y, "TOTAL": Z}
    """
    base = df.copy()
    base["OF_DATA_DT"] = pd.to_datetime(base.get(col_data), errors="coerce")
    base = base.dropna(subset=["OF_DATA_DT", col_of, col_tipo])

    # Filtra pelo mês/ano
    base = base[(base["OF_DATA_DT"].dt.year == ano) & (base["OF_DATA_DT"].dt.month == mes)]
    if base.empty:
        return {"BÁSICO": 0, "ESPECÍFICO": 0, "TOTAL": 0}

    # Cria um agrupamento por OF → se há pelo menos 1 item básico
    agrupado = (
        base.groupby(col_of)[col_tipo]
        .apply(lambda x: "BÁSICO" if "BÁSICO" in set(x) else "ESPECÍFICO")
        .reset_index(name="TIPO_OF")
    )

    total_basico = (agrupado["TIPO_OF"] == "BÁSICO").sum()
    total_especifico = (agrupado["TIPO_OF"] == "ESPECÍFICO").sum()

    return {
        "BÁSICO": int(total_basico),
        "ESPECÍFICO": int(total_especifico),
        "TOTAL": int(len(agrupado))
    }

