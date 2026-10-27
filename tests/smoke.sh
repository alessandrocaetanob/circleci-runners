#!/usr/bin/env bash
# Roda dentro da imagem, como circleci, num shell de login:
#   docker run --rm -v "<repo>/tests/smoke.sh:/tmp/smoke.sh:ro" --entrypoint bash hyperius-runner:latest -lc 'bash /tmp/smoke.sh'
set -u

failures=()

check() {
  local name="$1" expected="$2"
  shift 2
  local out
  if ! out=$("$@" 2>&1); then
    echo "FALHOU  $name: comando falhou: ${out:0:200}"
    failures+=("$name")
  elif [[ -n "$expected" && "$out" != *$expected* ]]; then
    echo "FALHOU  $name: esperado '$expected', obtido '${out:0:200}'"
    failures+=("$name")
  else
    echo "ok      $name: ${out%%$'\n'*}"
  fi
}

check git "git version" git --version
check git-lfs "git-lfs/" git lfs version
check zip "Zip " zip -v
check unzip "UnZip" unzip -v
check tar "tar" tar --version
check xz "xz" xz --version
check sha256sum "sha256sum" sha256sum --version
check curl "curl" curl --version
check jq "jq-" jq --version
check ssh "" ssh -V
check rsync "rsync" rsync --version
check gcc "gcc" gcc --version
check java '"21.' java -version
check dotnet-sdk "10." dotnet --list-sdks
# shellcheck disable=SC2016
check pwsh "7.6.7" pwsh -NoProfile -Command '$PSVersionTable.PSVersion.ToString()'
check node-default "v24.22.0" node -v
# shellcheck disable=SC2016
check use-node-22 "v22.12.0" bash -c 'eval "$(use-node 22)"; node -v'
check python "Python 3.12." python3 --version
check python-venv "pip " bash -c 'python3 -m venv /tmp/v && /tmp/v/bin/pip --version'
check npm-global "1.2.3" bash -c 'npm i -g --no-audit --no-fund semver@7.6.3 >/dev/null && semver 1.2.3'
check sudo "" sudo -n true
check circleci-runner "" /opt/circleci/bin/circleci-runner --version
check ssh-known-hosts "github.com" ssh-keygen -F github.com -f /etc/ssh/ssh_known_hosts
# shellcheck disable=SC2016
check playwright-chromium "chromium ok" bash -c 'd=$(mktemp -d) && cd "$d" && npm init -y >/dev/null && npm i --no-audit --no-fund playwright-core@1.64.1 >/dev/null && node -e "const {chromium}=require(\"playwright-core\");(async()=>{const b=await chromium.launch();const p=await b.newPage();await p.goto(\"about:blank\");console.log(\"chromium ok \"+b.version());await b.close()})().catch(e=>{console.error(e.message);process.exit(1)})"'

if ((${#failures[@]})); then
  echo
  echo "Falhas (${#failures[@]}): ${failures[*]}"
  exit 1
fi
echo
echo "Todas as verificações passaram."
