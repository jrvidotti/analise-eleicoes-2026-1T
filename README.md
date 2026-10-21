# Análise das Eleições 2026 (1º turno) — votação para presidente por seção eleitoral

Cruza, para cada seção eleitoral, a **votação oficial para presidente** com informações extraídas dos **logs das urnas eletrônicas**:

- **horário de cada voto**, com destaque para os votos computados **depois das 17h de Brasília** (horário oficial de encerramento);
- **modelo da urna** (UE2013, UE2015, UE2020, UE2022);
- **forma de habilitação do eleitor** (biometria, liberação manual após falha da biometria, eleitor sem biometria cadastrada);
- **índice de abstenção** e **% de votos de cada candidato**, comparados entre grupos de seções (UF, modelo da urna, votos depois das 17h, uso de biometria).

## Fontes de dados

Todas são públicas, do Portal de Dados Abertos do TSE (<https://dadosabertos.tse.jus.br>).

| Conjunto | O que traz | URL |
|---|---|---|
| Resultados 2026 – Arquivos transmitidos para totalização | Um ZIP por UF com BU, RDV, log (`.jez`) e assinatura de cada seção | `https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2026/arqurnatot/bu_imgbu_logjez_rdv_vscmr_2026_1t_<UF>.zip` |
| Resultados 2026 – Presidente – Votação por seção eleitoral | CSV com votos por candidato em cada seção (Brasil) | `https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2026_BR.zip` |
| Resultados 2026 – Detalhe da apuração por seção eleitoral | Aptos, comparecimento, abstenções, modelo da urna e origem do voto por seção (usa-se o CSV `_BR`, de presidente) | `https://cdn.tse.jus.br/estatistica/sead/odsele/detalhe_votacao_secao/detalhe_votacao_secao_2026.zip` |

A página do TSE com os [resumos digitais (hashes) de 2026](https://www.tse.jus.br/eleicoes/urna-eletronica/seguranca-da-urna/hash/resumos-digitais-hashes-das-eleicoes-2026-1o-e-2o-turnos) **não contém dados de votação**. Ela traz só os hashes dos softwares lacrados (inclusive os de cada modelo de urna: `path1u13`, `path1u15`, `path1u20` e `path1u22`) e serve para auditar a integridade dos sistemas.

## Requisitos

- macOS ou Linux, Python ≥ 3.12 e [uv](https://docs.astral.sh/uv/)
- Espaço em disco: cerca de 3 GB para o piloto (AC, RR, SE, DF) e cerca de 70–80 GB de ZIPs de logs para o Brasil inteiro (é possível apagar o ZIP de cada UF depois de processado)
- Dependências (no `pyproject.toml`): `duckdb`, `pandas`, `pyarrow`

## Passo a passo para reproduzir

```bash
# 0. instalar dependências
uv sync

# 1. votação oficial para presidente por seção (~160 MB zip / ~1 GB CSV)
uv run python -I scripts/preparar_votacao.py

# 1b. aptos, comparecimento e abstenções por seção (~177 MB zip)
uv run python -I scripts/preparar_comparecimento.py

# 2. arquivos de urna das UFs desejadas (piloto: AC RR SE DF)
uv run python -I scripts/baixar.py AC RR SE DF

# 3. extrair dos logs: modelo da urna, horário e habilitação de cada voto
uv run python -I scripts/processar_logs.py AC RR SE DF

# 4. montar a tabela por seção e imprimir os resumos
uv run python -I scripts/analisar.py
```

Para o Brasil inteiro, troque a lista de UFs nos passos 2 e 3 (são 27 UFs mais `ZZ`, que é o exterior; veja as limitações). O passo 4 sempre consolida todas as UFs já processadas em `dados/proc/`.

O `-I` (modo isolado do Python) evita que algum arquivo baixado seja importado por engano como módulo. Os scripts devem ser rodados a partir da raiz do projeto, nunca de dentro de `dados/`.

## Estrutura

```
scripts/
  preparar_votacao.py   baixa o CSV nacional de votação por seção e grava só o cargo Presidente
  preparar_comparecimento.py  baixa o detalhe da apuração por seção (aptos, comparecimento, abstenções)
  baixar.py             baixa o ZIP de arquivos de urna de cada UF
  processar_logs.py     lê os logs direto do ZIP (sem extrair) e gera uma linha por voto e uma por seção
  analisar.py           cruza log × votação, infere o fuso, gera a tabela final e os resumos
dados/
  raw/<UF>/<UF>.zip                     arquivos de urna (entrada)
  raw/votacao_secao/                    CSV oficial de votação (entrada)
  raw/detalhe_secao/                    CSV oficial de detalhe da apuração (entrada)
  proc/presidente_secao.parquet         votos para presidente por seção e candidato
  proc/comparecimento_secao.parquet     aptos, comparecimento, abstenções, modelo e origem do voto por seção
  proc/eleitores_<UF>.parquet           um registro por voto computado
  proc/secoes_<UF>.parquet              metadados da urna por seção
  proc/analise_secoes.parquet           tabela final, uma linha por seção
```

### `analise_secoes.parquet` (tabela final)

| Coluna | Descrição |
|---|---|
| `sg_uf`, `cd_municipio`, `nm_municipio`, `nr_zona`, `nr_secao` | Identificação da seção (código de município do TSE) |
| `v_total`, `v_flavio`, `v_lula`, `v_cury`, `v_renan`, `v_caiado`, `v_branco`, `v_nulo`, `v_outros` | Votos para presidente segundo o CSV oficial |
| `v_validos` | `v_total − v_branco − v_nulo` |
| `qt_aptos`, `qt_comparecimento`, `qt_abstencoes` | Eleitores aptos, comparecimento e abstenções da seção (detalhe da apuração) |
| `ds_modelo_urna`, `ds_origem_voto` | Modelo da urna e origem do voto segundo o TSE (ex.: "Urna Eletrônica", "BU gerado por RED", "Sistema de apuração") |
| `modelo` | Modelo da urna que gerou o log |
| `fuso_h` | Diferença do horário local para o de Brasília (ex.: AC = −2) |
| `hora_pronta`, `hora_encerramento` | Hora local em que a urna ficou pronta para votos e em que o encerramento começou |
| `n_reinicios` | Quantas vezes a aplicação foi iniciada no dia da eleição |
| `n_votos_log` | Votos computados segundo o log |
| `n_biometrica`, `n_manual`, `n_sem_biometria` | Votos por tipo de habilitação do eleitor |
| `n_pos17`, `n_pos17_biometrica` | Votos computados depois das 17h00 de Brasília (total e com biometria) |
| `ultimo_voto_brasilia` | Horário (Brasília) do último voto |
| `log_incompleto` | `true` quando a contagem de votos do log é diferente da oficial (ver abaixo) |

### `eleitores_<UF>.parquet`

`sg_uf, cd_municipio, nr_zona, nr_secao, hora_local, habilitacao, voto_presidente`, em que:
- `habilitacao` ∈ `biometrica`, `manual_falha_biometria`, `sem_biometria`, `outro`;
- `voto_presidente` ∈ `confirmado`, `nulo_suspensao`, ou nulo.

## Metodologia

### Leitura do log (`logd.dat`)
Cada linha do log tem os campos `data hora`, nível, id da urna, aplicação, mensagem e hash, separados por tabulação, com codificação Latin-1. São consideradas só as linhas de **04/10/2026**; o log também traz linhas da carga da urna (dias anteriores). O nome do arquivo identifica a seção: `o03220ac0101500020088-log.jez` corresponde a UF `ac`, município `01015`, zona `0002`, seção `0088`.

Cada eleitor corresponde a um bloco de mensagens que começa em `Aguardando digitação do identificador do eleitor` e termina em `O voto do eleitor foi computado`. O horário do voto é o horário desta última mensagem. Dentro do bloco:

| Mensagem no log | Classificação |
|---|---|
| `Tipo de habilitação do eleitor [biométrica]` | `biometrica` |
| `Solicitação de dado pessoal do eleitor para habilitação manual` (depois de tentativas de digital) | `manual_falha_biometria` |
| `Ano de nascimento digitado é igual ao do cadastro` (sem pedido de digital) | `sem_biometria` |
| `Voto confirmado para [Presidente]` | voto para presidente `confirmado` |
| `Atribuido voto nulo por suspensão [Presidente]` | eleitor suspenso pelo mesário; presidente recebe `nulo_suspensao` |

O **modelo da urna** vem de `Identificação do Modelo de Urna: UE20xx`. Ele é procurado no log inteiro porque algumas urnas não foram religadas no dia da eleição e só registram o modelo em datas anteriores.

### Fuso horário
O log registra a **hora local** da urna. No Acre, por exemplo, a votação foi das 6h às 15h locais, que correspondem a 8h–17h de Brasília. O fuso de cada município é inferido como a **hora local mais frequente** em que as urnas ficaram prontas para receber votos (`Urna pronta para receber votos`) menos 8. Assim não é preciso manter uma tabela de fusos, e municípios com fuso diferente do resto da UF (por exemplo, no oeste do Amazonas) são tratados automaticamente.

Um voto conta como **depois das 17h** quando `hora_local > 17:00:00 + fuso_h`.

### Abstenção e % de votos
Os resumos calculam os percentuais como **razão de somas** dentro de cada grupo de seções (seções ponderadas pelo tamanho), e não como média dos percentuais de cada seção:

- **abstenção** = Σ `qt_abstencoes` ÷ Σ `qt_aptos`;
- **% de cada candidato** = votos do candidato ÷ Σ `v_validos` (critério oficial do TSE, que exclui brancos e nulos);
- **% de brancos e % de nulos** = votos ÷ Σ `qt_comparecimento`.

Os grupos comparados são sempre **dentro de cada UF**, para não misturar a composição dos estados: UF; UF × modelo da urna; UF × faixa de votos depois das 17h (0, 1–5, 6–20, >20); e UF × quartil de habilitação sem biometria (`(n_manual + n_sem_biometria) / n_votos_log`, quartis calculados dentro da UF).

### Validação
O total de votos computados no log é comparado com o total para presidente no CSV oficial, seção a seção. No piloto, **99,6% das seções batem exatamente**. As diferenças são urnas substituídas durante a votação (contingência): o log publicado é o da urna substituta, que só tem os votos dados depois da troca. Essas seções recebem `log_incompleto = true` e ficam de fora dos resumos de horário e de biometria.

Outras conferências que `analisar.py` imprime por UF:
- `qt_comparecimento` (detalhe da apuração) = `v_total` (votação por seção): batem em 100% das seções do piloto;
- modelo da urna no log = `ds_modelo_urna` oficial: diverge em 1 seção do piloto, cujo BU foi recuperado de outra urna ("BU gerado por RED");
- em todas as seções, válidos + brancos + nulos = total.

## Resultados do piloto (AC, RR, SE, DF)

16.681 seções e cerca de 4,1 milhões de votos.

| UF (fuso) | % dos votos depois das 17h (por modelo) | Último voto (Brasília) | % biometria |
|---|---|---|---|
| AC (−2) | 1,3–2,0% | 19h49 | ~91% |
| RR (−1) | 0,5–1,9% | 20h05 | ~93% |
| DF (0) | 0,6–2,2% | 18h55 | ~92% |
| SE (0) | 2,2–3,7% | 21h06 | ~90% |

### Abstenção e votação (% dos válidos) por UF

| UF | Aptos | Abstenção | Flávio | Lula | Cury | Renan | Caiado | Brancos* | Nulos* |
|---|---|---|---|---|---|---|---|---|---|
| AC | 613.742 | 20,4% | 64,6% | 28,7% | 2,9% | 1,7% | 1,8% | 1,1% | 2,8% |
| DF | 2.258.320 | 18,9% | 51,3% | 38,1% | 2,6% | 2,6% | 4,8% | 1,4% | 1,8% |
| RR | 401.521 | 17,1% | 71,1% | 22,9% | 2,6% | 2,0% | 1,1% | 0,8% | 1,4% |
| SE | 1.740.135 | 17,3% | 30,6% | 62,8% | 2,9% | 1,6% | 2,0% | 1,7% | 3,5% |

\* brancos e nulos sobre o comparecimento.

Principais padrões nas comparações dentro de cada UF (detalhes na saída de `analisar.py`):
- **Votos depois das 17h:** seções com mais votos depois das 17h têm abstenção um pouco maior (AC: 20,1% → 22,3%; DF: 18,5% → 20,0%) e votação um pouco maior em Lula em AC e SE. Em RR, as 42 seções com mais de 20 votos depois das 17h têm perfil muito diferente (Lula 49,6% contra 21,6%), provavelmente por se concentrarem em poucas regiões.
- **Habilitação sem biometria:** a abstenção cresce do 1º para o 4º quartil em todas as UFs (de +1,7 a +2,2 pontos). A votação nos candidatos muda pouco, exceto no AC (Lula: 27,6% → 31,1%).
- **Modelo da urna:** há diferenças de votação entre modelos (ex.: SE, UE2015 37,9% Flávio contra 28,8% nas UE2020), mas o modelo é distribuído por local de votação, então essas diferenças refletem a geografia, e não a urna.

## Limitações e cuidados de interpretação

- **Sigilo do voto:** o log registra *que* o eleitor votou para presidente e *quando*, mas não *em quem*. Por isso, a relação entre votos depois das 17h e candidatos só pode ser feita **no nível da seção** (correlação entre o percentual de votos depois das 17h da seção e o resultado da seção). Isso não diz em quem votaram os eleitores que votaram tarde, e diferenças entre seções podem refletir o perfil da região (urbana, rural, áreas indígenas etc.).
- **Associação não é causa:** abstenção, votação, modelo da urna, horário e biometria são atributos da seção inteira. As comparações mostram associações entre grupos de seções, que costumam refletir o perfil do local (urbano/rural, renda, idade, distância). Elas não descrevem o comportamento individual dos eleitores.
- **Seções com urna substituída:** os horários e a biometria refletem só a parte final do dia. Essas seções são excluídas pelo filtro `log_incompleto`.
- **Exterior (ZZ):** ainda não tratado. A inferência de fuso por município e a referência "17h de Brasília" precisam ser adaptadas para o exterior, onde a votação segue o horário local de cada país.
- **2º turno:** os arquivos ainda não estavam publicados quando o piloto foi feito; o parser filtra a data `04/10/2026` (`DIA_ELEICAO` em `scripts/processar_logs.py`).
- Seções agregadas, votação por cédula e outros casos raros ainda não foram examinados um a um.
