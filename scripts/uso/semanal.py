"""Duração e fila por semana de um job, e a mediana por faixa de jobs ao lado.

    python -I scripts/uso/semanal.py <pasta com os .csv> --projeto P --job J --executor E [--json]

Considera os jobs `success` do projeto, job e executor dados, agrupados pela semana ISO do
INÍCIO (2026-W44). A faixa vem da média de outros jobs `runner` rodando ao mesmo tempo, de
qualquer projeto e status: o tempo de sobreposição somado dividido pela duração do job.
Faixas: "<1", "1-3" (de 1 até menos de 3) e ">=3". O valor é a mediana de JOB_RUN_SECONDS.
"""
import argparse
import csv
import json
import statistics
import sys
from datetime import datetime
from pathlib import Path

# Vazio, \N (a forma entre aspas) e \\N (a forma sem aspas, com duas barras no CSV).
NULOS = ("", "\\N", "\\\\N")
FAIXAS = ("<1", "1-3", ">=3")


def numero(texto):
    if texto is None or texto.strip() in NULOS:
        return 0.0
    try:
        return float(texto)
    except ValueError:
        return 0.0


def momento(texto):
    if texto is None or texto.strip() in NULOS:
        return None
    try:
        return datetime.fromisoformat(texto.strip().replace(" UTC", "")[:26])
    except ValueError:
        return None


def ler_linhas(pasta):
    arquivos = sorted(Path(pasta).glob("*.csv"))
    if not arquivos:
        sys.exit(f"nenhum *.csv em {pasta}")
    linhas = []
    for arquivo in arquivos:
        with open(arquivo, newline="", encoding="utf-8") as f:
            linhas.extend(csv.DictReader(f))
    return linhas


def faixa(media):
    if media < 1:
        return "<1"
    return "1-3" if media < 3 else ">=3"


def mediana(valores):
    return int(round(statistics.median(valores)))


def semanal(linhas, projeto, job, executor):
    """Devolve {semana: {faixa: [(segundos, fila)]}} dos jobs success pedidos."""
    runner = []
    alvos = []
    for i, linha in enumerate(linhas):
        inicio, fim = momento(linha.get("JOB_RUN_STARTED_AT")), momento(linha.get("JOB_RUN_STOPPED_AT"))
        if inicio is None or fim is None:
            continue
        if linha.get("EXECUTOR") == "runner":
            runner.append((inicio, fim, i))
        if (
            linha.get("PROJECT_NAME") == projeto
            and linha.get("JOB_NAME") == job
            and linha.get("EXECUTOR") == executor
            and linha.get("JOB_BUILD_STATUS") == "success"
        ):
            alvos.append((inicio, fim, i))
    runner.sort()
    semanas = {}
    for inicio, fim, i in alvos:
        duracao = (fim - inicio).total_seconds()
        sobreposto = 0.0
        for v_inicio, v_fim, j in runner:
            if v_inicio >= fim:
                break
            if j == i:
                continue
            sobreposto += max(0.0, (min(fim, v_fim) - max(inicio, v_inicio)).total_seconds())
        media = sobreposto / duracao if duracao > 0 else 0.0
        entrada = linhas[i]
        fila = momento(entrada.get("JOB_RUN_QUEUED_AT"))
        espera = (inicio - fila).total_seconds() if fila else 0.0
        semana = inicio.strftime("%G-W%V")
        semanas.setdefault(semana, {}).setdefault(faixa(media), []).append(
            (numero(entrada.get("JOB_RUN_SECONDS")), espera)
        )
    return semanas


def imprimir_tabela(semanas):
    print("semana     execuções  duração mediana (s)  fila mediana (s)  mediana por faixa de jobs ao lado")
    for semana in sorted(semanas):
        pares = [p for lista in semanas[semana].values() for p in lista]
        por_faixa = "  ".join(
            f"{f}: {mediana([s for s, _ in semanas[semana][f]])} s (n={len(semanas[semana][f])})"
            for f in FAIXAS
            if f in semanas[semana]
        )
        print(
            f"{semana}  {len(pares):>9}  {mediana([s for s, _ in pares]):>19}  "
            f"{mediana([q for _, q in pares]):>16}  {por_faixa}"
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("pasta", help="pasta com os CSVs da exportação de uso")
    parser.add_argument("--projeto", required=True)
    parser.add_argument("--job", required=True)
    parser.add_argument("--executor", required=True)
    parser.add_argument("--json", action="store_true", help="saída em JSON")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    semanas = semanal(ler_linhas(args.pasta), args.projeto, args.job, args.executor)
    if args.json:
        resultado = {
            semana: {f: mediana([s for s, _ in semanas[semana][f]]) for f in FAIXAS if f in semanas[semana]}
            for semana in sorted(semanas)
        }
        print(json.dumps(resultado, ensure_ascii=False))
    else:
        imprimir_tabela(semanas)


if __name__ == "__main__":
    main()
