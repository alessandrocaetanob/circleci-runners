#!/bin/sh
# Supervisor de um slot: sobe um container de runner novo por job.
# O runner roda em single-task e sai ao fim do job; o laço sobe o próximo.
set -u

log() { printf '%s [%s] %s\n' "$(date -u +%H:%M:%S)" "${SLOT_NAME:-slot}" "$*"; }

if [ -z "${SLOT_NAME:-}" ]; then
  echo "SLOT_NAME vazio." >&2
  exit 1
fi
if [ -z "${CIRCLECI_RUNNER_API_AUTH_TOKEN:-}" ]; then
  log "CIRCLECI_RUNNER_API_AUTH_TOKEN vazio. Suba com scripts/up.ps1 (op run resolve o token)." >&2
  exit 1
fi

RUNNER_IMAGE="${RUNNER_IMAGE:-hyperius-runner:latest}"
JOB_CPUS="${JOB_CPUS:-8}"
JOB_MEMORY="${JOB_MEMORY:-10g}"
JOB_SHM="${JOB_SHM:-1g}"
STOP_TIMEOUT="${STOP_TIMEOUT:-30}"
MIN_RUN_SECONDS=10
PAUSE=5
MAX_BACKOFF=300

# O docker run herda o token do ambiente (-e NOME sem valor): ele não vai nos argumentos.
export CIRCLECI_RUNNER_API_AUTH_TOKEN

pid=""
stopping=0

# sleep em segundo plano para o trap de TERM interromper a espera.
nap() {
  sleep "$1" &
  pid=$!
  wait "$pid" 2>/dev/null
  pid=""
}

shutdown() {
  stopping=1
  log "sinal recebido, parando o container do job."
  docker stop -t "$STOP_TIMEOUT" "$SLOT_NAME" >/dev/null 2>&1
  if [ -n "$pid" ]; then
    wait "$pid" 2>/dev/null
  fi
  exit 0
}
trap shutdown TERM INT

delay=$PAUSE
while :; do
  state=$(docker inspect -f '{{.State.Running}}' "$SLOT_NAME" 2>/dev/null || true)
  if [ "$state" = "true" ]; then
    # Sobrou de um supervisor anterior: espera o job terminar em vez de brigar pelo nome.
    log "container $SLOT_NAME já está rodando, aguardando."
    docker wait "$SLOT_NAME" >/dev/null 2>&1 &
    pid=$!
    wait "$pid" 2>/dev/null
    pid=""
    continue
  elif [ "$state" = "false" ]; then
    log "removendo container parado $SLOT_NAME."
    docker rm -f "$SLOT_NAME" >/dev/null 2>&1 || true
  fi

  log "iniciando runner ($RUNNER_IMAGE, ${JOB_CPUS} cpus, ${JOB_MEMORY})."
  started=$(date +%s)
  docker run --rm --pull never \
    --name "$SLOT_NAME" \
    --label "hyperius.slot=$SLOT_NAME" \
    --cpus "$JOB_CPUS" \
    --memory "$JOB_MEMORY" \
    --shm-size "$JOB_SHM" \
    -e CIRCLECI_RUNNER_API_AUTH_TOKEN \
    -e CIRCLECI_RUNNER_NAME="$SLOT_NAME" \
    -e CIRCLECI_RUNNER_MODE=single-task \
    -e CIRCLECI_RUNNER_LOGGING_FORMAT=text \
    "$RUNNER_IMAGE" &
  pid=$!
  wait "$pid"
  code=$?
  pid=""
  [ "$stopping" -eq 1 ] && exit 0

  elapsed=$(( $(date +%s) - started ))
  if [ "$elapsed" -lt "$MIN_RUN_SECONDS" ]; then
    log "runner saiu com código $code após ${elapsed}s. Token inválido ou imagem ausente? Nova tentativa em ${delay}s."
    nap "$delay"
    delay=$(( delay * 2 ))
    [ "$delay" -gt "$MAX_BACKOFF" ] && delay=$MAX_BACKOFF
  else
    log "runner saiu com código $code após ${elapsed}s. Próximo em ${PAUSE}s."
    delay=$PAUSE
    nap "$PAUSE"
  fi
done
