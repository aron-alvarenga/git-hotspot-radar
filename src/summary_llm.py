"""Modulo responsavel por gerar resumos via LLM a partir dos hotspots identificados."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI
from openai import OpenAIError

_PROMPT_COLUMNS = (
    "file_path",
    "nloc",
    "max_complexity",
    "commit_count",
    "author_count",
    "risk_score",
)


class MissingAPIKeyError(Exception):
    """Erro levantado quando a chave da API do OpenRouter nao esta configurada."""


class LLMRequestError(Exception):
    """Erro levantado quando a chamada ao modelo de linguagem falha."""


class HotspotSummarizer:
    """Gera resumos executivos de hotspots criticos via OpenRouter."""

    def __init__(self, api_key: str | None = None) -> None:
        """Inicializa o summarizer e o client da OpenAI apontando para o OpenRouter.

        Args:
            api_key: Chave da API do OpenRouter. Se omitida, tenta ler
                ``OPENROUTER_API_KEY`` do ambiente (carregando ``.env`` se existir).

        Raises:
            MissingAPIKeyError: Se nenhuma chave valida estiver disponivel.
        """
        resolved_key = api_key or self._load_api_key_from_env()

        if not resolved_key:
            raise MissingAPIKeyError(
                "Chave da API do OpenRouter nao encontrada. "
                "Copie o arquivo .env.example para .env e defina OPENROUTER_API_KEY "
                "com a chave obtida em https://openrouter.ai/keys."
            )

        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=resolved_key,
        )

    @staticmethod
    def _load_api_key_from_env() -> str | None:
        """Carrega variaveis de um arquivo .env local e retorna a chave da API."""
        env_path = Path(".env")
        if env_path.is_file():
            load_dotenv(env_path)

        return os.getenv("OPENROUTER_API_KEY") or None

    def build_prompt(self, top_hotspots_df: pd.DataFrame) -> str:
        """Monta o prompt em portugues com os hotspots e instrucoes de resumo.

        Args:
            top_hotspots_df: DataFrame com os hotspots mais criticos, contendo
                as colunas file_path, nloc, max_complexity, commit_count,
                author_count e risk_score.

        Returns:
            Prompt completo pronto para envio ao modelo.
        """
        table_lines = [
            "file_path | nloc | max_complexity | commit_count | author_count | risk_score",
            "-" * 88,
        ]

        for _, row in top_hotspots_df.iterrows():
            table_lines.append(
                f"{row['file_path']} | {row['nloc']} | {row['max_complexity']} | "
                f"{row['commit_count']} | {row['author_count']} | {row['risk_score']}"
            )

        hotspots_table = "\n".join(table_lines)

        return (
            "Voce e um consultor tecnico analisando hotspots de risco em um repositorio de codigo.\n\n"
            "Dados dos arquivos mais criticos:\n\n"
            f"{hotspots_table}\n\n"
            "Com base nos dados acima, produza um resumo executivo objetivo direcionado a lideranca "
            "tecnica, sem jargao excessivo. Destaque os 3 arquivos mais criticos e explique o motivo "
            "de cada um estar no topo. Em seguida, sugira acoes concretas para cada um dos 3 "
            "(ex.: refatoracao, aumento de cobertura de testes, revisao de ownership).\n\n"
            "Responda de forma direta, sem introducoes longas."
        )

    def generate_summary(
        self,
        top_hotspots_df: pd.DataFrame,
        model: str = "openrouter/free",
    ) -> str:
        """Gera um resumo executivo dos hotspots via OpenRouter.

        Args:
            top_hotspots_df: DataFrame com os hotspots mais criticos.
            model: Identificador do modelo no OpenRouter.

        Returns:
            Texto do resumo executivo gerado pelo modelo.

        Raises:
            LLMRequestError: Se a chamada ao modelo falhar por qualquer motivo.
        """
        prompt = self.build_prompt(top_hotspots_df)

        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
            )
        except OpenAIError as exc:
            raise LLMRequestError(
                f"Falha ao gerar resumo executivo via OpenRouter: {exc}"
            ) from exc

        content = response.choices[0].message.content
        if content is None:
            raise LLMRequestError(
                "Falha ao gerar resumo executivo via OpenRouter: "
                "o modelo retornou uma resposta vazia."
            )

        return content


if __name__ == "__main__":
    mock_hotspots = pd.DataFrame(
        {
            "file_path": [
                "src/merger.py",
                "src/git_analyzer.py",
                "src/complexity.py",
            ],
            "nloc": [118, 245, 125],
            "max_complexity": [12, 18, 9],
            "commit_count": [32, 28, 15],
            "author_count": [5, 7, 3],
            "risk_score": [1920, 3528, 405],
        }
    )

    summarizer = HotspotSummarizer()
    summary = summarizer.generate_summary(mock_hotspots)
    print(summary)
