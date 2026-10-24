# Runners do CircleCI no Docker Desktop (resource class hyperius)

Data: 2026-10-24. Estado: aguardando aprovação.

## Objetivo

Rodar jobs do vnforge, do personal-notes e do dotfiles em machine runners self-hosted nesta máquina,
no Docker Desktop (backend WSL2), registrados no resource class `alessandrocaetanob/hyperius`.

## Decisões

| Tema | Escolha | Origem |
|---|---|---|
| Tipo de runner | Machine runner 3 em container, imagem base `circleci/runner-agent:machine-3` | Doc "Install machine runner 3 on Docker" (circleci.com/docs/guides/execution-runner/install-machine-runner-3-on-docker) |
| Isolamento | Um container novo por job: `CIRCLECI_RUNNER_MODE=single-task` e um supervisor que sobe o próximo com `docker run --rm` | Resposta do Alessandro em 2026-10-24 |
| Paralelismo | 3 runners, `hyperius-1` a `hyperius-3` | Resposta do Alessandro |
| Docker dentro do job | Não: os jobs não recebem o socket do Docker Desktop; só o supervisor recebe | Resposta do Alessandro |
| Node | 24.22.0 no PATH, 22.12.0 em `/opt/node/22` com o helper `use-node 22` | Resposta do Alessandro; versões dos configs do dotfiles e do personal-notes |
| Token | `op://Claude/CircleCI Runner/credential`, lido por `op run` na subida e nunca gravado em arquivo | Campos do item no 1Password (o campo `username` é `alessandrocaetanob`) |

O CircleCI distribui só um job por vez para cada runner. O modo `single-task` faz o processo
sair ao fim do job, e o container sai junto porque o entrypoint `run.sh` faz `exec` do
`circleci-runner machine`. O supervisor de cada slot repete o `docker run --rm`, então o job seguinte
encontra HOME, `/usr/local` e pacotes apt limpos, como numa máquina da nuvem.

## O que a imagem base já tem

Conferido com `docker run` na imagem em 2026-10-24: Ubuntu 22.04.5, `circleci-runner` 3.1.14,
usuário `circleci` (uid 1500) com sudo sem senha, `curl`, `jq`, `unzip`, `wget`, `gzip`. O entrypoint
define `CIRCLECI_RUNNER_WORK_DIR=/var/opt/circleci/workdir` e liga a limpeza do diretório de trabalho.

## O que a imagem vai instalar

| Ferramenta | Versão | Quem usa | Fonte da instalação |
|---|---|---|---|
| git, git-lfs, openssh-client | apt do jammy | todos (checkout) | apt |
| zip, xz-utils, tar, rsync, file | apt do jammy | `publicar` do vnforge (zip, tar, sha256sum) | apt |
| build-essential, pkg-config | apt do jammy | módulos nativos do npm | apt |
| OpenJDK | 21 headless | pedido no escopo (Sonar e ferramentas Java) | apt `openjdk-21-jdk-headless` |
| .NET SDK | canal 10.0 (global.json pede 10.0.100 com `latestFeature`) | vnforge `linux` e `publicar` | `dotnet-install.sh` em `/usr/share/dotnet` |
| PowerShell | 7.6.7 | dotfiles `test` e `lint` | `.deb` da release do GitHub, conferido com o sha256 que o dotfiles já fixa (`868c575f…c8b2`) |
| Node | 24.22.0 e 22.12.0 | dotfiles (24), personal-notes (22) | tarball do nodejs.org conferido com o SHASUMS256 |
| Python | 3.12 com venv e pip | personal-notes `pytest` | PPA deadsnakes; `python3` em `/usr/local/bin` aponta para 3.12, o `/usr/bin/python3` do sistema fica intacto |

As pastas do Node ficam com dono `circleci`, então `npm i -g` (Claude Code e TypeScript no dotfiles)
funciona sem sudo. Terraform e as dependências do Playwright ficam fora da imagem: o personal-notes
instala os dois no próprio job com sudo, e a versão do Terraform é fixada lá.

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| `image/Dockerfile` | `FROM circleci/runner-agent:machine-3`, versões em `ARG`, instalação da tabela acima |
| `image/use-node` | Helper que acrescenta `/opt/node/<versão>/bin` ao PATH via `$BASH_ENV` |
| `supervisor/slot.sh` | Laço de um slot: `docker run --rm` da imagem do runner, `trap` de TERM que para o filho |
| `compose.yaml` | Três serviços `slot-1..3` na imagem `docker:cli`, com o socket montado, `restart: unless-stopped` |
| `runner.env` | Referência `op://` do token e nomes; sem segredo, vai para o git |
| `scripts/build.ps1` | `docker build` da imagem `hyperius-runner:<data>` e `latest` |
| `scripts/up.ps1` | `op run --env-file runner.env -- docker compose up -d` |
| `scripts/down.ps1` | `docker compose down` e remoção dos containers de job que sobrarem |
| `scripts/status.ps1` | Slots, container de job ativo e últimas linhas do log |
| `tests/smoke.sh` | Roda dentro da imagem e falha se faltar uma ferramenta ou a versão divergir |
| `README.md` | Como subir, parar, atualizar a imagem e usar o runner num config |

Os scripts são PowerShell no Windows porque o `op` com a integração do 1Password desktop está lá.
O Docker Desktop guarda o token na configuração dos containers de supervisor (visível em
`docker inspect`); ele não aparece em arquivo nem no `ps`. Com o Docker Desktop iniciando no login,
os slots voltam sozinhos depois de um reboot.

## Uso nos projetos

Um job passa a rodar no runner trocando o executor por:

```yaml
machine: true
resource_class: alessandrocaetanob/hyperius
```

Jobs com `docker:` não rodam em machine runner. O job `windows` do vnforge continua na nuvem.
A troca nos três configs é trabalho de cada repositório e fica fora deste plano.

## Verificação

1. `scripts/build.ps1` termina sem erro.
2. `docker run --rm --entrypoint bash hyperius-runner tests/smoke.sh` passa: versões de git, zip,
   java 21, dotnet 10, pwsh 7.6.7, node 24.22.0, node 22.12.0 via `use-node`, python 3.12, `npm i -g`
   sem sudo.
3. `scripts/up.ps1` sobe três slots, e o CircleCI mostra `hyperius-1..3` conectados em Self-Hosted
   Runners. Este passo usa o token real e só roda com a sua confirmação.

## Riscos e pontos em aberto

- Não testei se o machine runner define `$BASH_ENV` em todo step; o `use-node` depende disso. Se não
  definir, o job usa `export PATH=/opt/node/22/bin:$PATH` no próprio step.
- O Playwright com `--with-deps` roda `apt-get` a cada job porque o container é novo; custa de 1 a 2
  minutos por job visual. Dá para mover as dependências para a imagem depois, fixando a versão do
  Playwright do personal-notes.
- O supervisor tem acesso total ao Docker Desktop pelo socket. Os containers de job não têm.
