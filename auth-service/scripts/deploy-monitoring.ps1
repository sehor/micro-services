# Auth-Supabase 监控部署脚本
# 用于部署完整的监控栈

param(
    [Parameter(Mandatory=$false)]
    [string]$Environment = "development",
    
    [Parameter(Mandatory=$false)]
    [switch]$SkipBuild = $false,
    
    [Parameter(Mandatory=$false)]
    [switch]$CleanStart = $false
)

# 设置错误处理
$ErrorActionPreference = "Stop"

# 颜色输出函数
function Write-ColorOutput {
    param(
        [string]$Message,
        [string]$Color = "White"
    )
    Write-Host $Message -ForegroundColor $Color
}

# 检查Docker是否运行
function Test-DockerRunning {
    try {
        docker info | Out-Null
        return $true
    }
    catch {
        return $false
    }
}

# 检查必要的文件
function Test-RequiredFiles {
    $requiredFiles = @(
        "docker-compose.yml",
        "docker-compose.monitoring.yml",
        "monitoring/prometheus.yml",
        "monitoring/alert_rules.yml",
        "monitoring/alertmanager.yml"
    )
    
    foreach ($file in $requiredFiles) {
        if (-not (Test-Path $file)) {
            Write-ColorOutput "错误: 缺少必要文件 $file" "Red"
            return $false
        }
    }
    return $true
}

# 创建必要的目录
function New-MonitoringDirectories {
    $directories = @(
        "monitoring/grafana/data",
        "monitoring/prometheus/data",
        "monitoring/alertmanager/data",
        "logs"
    )
    
    foreach ($dir in $directories) {
        if (-not (Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
            Write-ColorOutput "创建目录: $dir" "Green"
        }
    }
}

# 设置权限（Windows下的等效操作）
function Set-MonitoringPermissions {
    Write-ColorOutput "设置监控目录权限..." "Yellow"
    
    # 在Windows下，通常Docker Desktop会处理权限
    # 这里主要确保目录存在且可访问
    $directories = @(
        "monitoring/grafana/data",
        "monitoring/prometheus/data",
        "monitoring/alertmanager/data"
    )
    
    foreach ($dir in $directories) {
        if (Test-Path $dir) {
            # 确保目录可写
            $acl = Get-Acl $dir
            # 在Windows下，通常不需要特殊权限设置
            Write-ColorOutput "权限检查: $dir" "Green"
        }
    }
}

# 生成监控配置
function New-MonitoringConfig {
    Write-ColorOutput "生成监控配置..." "Yellow"
    
    # 检查环境变量文件
    if (-not (Test-Path ".env")) {
        if (Test-Path ".env.example") {
            Copy-Item ".env.example" ".env"
            Write-ColorOutput "已从 .env.example 创建 .env 文件" "Yellow"
            Write-ColorOutput "请检查并更新 .env 文件中的监控配置" "Yellow"
        } else {
            Write-ColorOutput "警告: 未找到 .env 或 .env.example 文件" "Yellow"
        }
    }
}

# 构建应用镜像
function Build-Application {
    if ($SkipBuild) {
        Write-ColorOutput "跳过应用构建" "Yellow"
        return
    }
    
    Write-ColorOutput "构建应用镜像..." "Yellow"
    
    try {
        if ($Environment -eq "development") {
            docker-compose -f docker-compose.yml -f docker-compose.dev.yml build
        } else {
            docker-compose build
        }
        Write-ColorOutput "应用镜像构建完成" "Green"
    }
    catch {
        Write-ColorOutput "应用镜像构建失败: $($_.Exception.Message)" "Red"
        throw
    }
}

# 启动监控服务
function Start-MonitoringServices {
    Write-ColorOutput "启动监控服务..." "Yellow"
    
    try {
        # 首先启动基础服务
        if ($Environment -eq "development") {
            docker-compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.monitoring.yml up -d redis
        } else {
            docker-compose -f docker-compose.yml -f docker-compose.monitoring.yml up -d redis
        }
        
        Start-Sleep -Seconds 5
        
        # 启动监控栈
        docker-compose -f docker-compose.monitoring.yml up -d prometheus grafana jaeger alertmanager
        
        Start-Sleep -Seconds 10
        
        # 启动应用
        if ($Environment -eq "development") {
            docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
        } else {
            docker-compose up -d
        }
        
        Write-ColorOutput "监控服务启动完成" "Green"
    }
    catch {
        Write-ColorOutput "监控服务启动失败: $($_.Exception.Message)" "Red"
        throw
    }
}

# 检查服务状态
function Test-ServicesHealth {
    Write-ColorOutput "检查服务健康状态..." "Yellow"
    
    $services = @(
        @{Name="Prometheus"; Url="http://localhost:9090/-/healthy"; Port=9090},
        @{Name="Grafana"; Url="http://localhost:3000/api/health"; Port=3000},
        @{Name="Jaeger"; Url="http://localhost:16686"; Port=16686},
        @{Name="AlertManager"; Url="http://localhost:9093/-/healthy"; Port=9093},
        @{Name="Auth-Supabase"; Url="http://localhost:8000/health"; Port=8000}
    )
    
    foreach ($service in $services) {
        $maxRetries = 30
        $retryCount = 0
        $healthy = $false
        
        while ($retryCount -lt $maxRetries -and -not $healthy) {
            try {
                $response = Invoke-WebRequest -Uri $service.Url -TimeoutSec 5 -UseBasicParsing
                if ($response.StatusCode -eq 200) {
                    Write-ColorOutput "✓ $($service.Name) 健康检查通过" "Green"
                    $healthy = $true
                } else {
                    throw "HTTP $($response.StatusCode)"
                }
            }
            catch {
                $retryCount++
                if ($retryCount -lt $maxRetries) {
                    Write-ColorOutput "等待 $($service.Name) 启动... ($retryCount/$maxRetries)" "Yellow"
                    Start-Sleep -Seconds 2
                } else {
                    Write-ColorOutput "✗ $($service.Name) 健康检查失败" "Red"
                }
            }
        }
    }
}

# 显示访问信息
function Show-AccessInfo {
    Write-ColorOutput "`n=== 监控服务访问信息 ===" "Cyan"
    Write-ColorOutput "Grafana:      http://localhost:3000 (admin/admin)" "White"
    Write-ColorOutput "Prometheus:   http://localhost:9090" "White"
    Write-ColorOutput "Jaeger:       http://localhost:16686" "White"
    Write-ColorOutput "AlertManager: http://localhost:9093" "White"
    Write-ColorOutput "Auth-Supabase: http://localhost:8000" "White"
    Write-ColorOutput "API文档:      http://localhost:8000/docs" "White"
    Write-ColorOutput "指标端点:    http://localhost:8000/metrics" "White"
    Write-ColorOutput "`n=== 有用的命令 ===" "Cyan"
    Write-ColorOutput "查看日志: docker-compose -f docker-compose.monitoring.yml logs -f [service]" "White"
    Write-ColorOutput "停止服务: docker-compose -f docker-compose.monitoring.yml down" "White"
    Write-ColorOutput "重启服务: docker-compose -f docker-compose.monitoring.yml restart [service]" "White"
}

# 清理函数
function Stop-MonitoringServices {
    if ($CleanStart) {
        Write-ColorOutput "清理现有服务..." "Yellow"
        
        try {
            docker-compose -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.monitoring.yml down -v
            Write-ColorOutput "服务清理完成" "Green"
        }
        catch {
            Write-ColorOutput "服务清理失败: $($_.Exception.Message)" "Yellow"
        }
    }
}

# 主函数
function Main {
    Write-ColorOutput "=== Auth-Supabase 监控部署脚本 ===" "Cyan"
    Write-ColorOutput "环境: $Environment" "White"
    
    try {
        # 检查Docker
        if (-not (Test-DockerRunning)) {
            Write-ColorOutput "错误: Docker未运行，请启动Docker Desktop" "Red"
            exit 1
        }
        
        # 检查必要文件
        if (-not (Test-RequiredFiles)) {
            Write-ColorOutput "错误: 缺少必要文件" "Red"
            exit 1
        }
        
        # 清理现有服务（如果需要）
        Stop-MonitoringServices
        
        # 创建目录
        New-MonitoringDirectories
        
        # 设置权限
        Set-MonitoringPermissions
        
        # 生成配置
        New-MonitoringConfig
        
        # 构建应用
        Build-Application
        
        # 启动服务
        Start-MonitoringServices
        
        # 健康检查
        Test-ServicesHealth
        
        # 显示访问信息
        Show-AccessInfo
        
        Write-ColorOutput "`n✓ 监控部署完成!" "Green"
        
    }
    catch {
        Write-ColorOutput "`n✗ 部署失败: $($_.Exception.Message)" "Red"
        Write-ColorOutput "请检查错误信息并重试" "Yellow"
        exit 1
    }
}

# 执行主函数
Main