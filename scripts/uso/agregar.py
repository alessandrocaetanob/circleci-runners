"""Agrega a exportação de uso do CircleCI: créditos por projeto e job.

    python -I scripts/uso/agregar.py <pasta com os .csv> [--json]

Lê todos os *.csv da pasta. O nulo da exportação é escrito \\N (também entre aspas) e o vazio
conta como 0, como qualquer valor que não seja número.
"""
import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

NULO = "\\N"


def numero(texto):
    if texto is None or texto.strip() in ("", NULO):
        return 0.0
    try:
        return float(texto)
    except ValueError:
        return 0.0


def texto(valor):
    return "" if valor is None or valor.strip() == NULO else valor.strip()


def ler_linhas(pasta):
    arquivos = sorted(Path(pasta).glob("*.csv"))
    if not arquivos:
        sys.exit(f"nenhum *.csv em {pasta}")
    for arquivo in arquivos:
        with open(arquivo, newline="", encoding="utf-8") as f:
            yield from csv.DictReader(f)


def agregar(linhas):
    totais = defaultdict(float)
    jobs = {}
    for linha in linhas:
        for coluna, chave in (
            ("COMPUTE_CREDITS", "compute"),
            ("NETWORK_CREDITS", "network"),
            ("STORAGE_CREDITS", "storage"),
            ("TOTAL_CREDITS", "total"),
        ):
            totais[chave] += numero(linha.get(coluna))
        chave = tuple(
            texto(linha.get(c)) for c in ("PROJECT_NAME", "JOB_NAME", "RESOURCE_CLASS", "EXECUTOR")
        )
        job = jobs.setdefault(chave, {"execucoes": 0, "segundos": 0.0, "creditos": 0.0})
        job["execucoes"] += 1
        job["segundos"] += numero(linha.get("JOB_RUN_SECONDS"))
        job["creditos"] += numero(linha.get("TOTAL_CREDITS"))
    lista = [
        {
            "projeto": projeto,
            "job": nome,
            "classe": classe,
            "executor": executor,
            "execucoes": dados["execucoes"],
            "minutos": round(dados["segundos"] / 60),
            "creditos": round(dados["creditos"]),
        }
        for (projeto, nome, classe, executor), dados in sorted(
            jobs.items(), key=lambda item: (-item[1]["segundos"], item[0])
        )
    ]
    return {"totais": {k: round(totais[k]) for k in ("compute", "network", "storage", "total")},
            "jobs": lista}


def imprimir_tabela(resultado):
    t = resultado["totais"]
    print(
        f"total {t['total']} creditos: cômputo {t['compute']}, rede {t['network']}, "
        f"armazenamento {t['storage']}\n"
    )
    cabecalho = ("projeto", "job", "classe", "executor", "execuções", "minutos", "créditos")
    linhas = [cabecalho] + [
        (j["projeto"], j["job"], j["classe"], j["executor"], str(j["execucoes"]),
         str(j["minutos"]), str(j["creditos"]))
        for j in resultado["jobs"]
    ]
    larguras = [max(len(l[i]) for l in linhas) for i in range(len(cabecalho))]
    for l in linhas:
        print("  ".join(c.ljust(w) if i < 4 else c.rjust(w) for i, (c, w) in enumerate(zip(l, larguras))))


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("pasta", help="pasta com os CSVs da exportação de uso")
    parser.add_argument("--json", action="store_true", help="saída em JSON")
    args = parser.parse_args()
    resultado = agregar(ler_linhas(args.pasta))
    if args.json:
        print(json.dumps(resultado, ensure_ascii=False))
    else:
        imprimir_tabela(resultado)


if __name__ == "__main__":
    main()
