"""Baixa o detalhe da apuração por seção (aptos, comparecimento, abstenções) e grava só o cargo Presidente.

Gera dados/proc/comparecimento_secao.parquet.
Uso: uv run python -I scripts/preparar_comparecimento.py
"""

import urllib.request
import zipfile
from pathlib import Path

import duckdb

URL = "https://cdn.tse.jus.br/estatistica/sead/odsele/detalhe_votacao_secao/detalhe_votacao_secao_2026.zip"
RAIZ = Path(__file__).resolve().parent.parent / "dados"
DIR_RAW = RAIZ / "raw" / "detalhe_secao"
ARQUIVO_ZIP = DIR_RAW / "detalhe_votacao_secao_2026.zip"
CSV = DIR_RAW / "detalhe_votacao_secao_2026_BR.csv"
DESTINO = RAIZ / "proc" / "comparecimento_secao.parquet"


def baixar() -> None:
    if CSV.exists():
        print(f"já existe: {CSV}")
        return
    DIR_RAW.mkdir(parents=True, exist_ok=True)
    if not ARQUIVO_ZIP.exists():
        req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as resp, open(ARQUIVO_ZIP, "wb") as f:
            while bloco := resp.read(1 << 20):
                f.write(bloco)
    # o ZIP traz um CSV por UF e um _BR (presidente); só o _BR é necessário
    with zipfile.ZipFile(ARQUIVO_ZIP) as z:
        z.extract(CSV.name, DIR_RAW)
    print(f"baixado: {CSV}")


def converter() -> None:
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    duckdb.sql(f"""
    copy (
      select SG_UF sg_uf, CD_MUNICIPIO cd_municipio, NR_ZONA nr_zona, NR_SECAO nr_secao,
             QT_APTOS qt_aptos, QT_COMPARECIMENTO qt_comparecimento, QT_ABSTENCOES qt_abstencoes,
             QT_VOTOS_NOMINAIS qt_votos_nominais, QT_VOTOS_BRANCOS qt_votos_brancos, QT_VOTOS_NULOS qt_votos_nulos,
             DS_ORIGEM_VOTO ds_origem_voto, ST_SECAO_INSTALADA st_secao_instalada, ST_SECAO_ANULADA st_secao_anulada,
             DS_MODELO_URNA ds_modelo_urna
      from read_csv('{CSV}', delim=';', encoding='latin-1', header=true)
      where CD_CARGO = 1
    ) to '{DESTINO}'
    """)
    print(f"gerado: {DESTINO}")


if __name__ == "__main__":
    baixar()
    converter()
