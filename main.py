"""CLI do git-hotspot-radar — orquestra analise Git, complexidade e resumo LLM."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.complexity import ComplexityAnalyzer
from src.git_analyzer import GitAnalyzer, GitRepositoryError
from src.merger import EmptyMergeError, build_ranking
from src.summary_llm import HotspotSummarizer, LLMRequestError, MissingAPIKeyError

_RANKING_COLUMNS = (
    "file_path",
    "nloc",
    "max_complexity",
    "commit_count",
    "author_count",
    "risk_score",
)


def parse_args() -> argparse.Namespace:
    """Define e retorna os argumentos da linha de comando."""
    parser = argparse.ArgumentParser(
        description=(
            "Identifica hotspots de risco cruzando complexidade ciclomatica "
            "com o historico do Git."
        )
    )
    parser.add_argument(
        "--repo-path",
        required=True,
        help="Caminho para o repositorio Git a ser analisado.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        help=(
            "Quantidade de hotspots criticos no ranking final e no resumo do LLM "
            "(padrao: 10)."
        ),
    )
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help=(
            "Pula a chamada ao OpenRouter e gera apenas o ranking em CSV/console, "
            "util para testes sem gastar quota de API."
        ),
    )
    parser.add_argument(
        "--output",
        default="hotspot_report.md",
        help="Caminho do arquivo de relatorio final (padrao: hotspot_report.md).",
    )
    return parser.parse_args()


def _dataframe_to_markdown_table(df: pd.DataFrame) -> str:
    """Converte um DataFrame em tabela Markdown sem dependencias extras."""
    headers = "| " + " | ".join(df.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(df.columns)) + " |"
    rows = [
        "| " + " | ".join(str(value) for value in row) + " |"
        for row in df.values
    ]
    return "\n".join([headers, separator, *rows])


def build_report(
    top_hotspots: pd.DataFrame,
    *,
    executive_summary: str | None = None,
    llm_error_note: str | None = None,
    skip_llm: bool = False,
) -> str:
    """Monta o conteudo final do relatorio em Markdown.

    Args:
        top_hotspots: DataFrame com os hotspots mais criticos.
        executive_summary: Texto do resumo executivo gerado pelo LLM, se disponivel.
        llm_error_note: Mensagem de erro amigavel quando o LLM falhou.
        skip_llm: Indica se a geracao via LLM foi deliberadamente ignorada.

    Returns:
        Conteudo completo do relatorio em Markdown.
    """
    executed_at = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    table_df = top_hotspots.loc[:, list(_RANKING_COLUMNS)]
    sections = [
        "# Relatorio de Hotspots de Risco",
        "",
        f"**Gerado em:** {executed_at}",
        "",
        f"## Top {len(top_hotspots)} Hotspots",
        "",
        _dataframe_to_markdown_table(table_df),
    ]

    if executive_summary:
        sections.extend(
            [
                "",
                "## Resumo Executivo",
                "",
                executive_summary,
            ]
        )
    elif not skip_llm:
        sections.extend(
            [
                "",
                "## Resumo Executivo",
                "",
                (
                    "_O resumo executivo nao pode ser gerado._"
                    + (f" {llm_error_note}" if llm_error_note else "")
                ),
            ]
        )

    sections.append("")
    return "\n".join(sections)


def run(args: argparse.Namespace) -> None:
    """Executa o fluxo completo de analise e gera o relatorio de hotspots.

    Args:
        args: Namespace com os argumentos parseados da CLI.
    """
    try:
        repo_path = Path(args.repo_path)

        if not repo_path.exists():
            print(f"Erro: o caminho informado nao existe: {repo_path}")
            sys.exit(1)

        try:
            git_analyzer = GitAnalyzer(str(repo_path))
            git_df = git_analyzer.analyze()
        except GitRepositoryError as exc:
            print(f"Erro ao analisar repositorio Git: {exc}")
            sys.exit(1)

        try:
            complexity_analyzer = ComplexityAnalyzer(str(repo_path))
            complexity_df = complexity_analyzer.analyze()
        except FileNotFoundError as exc:
            print(f"Erro ao analisar complexidade: {exc}")
            sys.exit(1)

        try:
            ranking = build_ranking(complexity_df, git_df)
        except EmptyMergeError as exc:
            print(f"Erro ao cruzar metricas: {exc}")
            sys.exit(1)

        top_hotspots = ranking.head(args.top)

        print("\n=== Top Hotspots ===\n")
        print(top_hotspots.loc[:, list(_RANKING_COLUMNS)].to_string(index=False))

        executive_summary: str | None = None
        llm_error_note: str | None = None

        if not args.skip_llm:
            try:
                summarizer = HotspotSummarizer()
                executive_summary = summarizer.generate_summary(top_hotspots)
            except MissingAPIKeyError as exc:
                llm_error_note = str(exc)
                print(f"\nAviso: {exc}")
            except LLMRequestError as exc:
                llm_error_note = str(exc)
                print(f"\nAviso: {exc}")

        report = build_report(
            top_hotspots,
            executive_summary=executive_summary,
            llm_error_note=llm_error_note,
            skip_llm=args.skip_llm,
        )

        output_path = Path(args.output)
        output_path.write_text(report, encoding="utf-8")
        print(f"\nRelatorio salvo em: {output_path.resolve()}")

    except Exception as exc:
        print(f"Erro inesperado: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    run(parse_args())
