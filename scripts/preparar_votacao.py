"""Baixa a votação oficial para presidente por seção (Brasil) e grava em Parquet.

Gera dados/proc/presidente_secao.parquet.
Uso: uv run python -I scripts/preparar_votacao.py
"""

import urllib.request
import zipfile
from pathlib import Path

import duckdb

URL = "https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_secao/votacao_secao_2026_BR.zip"
RAIZ = Path(__file__).resolve().parent.parent / "dados"
DIR_RAW = RAIZ / "raw" / "votacao_secao"
CSV = DIR_RAW / "votacao_secao_2026_BR.csv"
DESTINO = RAIZ / "proc" / "presidente_secao.parquet"


def baixar() -> None:
    if CSV.exists():
        print(f"já existe: {CSV}")
        return
    DIR_RAW.mkdir(parents=True, exist_ok=True)
    arquivo_zip = DIR_RAW / "votacao_secao_2026_BR.zip"
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp, open(arquivo_zip, "wb") as f:
        while bloco := resp.read(1 << 20):
            f.write(bloco)
    with zipfile.ZipFile(arquivo_zip) as z:
        z.extractall(DIR_RAW)
    print(f"baixado: {CSV}")


def converter() -> None:
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    duckdb.sql(f"""
    copy (
      select SG_UF sg_uf, CD_MUNICIPIO cd_municipio, NM_MUNICIPIO nm_municipio, NR_ZONA nr_zona, NR_SECAO nr_secao,
             NR_LOCAL_VOTACAO nr_local_votacao, NR_VOTAVEL nr_votavel, NM_VOTAVEL nm_votavel, QT_VOTOS qt_votos
      from read_csv('{CSV}', delim=';', encoding='latin-1', header=true)
      where CD_CARGO = 1
    ) to '{DESTINO}'
    """)
    print(f"gerado: {DESTINO}")


if __name__ == "__main__":
    baixar()
    converter()
