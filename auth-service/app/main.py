from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 导入配置
from app.config import settings
from app.factory import create_app
from app.logging.config import StructuredLogger, get_structured_logger

# 配置结构化日志
StructuredLogger.setup_logging(
    log_level=settings.log_level,
    enable_json=settings.environment == "production"
)
logger = get_structured_logger("auth-service")

# 创建应用实例
app = create_app()
