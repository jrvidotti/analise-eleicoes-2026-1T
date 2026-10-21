"""Monta a tabela por seção (log da urna + votação oficial para presidente + comparecimento) e imprime resumos.

Horário de Brasília: o log registra a hora local da urna. O fuso de cada município é inferido pela
hora local mais frequente em que as urnas ficaram prontas para receber votos (abertura oficial: 8h de Brasília).

Percentuais dos resumos são razão de somas dentro de cada grupo (seções ponderadas pelo tamanho):
  abstenção = abstenções / aptos; candidatos = % dos votos válidos; brancos e nulos = % do comparecimento.

Gera dados/proc/analise_secoes.parquet.
Uso: uv run python -I scripts/analisar.py
"""

from pathlib import Path

import duckdb

PROC = Path(__file__).resolve().parent.parent / "dados" / "proc"
CANDIDATOS = {22: "flavio", 13: "lula", 70: "cury", 14: "renan", 55: "caiado", 95: "branco", 96: "nulo"}

db = duckdb.connect()
db.execute(f"create view eleitores as select * from read_parquet('{PROC}/eleitores_*.parquet')")
db.execute(f"create view secoes as select * from read_parquet('{PROC}/secoes_*.parquet')")
db.execute(f"create view presidente as select * from read_parquet('{PROC}/presidente_secao.parquet')")
db.execute(f"create view comparecimento as select * from read_parquet('{PROC}/comparecimento_secao.parquet')")

db.execute("""
create temp table fuso as
select sg_uf, cd_municipio,
       mode(hour(hora_pronta::time)) - 8 as fuso_h  -- AC: 6h local -> -2
from secoes where hora_pronta is not null
group by all
""")

colunas_cand = ",\n".join(
    f"coalesce(sum(qt_votos) filter (nr_votavel = {nr}), 0) as v_{nome}" for nr, nome in CANDIDATOS.items()
)
db.execute(f"""
create temp table votacao as
select sg_uf, cd_municipio, nr_zona, nr_secao,
       any_value(nm_municipio) as nm_municipio,
       sum(qt_votos) as v_total,
       {colunas_cand},
       coalesce(sum(qt_votos) filter (nr_votavel not in ({', '.join(map(str, CANDIDATOS))})), 0) as v_outros
from presidente group by all
""")

db.execute("""
create temp table votos_log as
select e.sg_uf, e.cd_municipio, e.nr_zona, e.nr_secao,
       count(*) as n_votos_log,
       count(*) filter (e.habilitacao = 'biometrica') as n_biometrica,
       count(*) filter (e.habilitacao = 'manual_falha_biometria') as n_manual,
       count(*) filter (e.habilitacao = 'sem_biometria') as n_sem_biometria,
       count(*) filter (e.hora_local::time > time '17:00:00' + to_hours(f.fuso_h)) as n_pos17,
       count(*) filter (e.hora_local::time > time '17:00:00' + to_hours(f.fuso_h)
                        and e.habilitacao = 'biometrica') as n_pos17_biometrica,
       max(e.hora_local::time - to_hours(f.fuso_h)) as ultimo_voto_brasilia
from eleitores e join fuso f using (sg_uf, cd_municipio)
group by all
""")

db.execute(f"""
copy (
  select v.*, v.v_total - v.v_branco - v.v_nulo as v_validos,
         c.qt_aptos, c.qt_comparecimento, c.qt_abstencoes, c.ds_origem_voto, c.ds_modelo_urna,
         s.modelo, f.fuso_h, s.hora_pronta, s.hora_encerramento, s.n_reinicios,
         l.* exclude (sg_uf, cd_municipio, nr_zona, nr_secao),
         coalesce(l.n_votos_log, 0) <> v.v_total as log_incompleto
  from votacao v
  join secoes s using (sg_uf, cd_municipio, nr_zona, nr_secao)
  join fuso f using (sg_uf, cd_municipio)
  left join comparecimento c using (sg_uf, cd_municipio, nr_zona, nr_secao)
  left join votos_log l using (sg_uf, cd_municipio, nr_zona, nr_secao)
) to '{PROC}/analise_secoes.parquet'
""")
db.execute(f"create view a as select * from read_parquet('{PROC}/analise_secoes.parquet')")

# colunas de comparação comuns a todos os resumos de abstenção e votação
METRICAS = """count(*) secoes, sum(qt_aptos) aptos,
       round(100 * sum(qt_abstencoes) / sum(qt_aptos), 2) abst,
       round(100 * sum(v_flavio) / sum(v_validos), 2) flavio,
       round(100 * sum(v_lula) / sum(v_validos), 2) lula,
       round(100 * sum(v_cury) / sum(v_validos), 2) cury,
       round(100 * sum(v_renan) / sum(v_validos), 2) renan,
       round(100 * sum(v_caiado) / sum(v_validos), 2) caiado,
       round(100 * sum(v_outros) / sum(v_validos), 2) outros,
       round(100 * sum(v_branco) / sum(qt_comparecimento), 2) branco,
       round(100 * sum(v_nulo) / sum(qt_comparecimento), 2) nulo"""


def mostrar(titulo: str, sql: str) -> None:
    print(f"\n== {titulo}")
    db.sql(sql).show(max_width=250, max_rows=200)


mostrar("Cobertura, fuso e conferências por UF", """
select sg_uf, count(*) secoes, count(*) filter (log_incompleto) secoes_log_incompleto,
       count(*) filter (qt_comparecimento is distinct from v_total) secoes_comparec_diverge,
       count(*) filter (replace(ds_modelo_urna, ' ', '') is distinct from modelo) secoes_modelo_diverge,
       list(distinct fuso_h order by fuso_h) fusos, sum(v_total) votos
from a group by all order by sg_uf""")

mostrar("Votos depois das 17h (Brasília) e biometria, por UF e modelo de urna (seções com log completo)", """
select sg_uf, modelo, count(*) secoes, sum(n_votos_log) votos,
       sum(n_pos17) votos_pos17,
       round(100 * sum(n_pos17) / sum(n_votos_log), 2) pct_pos17,
       count(*) filter (n_pos17 > 0) secoes_com_pos17,
       round(100 * sum(n_biometrica) / sum(n_votos_log), 1) pct_bio,
       round(100 * sum(n_manual) / sum(n_votos_log), 1) pct_manual,
       round(100 * sum(n_sem_biometria) / sum(n_votos_log), 1) pct_sem_bio,
       round(100 * sum(n_pos17_biometrica) / nullif(sum(n_pos17), 0), 1) pct_bio_pos17,
       max(ultimo_voto_brasilia) ultimo_voto_brasilia
from a where not log_incompleto group by all order by sg_uf, modelo""")

mostrar("Abstenção e votação (% válidos) por UF — todas as seções", f"""
select sg_uf, {METRICAS} from a group by all order by sg_uf""")

mostrar("Abstenção e votação por UF × modelo de urna — todas as seções", f"""
select sg_uf, modelo, {METRICAS} from a group by all order by sg_uf, modelo""")

mostrar("Abstenção e votação por UF × faixa de votos depois das 17h — seções com log completo", f"""
select sg_uf,
       case when n_pos17 = 0 then '0' when n_pos17 <= 5 then '1-5' when n_pos17 <= 20 then '6-20' else '>20' end faixa_pos17,
       {METRICAS}
from a where not log_incompleto group by all order by sg_uf, min(n_pos17)""")

mostrar("Abstenção e votação por UF × quartil de habilitação sem biometria (manual + sem cadastro) — seções com log completo", f"""
with q as (
  select *, (n_manual + n_sem_biometria) / n_votos_log as pct_nao_bio,
         ntile(4) over (partition by sg_uf order by (n_manual + n_sem_biometria) / n_votos_log) quartil
  from a where not log_incompleto and n_votos_log > 0
)
select sg_uf, quartil, round(100 * min(pct_nao_bio), 1) || '–' || round(100 * max(pct_nao_bio), 1) || '%' faixa_nao_bio,
       {METRICAS}
from q group by all order by sg_uf, quartil""")
