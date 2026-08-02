"""Modulo responsavel por calcular a complexidade ciclomatica dos arquivos."""

from __future__ import annotations

import contextlib
import io
import re
from pathlib import Path

import lizard
import pandas as pd


class ComplexityAnalyzer:
    """Extrai metricas de complexidade ciclomatica dos arquivos de um repositorio.

    O analisador percorre recursivamente o caminho informado usando o lizard,
    calculando linhas de codigo e estatisticas de complexidade ciclomatica por
    arquivo. Arquivos que nao puderem ser analisados sao ignorados silenciosamente.
    """

    _LIZARD_ERROR_PATTERN = re.compile(
        r"(?:Error: (?:doesn't support none utf encoding|Fail to read source file)|"
        r"\[skip\] fail to process) '([^']+)'"
    )

    def __init__(self, repo_path: str) -> None:
        """Inicializa o analisador com o caminho raiz do repositorio.

        Args:
            repo_path: Caminho para o diretorio a ser analisado.

        Raises:
            FileNotFoundError: Se o caminho informado nao existir.
        """
        self.repo_path = Path(repo_path).resolve()

        if not self.repo_path.is_dir():
            raise FileNotFoundError(
                f"Caminho do repositorio nao existe: {self.repo_path}"
            )

    def _relative_path(self, absolute_path: str) -> str:
        """Converte um caminho absoluto em relativo ao repo_path com barras '/'."""
        return Path(absolute_path).resolve().relative_to(self.repo_path).as_posix()

    def _extract_row(self, file_info: lizard.FileInformation) -> dict[str, int | str | float]:
        """Extrai as metricas de complexidade de um arquivo analisado pelo lizard."""
        complexities = [function.cyclomatic_complexity for function in file_info.function_list]
        function_count = len(complexities)

        if function_count:
            max_complexity = max(complexities)
            avg_complexity = sum(complexities) / function_count
        else:
            max_complexity = 0
            avg_complexity = 0.0

        return {
            "file_path": self._relative_path(file_info.filename),
            "nloc": file_info.nloc,
            "max_complexity": max_complexity,
            "avg_complexity": avg_complexity,
            "function_count": function_count,
        }

    def _parse_failed_files(self, stderr_output: str) -> set[str]:
        """Extrai caminhos absolutos de arquivos que o lizard nao conseguiu analisar."""
        return {str(Path(path).resolve()) for path in self._LIZARD_ERROR_PATTERN.findall(stderr_output)}

    def analyze(self) -> pd.DataFrame:
        """Analisa a complexidade ciclomatica de todos os arquivos suportados pelo lizard.

        Returns:
            DataFrame com colunas file_path, nloc, max_complexity, avg_complexity
            e function_count para cada arquivo analisado com sucesso.
        """
        rows: list[dict[str, int | str | float]] = []
        skipped_count = 0
        file_infos: list[lizard.FileInformation] = []
        stderr_buffer = io.StringIO()

        with contextlib.redirect_stderr(stderr_buffer):
            try:
                for file_info in lizard.analyze([str(self.repo_path)]):
                    file_infos.append(file_info)
            except IndexError:
                skipped_count += 1

        failed_files = self._parse_failed_files(stderr_buffer.getvalue())

        for file_info in file_infos:
            resolved_path = str(Path(file_info.filename).resolve())

            if resolved_path in failed_files:
                skipped_count += 1
                continue

            try:
                rows.append(self._extract_row(file_info))
            except (OSError, ValueError):
                skipped_count += 1

        if skipped_count:
            print(
                f"{skipped_count} arquivos nao puderam ser analisados e foram ignorados"
            )

        return pd.DataFrame(
            rows,
            columns=[
                "file_path",
                "nloc",
                "max_complexity",
                "avg_complexity",
                "function_count",
            ],
        )


if __name__ == "__main__":
    analyzer = ComplexityAnalyzer(".")
    df = analyzer.analyze()
    print(df.sort_values("max_complexity", ascending=False).head(10))
