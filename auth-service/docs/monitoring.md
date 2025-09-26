# Auth-Supabase 监控指南

本文档介绍 Auth-Supabase 项目的完整监控解决方案，包括指标收集、分布式追踪、错误监控和告警系统。

## 监控架构

### 核心组件

- **Prometheus**: 指标收集和存储
- **Grafana**: 可视化仪表板
- **Jaeger**: 分布式追踪
- **AlertManager**: 告警管理
- **Sentry**: 错误监控和性能分析

### 监控指标

#### HTTP 指标
- `http_requests_total`: HTTP请求总数
- `http_request_duration_seconds`: HTTP请求响应时间
- `http_requests_in_progress`: 正在处理的HTTP请求数

#### 认证指标
- `auth_operations_total`: 认证操作总数
- `auth_token_validation_duration_seconds`: Token验证时间
- `auth_active_sessions`: 活跃会话数

#### 数据库指标
- `supabase_operations_total`: Supabase操作总数
- `supabase_operation_duration_seconds`: 数据库操作时间
- `database_connections_active`: 活跃数据库连接数

#### 缓存指标
- `redis_operations_total`: Redis操作总数
- `redis_cache_hits_total`: 缓存命中数
- `redis_cache_misses_total`: 缓存未命中数

#### 系统指标
- `system_cpu_usage_percent`: CPU使用率
- `system_memory_usage_bytes`: 内存使用量
- `process_memory_usage_bytes`: 进程内存使用量
- `active_connections_total`: 活跃连接数
- `error_count_total`: 错误计数

## 快速开始

### 1. 环境准备

确保已安装 Docker 和 Docker Compose：

```powershell
# 检查 Docker 版本
docker --version
docker-compose --version
```

### 2. 配置环境变量

复制并编辑环境变量文件：

```powershell
cp .env.example .env
```

重要的监控相关环境变量：

```env
# Sentry 错误监控
SENTRY_DSN=your-sentry-dsn
SENTRY_ENVIRONMENT=development
SENTRY_TRACES_SAMPLE_RATE=0.1

# OpenTelemetry 分布式追踪
OTEL_EXPORTER_JAEGER_ENDPOINT=http://jaeger:14268/api/traces
OTEL_SERVICE_NAME=auth-supabase
OTEL_TRACES_EXPORTER=jaeger

# Prometheus 指标
PROMETHEUS_METRICS_ENABLED=true
PROMETHEUS_METRICS_PATH=/metrics
```

### 3. 部署监控栈

使用提供的部署脚本：

```powershell
# 开发环境部署
.\scripts\deploy-monitoring.ps1 -Environment development

# 生产环境部署
.\scripts\deploy-monitoring.ps1 -Environment production

# 清理重新部署
.\scripts\deploy-monitoring.ps1 -CleanStart
```

或手动部署：

```powershell
# 启动监控服务
docker-compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d

# 查看服务状态
docker-compose ps
```

### 4. 访问监控界面

部署完成后，可以通过以下地址访问各个监控组件：

- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **Jaeger**: http://localhost:16686
- **AlertManager**: http://localhost:9093
- **应用指标**: http://localhost:8000/metrics

## 监控配置

### Prometheus 配置

Prometheus 配置文件位于 `monitoring/prometheus.yml`，包含：

- 全局配置
- 告警规则文件
- 抓取目标配置
- AlertManager 集成

### 告警规则

告警规则定义在 `monitoring/alert_rules.yml`，包括：

#### 应用健康告警
- 服务宕机检测
- 高错误率告警
- 响应时间过长告警

#### 系统资源告警
- CPU 使用率过高
- 内存使用率过高
- 进程内存泄漏检测

#### 业务指标告警
- 认证失败率过高
- 数据库操作异常
- 缓存命中率过低

### AlertManager 配置

AlertManager 配置文件位于 `monitoring/alertmanager.yml`，支持：

- 邮件通知
- Slack 集成
- 告警分组和抑制
- 多级告警路由

### Grafana 仪表板

预配置的仪表板包括：

- **Auth-Supabase 主仪表板**: 应用核心指标
- **系统监控**: 系统资源使用情况
- **错误分析**: 错误趋势和分布
- **性能分析**: 响应时间和吞吐量

## 分布式追踪

### OpenTelemetry 集成

应用集成了 OpenTelemetry 进行分布式追踪：

```python
from app.monitoring.tracing import TracingHelper

# 创建自定义 span
with TracingHelper.create_span("custom_operation") as span:
    span.set_attribute("user_id", user_id)
    # 执行业务逻辑
    result = perform_operation()
    span.set_attribute("result_count", len(result))
```

### 追踪数据查看

在 Jaeger UI 中可以：

- 查看请求链路
- 分析性能瓶颈
- 追踪错误传播
- 监控服务依赖

## 错误监控

### Sentry 集成

Sentry 提供实时错误监控和性能分析：

```python
from app.monitoring.sentry_config import SentryHelper

# 手动发送错误
SentryHelper.capture_exception(exception)

# 添加上下文信息
SentryHelper.add_context("user", {"id": user_id, "email": email})

# 设置标签
SentryHelper.set_tag("feature", "authentication")
```

### 错误分析

Sentry 提供：

- 实时错误通知
- 错误趋势分析
- 性能监控
- 发布版本追踪

## 性能优化

### 指标分析

通过监控指标识别性能问题：

1. **响应时间分析**
   - 查看 95th percentile 响应时间
   - 识别慢查询和慢接口
   - 分析响应时间趋势

2. **吞吐量分析**
   - 监控 QPS (每秒查询数)
   - 分析流量模式
   - 识别流量峰值

3. **错误率分析**
   - 监控 4xx/5xx 错误率
   - 分析错误分布
   - 追踪错误根因

### 缓存优化

监控 Redis 缓存性能：

- 缓存命中率
- 缓存响应时间
- 内存使用情况

### 数据库优化

监控 Supabase 数据库性能：

- 查询响应时间
- 连接池使用情况
- 慢查询识别

## 告警配置

### 告警级别

- **Critical**: 服务宕机、严重错误
- **Warning**: 性能下降、资源使用过高
- **Info**: 一般性通知

### 通知渠道

配置多种通知方式：

1. **邮件通知**
   ```yaml
   email_configs:
     - to: 'admin@example.com'
       subject: '[Alert] {{ .GroupLabels.alertname }}'
   ```

2. **Slack 通知**
   ```yaml
   slack_configs:
     - api_url: 'https://hooks.slack.com/...'
       channel: '#alerts'
   ```

3. **Webhook 通知**
   ```yaml
   webhook_configs:
     - url: 'http://example.com/webhook'
   ```

## 故障排查

### 常见问题

1. **服务无法启动**
   ```powershell
   # 查看服务日志
   docker-compose logs [service_name]
   
   # 检查端口占用
   netstat -an | findstr :9090
   ```

2. **指标数据缺失**
   ```powershell
   # 检查 Prometheus 目标状态
   # 访问 http://localhost:9090/targets
   
   # 检查应用指标端点
   curl http://localhost:8000/metrics
   ```

3. **告警不工作**
   ```powershell
   # 检查 AlertManager 配置
   docker-compose exec alertmanager amtool config show
   
   # 查看告警状态
   # 访问 http://localhost:9093
   ```

### 日志查看

```powershell
# 查看所有服务日志
docker-compose -f docker-compose.monitoring.yml logs -f

# 查看特定服务日志
docker-compose -f docker-compose.monitoring.yml logs -f prometheus
docker-compose -f docker-compose.monitoring.yml logs -f grafana
docker-compose -f docker-compose.monitoring.yml logs -f jaeger
```

## 生产环境部署

### 安全配置

1. **更改默认密码**
   ```env
   GRAFANA_ADMIN_PASSWORD=secure_password
   ```

2. **配置 HTTPS**
   - 使用反向代理 (Nginx)
   - 配置 SSL 证书
   - 启用 HTTPS 重定向

3. **网络安全**
   - 限制端口访问
   - 配置防火墙规则
   - 使用 VPN 或内网访问

### 数据持久化

确保监控数据持久化：

```yaml
volumes:
  prometheus_data:
    driver: local
  grafana_data:
    driver: local
  alertmanager_data:
    driver: local
```

### 备份策略

定期备份监控配置和数据：

```powershell
# 备份 Grafana 仪表板
docker-compose exec grafana grafana-cli admin export-dashboard

# 备份 Prometheus 数据
docker-compose exec prometheus promtool tsdb snapshot /prometheus
```

## 最佳实践

### 指标命名

- 使用描述性的指标名称
- 遵循 Prometheus 命名约定
- 添加适当的标签

### 告警设计

- 避免告警疲劳
- 设置合理的阈值
- 提供可操作的告警信息

### 仪表板设计

- 关注关键业务指标
- 使用合适的可视化类型
- 提供不同层次的详细信息

### 性能考虑

- 合理设置抓取间隔
- 控制指标基数
- 定期清理历史数据

## 扩展功能

### 自定义指标

添加业务特定的指标：

```python
from app.monitoring.metrics import MetricsCollector

# 创建自定义指标
custom_counter = MetricsCollector.create_counter(
    'business_operations_total',
    'Total business operations',
    ['operation_type', 'status']
)

# 记录指标
custom_counter.labels(operation_type='payment', status='success').inc()
```

### 集成外部服务

- **APM 工具**: New Relic, Datadog
- **日志聚合**: ELK Stack, Fluentd
- **云监控**: AWS CloudWatch, Azure Monitor

### 自动化运维

- **自动扩缩容**: 基于指标的自动扩缩容
- **自愈系统**: 自动重启异常服务
- **容量规划**: 基于历史数据的容量预测

## 参考资源

- [Prometheus 官方文档](https://prometheus.io/docs/)
- [Grafana 官方文档](https://grafana.com/docs/)
- [Jaeger 官方文档](https://www.jaegertracing.io/docs/)
- [OpenTelemetry 官方文档](https://opentelemetry.io/docs/)
- [Sentry 官方文档](https://docs.sentry.io/)