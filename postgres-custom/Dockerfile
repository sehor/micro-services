# 使用与您当前版本匹配的官方 Postgres 镜像作为基础
FROM postgres:17-bookworm

# 构建期代理参数（可选）
# 函数级注释：为 apt/git 设置代理，保证在受限网络下可用
ARG HTTP_PROXY=http://host.docker.internal:33210
ARG HTTPS_PROXY=http://host.docker.internal:33210
ENV HTTP_PROXY=${HTTP_PROXY}
ENV HTTPS_PROXY=${HTTPS_PROXY}

# 使用 Debian 的 apt-get 安装构建依赖并构建安装 pgvector
# 函数级注释：安装必要工具、编译并安装 pgvector，然后清理依赖与缓存
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    build-essential \
    postgresql-server-dev-17 \
    git \
 && git config --global http.proxy "${HTTP_PROXY}" \
 && git config --global https.proxy "${HTTPS_PROXY}" \
 && git clone --depth 1 --branch v0.8.1 https://github.com/pgvector/pgvector.git \
 && cd pgvector \
 && make \
 && make install \
 && cd .. \
 && rm -rf pgvector \
 && apt-get purge -y git \
 && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*