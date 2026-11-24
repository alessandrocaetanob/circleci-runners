# CI mais rápido: pool de 16 CPUs, Sonar na imagem e proxy de pacotes

Data: 2026-11-24 · Repo: circleci-runners · Tópico do handoff: `maratona-ci-circleci-runners`

Ondas: 3

## Contexto

A exportação de uso do CircleCI de 24/10 a 23/11 mostrou o vnforge 2,4x a 2,9x mais lento com 3 ou mais jobs ao lado na mesma semana (pool com teto de 12 CPUs, 15 h com os 6 slots ocupados) e todo job baixando pacotes e ferramentas do zero. Esta maratona sobe o teto de CPU para 16, põe as ferramentas do Sonar na imagem, guarda os scripts que mediram isso e mede o proxy de pacotes antes de construí-lo. As maratonas do dotfiles, do vnforge e do personal-notes dependem desta. Plano completo e decisões do Alessandro: `C:\Users\aless\.claude\plans\quero-que-pesquise-bastente-clever-aho-of-6fbedb28-d0dd-4002-bf30-c404727b69ac.md`.

## Tarefas

- [x] **T1 · Teto do pool em 16 CPUs**
  - Issue: #3
  - Arquivos: `compose.yaml`, `tests/pool.sh`, `README.md`
  - Nível: leve
  - Testes: nenhum
  - Prova: `bash tests/pool.sh` com os slots ociosos (`scripts/status.ps1` antes), soma dos 6 containers dentro da faixa nova
  - Pronto:
    - [x] `POOL_CPUS` padrão 16 no `compose.yaml`; `POOL_MEMORY` continua `24g`, sem `.wslconfig` (a VM do Docker tem 31,3 GB e nenhum dado mostra falta de memória)
      Evidência: commit 24d1eb6 muda o padrão para 16 em `compose.yaml`, `supervisor/slot.sh` e `supervisor/pool.sh`; `POOL_MEMORY` segue `24g`; o reviewer conferiu `docker info` com NCPU=24 e 31,3 GiB
    - [x] `tests/pool.sh` sobe 6 containers com 4 CPUs ocupadas cada e aceita a soma entre 1.450% e 1.650%; o README diz a faixa nova e "Com os seis slots ocupados, os jobs dividem 16 CPUs"
      Evidência: a faixa passou a sair de `POOL_CPUS` (90% a 105%, 1440 a 1680 com 16), com média de 3 amostras, depois que uma leitura única deu 1716% por ruído; 10 rodadas: 1543, 1501, 1474, 1528, 1610, 1642, 1583, 1577, 1608, 1563; README atualizado (re-revisão limpa do reviewer)
    - [x] o PR fecha a issue
      Evidência: https://github.com/alessandrocaetanob/circleci-runners/pull/7 (Closes #3, mergeado em 24d1eb6)
- [x] **T2 · Scripts de agregação do uso do CircleCI**
  - Issue: #4
  - Arquivos: `scripts/uso/agregar.py` (novo), `scripts/uso/semanal.py` (novo), `README.md`
  - Testes: tester · até 4 (motivo: sem `USO_CSV_DIR` nenhum teste cobria a regra de sobreposição do `semanal.py`; o caso sintético 4 pega faixa ou semana errada, job de outro projeto ignorado e job não `success` contado)
  - Exemplos:
    - exportação de 24/10 a 23/11 → total de 63.343 créditos, 44.379 de cômputo, 18.255 de rede (fonte: exportação `01c8a143-0525-c5f6-001b-7a8366cb4f96`, CSVs em `H:\TMP\claude\5e0e1b5787328ac3\6fbedb28-d0dd-4002-bf30-c404727b69ac\scratchpad\usage`)
    - linha com `\N` em `JOB_RUN_SECONDS` → conta como 0 e não derruba o script (fonte: mesma exportação, 76 linhas do vnforge `linux` sem executor)
    - mesma exportação, vnforge `linux` no runner, W44 → mediana de 378 s sem job ao lado e 1.086 s com 3 ou mais (fonte: medição desta sessão)
  - Prova: `python -I scripts/uso/agregar.py <pasta dos CSVs>` e os testes do tester
  - Pronto:
    - [x] os dois scripts partem de `agg.py` e `weekly.py` em `H:\TMP\claude\5e0e1b5787328ac3\6fbedb28-d0dd-4002-bf30-c404727b69ac\scratchpad\scripts`, recebem a pasta dos CSVs como argumento e imprimem os totais por projeto e job e a mediana por número de jobs ao lado
      Evidência: `scripts/uso/agregar.py` e `scripts/uso/semanal.py` em 48e0832; `python -I -m unittest discover -s tests/uso -v` com `USO_CSV_DIR` deu OK em 4 testes (totais 63343, linha dotfiles 562/14558, W44 378 e 1086); vermelho pela asserção no esboço 8a576e7; 12 de 13 mutações vermelhas na revisão
    - [x] o README diz como baixar a exportação (`download_usage_data` do MCP do CircleCI, janela de até 31 dias) e rodar os scripts
      Evidência: seção "Medir o uso do CircleCI" do README em 48e0832; a janela de 31 dias vem da descrição da ferramenta `download_usage_data`
    - [x] o PR fecha a issue
      Evidência: https://github.com/alessandrocaetanob/circleci-runners/pull/8 (Closes #4, mergeado em 48e0832)
  - Depende de: T1
- [x] **T3 · Ferramentas do Sonar na imagem**
  - Issue: #5
  - Arquivos: `image/Dockerfile`, `tests/smoke.sh`, `README.md`
  - Testes: tester · até 2
  - Exemplos:
    - `dotnet-sonarscanner --version` no PATH do job → 11.3.0 (fonte: `.circleci/config.yml` do vnforge, `dotnet tool install ... --version 11.3.0`)
    - `dotnet-coverage --version` → 18.11.2 (fonte: mesma linha do config do vnforge)
    - o usuário `circleci` tenta gravar na pasta das ferramentas → permissão negada (fonte: comentário do vnforge sobre binário deixado por outro job receber o `SONAR_TOKEN`)
  - Prova: `pwsh scripts/build.ps1` (build e smoke)
  - Pronto:
    - [x] as duas ferramentas ficam num `--tool-path` de dono root no PATH, com versão em `ARG`, numa camada depois do .NET
      Evidência: d5e3a8f; `ARG` SONARSCANNER_VERSION e DOTNET_COVERAGE_VERSION, `/opt/dotnet-tools` root:root 755 (reviewer: `find ! -user root` vazio), PATH pelo `ENV` e por `/etc/profile.d/hyperius.sh`; como `circleci`, `dotnet-sonarscanner --version` e `begin` rodaram, `dotnet-coverage collect` gerou o XML
    - [x] o smoke confere versões e que a pasta não aceita escrita do `circleci`
      Evidência: casos `sonar-tools` e `sonar-tools-readonly` (300dead) vermelhos pela asserção na imagem anterior; `pwsh scripts/build.ps1 -Image hyperius-runner-teste` com "Todas as verificações passaram." (builder e reviewer); com sudo o `circleci` ainda escreve, o que o README diz
    - [x] a tabela "O que a imagem tem" do README lista as duas
      Evidência: README em d5e3a8f com as duas linhas e o parágrafo sobre a pasta só leitura sem sudo
    - [x] o PR fecha a issue
      Evidência: https://github.com/alessandrocaetanob/circleci-runners/pull/10 (Closes #5, mergeado em d5e3a8f)
  - Depende de: T2
- [x] **T4 · Medição do proxy de pacotes (go/no-go)**
  - Issue: #6
  - Arquivos: `docs/medicoes/2026-11-proxy-pacotes.md` (novo)
  - Nível: padrao
  - Testes: nenhum
  - Prova: o relatório com os números e o comando de cada medida
  - Pronto:
    - [x] Verdaccio (versão fixada, configuração confirmada no Context7) servindo o npm com publicação e cadastro recusados; `npm ci` do `.app` do personal-notes (cópia por `git archive`) medido 3 vezes direto do registry e 3 pelo proxy quente, dentro da imagem `hyperius-runner:latest`
      Evidência: relatório em b1c41af; Verdaccio 7.1.2 por digest, cadastro 409 e publicação recusada sem credencial (recusa para usuário autenticado só pela documentação: critério parcial, declarado no relatório); `npm ci` mediana 20,4 s direto e 15,4 s pelo proxy quente
    - [x] um espelho de NuGet escolhido com fonte citada (BaGetter ou outro), e o `dotnet restore VNForge.slnx` medido do mesmo jeito; o tempo de restore de hoje lido no log do Build do job 1928 do vnforge (API v1.1 pública)
      Evidência: BaGetter 1.6.5 em modo Mirror (bagetter.com/docs/configuration); restore mediana 54,0 s direto e 14,4 s quente; job 1928: restore de pelo menos 20,08 s, Build 110,9 s, job 271,2 s (conferido pelo reviewer na API)
    - [x] o relatório fecha com go ou no-go por gerenciador e o que o vnforge precisa antes (lockfile `packages.lock.json` com restore travado, que hoje não existe)
      Evidência: critério único (10% do job ou 30 s): npm no-go, NuGet no-go agora (6 a 15 s estimados no CI); lockfile com `RestorePackagesWithLockFile`, `--locked-mode` e `rollForward: disable` recomendado à parte; re-revisão do reviewer sem pendência
    - [x] o PR fecha a issue
      Evidência: https://github.com/alessandrocaetanob/circleci-runners/pull/9 (Closes #6, mergeado em b1c41af)

## Condição do /goal

```
/goal todas as tarefas de docs/plans/2026-11-24-ci-circleci-runners.md estão [x] com PR mergeado, ou uma tarefa falhou duas vezes (anotada no handoff maratona-ci-circleci-runners), ou passaram 150 turnos
```

## Progresso

- 2026-11-24 · T1 · PR #7 · mergeado (faixa do `tests/pool.sh` derivada de `POOL_CPUS` depois da revisão)
- 2026-11-24 · T2 · PR #8 · mergeado (UTF-8 no stdout e as duas formas de nulo depois da revisão)
- 2026-11-24 · T4 · PR #9 · mergeado (veredito do NuGet passou de go a no-go na revisão)
- 2026-11-24 · T3 · PR #10 · mergeado (texto sobre o sudo do `circleci` corrigido na revisão)

## Fora da corrida

- Aplicar o teto novo no PC (`scripts/down.ps1` com os slots ociosos e `scripts/up.ps1`, com o token do 1Password): é do Alessandro, depois do merge da T1.
- Proxy de pacotes: a T4 deu no-go para npm e NuGet; só volta com uma medida do restore dentro de um job real. O lockfile do NuGet no vnforge (V0) segue por reprodutibilidade, em plano próprio.
- Auto-cancel de workflows redundantes nos três projetos e conferir que o vnforge (público) não constrói PR de fork: configuração na UI do CircleCI, do Alessandro.
- Maratonas do dotfiles (D1 a D3), vnforge (V0, V1) e personal-notes (P1, P2): planos próprios em cada repo, depois desta.
