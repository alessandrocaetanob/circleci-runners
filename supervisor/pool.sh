#!/bin/sh
# Teto do conjunto de slots: um cgroup pai /hyperius com cpu.max e memory.max.
# Lido por slot.sh (dentro do docker:29-cli) e por tests/pool.sh (no host, em Git Bash).
#
# O diretório precisa existir com os limites ANTES do primeiro docker run --cgroup-parent=/hyperius:
# sem ele o Docker cria o pai sozinho e sem limite. Depois de reiniciar o Docker Desktop a VM volta
# sem /hyperius e os slots sobem pelo restart policy, então a garantia roda antes de cada job.

command -v log >/dev/null 2>&1 || log() { printf '%s\n' "$*"; }

POOL_HELPER_IMAGE="${POOL_HELPER_IMAGE:-docker:29-cli}"

# Converte 24g, 512m, 1024k ou 1048576 em bytes (mesmos sufixos do docker --memory).
pool_to_bytes() {
  n=${1%%[!0-9]*}
  [ -n "$n" ] && [ "$n" -gt 0 ] || return 1
  # Um sufixo só: 24gb ou 1g5 virariam um memory.max de poucos bytes e matariam todo job.
  case "${1#"$n"}" in
    '' | [bB]) echo "$n" ;;
    [kK]) echo $(( n * 1024 )) ;;
    [mM]) echo $(( n * 1048576 )) ;;
    [gG]) echo $(( n * 1073741824 )) ;;
    *) return 1 ;;
  esac
}

# Cria /hyperius se faltar, grava os limites e confere o que o kernel devolveu.
# Retorna diferente de zero se não conseguir ou se os valores não baterem.
ensure_pool_cgroup() {
  _cpus="${POOL_CPUS:-12}"
  _mem="${POOL_MEMORY:-24g}"
  case "$_cpus" in
    '' | *[!0-9.]* | *.*.* | .)
      log "POOL_CPUS inválido: '$_cpus'."
      return 1
      ;;
  esac
  if ! _mem_bytes=$(pool_to_bytes "$_mem"); then
    log "POOL_MEMORY inválido: '$_mem' (use 24g, 512m, ...)."
    return 1
  fi
  _quota=$(awk -v c="$_cpus" 'BEGIN { printf "%d", c * 100000 }')

  # shellcheck disable=SC2016
  _out=$(MSYS_NO_PATHCONV=1 docker run --rm --pull never --privileged --cgroupns=host \
    -v /sys/fs/cgroup:/sys/fs/cgroup "$POOL_HELPER_IMAGE" sh -c '
      set -eu
      d=/sys/fs/cgroup/hyperius
      mkdir -p "$d"
      echo "+cpu +memory" > "$d/cgroup.subtree_control"
      echo "$1 100000" > "$d/cpu.max"
      echo "$2" > "$d/memory.max"
      cpu=$(cat "$d/cpu.max")
      mem=$(cat "$d/memory.max")
      sub=$(cat "$d/cgroup.subtree_control")
      echo "cpu.max=$cpu memory.max=$mem subtree_control=$sub"
      [ "$cpu" = "$1 100000" ] && [ "$mem" = "$2" ] &&
        case " $sub " in *" cpu "*) case " $sub " in *" memory "*) exit 0 ;; esac ;; esac
      exit 1
    ' pool-helper "$_quota" "$_mem_bytes" 2>&1) && _rc=0 || _rc=$?

  if [ "$_rc" -ne 0 ]; then
    log "cgroup /hyperius fora do esperado (cpu.max=${_quota} 100000, memory.max=${_mem_bytes}): $_out"
    return 1
  fi
  log "cgroup /hyperius pronto: $_out"
}
