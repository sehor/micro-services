# 多阶段Docker构建 - Auth-Supabase服务
# 构建阶段：安装依赖和构建应用
FROM python:3.11-slim as builder

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 升级pip并安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --user -r requirements.txt

# 生产运行阶段：最小化镜像
FROM python:3.11-slim as production

# 创建非root用户
RUN groupadd -r appuser && useradd -r -g appuser appuser

# 设置工作目录
WORKDIR /app

# 安装运行时依赖
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# 从构建阶段复制Python包
COPY --from=builder /root/.local /home/appuser/.local

# 复制应用代码
COPY app/ ./app/
COPY run.py .

# 设置Python路径
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 创建日志目录
RUN mkdir -p /app/logs && chown -R appuser:appuser /app

# 切换到非root用户
USER appuser

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 暴露端口
EXPOSE 8000

# 启动命令 - 使用gunicorn + uvicorn workers
CMD ["gunicorn", "app.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "4", \
     "--bind", "0.0.0.0:8000", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "info", \
     "--timeout", "120", \
     "--keep-alive", "5", \
     "--max-requests", "1000", \
     "--max-requests-jitter", "100", \
     "--preload"]

# 开发阶段：用于本地开发
FROM production as development

# 切换回root用户安装开发依赖
USER root

# 安装开发依赖
RUN pip install --no-cache-dir \
    pytest \
    pytest-asyncio \
    pytest-cov \
    pytest-mock \
    httpx \
    ruff \
    mypy \
    bandit \
    pip-audit

# 切换回非root用户
USER appuser

# 开发模式启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]