#!/usr/bin/env python3
"""
提供便捷的服务启动方式，默认开启热重载
"""

import uvicorn
import argparse
import sys
from pathlib import Path

def main():
    """主函数：解析参数并启动 FastAPI 服务"""
    parser = argparse.ArgumentParser(description="启动 RAG 服务")
    parser.add_argument("--host", default="127.0.0.1", help="服务监听地址 (默认: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8005, help="服务监听端口 (默认: 8005)")
    parser.add_argument("--reload", action="store_true", default=True, help="开启热重载 (默认: True)")
    parser.add_argument("--no-reload", action="store_true", help="禁用热重载")
    parser.add_argument("--workers", type=int, default=1, help="工作进程数 (默认: 1)")
    
    args = parser.parse_args()
    
    # 处理 reload 参数
    reload = args.reload and not args.no_reload
    
    # 确保在项目根目录
    project_root = Path(__file__).parent
    sys.path.insert(0, str(project_root))
    
    print(f"🚀 启动 TODO 服务...")
    print(f"📍 地址: http://{args.host}:{args.port}")
    print(f"🔄 热重载: {'开启' if reload else '关闭'}")
    print(f"👥 工作进程: {args.workers}")
    print(f"📚 API 文档: http://{args.host}:{args.port}/docs")
    print("-" * 50)
    
    try:
        uvicorn.run(
            "app.main:app",
            host=args.host,
            port=args.port,
            reload=reload,
            workers=args.workers if not reload else 1,  # reload 模式下只能单进程
            access_log=True,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n🛑 服务已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()