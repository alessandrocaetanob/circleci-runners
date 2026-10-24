FROM circleci/runner-agent:machine-3

ARG POWERSHELL_VERSION=7.6.7
ARG POWERSHELL_SHA256=868c575f0822b2deed054c1c3c464a9d4b841f67e153369147fb6ace3545c8b2
ARG NODE_LATEST_VERSION=24.22.0
ARG NODE_LATEST_SHA256=cc2f601cee82d9a5a233302fe307abc600727035fd7d2c3a3571755989e95008
ARG NODE_LTS_VERSION=22.12.0
ARG NODE_LTS_SHA256=22982235e1b71fa8850f82edd09cdae7e3f32df1764a9ec298c72d25ef2c164f
ARG DOTNET_CHANNEL=10.0

USER root
ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Etc/UTC \
    LANG=C.UTF-8

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates curl wget jq unzip zip xz-utils tar rsync file \
      git git-lfs openssh-client \
      build-essential pkg-config \
      gnupg software-properties-common locales tzdata \
      libicu70 libssl3 zlib1g libgcc-s1 libstdc++6 \
 && git lfs install --system \
 && rm -rf /var/lib/apt/lists/*

# O python3 do sistema (/usr/bin) fica intacto: o apt do Ubuntu depende dele.
RUN add-apt-repository -y ppa:deadsnakes/ppa \
 && apt-get update \
 && apt-get install -y --no-install-recommends python3.12 python3.12-venv python3.12-dev \
 && ln -sf /usr/bin/python3.12 /usr/local/bin/python3 \
 && ln -sf /usr/bin/python3.12 /usr/local/bin/python \
 && rm -rf /var/lib/apt/lists/*

RUN apt-get update \
 && apt-get install -y --no-install-recommends openjdk-21-jdk-headless \
 && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL -o /tmp/pwsh.deb \
      "https://github.com/PowerShell/PowerShell/releases/download/v${POWERSHELL_VERSION}/powershell_${POWERSHELL_VERSION}-1.deb_amd64.deb" \
 && echo "${POWERSHELL_SHA256}  /tmp/pwsh.deb" | sha256sum -c - \
 && apt-get update \
 && apt-get install -y --no-install-recommends /tmp/pwsh.deb \
 && rm -rf /tmp/pwsh.deb /var/lib/apt/lists/*

RUN curl -fsSL -o /tmp/dotnet-install.sh https://dot.net/v1/dotnet-install.sh \
 && bash /tmp/dotnet-install.sh --channel "${DOTNET_CHANNEL}" --install-dir /usr/share/dotnet \
 && ln -sf /usr/share/dotnet/dotnet /usr/local/bin/dotnet \
 && rm -f /tmp/dotnet-install.sh

RUN set -eux; \
    install_node() { \
      version="$1"; sha="$2"; major="${version%%.*}"; \
      curl -fsSL -o /tmp/node.tar.xz "https://nodejs.org/dist/v${version}/node-v${version}-linux-x64.tar.xz"; \
      echo "${sha}  /tmp/node.tar.xz" | sha256sum -c -; \
      mkdir -p "/opt/node/${major}"; \
      tar -xJf /tmp/node.tar.xz -C "/opt/node/${major}" --strip-components=1; \
      rm -f /tmp/node.tar.xz; \
    }; \
    install_node "${NODE_LATEST_VERSION}" "${NODE_LATEST_SHA256}"; \
    install_node "${NODE_LTS_VERSION}" "${NODE_LTS_SHA256}"; \
    chown -R circleci:circleci /opt/node

COPY use-node /usr/local/bin/use-node

# Shells de login (o CircleCI usa bash --login) refazem o PATH em /etc/profile,
# então o ENV do Docker sozinho não basta.
RUN chmod 0755 /usr/local/bin/use-node \
 && printf '%s\n' \
      'export DOTNET_ROOT=/usr/share/dotnet' \
      'export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64' \
      'export DOTNET_CLI_TELEMETRY_OPTOUT=1' \
      'export DOTNET_NOLOGO=1' \
      'export PATH=/opt/node/24/bin:/usr/local/bin:$PATH' \
    > /etc/profile.d/hyperius.sh

ENV DOTNET_ROOT=/usr/share/dotnet \
    JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64 \
    DOTNET_CLI_TELEMETRY_OPTOUT=1 \
    DOTNET_NOLOGO=1 \
    PATH=/opt/node/24/bin:/usr/local/bin:${PATH}

USER circleci
