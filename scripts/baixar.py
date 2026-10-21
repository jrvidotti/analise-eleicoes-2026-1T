"""Baixa os arquivos de urna (BU/LOG/RDV) de uma ou mais UFs do 1º turno 2026.

Uso: uv run python -I scripts/baixar.py AC RR SE DF
"""

import sys
import urllib.request
from pathlib import Path

URL = "https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2026/arqurnatot/bu_imgbu_logjez_rdv_vscmr_2026_1t_{uf}.zip"
RAIZ = Path(__file__).resolve().parent.parent / "dados" / "raw"


def baixar(uf: str) -> Path:
    destino = RAIZ / uf / f"{uf}.zip"
    if destino.exists():
        print(f"{uf}: já existe ({destino.stat().st_size / 1e6:.0f} MB)")
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(".part")
    req = urllib.request.Request(URL.format(uf=uf), headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp, open(tmp, "wb") as f:
        while bloco := resp.read(1 << 20):
            f.write(bloco)
    tmp.rename(destino)
    print(f"{uf}: baixado ({destino.stat().st_size / 1e6:.0f} MB)")
    return destino


if __name__ == "__main__":
    for uf in sys.argv[1:]:
        baixar(uf.upper())
