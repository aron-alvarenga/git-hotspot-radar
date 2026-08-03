# git-hotspot-radar

Ferramenta de linha de comando que identifica arquivos de alto risco em repositórios Git, cruzando complexidade ciclomática com métricas de churn do histórico de commits.

Arquivos que concentram lógica complexa, mudam com frequência e passam por várias mãos costumam ser os que mais geram bugs e retrabalho. O git-hotspot-radar automatiza essa triagem e produz um ranking priorizado, com opção de resumo executivo via LLM.

## Como funciona

O fluxo de análise segue quatro etapas:

1. **Histórico Git** — para cada arquivo rastreado no `HEAD`, conta commits (`git log --follow`) e autores distintos.
2. **Complexidade** — percorre o repositório com [lizard](https://github.com/terryyin/lizard) e extrai linhas de código, complexidade ciclomática máxima/média e quantidade de funções por arquivo.
3. **Ranking** — faz o cruzamento das duas fontes por caminho de arquivo e calcula um score de risco:

   ```
   risk_score = max_complexity × commit_count × author_count
   ```

4. **Relatório** — imprime o ranking no terminal e gera um arquivo Markdown. Opcionalmente, envia os top N hotspots para um modelo via [OpenRouter](https://openrouter.ai/) e inclui um resumo executivo no relatório.

## Requisitos

- Python 3.10 ou superior
- [Git](https://git-scm.com/) instalado e disponível no `PATH`
- Chave de API do OpenRouter (apenas se quiser o resumo executivo via LLM)

## Instalação

```bash
git clone <url-do-repositorio>
cd git-hotspot-radar

python -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows
.venv\Scripts\activate

pip install -r requirements.txt
```

## Configuração

O resumo via LLM é opcional. Para habilitá-lo, copie o arquivo de exemplo e preencha a chave:

```bash
cp .env.example .env
```

Edite `.env` e defina `OPENROUTER_API_KEY` com a chave obtida em [openrouter.ai/keys](https://openrouter.ai/keys). O modelo padrão é `openrouter/free`.

Para rodar apenas o ranking, sem consumir quota de API, use a flag `--skip-llm`.

## Uso

Análise básica de um repositório local:

```bash
python main.py --repo-path /caminho/do/repo --top 10
```

Exemplos adicionais:

```bash
# Ranking dos 20 arquivos mais críticos, sem chamar a API
python main.py --repo-path ./meu-projeto --top 20 --skip-llm

# Salvar o relatório em outro caminho
python main.py --repo-path ./meu-projeto --output relatorios/hotspots-jan.md
```

### Opções da CLI

| Flag | Obrigatório | Padrão | Descrição |
|------|:-----------:|--------|-----------|
| `--repo-path` | sim | — | Caminho para o repositório Git a ser analisado |
| `--top` | não | `10` | Quantidade de hotspots no ranking e no prompt do LLM |
| `--skip-llm` | não | — | Gera apenas o ranking, sem chamar o OpenRouter |
| `--output` | não | `hotspot_report.md` | Caminho do relatório final em Markdown |

## Saída

Durante a execução, o terminal exibe o progresso da análise Git e uma tabela com os top N arquivos:

```
=== Top Hotspots ===

          file_path  nloc  max_complexity  commit_count  author_count  risk_score
  src/complexity.py    77               7             2             1          14
src/git_analyzer.py    83               5             2             1          10
            main.py   154               9             1             1           9
```

O arquivo Markdown gerado contém a data da execução, a tabela completa dos hotspots e, quando disponível, a seção **Resumo Executivo** com a análise do LLM. Se a chamada à API falhar, o relatório é salvo mesmo assim, com uma nota indicando que o resumo não pôde ser gerado.

## Estrutura do projeto

```
git-hotspot-radar/
├── main.py              # CLI e orquestração
├── src/
│   ├── git_analyzer.py  # Métricas de histórico Git
│   ├── complexity.py    # Análise de complexidade ciclomática
│   ├── merger.py        # Cruzamento de dados e cálculo do risk_score
│   └── summary_llm.py   # Resumo executivo via OpenRouter
├── requirements.txt
└── .env.example
```

Cada módulo em `src/` pode ser executado isoladamente para testes (`python -m src.git_analyzer`, etc.).

## Limitações

- A análise Git considera apenas arquivos rastreados no `HEAD` atual; arquivos não commitados ou em branches diferentes não entram no ranking.
- O lizard ignora silenciosamente arquivos que não consegue parsear (encoding inválido, linguagens não suportadas, etc.).
- O merge entre Git e complexidade é um inner join: arquivos presentes em apenas uma das fontes são descartados.
- Repositórios grandes podem levar vários minutos na etapa de `git log --follow` por arquivo.

## Contribuindo

Issues e pull requests são bem-vindos. Ao abrir um PR, descreva o problema que resolve e inclua, se possível, um exemplo de execução com `--skip-llm`.

