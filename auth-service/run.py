#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
应用启动脚本
用于快速启动 FastAPI 认证服务

使用方法:
    python run.py              # 默认启动（带自动重载）
    python run.py --no-reload  # 不启用自动重载
    python run.py --port 8080  # 指定端口
"""

import argparse
import uvicorn
import os
import sys

# 确保项目根目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    """主函数：解析命令行参数并启动应用。"""
    parser = argparse.ArgumentParser(description="启动 FastAPI 认证服务")
    parser.add_argument(
        "--host", 
        default="127.0.0.1", 
        help="服务器主机地址 (默认: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", 
        type=int, 
        default=8000, 
        help="服务器端口 (默认: 8000)"
    )
    parser.add_argument(
        "--no-reload", 
        action="store_true", 
        help="禁用自动重载功能"
    )
    parser.add_argument(
        "--log-level", 
        default="info", 
        choices=["critical", "error", "warning", "info", "debug", "trace"],
        help="日志级别 (默认: info)"
    )
    
    args = parser.parse_args()
    
    # 检查环境变量文件
    env_file = ".env"
    if not os.path.exists(env_file):
        print(f"⚠️  警告: 未找到 {env_file} 文件，请确保已配置环境变量")
    
    print(f"🚀 启动 FastAPI 认证服务...")
    print(f"📍 地址: http://{args.host}:{args.port}")
    print(f"📖 API 文档: http://{args.host}:{args.port}/docs")
    print(f"🔄 自动重载: {'启用' if not args.no_reload else '禁用'}")
    print(f"📝 日志级别: {args.log_level.upper()}")
    print("\n按 Ctrl+C 停止服务\n")
    
    try:
        uvicorn.run(
            "app.main:app",
            host=args.host,
            port=args.port,
            reload=not args.no_reload,
            log_level=args.log_level,
            access_log=True
        )
    except KeyboardInterrupt:
        print("\n👋 服务已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()