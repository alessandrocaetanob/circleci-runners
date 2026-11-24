#!/usr/bin/env bash
# Roda no host (Git Bash), com o Docker Desktop ligado: confere que o teto do cgroup /hyperius vale.
# Sobe 6 containers que ocupam 4 CPUs cada, sob /hyperius, e exige que a soma do docker stats
# fique perto das 16 CPUs do pool (90% a 105% de POOL_CPUS), não nas 24 que os limites por job somariam.
set -u

# Sem isso o Git Bash converte -v /sys/... em C:\Program Files\Git\sys\...
export MSYS_NO_PATHCONV=1

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
image="${POOL_TEST_IMAGE:-docker:29-cli}"
count=6
warmup="${POOL_TEST_WARMUP:-15}"
names=()
for ((i = 1; i <= count; i++)); do names+=("pool-test-$i"); done

cleanup() {
  docker rm -f "${names[@]}" >/dev/null 2>&1
}
trap cleanup EXIT

export POOL_HELPER_IMAGE="$image"
# shellcheck source=../supervisor/pool.sh
. "$root/supervisor/pool.sh"
POOL_CPUS="${POOL_CPUS:-16}"
POOL_MEMORY="${POOL_MEMORY:-24g}"
# Faixa derivada do teto: 90% a 105% de POOL_CPUS*100. Sem teto a soma daria 2400%.
min=$((POOL_CPUS * 100 * 90 / 100))
max=$((POOL_CPUS * 100 * 105 / 100))

cleanup
if ! ensure_pool_cgroup; then
  echo "FALHOU  não foi possível garantir o cgroup /hyperius."
  exit 1
fi

for name in "${names[@]}"; do
  if ! docker run -d --rm --pull never --name "$name" --cgroup-parent=/hyperius --cpus 4 \
    "$image" sh -c 'for i in 1 2 3 4; do (while :; do :; done) & done; wait' >/dev/null; then
    echo "FALHOU  docker run de $name."
    exit 1
  fi
done

echo "Aguardando ${warmup}s para o uso de CPU estabilizar."
sleep "$warmup"

# Média de 3 amostras: um só docker stats --no-stream oscila acima do teto duro do cgroup.
samples=3
sum_all=0
for ((n = 1; n <= samples; n++)); do
  stats=$(docker stats --no-stream --format '{{.Name}} {{.CPUPerc}}' "${names[@]}") || {
    echo "FALHOU  docker stats."
    exit 1
  }
  echo "$stats"
  sum_all=$((sum_all + $(echo "$stats" | awk '{ gsub(/%/, "", $2); sum += $2 } END { printf "%d", sum }')))
  ((n < samples)) && sleep 2
done
total=$((sum_all / samples))
echo "Soma de CPU: ${total}% (esperado entre ${min}% e ${max}%)."

if ((total < min || total > max)); then
  echo "FALHOU  a soma ficou fora da faixa."
  exit 1
fi
echo "ok      o teto do pool vale."
