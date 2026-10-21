"""Extrai dos logs de urna, por seção, o modelo da urna e cada voto com horário e tipo de habilitação.

Lê dados/raw/<UF>/<UF>.zip sem descompactar em disco e grava:
  dados/proc/eleitores_<UF>.parquet  -> uma linha por voto computado
  dados/proc/secoes_<UF>.parquet     -> uma linha por seção (metadados da urna)

Uso: uv run python -I scripts/processar_logs.py AC RR SE DF
"""

import io
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

RAIZ = Path(__file__).resolve().parent.parent / "dados"
DIA_ELEICAO = "04/10/2026"
# o03220ac0101500020088-log.jez -> uf=ac, municipio=01015, zona=0002, secao=0088
RE_ARQUIVO = re.compile(r"o\d{5}([a-z]{2})(\d{5})(\d{4})(\d{4})-log\.jez$")
RE_MODELO = re.compile(r"Identificação do Modelo de Urna: (\w+)")


def ler_log(conteudo_jez: bytes) -> tuple[list[tuple[str, str]], str | None]:
    """Devolve (hora, mensagem) das linhas do dia da eleição e o último modelo de urna citado no log inteiro.

    O modelo é buscado no log todo porque urnas que não foram religadas no dia só o registram em datas anteriores.
    """
    with zipfile.ZipFile(io.BytesIO(conteudo_jez)) as jez:
        texto = jez.read("logd.dat").decode("latin-1")
    linhas = []
    for linha in texto.splitlines():
        if not linha.startswith(DIA_ELEICAO):
            continue
        campos = linha.split("\t")
        if len(campos) >= 5:
            linhas.append((campos[0][11:19], campos[4]))
    modelos = RE_MODELO.findall(texto)
    return linhas, (modelos[-1] if modelos else None)


def processar_secao(linhas: list[tuple[str, str]]) -> tuple[dict, list[dict]]:
    meta = {"modelo": None, "hora_pronta": None, "hora_encerramento": None, "n_reinicios": 0}
    votos = []
    # estado do eleitor corrente
    bio = manual = ano_nasc = False
    presidente = None
    for hora, msg in linhas:
        if msg.startswith("Identificação do Modelo de Urna"):
            if m := RE_MODELO.search(msg):
                meta["modelo"] = m.group(1)
        elif msg == "Urna pronta para receber votos":
            meta["hora_pronta"] = meta["hora_pronta"] or hora
        elif msg == "Inicio do Encerramento":
            meta["hora_encerramento"] = hora
        elif msg == "Iniciando aplicação - 1º turno":
            meta["n_reinicios"] += 1
        elif msg == "Aguardando digitação do identificador do eleitor":
            bio = manual = ano_nasc = False
            presidente = None
        elif msg == "Tipo de habilitação do eleitor [biométrica]":
            bio = True
        elif msg == "Solicitação de dado pessoal do eleitor para habilitação manual":
            manual = True
        elif msg == "Ano de nascimento digitado é igual ao do cadastro":
            ano_nasc = True
        elif msg == "Voto confirmado para [Presidente]":
            presidente = "confirmado"
        elif msg == "Atribuido voto nulo por suspensão [Presidente]":
            presidente = "nulo_suspensao"
        elif msg == "O voto do eleitor foi computado":
            if bio:
                tipo = "biometrica"
            elif manual:
                tipo = "manual_falha_biometria"
            elif ano_nasc:
                tipo = "sem_biometria"
            else:
                tipo = "outro"
            votos.append({"hora_local": hora, "habilitacao": tipo, "voto_presidente": presidente})
            bio = manual = ano_nasc = False
            presidente = None
    return meta, votos


def processar_uf(uf: str) -> None:
    origem = RAIZ / "raw" / uf / f"{uf}.zip"
    secoes, eleitores = [], []
    with zipfile.ZipFile(origem) as z:
        for nome in z.namelist():
            m = RE_ARQUIVO.search(nome)
            if not m:
                continue
            sg_uf, mun, zona, secao = m.groups()
            chave = {"sg_uf": sg_uf.upper(), "cd_municipio": int(mun), "nr_zona": int(zona), "nr_secao": int(secao)}
            try:
                linhas, modelo_log = ler_log(z.read(nome))
                meta, votos = processar_secao(linhas)
                meta["modelo"] = meta["modelo"] or modelo_log
            except (zipfile.BadZipFile, KeyError) as e:
                print(f"  aviso: {nome}: {e}", file=sys.stderr)
                continue
            secoes.append({**chave, **meta, "n_votos_log": len(votos)})
            eleitores.extend({**chave, **v} for v in votos)
    destino = RAIZ / "proc"
    destino.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(secoes), destino / f"secoes_{uf}.parquet")
    pq.write_table(pa.Table.from_pylist(eleitores), destino / f"eleitores_{uf}.parquet")
    print(f"{uf}: {len(secoes)} seções, {len(eleitores)} votos — {datetime.now():%H:%M:%S}")


if __name__ == "__main__":
    for uf in sys.argv[1:]:
        processar_uf(uf.upper())
