"""Testes dos scripts de agregação do uso do CircleCI (scripts/uso/agregar.py e semanal.py).

Roda com a stdlib, sem dependência:

    python -I -m unittest discover -s tests/uso -v

Os testes com a exportação real leem a pasta de CSVs da variável de ambiente USO_CSV_DIR
e são pulados, com o aviso na saída, quando ela não existe. Os CSVs reais trazem nomes de
branches de repos privados e não entram no repositório.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
AGREGAR = RAIZ / "scripts" / "uso" / "agregar.py"
SEMANAL = RAIZ / "scripts" / "uso" / "semanal.py"

PASTA_REAL = os.environ.get("USO_CSV_DIR", "")
SEM_EXPORTACAO = (
    "AVISO: USO_CSV_DIR nao aponta para a exportacao real de uso do CircleCI; teste pulado"
)
tem_exportacao = bool(PASTA_REAL) and Path(PASTA_REAL).is_dir()

CABECALHO = (
    '"PROJECT_NAME","JOB_NAME","JOB_RUN_STARTED_AT","JOB_RUN_STOPPED_AT","JOB_BUILD_STATUS",'
    '"RESOURCE_CLASS","EXECUTOR","JOB_RUN_SECONDS","COMPUTE_CREDITS","STORAGE_CREDITS",'
    '"NETWORK_CREDITS","TOTAL_CREDITS"'
)


def rodar(script, *args):
    """Roda o script como o usuário roda, em modo isolado, e devolve o processo concluído."""
    return subprocess.run(
        [sys.executable, "-I", str(script), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )


class UsoTests(unittest.TestCase):
    @unittest.skipUnless(tem_exportacao, SEM_EXPORTACAO)
    def test_totais_da_exportacao_real_de_24_10_a_23_11(self):
        # Dano: somar créditos errado e subestimar ou superestimar o gasto do mês.
        # Fonte: exportação 01c8a143-0525-c5f6-001b-7a8366cb4f96 do CircleCI.
        r = rodar(AGREGAR, PASTA_REAL, "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(
            json.loads(r.stdout)["totais"],
            {"compute": 44379, "network": 18255, "storage": 709, "total": 63343},
        )

    def test_nulo_e_vazio_contam_como_zero_e_o_script_nao_falha(self):
        # Dano: a exportação traz \N em duração e créditos (76 linhas do vnforge `linux`)
        # e o script quebrar ou tratar o \N como texto no meio da soma.
        linhas = [
            CABECALHO,
            # linha normal
            '"vnforge","linux","2026-11-03 19:44:28.000","2026-11-03 19:45:28.000","success",'
            '"alessandrocaetanob/hyperius","runner",60,10,1,3,14',
            # linha com \N na classe, no executor, na duração e em todos os créditos
            '"vnforge","linux","2026-11-03 20:00:00.000","2026-11-03 20:01:00.000","failed",'
            r'"\N","\N",\N,\N,\N,\N,\N',
            # linha com crédito vazio e outro \N
            '"vnforge","linux","2026-11-03 21:00:00.000","2026-11-03 21:01:00.000","success",'
            '"alessandrocaetanob/hyperius","runner",60,"",\\N,5,5',
        ]
        with tempfile.TemporaryDirectory() as pasta:
            Path(pasta, "sintetico.csv").write_text("\n".join(linhas) + "\n", encoding="utf-8")
            r = rodar(AGREGAR, pasta, "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(
            json.loads(r.stdout)["totais"],
            {"compute": 10, "network": 8, "storage": 1, "total": 19},
        )

    def test_semanal_faixas_fronteiras_semana_iso_e_vizinhos_runner(self):
        # Dano: faixa errada nas fronteiras 1 e 3, vizinho contado ou perdido (outro projeto,
        # job que falhou, executor que nao e runner) e semana tirada do fim do job em vez do inicio.
        # Fonte: regra do brief, esperados contados a mao sobre os horarios abaixo.
        #
        # Alvo: projeto "alvo", job "j", executor runner. Dia 2026-11-02 e segunda (2026-W45),
        # 2026-11-01 e domingo (2026-W44).
        #
        # T1 10:00:00-10:01:40 (100 s, success). Vizinhos runner: N1 (projeto "outro", job "j",
        #    09:59:30-10:00:50) sobrepoe 10:00:00-10:00:50 = 50 s. D (executor docker) cobre T1
        #    inteiro e nao conta. Media = 50/100 = 0,5 -> "<1".
        #    N1 tem projeto "outro" e fica fora da mediana: so T1 entra em "<1" de W45.
        # T2 11:00:00-11:03:20 (200 s, success). Vizinho: F (projeto "alvo", job "j", status
        #    failed, 11:00:00-11:06:40, 400 s) sobrepoe 200 s; F conta como vizinho e nao entra
        #    na mediana. Media = 200/200 = 1,0 -> "1-3" (de 1 ate menos de 3).
        # T3 12:00:00-12:05:00 (300 s, success). Vizinhos: O1, O2, O3 (projeto "outro", job "x")
        #    cobrem 12:00:00-12:05:00, 300 s cada = 900 s. Media = 900/300 = 3,0 -> ">=3".
        # S  2026-11-01 23:59:00 a 2026-11-02 00:01:00 (120 s, success), sem vizinhos: media 0
        #    -> "<1". Comeca no domingo, entao e W44, mesmo terminando na segunda.
        #
        # Medianas: W44 {"<1": 120}; W45 {"<1": 100, "1-3": 200, ">=3": 300}.
        def linha(projeto, job, ini, fim, status, executor, segundos):
            return (
                f'"{projeto}","{job}","{ini}.000","{fim}.000","{status}",'
                f'"alessandrocaetanob/hyperius","{executor}",{segundos},0,0,0,0'
            )

        d = "2026-11-02"
        linhas = [
            CABECALHO,
            linha("alvo", "j", f"{d} 10:00:00", f"{d} 10:01:40", "success", "runner", 100),
            linha("outro", "j", f"{d} 09:59:30", f"{d} 10:00:50", "success", "runner", 80),
            linha("outro", "y", f"{d} 10:00:00", f"{d} 10:01:40", "success", "docker", 100),
            linha("alvo", "j", f"{d} 11:00:00", f"{d} 11:03:20", "success", "runner", 200),
            linha("alvo", "j", f"{d} 11:00:00", f"{d} 11:06:40", "failed", "runner", 400),
            linha("alvo", "j", f"{d} 12:00:00", f"{d} 12:05:00", "success", "runner", 300),
            linha("outro", "x", f"{d} 12:00:00", f"{d} 12:05:00", "success", "runner", 300),
            linha("outro", "x", f"{d} 12:00:00", f"{d} 12:05:00", "success", "runner", 300),
            linha("outro", "x", f"{d} 12:00:00", f"{d} 12:05:00", "success", "runner", 300),
            linha("alvo", "j", "2026-11-01 23:59:00", f"{d} 00:01:00", "success", "runner", 120),
        ]
        with tempfile.TemporaryDirectory() as pasta:
            Path(pasta, "sintetico.csv").write_text("\n".join(linhas) + "\n", encoding="utf-8")
            r = rodar(
                SEMANAL,
                pasta,
                "--projeto", "alvo",
                "--job", "j",
                "--executor", "runner",
                "--json",
            )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(
            json.loads(r.stdout),
            {
                "2026-W44": {"<1": 120},
                "2026-W45": {"<1": 100, "1-3": 200, ">=3": 300},
            },
        )

    @unittest.skipUnless(tem_exportacao, SEM_EXPORTACAO)
    def test_semanal_vnforge_linux_runner_na_semana_44(self):
        # Dano: medir mal a lentidão por concorrência e dimensionar o pool sobre o número errado.
        # Fonte: medição sobre a mesma exportação real (mediana de JOB_RUN_SECONDS por faixa).
        r = rodar(
            SEMANAL,
            PASTA_REAL,
            "--projeto", "vnforge",
            "--job", "linux",
            "--executor", "runner",
            "--json",
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        semana = json.loads(r.stdout)["2026-W44"]
        self.assertEqual(semana["<1"], 378)
        self.assertEqual(semana[">=3"], 1086)


if __name__ == "__main__":
    unittest.main()
