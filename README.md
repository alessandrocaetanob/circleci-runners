# circleci-runners

Machine runners do CircleCI no Docker Desktop, registrados no resource class `alessandrocaetanob/hyperius`.
Seis slots (`hyperius-1` a `hyperius-6`) rodam jobs em paralelo, com teto de 12 CPUs e 24 GB para o conjunto. Cada job executa num container novo, que some ao
fim do job, então o job seguinte encontra HOME, `/usr/local` e pacotes apt limpos.

Como funciona: o runner sobe em modo `single-task` e sai quando termina um job. Um supervisor por slot
(`supervisor/slot.sh`, no `docker:29-cli`) repete o `docker run --rm` da imagem do runner.

Plano e decisões: `docs/plans/2026-10-24-runners-hyperius.md` e `docs/plans/2026-10-27-seis-slots.md`.

## Pré-requisitos

- Docker Desktop com backend WSL2. Cada job recebe no máximo 4 CPUs e 6 GB (ajustável, veja abaixo) e o conjunto
  dos seis slots fica limitado a 12 CPUs e 24 GB, cerca de metade de um host de 24 threads e 64 GB.
- 1Password CLI (`op`) com a integração do app desktop ligada.
- O item `CircleCI Runner` no vault `Claude`, com o token do resource class no campo `credential`
  (`op://Claude/CircleCI Runner/credential`).
- PowerShell 7 (`pwsh`).

## Uso

Todos os scripts ficam em `scripts/` e funcionam de qualquer diretório.

```powershell
scripts/build.ps1     # constrói hyperius-runner:latest e hyperius-runner:<yyyyMMdd>, depois roda o smoke test
scripts/up.ps1        # op run lê o token e o compose sobe os seis slots
scripts/status.ps1    # slots, containers de job, teto /hyperius e as últimas linhas do log (-Tail 20)
scripts/down.ps1      # para os slots e remove os containers de job que sobrarem
```

Com o Docker Desktop iniciando no login, os slots voltam sozinhos depois de um reboot (`restart: unless-stopped`).
O token é lido só em `up.ps1`; no reboot, o Docker reutiliza o valor guardado na configuração dos containers.

Limites, via variáveis de ambiente antes do `up.ps1`: `JOB_CPUS` (padrão `4`), `JOB_MEMORY` (padrão `6g`),
`JOB_SHM` (padrão `1g`, o `/dev/shm` do container, útil para navegadores), `POOL_CPUS` (padrão `12`) e
`POOL_MEMORY` (padrão `24g`), o teto do conjunto de slots.

### Teto do conjunto

Os containers de job rodam sob o cgroup pai `/hyperius`, com `cpu.max` de `POOL_CPUS` e `memory.max` de `POOL_MEMORY`.
Com os seis slots ocupados, os jobs dividem 12 CPUs (2 em média); com um ou dois jobs, cada um usa até 4. Antes de cada
job, o `supervisor/slot.sh` cria o `/hyperius` se faltar e grava os limites por um container auxiliar privilegiado
(`supervisor/pool.sh`, imagem `docker:29-cli`). Se o kernel devolver outros valores, o runner não sobe e o slot tenta
de novo com backoff. Isso cobre o reinício do Docker Desktop, depois do qual a VM volta sem o cgroup e os slots sobem
pelo restart policy, sem passar pelo compose.

`scripts/status.ps1` mostra `cpu.max`, `memory.current` e `memory.max` do `/hyperius`.

### Testes

- `scripts/build.ps1` roda `tests/smoke.sh` dentro da imagem (ferramentas, `known_hosts`, Chromium).
- `bash tests/pool.sh` roda no host, em Git Bash, com o Docker Desktop ligado. Garante o `/hyperius`, sobe seis
  containers `pool-test-1` a `pool-test-6` com 4 CPUs ocupadas cada e falha se a soma do `docker stats` ficar fora de
  1100% a 1250%. Os containers somem no fim.

### Atualizar a imagem

1. `scripts/build.ps1`.
2. `scripts/down.ps1` e `scripts/up.ps1`.

`down.ps1` para os slots e mata o job que estiver rodando. Para não perder job, espere os slots ficarem ociosos
(`scripts/status.ps1`) antes do passo 2. Sem `down`, um slot só usa a imagem nova no próximo job, porque o
`docker run` lê `hyperius-runner:latest` a cada iteração.

## Usar o runner num projeto

No `.circleci/config.yml`, troque o executor do job:

```yaml
jobs:
  test:
    machine: true
    resource_class: alessandrocaetanob/hyperius
    steps:
      - checkout
      - run: use-node 22
      - run: node -v
```

- Jobs com `docker:` não rodam em machine runner. Use `machine: true`.
- O Node 24.22.0 é o padrão. `use-node 22` troca para o 22.12.0 e grava o novo PATH em `$BASH_ENV`, para os steps
  seguintes. Se um step não enxergar `$BASH_ENV`, use `eval "$(use-node 22)"` no próprio step, que sempre funciona.
- O job tem `sudo` sem senha dentro do container, mas não tem acesso ao Docker.

## O que a imagem tem

Base: `circleci/runner-agent:machine-3` (Ubuntu 22.04, usuário `circleci`).

| Ferramenta | Versão | Origem |
|---|---|---|
| Node | 24.22.0 (padrão), 22.12.0 (`use-node 22`) | tarball do nodejs.org, sha256 fixado, em `/opt/node/<major>` |
| .NET SDK | 10.0 (último do canal) | `dotnet-install.sh` em `/usr/share/dotnet` |
| PowerShell | 7.6.7 | `.deb` da release do GitHub, sha256 fixado |
| Python | 3.12 com venv e pip | PPA deadsnakes; `python3` em `/usr/local/bin` |
| OpenJDK | 21 (headless) | apt |
| git, git-lfs, openssh-client | apt do jammy | apt |
| zip, unzip, xz-utils, tar, rsync, file, jq, curl | apt do jammy | apt |
| build-essential, pkg-config | apt do jammy | apt |
| Playwright (dependências de sistema e Chromium) | 1.64.1 | `npx playwright@1.64.1 install-deps chromium` e `install chromium`; navegador em `/opt/ms-playwright` (`PLAYWRIGHT_BROWSERS_PATH`) |
| Chaves SSH do github.com | ed25519, ecdsa, rsa | `image/ssh_known_hosts`, em `/etc/ssh/ssh_known_hosts` |

As pastas do Node pertencem ao usuário `circleci`, então `npm i -g` funciona sem sudo. O `/usr/bin/python3` do
sistema não muda. Terraform fica fora da imagem: cada projeto instala no job.

O Chromium do Playwright 1.64.1 já está na imagem. Um projeto com a mesma versão do Playwright usa
`npx playwright install chromium` sem baixar nada nem rodar `--with-deps`; outra versão baixa o seu navegador para
`/opt/ms-playwright`, que pertence ao `circleci`. Sem o `known_hosts`, o `git fetch` por SSH ficava esperando a
confirmação da chave do github.com.

`image/ssh_known_hosts` vem de `https://api.github.com/meta` (campo `ssh_keys`), conferido contra as impressões SHA256
publicadas em "GitHub's SSH key fingerprints" na documentação do GitHub. Para atualizar as chaves, repita essa conferência.

As versões ficam em `ARG` no `image/Dockerfile`. Para subir uma versão do Node ou do PowerShell, troque o
`ARG` da versão e do sha256 juntos; o Playwright tem só `PLAYWRIGHT_VERSION`, e o smoke test também fixa a versão.

## Segurança

- O supervisor monta o socket do Docker Desktop, que dá controle total sobre o Docker. Os containers de job não
  recebem o socket.
- O token fica na configuração dos containers de supervisor e aparece em `docker inspect`. Ele não é gravado em
  arquivo (`runner.env` só tem a referência `op://`) nem aparece nos argumentos de processo ou nos logs.
- Quem executa código do repositório no runner tem o token do container e `sudo` dentro dele. Use o resource
  class só com repositórios em que você confia.
