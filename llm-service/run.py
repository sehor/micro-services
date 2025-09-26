import uvicorn
import os

if __name__ == "__main__":
    """
    应用启动脚本。
    
    使用此脚本可以通过 `python run.py` 命令来启动应用。
    支持通过环境变量来自定义 host 和 port。
    - HOST: 监听的主机地址, 默认为 "127.0.0.1"
    - PORT: 监听的端口, 默认为 8000
    """
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    
    uvicorn.run(
        "app.main:app", 
        host=host, 
        port=port, 
        reload=True
    )