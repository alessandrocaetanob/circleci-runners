# circleci-runners

Machine runners do CircleCI no Docker Desktop, registrados no resource class `alessandrocaetanob/hyperius`.
Três slots (`hyperius-1` a `hyperius-3`) rodam jobs em paralelo. Cada job executa num container novo, que some ao
fim do job, então o job seguinte encontra HOME, `/usr/local` e pacotes apt limpos.

Como funciona: o runner sobe em modo `single-task` e sai quando termina um job. Um supervisor por slot
(`supervisor/slot.sh`, no `docker:29-cli`) repete o `docker run --rm` da imagem do runner.

Plano e decisões: `docs/plans/2026-10-24-runners-hyperius.md`.

## Pré-requisitos

- Docker Desktop com backend WSL2. Cada job recebe no máximo 8 CPUs e 10 GB (ajustável, veja abaixo), então
  três jobs cabem em 24 CPUs e 31 GB.
- 1Password CLI (`op`) com a integração do app desktop ligada.
- O item `CircleCI Runner` no vault `Claude`, com o token do resource class no campo `credential`
  (`op://Claude/CircleCI Runner/credential`).
- PowerShell 7 (`pwsh`).

## Uso

Todos os scripts ficam em `scripts/` e funcionam de qualquer diretório.

```powershell
scripts/build.ps1     # constrói hyperius-runner:latest e hyperius-runner:<yyyyMMdd>, depois roda o smoke test
scripts/up.ps1        # op run lê o token e o compose sobe os três slots
scripts/status.ps1    # slots, containers de job e as últimas linhas do log (-Tail 20)
scripts/down.ps1      # para os slots e remove os containers de job que sobrarem
```

Com o Docker Desktop iniciando no login, os slots voltam sozinhos depois de um reboot (`restart: unless-stopped`).
O token é lido só em `up.ps1`; no reboot, o Docker reutiliza o valor guardado na configuração dos containers.

Limites por job, via variáveis de ambiente antes do `up.ps1`: `JOB_CPUS` (padrão `8`), `JOB_MEMORY` (padrão `10g`),
`JOB_SHM` (padrão `1g`, o `/dev/shm` do container, útil para navegadores).

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

As pastas do Node pertencem ao usuário `circleci`, então `npm i -g` funciona sem sudo. O `/usr/bin/python3` do
sistema não muda. Terraform e as dependências do Playwright ficam fora da imagem: cada projeto instala no job.

As versões ficam em `ARG` no `image/Dockerfile`. Para subir uma versão do Node ou do PowerShell, troque o
`ARG` da versão e do sha256 juntos.

## Segurança

- O supervisor monta o socket do Docker Desktop, que dá controle total sobre o Docker. Os containers de job não
  recebem o socket.
- O token fica na configuração dos containers de supervisor e aparece em `docker inspect`. Ele não é gravado em
  arquivo (`runner.env` só tem a referência `op://`) nem aparece nos argumentos de processo ou nos logs.
- Quem executa código do repositório no runner tem o token do container e `sudo` dentro dele. Use o resource
  class só com repositórios em que você confia.
