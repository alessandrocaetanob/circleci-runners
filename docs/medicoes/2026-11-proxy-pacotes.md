# Medição do proxy de pacotes (T4, issue #6)

Data: 2026-11-24. Pergunta: vale construir um proxy local de pacotes para os jobs do hyperius, que começam sem cache e baixam npm e NuGet do zero?

## Decisão

| Gerenciador | Decisão | Número que decide |
|---|---|---|
| npm (personal-notes) | **No-go** | `npm ci` do `.app`: mediana 20,4 s direto contra 15,4 s pelo Verdaccio quente. Ganho de 5 s, do tamanho da oscilação entre as amostras diretas (18,9 a 23,2 s). |
| NuGet (vnforge) | **Go, depois do lockfile** | `dotnet restore VNForge.slnx`: mediana 54,0 s direto contra 14,4 s pelo BaGetter quente (menos 73%), com oscilação de 15 s no direto e 6 s no quente. |

O ganho real do NuGet no job é menor que os 40 s da medida. O log do job 1928 mostra restore de pelo menos 20 s, não de 54 s (seção "Restore de hoje"). Aplicando a razão quente/direto desta medida (0,27) a 20 s, o job economiza uns 15 s de 271 s; como os 20 s são um piso, esse valor é a estimativa baixa e o ganho real fica entre 15 s e os 40 s medidos. Nenhum dos dois foi medido no CI.

O BaGetter não é um espelho offline: com o nuget.org inalcançável o restore terminou, mas em 8 a 11 minutos contra 14 s (seção "O espelho de NuGet não é offline"). Ele acelera o restore, não protege contra queda do nuget.org.

## Como foi medido

- Cada amostra é um `docker run --rm` novo de `hyperius-runner:latest` com `--cpus 4 --memory 6g`, os limites dos jobs reais. O cache de npm (`~/.npm`) e o de NuGet (`~/.nuget/packages`) começam vazios.
- A cópia do projeto entra por bind mount somente leitura em `/src` e é copiada para o disco do container antes do cronômetro. Só o comando medido é cronometrado (`$EPOCHREALTIME` do bash antes e depois), então escrever `node_modules` e `obj` não passa pelo bind mount do Windows.
- Os sources são cópias de `HEAD` extraídas por `git archive`: personal-notes `fc0d500f` (só `.app`) e vnforge `f8e89466`. Os dois repos não foram tocados.
- Direto: container na rede `bridge` do Docker, com saída para a internet. Proxy: container na rede `proxypk-int` (`--internal`, sem saída), então todo byte veio do espelho.
- Os dois espelhos ficam na rede `proxypk-net` (com saída) e também em `proxypk-int`. Imagens fixadas: `verdaccio/verdaccio:7.1.2` (digest `sha256:4addf64c2fd5f86e963444e8a482d7cd20cd2243e01470d548bdb23d0cd609de`) e `bagetter/bagetter:1.6.5` (digest `sha256:ed12b9450c7fe97df7d18b0ade1e7737abbfc865807e0ff7d5f3535860266241`).
- Os espelhos rodam sem limite de CPU e de memória. Foi uma amostra por vez, nunca seis jobs ao mesmo tempo: a concorrência dos seis slots não foi medida.
- Ordem das amostras, intercalando os dois braços para que uma oscilação de rede não caia só num deles: npm D1, P-frio, P1, D2, P2, D3, P3; NuGet P-frio, P1, D1, P2, D2, P3, D3. "P-frio" é a primeira passada pelo proxy vazio (aquece o espelho).
- Antes de medir, `docker stats --no-stream` mostrou os seis slots em 0,00% de CPU e os outros containers em menos de 0,5%. Conferido de novo ao fim: igual.
- Rede e espelhos (`<cfg>` é um `config.yaml` do Verdaccio com o texto da seção npm):

```bash
docker network create proxypk-net
docker network create --internal proxypk-int
docker run -d --name proxypk-verdaccio --network proxypk-net -v "<cfg>:/verdaccio/conf/config.yaml:ro" verdaccio/verdaccio:7.1.2
docker run -d --name proxypk-bagetter --network proxypk-net -e ApiKey=<chave inventada> \
  -e Mirror__Enabled=true -e Mirror__PackageSource=https://api.nuget.org/v3/index.json bagetter/bagetter:1.6.5
docker network connect proxypk-int proxypk-verdaccio
docker network connect proxypk-int proxypk-bagetter
```

- Cada amostra é este `docker run`, com `<rede>` igual a `bridge` (direto) ou `proxypk-int` (proxy), `<fonte>` a cópia do projeto e `dentro.sh` o script cujos comandos estão abaixo (o script e as cópias ficaram no scratchpad da sessão e não vão para o repo):

```bash
docker run --rm --cpus 4 --memory 6g --network <rede> --entrypoint bash \
  -v "<fonte>:/src:ro" -v "<dir>/dentro.sh:/med/dentro.sh:ro" \
  hyperius-runner:latest /med/dentro.sh <npm|nuget> <direto|proxy|cache>
```

- Dentro do container, o que `dentro.sh` executa (a variante `cache` roda o mesmo comando uma vez antes, sem cronometrar, e apaga `obj/` no caso do NuGet; o `npm ci` já apaga o `node_modules`):

```bash
# preparo, fora do cronômetro
cp -r /src /home/circleci/w
# npm (personal-notes), Node 22 como nos jobs
eval "$(use-node 22)"; cd /home/circleci/w/.app
npm ci                                              # direto
npm ci --registry http://proxypk-verdaccio:4873/    # proxy
# NuGet (vnforge)
cd /home/circleci/w
dotnet restore VNForge.slnx                         # direto
# proxy: o mesmo comando, com este nuget.config ao lado da .slnx
#   <packageSources><clear />
#     <add key="espelho" value="http://proxypk-bagetter:8080/v3/index.json" allowInsecureConnections="true" />
#   </packageSources>
```

O `npm ci` de personal-notes vem de `.circleci/continue_config.yml` do próprio repo (`working_directory: .app`, passo `npm ci`). O `npm` do container é o 10.9.0 com Node 22.12.0; o SDK é o .NET 10.0.403.

## npm: Verdaccio 7.1.2

### Configuração

```yaml
storage: /verdaccio/storage/data
auth:
  htpasswd:
    file: /verdaccio/storage/htpasswd
    max_users: -1
uplinks:
  npmjs:
    url: https://registry.npmjs.org/
    maxage: 30m
packages:
  '**':
    access: $all
    proxy: npmjs
```

Fontes, lidas no Context7 (biblioteca `/websites/verdaccio`, páginas de verdaccio.org; o README de `/verdaccio/verdaccio` v6.11.3 confere o uso de `uplinks`/`packages`):

- `max_users: -1` recusa todo cadastro, inclusive `npm adduser` (https://www.verdaccio.org/docs/user-registration/ e /docs/authentication/). A flag `createUser` só governa o cadastro pela web, então não basta.
- Lista `publish` vazia ou ausente não casa com ninguém (https://www.verdaccio.org/docs/packages/ e /docs/protect-your-dependencies/, receita "read-only mirror"). Por isso `publish` e `unpublish` não aparecem na configuração.
- `maxage` do uplink é o tempo em que o metadado fica em cache antes de ser revalidado; o padrão é 2 min (https://www.verdaccio.org/docs/caching/). Usei 30 min.

A documentação do site não é versionada; ela cita recursos do 7.x. A versão da imagem foi fixada em 7.1.2 (a `latest` de 2026-11-18) e o comportamento abaixo foi confirmado nela.

### Publicação e cadastro recusados

Comando (dentro de um container de `hyperius-runner:latest` na rede `proxypk-int`):

```bash
R=http://proxypk-verdaccio:4873
curl -sS -X PUT -H 'content-type: application/json' -d '{"name":"teste","password":"senha-de-teste-123","email":"t@e.st","type":"user"}' $R/-/user/org.couchdb.user:teste
npm publish --registry $R                      # pacote proxypk-teste-sem-escopo, sem credencial
npm publish --registry $R                      # pacote @proxypk/teste, com .npmrc de token qualquer
curl -sS -o /dev/null -w "%{http_code}\n" $R/proxypk-teste-sem-escopo
```

Resultado:

| Ação | Resposta |
|---|---|
| leitura de `left-pad` | 200 (veio do npmjs) |
| cadastro (`PUT /-/user/...`, o que o `npm adduser` envia) | 409 `user registration disabled` |
| `npm publish` sem credencial | `npm error code ENEEDAUTH` (o cliente npm recusa antes de enviar; não é resposta do servidor) |
| `npm publish` com token inventado, pacote com escopo | `npm error code E401` |
| `GET /proxypk-teste-sem-escopo` depois | 404 (nada foi gravado) |

Como nenhum usuário pode existir, a publicação por um usuário logado de verdade não foi exercitada: a recusa provada é para anônimo e para token inválido.

### Tempos do `npm ci` do `.app` (81 pacotes adicionados)

| Amostra | Direto (s) | Proxy (s) |
|---|---|---|
| 1 | 20,36 | 18,92 |
| 2 | 23,21 | 15,43 |
| 3 | 18,91 | 14,60 |
| **mediana** | **20,36** | **15,43** |
| média | 20,83 | 16,32 |

Referências, mesmo método:

| Medida | Segundos |
|---|---|
| proxy frio (primeira passada, enche o espelho) | 23,02 |
| proxy quente com a saída do Verdaccio cortada (`docker network disconnect proxypk-net proxypk-verdaccio`) | 16,25 |
| cache local do npm quente (`npm ci` duas vezes no mesmo container, cronometrada a segunda), 3 amostras | 12,63 / 8,50 / 6,80 |

A passada com a saída cortada funcionou, então o `npm` reescreveu as URLs `registry.npmjs.org` do `package-lock.json` para o registry configurado (`replace-registry-host`, que `npm config get replace-registry-host` mostra como `npmjs` na imagem) e nada contornou o Verdaccio. O espelho guardou 212 MB para este lockfile.

Leitura: o proxy tira 5 s de um `npm ci` de 20 s. O que sobra é extração e scripts de instalação, que o proxy não toca. Um cache local de `~/.npm` chega a 8,5 s de mediana, mas depende de manter estado entre jobs, que é outro desenho.

## NuGet: BaGetter 1.6.5

### Escolha e fonte

BaGetter tem `Mirror` (read-through): ao pedir um pacote que não tem, indexa e baixa do nuget.org. Fontes:

- https://www.bagetter.com/docs/Import/nugetorg ("Mirroring": o primeiro `Newtonsoft.Json` pedido é indexado do nuget.org, "read-through caching").
- https://www.bagetter.com/docs/configuration (chaves `Mirror.Enabled` e `Mirror.PackageSource`, o service index do upstream).
- O BaGet original anuncia o uso como acelerador de restore e para "restores in offline scenarios" (https://loic-sharma.github.io/BaGet/configuration). A medida abaixo não confirma o segundo uso.

Alternativa considerada, não medida: Sonatype Nexus Repository Community Edition tem repositório proxy de NuGet (https://help.sonatype.com/en/nuget-repositories.html), mas é um serviço bem mais pesado. Só mediria se o BaGetter falhasse.

Container: `docker run -d --name proxypk-bagetter --network proxypk-net -e ApiKey=<chave inventada> -e Mirror__Enabled=true -e Mirror__PackageSource=https://api.nuget.org/v3/index.json bagetter/bagetter:1.6.5`. O `ApiKey` fecha a publicação (a recusa de push no BaGetter não foi testada; a leitura é anônima, em rede interna). O banco é SQLite e os pacotes ficam em `/data`, que cresceu para 421 MB com este restore.

### Tempos do `dotnet restore VNForge.slnx` (20 projetos restaurados, 0 erros)

| Amostra | Direto (s) | Proxy (s) |
|---|---|---|
| 1 | 56,92 | 14,36 |
| 2 | 53,96 | 18,86 |
| 3 | 41,32 | 12,64 |
| **mediana** | **53,96** | **14,36** |
| média | 50,73 | 15,29 |

Referências, mesmo método:

| Medida | Segundos |
|---|---|
| proxy frio (primeira passada) | 54,56 |
| proxy quente com a saída do BaGetter cortada (`docker network disconnect proxypk-net proxypk-bagetter`) | **475,95** e **647,47** (rc 0 e 20 projetos restaurados nas duas; ver a nota abaixo) |
| `~/.nuget/packages` quente, `obj/` apagado (restore duas vezes no mesmo container, cronometrada a segunda), 3 amostras | 2,52 / 2,89 / 3,50 |

### O espelho de NuGet não é offline

Com o nuget.org inalcançável o restore ainda terminou com sucesso, porque os pacotes estavam no espelho, mas levou entre 8 e 11 minutos contra 14 s. Foram duas execuções, e as duas se sobrepuseram: a primeira passou de 300 s, o comando foi para segundo plano e seguiu rodando, e a segunda começou por cima dela. Logo 475,95 s e 647,47 s não são amostras limpas; o que vale é a ordem de grandeza (minutos, não segundos). O log do BaGetter mostra `Failed to mirror <pacote>'s upstream versions` para cada pacote: a cada pedido ele consulta o upstream para a lista de versões e espera o erro. O espelho precisa de acesso ao nuget.org em cada restore; ele evita baixar os `.nupkg` de novo, não evita a dependência do nuget.org.

### Restore de hoje, no job 1928 do vnforge

Comando:

```bash
curl -fsS https://circleci.com/api/v1.1/project/github/alessandrocaetanob/vnforge/1928   # steps, output_url de cada passo
curl -fsS "<output_url do passo Build>"                                                   # JSON com a mensagem do log
```

O job rodou no `alessandrocaetanob/hyperius` (campo `picard.resource_class`), sem passo de `restore_cache` (a configuração só restaura o cache de NuGet no executor `nuvem`). O restore é o implícito do `dotnet build VNForge.slnx --configuration Release --no-incremental`.

- Passo Build: 110,9 s (API); `Time Elapsed 00:01:49.91` no log do MSBuild. Job inteiro: 271,2 s.
- O log não tem horário por linha e os projetos restauram em paralelo. O maior `Restored ... (in 20.08 sec)` é `tools/VNForge.Capturas`; os seguintes são 12,76 s (`Installer.Tests`) e 12,45 s (`App`). Por isso o restore leva **pelo menos 20 s** (cerca de 18% do Build) e não dá para somar as linhas.
- Das 20 linhas `Restored`, 12 levaram menos de 1 s e 8 levaram de 5,85 a 20,08 s.

Não consegui explicar por que o `dotnet restore` direto neste PC (40 a 57 s) é duas a três vezes mais lento que o do CI (20 s ou pouco mais). Hipóteses que não testei: a rede, e a pasta `~/.nuget/packages` do slot já ter pacotes de jobs anteriores (a issue diz que cada job do hyperius começa sem cache). Por isso o ganho no job real fica entre os 15 s extrapolados e os 40 s medidos aqui.

## O que o vnforge precisa antes do proxy

Hoje não existe nenhum `packages.lock.json` (0 arquivos na cópia de `HEAD`). Sem ele, o restore é solto: o espelho pode devolver uma versão diferente da de ontem sem que nada acuse, e não há chave estável para um cache.

1. Ligar o lockfile em todos os projetos: `<RestorePackagesWithLockFile>true</RestorePackagesWithLockFile>` no `Directory.Build.props` (o vnforge já usa `Directory.Packages.props` para as versões centrais), rodar um `dotnet restore VNForge.slnx` e commitar os 20 `packages.lock.json`. Fonte: https://learn.microsoft.com/nuget/consume-packages/package-references-in-project-files#locking-dependencies.
2. Travar o restore no CI: `dotnet restore VNForge.slnx --locked-mode`, ou `-p:RestoreLockedMode=true` no `dotnet build`. Em modo travado o restore usa exatamente os pacotes do lockfile ou falha se as dependências mudaram (mesma fonte). Esse passo roda antes do `dotnet build ... --no-incremental` do job.
3. Fixar o SDK. O `global.json` tem `"rollForward": "latestFeature"`, e a mesma página da Microsoft avisa que pacotes implícitos do SDK mudam de versão com ele e quebram o restore travado; ela recomenda `rollForward: disable`.
4. Um `nuget.config` (no repo ou no runner) com `<clear />` e só o espelho, com `allowInsecureConnections="true"` por ser HTTP dentro da rede do Docker. Sem o `<clear />` o NuGet cai de volta no nuget.org e a medida não vale.
5. Não verificado: se o modo travado aceita o hash dos `.nupkg` servidos pelo BaGetter (devem ser os mesmos bytes do nuget.org, mas o restore travado não foi rodado aqui, porque não há lockfile).

## O que não foi medido

- Seis jobs ao mesmo tempo contra um espelho só, e o custo de disco ao longo de semanas (212 MB de npm e 421 MB de NuGet para um lockfile de cada).
- Recusa de publicação no BaGetter, e persistência do espelho depois de reiniciar o container.
- O tempo do job do vnforge ou do personal-notes de ponta a ponta com o proxy; as medidas são do comando isolado.
