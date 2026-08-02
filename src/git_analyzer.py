"""Modulo responsavel por analisar o historico do Git do repositorio."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pandas as pd


class GitRepositoryError(Exception):
    """Erro levantado quando o caminho informado nao e um repositorio Git valido."""


class GitAnalyzer:
    """Extrai metricas de historico do Git a partir de um repositorio local.

    O analisador lista apenas arquivos rastreados no HEAD atual e, para cada um,
    calcula quantos commits o tocaram e quantos autores distintos contribuiram,
    seguindo renomeacoes via ``git log --follow``.
    """

    def __init__(self, repo_path: str) -> None:
        self.repo_path = str(Path(repo_path).resolve())

        if not os.path.isdir(self.repo_path):
            raise GitRepositoryError(
                f"Caminho do repositorio nao existe: {self.repo_path}"
            )

        self._validate_git_repository()

    def _run_git(self, args: list[str]) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            raise GitRepositoryError(
                stderr or f"Comando git falhou: git {' '.join(args)}"
            )

        return result.stdout

    def _validate_git_repository(self) -> None:
        git_dir = os.path.join(self.repo_path, ".git")
        if not (os.path.isdir(git_dir) or os.path.isfile(git_dir)):
            raise GitRepositoryError(
                f"Caminho nao e um repositorio Git valido: {self.repo_path}"
            )

        output = self._run_git(["rev-parse", "--is-inside-work-tree"]).strip()
        if output != "true":
            raise GitRepositoryError(
                f"Caminho nao e um repositorio Git valido: {self.repo_path}"
            )

    def get_current_files(self) -> list[str]:
        """Retorna caminhos relativos de todos os arquivos rastreados no HEAD."""
        output = self._run_git(["ls-tree", "-r", "HEAD", "--name-only"])
        return [line for line in output.splitlines() if line.strip()]

    def get_file_metrics(self, file_path: str) -> dict[str, int]:
        """Retorna metricas de historico para um arquivo especifico."""
        commit_output = self._run_git(
            ["log", "--follow", "--pretty=format:%H", "--", file_path]
        )
        commit_count = len(
            [line for line in commit_output.splitlines() if line.strip()]
        )

        author_output = self._run_git(
            ["log", "--follow", "--pretty=format:%an", "--", file_path]
        )
        authors = {
            line.strip()
            for line in author_output.splitlines()
            if line.strip()
        }
        author_count = len(authors)

        return {
            "commit_count": commit_count,
            "author_count": author_count,
        }

    def analyze(self) -> pd.DataFrame:
        """Analisa todos os arquivos atuais e retorna um DataFrame com metricas."""
        files = self.get_current_files()
        total = len(files)
        rows: list[dict[str, int | str]] = []

        for index, file_path in enumerate(files, start=1):
            metrics = self.get_file_metrics(file_path)
            rows.append(
                {
                    "file_path": file_path,
                    "commit_count": metrics["commit_count"],
                    "author_count": metrics["author_count"],
                }
            )
            print(f"Analisando historico Git: {index}/{total} arquivos")

        return pd.DataFrame(rows, columns=["file_path", "commit_count", "author_count"])


if __name__ == "__main__":
    analyzer = GitAnalyzer(".")
    df = analyzer.analyze()
    print(df.head())
