"""Modulo responsavel por cruzar os dados de complexidade com o historico do Git."""

from __future__ import annotations

import pandas as pd


class EmptyMergeError(Exception):
    """Erro levantado quando o merge entre complexidade e Git nao produz resultados."""


def _normalize_file_path(path: str) -> str:
    """Normaliza um caminho de arquivo para facilitar o merge entre DataFrames."""
    normalized = str(path).strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def merge_metrics(complexity_df: pd.DataFrame, git_df: pd.DataFrame) -> pd.DataFrame:
    """Unifica metricas de complexidade e historico Git por caminho de arquivo.

    Normaliza a coluna ``file_path`` em ambos os DataFrames (remove espacos,
    converte separadores para ``/`` e remove prefixos ``./``) e realiza um
    inner join, mantendo apenas arquivos presentes nas duas fontes.

    Args:
        complexity_df: DataFrame gerado pelo ComplexityAnalyzer.
        git_df: DataFrame gerado pelo GitAnalyzer.

    Returns:
        DataFrame unificado com colunas de ambas as fontes.

    Raises:
        EmptyMergeError: Se nenhum arquivo coincidir apos a normalizacao.
    """
    complexity = complexity_df.copy()
    git = git_df.copy()

    complexity["file_path"] = complexity["file_path"].map(_normalize_file_path)
    git["file_path"] = git["file_path"].map(_normalize_file_path)

    merged = complexity.merge(git, on="file_path", how="inner")

    if merged.empty:
        raise EmptyMergeError(
            "O merge entre complexidade e historico Git nao produziu resultados. "
            "Possiveis causas: caminhos com formatacao diferente entre os dois "
            "DataFrames (separadores, prefixos ou espacos), ausencia de arquivos "
            "comuns entre o lizard e o HEAD do Git, ou DataFrames de entrada vazios."
        )

    return merged


def calculate_risk_score(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula o score de risco e ordena os arquivos por prioridade.

    A formula aplicada e::

        risk_score = max_complexity * commit_count * author_count

    Valores ausentes em ``max_complexity``, ``commit_count`` ou ``author_count``
    sao tratados como zero antes da multiplicacao.

    Args:
        df: DataFrame unificado com metricas de complexidade e Git.

    Returns:
        DataFrame com a coluna ``risk_score``, ordenado de forma decrescente.
    """
    result = df.copy()

    for column in ("max_complexity", "commit_count", "author_count"):
        result[column] = result[column].fillna(0)

    result["risk_score"] = (
        result["max_complexity"] * result["commit_count"] * result["author_count"]
    )

    return result.sort_values("risk_score", ascending=False).reset_index(drop=True)


def build_ranking(complexity_df: pd.DataFrame, git_df: pd.DataFrame) -> pd.DataFrame:
    """Ponto de entrada que unifica metricas e calcula o ranking de risco.

    Args:
        complexity_df: DataFrame gerado pelo ComplexityAnalyzer.
        git_df: DataFrame gerado pelo GitAnalyzer.

    Returns:
        DataFrame ranqueado por ``risk_score`` em ordem decrescente.
    """
    merged = merge_metrics(complexity_df, git_df)
    return calculate_risk_score(merged)


if __name__ == "__main__":
    complexity_mock = pd.DataFrame(
        {
            "file_path": ["./src/app.py", "src/utils/helper.py", "  docs/readme.md  "],
            "nloc": [120, 45, 10],
            "max_complexity": [15, 8, 2],
            "avg_complexity": [5.0, 4.0, 1.0],
            "function_count": [10, 5, 2],
        }
    )

    git_mock = pd.DataFrame(
        {
            "file_path": ["src/app.py", "src\\utils\\helper.py", "other/file.py"],
            "commit_count": [20, 5, 100],
            "author_count": [4, 2, 10],
        }
    )

    ranking = build_ranking(complexity_mock, git_mock)
    print(ranking[["file_path", "max_complexity", "commit_count", "author_count", "risk_score"]])
