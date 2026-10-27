# Seis slots com teto de metade da máquina

Data: 2026-10-27. Estado: aguardando aprovação.

## Objetivo

Passar de 3 para 6 slots no resource class `alessandrocaetanob/hyperius`, com o pool inteiro limitado a cerca de
metade da CPU e da RAM do PC, e garantir que os jobs do personal-notes e do vnforge rodem nele sem ajuste manual.

## Situação medida em 2026-10-27

| Item | Valor | Origem |
|---|---|---|
| Host | Ryzen 9 3900XT, 12 núcleos e 24 threads, 63,9 GB | `Win32_Processor`, `Win32_ComputerSystem` |
| VM do Docker Desktop | 24 CPUs, 31,3 GB (padrão do WSL2, sem `.wslconfig`) | `docker info` |
| Limite por job hoje | 8 CPUs e 10 GB, sem teto para o conjunto | `compose.yaml` |
| Pior caso hoje | 3 jobs × 8 CPUs = 24 CPUs, a máquina inteira | conta sobre o limite acima |
| Job Playwright (visual, lume) | pico de 3,1 a 3,6 GB (com cache de página) e até 5,8 CPUs; 6,2 CPUs somando os 3 slots | `memory.peak` do cgroup e `docker stats`, amostrados durante o pipeline do PR 454 |
| Jobs Node e Python leves | 0,3 a 0,9 GB, 1 a 1,3 CPUs | mesma amostragem |
| Pipeline do personal-notes | setup + até 7 workflows em paralelo (companion, pytest, lume-plugin, lume, visual, workers, infra) | `list_run_workflows` do run `dd0ca024` |

O vnforge já roda o job `linux` no hyperius e os seis últimos pipelines passaram. O personal-notes está migrando no
PR [alessandrocaetanob/personal-notes#454](https://github.com/alessandrocaetanob/personal-notes/pull/454); com 3 slots,
os 7 workflows de um pipeline completo ficam em fila.

O primeiro pipeline do PR 454 falhou porque o `setup.sh` ficou 5 minutos parado num `git fetch` por SSH: a imagem não
tem as chaves do github.com no `known_hosts`, e o ssh esperou a confirmação da chave. O step `checkout` do CircleCI grava
as chaves só num diretório temporário dele. O PR contornou no próprio repositório; o lugar certo é a imagem.

## Decisões

| Tema | Escolha | Origem |
|---|---|---|
| Slots | 6, `hyperius-1` a `hyperius-6` | pedido do Alessandro |
| Teto do conjunto | 12 CPUs e 24 GB num cgroup pai `/hyperius`, com `cpu.max` e `memory.max` | teste abaixo |
| Limite por job | 4 CPUs, 6 GB, `/dev/shm` de 1 GB | dobro do pico do Playwright em memória; 4 CPUs deixa um job sozinho rápido |
| Imagem | chaves do github.com no `/etc/ssh/ssh_known_hosts`; dependências de sistema e Chromium do Playwright 1.64.1 | falha do PR 454; versão do `.app/package-lock.json` do personal-notes |

Com o pool cheio, os 6 jobs dividem 12 CPUs (2 cada em média). Com 1 ou 2 jobs, cada um usa até 4. A memória somada
pode passar de 24 GB só se mais de quatro jobs chegarem perto dos 6 GB ao mesmo tempo; nesse caso o kernel recupera
cache de página e, em último caso, mata um processo de job dentro do cgroup `/hyperius`. A VM do Docker e os outros
containers (SonarQube MCP) ficam fora do teto e com folga de cerca de 7 GB.

A alternativa de limitar a VM inteira no `.wslconfig` (`processors=12`, `memory=32GB`) foi descartada: ela vale para
todo o WSL e todo o Docker Desktop, não só para os runners, e exige `wsl --shutdown` a cada ajuste.

### Teste do cgroup pai

Feito em 2026-10-27 no Docker Desktop 29.9.2 (cgroup v2, driver cgroupfs, kernel 6.18.54.1-microsoft-standard-WSL2).
A raiz já habilita `cpu` e `memory` no `cgroup.subtree_control`. Um cgroup `/hyperius-spike` com `cpu.max` de 2 CPUs
recebeu dois containers `--cpus 2 --cgroup-parent=/hyperius-spike`, cada um com dois `yes`: cada container ficou em
97% a 101%, 200% no total, com `nr_throttled` subindo no pai. O cgroup de teste foi removido.

O teste mostrou um risco: sem o cgroup criado antes, o `docker run --cgroup-parent` cria o diretório sozinho e sem
limite. Depois de reiniciar o Docker Desktop a VM volta sem `/hyperius`, e os slots sobem pelo `restart: unless-stopped`
sem passar pelo compose. Por isso quem garante o cgroup é o `slot.sh`, antes de cada `docker run`, e não um serviço de
inicialização do compose.

## Mudanças

| Arquivo | Mudança |
|---|---|
| `supervisor/slot.sh` | Antes de cada job, cria `/hyperius` se faltar e grava `cpu.max` e `memory.max` a partir de `POOL_CPUS` e `POOL_MEMORY`, por um container auxiliar `--privileged --cgroupns=host`; confere os valores lidos de volta e não sobe o runner se não baterem. O `docker run` do job ganha `--cgroup-parent=/hyperius`. |
| `compose.yaml` | Serviços `slot-4` a `slot-6`; padrões `JOB_CPUS=4`, `JOB_MEMORY=6g`, `POOL_CPUS=12`, `POOL_MEMORY=24g`. |
| `image/ssh_known_hosts` | As três chaves do github.com (ed25519, ecdsa, rsa), copiadas de `api.github.com/meta` e conferidas contra as impressões publicadas em docs.github.com ("GitHub's SSH key fingerprints"). |
| `image/Dockerfile` | Copia o `ssh_known_hosts` para `/etc/ssh/`. Instala as dependências de sistema do Chromium com `npx playwright@1.64.1 install-deps chromium` e o Chromium em `/opt/ms-playwright` (`PLAYWRIGHT_BROWSERS_PATH`), com dono `circleci`, para outra versão do Playwright ainda conseguir baixar o seu. |
| `tests/smoke.sh` | `ssh-keygen -F github.com` no arquivo global, Chromium do Playwright 1.64.1 abrindo `about:blank` headless. |
| `tests/pool.sh` | Novo. Sobe 6 containers ocupando 4 CPUs cada sob `/hyperius` e falha se a soma passar de 1250% ou ficar abaixo de 1100%. |
| `scripts/status.ps1` | Mostra o uso do cgroup `/hyperius`: `cpu.max`, `memory.current` e `memory.max`. |
| `README.md` | Seis slots, limites novos, teto do conjunto, Playwright na imagem. |

Os dois `apt-get` do Playwright entram numa camada própria, depois do Node, para uma troca de versão não refazer as
camadas do .NET e do Java.

## O que o PR 454 do personal-notes precisa saber

Fica fora deste repositório, mas a imagem nova muda o que vale a pena no config de lá:

- `npx playwright install --with-deps chromium` pode virar `npx playwright install chromium` no hyperius: as dependências
  já estão na imagem, e o `--with-deps` roda `apt-get update` a cada job.
- Os `restore_cache` e `save_cache` do `~/.npm` e do `~/.cache/ms-playwright` contam como tráfego de rede no runner,
  como já anota o config do vnforge. No hyperius o Chromium vem da imagem, então o cache do Playwright sai.
- O contorno do `known_hosts` no `setup.sh` deixa de ser necessário depois do build da imagem nova.

## Verificação

1. `scripts/build.ps1` termina e o smoke test passa, incluindo `known_hosts` e o Chromium.
2. `tests/pool.sh` mostra a soma entre 1100% e 1250% com 6 containers.
3. `scripts/down.ps1` com os slots ociosos e `scripts/up.ps1`; o CircleCI lista `hyperius-1` a `hyperius-6`. Usa o
   token real e só roda com confirmação do Alessandro.
4. Reiniciar o Docker Desktop e conferir no `status.ps1` que `/hyperius` voltou com 12 CPUs e 24 GB antes do primeiro job.
5. Um pipeline completo do personal-notes (parâmetro `rodar-tudo`) e um do vnforge passam, com `status.ps1` amostrado
   durante a execução: soma de CPU perto de 1200% no pico e nenhum OOM no `docker events`.

## Riscos e pontos em aberto

- A memória do job do vnforge (build .NET com SonarScanner) não foi medida; os pipelines dele não rodaram durante a
  amostragem. Se passar de 6 GB, o passo 5 mostra e o `JOB_MEMORY` sobe.
- O container auxiliar do `slot.sh` é privilegiado. O supervisor já tem o socket do Docker, que dá o mesmo poder, então
  o risco não muda; o container de job continua sem socket e sem privilégio.
- Os 24 GB do teto ficam a 7 GB do total da VM. Se o Alessandro rodar outras cargas pesadas no Docker ao mesmo tempo,
  a VM inteira pode faltar memória antes do teto do pool atuar.
- Cache local compartilhado entre jobs (npm, NuGet) aceleraria `npm ci` e `dotnet restore`, mas quebra o isolamento
  por job decidido no plano de 2026-10-24. Fica para depois, com o tempo dessas etapas medido nos seis slots.
