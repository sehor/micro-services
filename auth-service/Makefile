# Makefile for Auth-Supabase Project
# 使用方法: make <target>

.PHONY: help install dev test lint format type-check security clean build docker run

# 默认目标
help:
	@echo "可用的命令:"
	@echo "  install     - 安装项目依赖"
	@echo "  dev         - 安装开发依赖"
	@echo "  test        - 运行测试"
	@echo "  test-cov    - 运行测试并生成覆盖率报告"
	@echo "  lint        - 代码检查 (ruff)"
	@echo "  format      - 代码格式化 (ruff)"
	@echo "  type-check  - 类型检查 (mypy)"
	@echo "  security    - 安全扫描 (bandit + pip-audit)"
	@echo "  pre-commit  - 运行pre-commit检查"
	@echo "  clean       - 清理临时文件"
	@echo "  build       - 构建Python包"
	@echo "  docker      - 构建Docker镜像"
	@echo "  run         - 启动开发服务器"
	@echo "  run-prod    - 启动生产服务器"

# 安装依赖
install:
	pip install --upgrade pip
	pip install -r requirements.txt

# 安装开发依赖
dev: install
	pip install pytest pytest-asyncio pytest-cov pytest-mock httpx
	pip install ruff mypy bandit pip-audit pre-commit
	pre-commit install

# 运行测试
test:
	pytest tests/ -v

# 运行测试并生成覆盖率报告
test-cov:
	pytest tests/ --cov=app --cov-report=term-missing --cov-report=html:htmlcov --cov-report=xml:coverage.xml --cov-fail-under=80 -v

# 代码检查
lint:
	ruff check app/ tests/

# 代码格式化
format:
	ruff format app/ tests/
	ruff check app/ tests/ --fix

# 类型检查
type-check:
	mypy app/ --config-file pyproject.toml

# 安全扫描
security:
	bandit -r app/ -f txt
	pip-audit

# 运行所有检查
check: lint type-check security

# 运行pre-commit
pre-commit:
	pre-commit run --all-files

# 清理临时文件
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/
	rm -rf dist/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf coverage.xml
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/

# 构建Python包
build: clean
	pip install build
	python -m build

# 构建Docker镜像
docker:
	docker build -t auth-supabase:latest .

# 启动开发服务器
run:
	uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# 启动生产服务器
run-prod:
	gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# 运行完整的CI检查流程
ci: clean install dev check test-cov
	@echo "✅ 所有CI检查通过!"

# 快速开发设置
quick-start: dev
	@echo "🚀 开发环境已准备就绪!"
	@echo "运行 'make run' 启动开发服务器"

# 生产部署准备
prod-ready: ci build
	@echo "🎯 生产部署包已准备就绪!"