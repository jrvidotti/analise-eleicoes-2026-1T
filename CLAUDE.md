# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Projeto de análise de dados (não é uma aplicação): cruza a votação oficial para presidente do 1º turno de 2026, por seção eleitoral, com informações extraídas dos logs das urnas eletrônicas publicados pelo TSE (horário de cada voto, modelo da urna, forma de habilitação do eleitor). O `README.md` traz a metodologia completa, o dicionário das colunas e as limitações. Leia o README antes de mudar regras de classificação ou de fuso.

Código, comentários, nomes de variáveis e documentação ficam em português.

## Comandos

Não há testes, linter nem build. O pipeline é formado por quatro scripts, rodados em ordem a partir da raiz do projeto, sempre com `python -I` (modo isolado, para que nenhum arquivo baixado em `dados/` seja importado como módulo):

```bash
uv sync
uv run python -I scripts/preparar_votacao.py          # CSV nacional -> dados/proc/presidente_secao.parquet
uv run python -I scripts/baixar.py AC RR SE DF         # ZIPs de urna por UF -> dados/raw/<UF>/<UF>.zip
uv run python -I scripts/processar_logs.py AC RR SE DF # logs -> dados/proc/{eleitores,secoes}_<UF>.parquet
uv run python -I scripts/analisar.py                   # consolida tudo -> dados/proc/analise_secoes.parquet + resumos
```

- `baixar.py` e `preparar_votacao.py` não baixam de novo se o arquivo já existe. Para forçar, apague o arquivo.
- `processar_logs.py` reprocessa e sobrescreve os parquets da UF a cada execução.
- `analisar.py` lê **todos** os `eleitores_*.parquet` / `secoes_*.parquet` presentes em `dados/proc/` (glob), não uma lista de UFs.
- Para testar uma mudança no parser, use uma UF pequena (AC ou RR) ou a amostra já extraída em `dados/raw/AC/amostra/` (`log/logd.txt` é o log legível de uma seção).

## Arquitetura

Fluxo: ZIP por UF (TSE) → `processar_logs.py` (Python puro + pyarrow) → parquets por UF → `analisar.py` (SQL em DuckDB) → `analise_secoes.parquet`.

- **`processar_logs.py`**: lê cada `*-log.jez` direto do ZIP da UF, sem extrair em disco. O `.jez` é ele mesmo um ZIP com `logd.dat` (Latin-1, campos separados por tabulação). A chave da seção (UF, município, zona, seção) sai do **nome do arquivo** (`RE_ARQUIVO`). `processar_secao` é uma máquina de estados sobre as mensagens do log: cada eleitor é o bloco entre `Aguardando digitação do identificador do eleitor` e `O voto do eleitor foi computado`, e as mensagens no meio definem a habilitação e o voto para presidente. As mensagens são comparadas por string exata, então qualquer mudança no texto dos logs (outro turno, outra eleição) exige revisá-las. Só entram linhas da data `DIA_ELEICAO`. A exceção é o modelo da urna, que é procurado no log inteiro.
- **`analisar.py`**: monta tudo com tabelas temporárias no DuckDB. O fuso de cada município é **inferido** (moda da hora local de `hora_pronta` − 8); não existe tabela de fusos. Os votos de candidatos viram colunas a partir do dicionário `CANDIDATOS` (número → nome). Candidatos fora dele caem em `v_outros`. `log_incompleto` marca seções em que o total de votos do log difere do oficial (urna substituída). Os resumos impressos filtram essas seções.
- A chave de junção em todas as tabelas é `(sg_uf, cd_municipio, nr_zona, nr_secao)`, com `cd_municipio` no código do TSE (não IBGE).

## Dados

`dados/` é grande (ZIPs de UF chegam a vários GB; o Brasil inteiro tem cerca de 70–80 GB). Não leia os ZIPs ou o CSV nacional inteiros no contexto; consulte os parquets com DuckDB. O exterior (`ZZ`) e o 2º turno ainda não são tratados (ver limitações no README).
