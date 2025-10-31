# fornecedores_core.py
import pandas as pd
from pathlib import Path

# ---------- Carga ----------
def carregar_fornecedores(path: Path | None = None, sheet: int | str = 0) -> pd.DataFrame:
    """
    Lê a base de fornecedores (padrão: FornecedoresAtivos.xlsx no mesmo diretório).
    """
    base_dir = Path(__file__).parent
    arq = path or (base_dir / "FornecedoresAtivos.xlsx")
    df = pd.read_excel(arq, sheet_name=sheet)
    return df

# util interno: detectar coluna
def _col(df: pd.DataFrame, candidatos):
    """Retorna a 1ª coluna encontrada entre candidatos/aliases (case-insensitive, com trim)."""
    aliases = {
        "FORNECEDOR_CDG": ["FORNECEDOR_ID", "COD_FORNECEDOR", "FORN_ID", "FORN_CODIGO", "FORN_CDG",
                           "FORN_CNPJ", "CNPJ", "PED_FORNECEDOR", "FORNECEDOR"],
        "FORNECEDOR_UF":  ["FORN_UF", "UF"],
        "DATA_OF":        ["OF_DATA", "PED_DT", "REQ_DATA", "DATA", "DT"],
    }

    # Expande candidatos com aliases
    lista = []
    for c in candidatos:
        lista.append(c)
        lista.extend(aliases.get(c, []))

    # Match exato e case-insensitive/trim
    cols = list(df.columns)
    upmap = {c.strip().upper(): c for c in cols}
    for cand in lista:
        key = cand.strip().upper()
        if key in upmap:
            return upmap[key]
        # fallback por substring (ex.: pega qualquer coluna que contenha 'CNPJ')
        for k, original in upmap.items():
            if key in k:
                return original

    raise KeyError(f"Não encontrei nenhuma das colunas: {candidatos}. Disponíveis: {cols}")


def total_empresas_cadastradas(df_forn: pd.DataFrame, col_id: str | None = None) -> int:
    """Conta fornecedores únicos de maneira robusta."""
    # tenta identificar coluna de ID
    try:
        col = col_id or _col(df_forn, ["FORNECEDOR_CDG"])
    except KeyError:
        # fallback direto para CNPJ/variantes
        col = _col(df_forn, ["FORN_CNPJ", "CNPJ"])

    s = (
        df_forn[col]
        .astype("string")
        .str.strip()
        .replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
        .dropna()
    )
    return int(s.nunique())

def serie_fornecedores_ativos_ultimos_anos(df_erp: pd.DataFrame,
                                           anos: int = 10,
                                           col_id: str = "FORNECEDOR_CDG",
                                           col_data: str = "OF_DATA") -> tuple[pd.DataFrame, dict]:
    """
    Série anual (últimos N anos) de fornecedores *ativos* no ERP (ao menos 1 OF no ano).
    Retorna (df_serie, resumo) onde:
      df_serie = ANO | FORNECEDORES_ATIVOS
      resumo = {'primeiro_ano':..., 'ultimo_ano':..., 'var_abs':..., 'var_pct':...}
    """
    df = df_erp.copy()
    df[col_data + "_DT"] = pd.to_datetime(df[col_data], errors="coerce")

    limite = pd.Timestamp.today() - pd.DateOffset(years=anos)
    base = df[df[col_data + "_DT"] >= limite].copy()
    if base.empty or col_id not in base.columns:
        return pd.DataFrame(columns=["ANO", "FORNECEDORES_ATIVOS"]), {
            "primeiro_ano": None, "ultimo_ano": None, "var_abs": 0, "var_pct": 0.0
        }

    base["ANO"] = base[col_data + "_DT"].dt.year
    serie = (base.groupby("ANO")[col_id]
             .nunique()
             .reset_index(name="FORNECEDORES_ATIVOS")
             .sort_values("ANO"))

    if serie.empty:
        return serie, {"primeiro_ano": None, "ultimo_ano": None, "var_abs": 0, "var_pct": 0.0}

    prim = serie.iloc[0]["FORNECEDORES_ATIVOS"]
    ult  = serie.iloc[-1]["FORNECEDORES_ATIVOS"]
    var_abs = int(ult - prim)
    var_pct = float((ult - prim) / prim * 100) if prim else 0.0

    resumo = {
        "primeiro_ano": int(serie.iloc[0]["ANO"]),
        "ultimo_ano":   int(serie.iloc[-1]["ANO"]),
        "var_abs":      var_abs,
        "var_pct":      var_pct
    }
    return serie, resumo

def serie_fornecedores_cadastrados_por_ano(df_forn: pd.DataFrame,
                                           anos: int = 10,
                                           col_id: str | None = None,
                                           col_data_cad: str | None = None) -> pd.DataFrame:
    """
    Série anual de fornecedores CADASTRADOS (primeira data de cadastro por fornecedor).
    Retorna df com colunas: ANO | FORNECEDORES_CADASTRADOS
    """
    df = df_forn.copy()

    # Detecta ID do fornecedor
    try:
        col_id = col_id or _col(df, ["FORNECEDOR_CDG", "FORNECEDOR_ID", "COD_FORNECEDOR", "FORN_CNPJ", "CNPJ"])
    except KeyError:
        raise KeyError("Não encontrei coluna de ID do fornecedor.")

    # Detecta data de cadastro (vários aliases comuns)
    try:
        col_data_cad = col_data_cad or _col(
            df,
            ["DATA_CADASTRO", "DT_CADASTRO", "DATA_INCLUSAO", "DT_INCLUSAO",
             "CRIACAO", "DATA_CRIACAO", "CADASTRO_DATA", "INCLUSAO", "DT_CAD", "DATA", "FORN_DTCADASTRO"]
        )
    except KeyError:
        raise KeyError("Não encontrei coluna de data de cadastro.")

    df[col_data_cad] = pd.to_datetime(df[col_data_cad], errors="coerce")
    base = df.dropna(subset=[col_data_cad]).copy()
    if base.empty:
        return pd.DataFrame(columns=["ANO", "FORNECEDORES_CADASTRADOS"])

    # Primeiro cadastro por fornecedor
    first = (base.sort_values(col_data_cad)
                  .groupby(col_id, as_index=False)[col_data_cad].first())

    # Filtro de anos (opcional)
    if anos:
        limite = pd.Timestamp.today() - pd.DateOffset(years=anos)
        first = first[first[col_data_cad] >= limite]

    first["ANO"] = first[col_data_cad].dt.year
    serie = (first.groupby("ANO")[col_id]
                  .nunique()
                  .reset_index(name="FORNECEDORES_CADASTRADOS")
                  .sort_values("ANO"))

    return serie

# --- Loader da planilha de movimentação (materiais + serviços) ---
def carregar_movimentacao(path: Path | None = None, sheet: int | str = 0) -> pd.DataFrame:
    """
    Lê a planilha com as colunas:
    FORN_CNPJ | FORN_RAZAO | FORN_FANTASIA | FORN_CPFCNPJ | FORN_UF |
    FORN_DTCADASTRO | FORN_QUEMCADASTROU | ULTIMO_PEDIDO | ULTIMA_BAIXA |
    ULTIMA_MOVIMENTACAO | CATEGORIAS
    """
    base_dir = Path(__file__).parent
    arq = path or (base_dir / "AnaliseFornecedores.xlsx")  # ajuste o nome se for diferente
    df = pd.read_excel(
        arq, sheet_name=sheet,
        dtype={"FORN_CNPJ": "string", "FORN_CPFCNPJ": "string", "FORN_UF": "string"}
    )

    # Normalizações
    for c in ["FORN_CNPJ", "FORN_RAZAO", "FORN_FANTASIA", "FORN_UF", "CATEGORIAS"]:
        if c in df.columns:
            df[c] = df[c].astype("string").str.strip()

    # Datas robustas
    for col in ["FORN_DTCADASTRO", "ULTIMO_PEDIDO", "ULTIMA_BAIXA", "ULTIMA_MOVIMENTACAO"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    return df


# --- Resumo direto usando apenas a nova planilha ---
def resumo_movimentacao_fornecedores(df_mov: pd.DataFrame, anos: int = 2):
    """
    KPIs:
      - total_cadastrados
      - cadastrados_ult2a
      - utilizados_ult2a
      - nunca_utilizados

    Retorna (resumo_dict, df_nunca_utilizados)
    """
    df = df_mov.copy()

    # Garantir colunas mínimas
    for c in ["FORN_CNPJ", "FORN_DTCADASTRO", "ULTIMA_MOVIMENTACAO"]:
        if c not in df.columns:
            raise KeyError(f"Coluna obrigatória ausente: {c}")

    df["FORN_CNPJ"] = df["FORN_CNPJ"].astype("string").str.strip()
    df["FORN_DTCADASTRO"] = pd.to_datetime(df["FORN_DTCADASTRO"], errors="coerce")
    df["ULTIMA_MOVIMENTACAO"] = pd.to_datetime(df["ULTIMA_MOVIMENTACAO"], errors="coerce")

    hoje = pd.Timestamp.today().normalize()
    limite = hoje - pd.DateOffset(years=anos)

    total_cadastrados = df["FORN_CNPJ"].nunique()
    cadastrados_ult2a = df.loc[df["FORN_DTCADASTRO"] >= limite, "FORN_CNPJ"].nunique()
    utilizados_ult2a  = df.loc[df["ULTIMA_MOVIMENTACAO"] >= limite, "FORN_CNPJ"].nunique()
    nunca_utilizados  = df.loc[df["ULTIMA_MOVIMENTACAO"].isna(), "FORN_CNPJ"].nunique()

    cols_exibir = [c for c in ["FORN_CNPJ","FORN_RAZAO","FORN_FANTASIA","FORN_UF","FORN_DTCADASTRO"] if c in df.columns]
    df_nunca = df.loc[df["ULTIMA_MOVIMENTACAO"].isna(), cols_exibir].drop_duplicates().reset_index(drop=True)

    resumo = {
        "total_cadastrados": int(total_cadastrados),
        "cadastrados_ult2a": int(cadastrados_ult2a),
        "utilizados_ult2a": int(utilizados_ult2a),
        "nunca_utilizados": int(nunca_utilizados),
    }
    return resumo, df_nunca
