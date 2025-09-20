import os
import pytest
from dotenv import load_dotenv

# 在所有测试运行前加载环境变量
load_dotenv()

@pytest.fixture(scope="session")
def database_url():
    """提供数据库URL的fixture"""
    return os.getenv("DATABASE_URL")

@pytest.fixture(scope="session", autouse=True)
def setup_environment():
    """自动运行的环境设置fixture"""
    # 确保环境变量已加载
    if not os.getenv("DATABASE_URL"):
        raise ValueError("DATABASE_URL environment variable not found")
    yield
    # 测试完成后的清理工作（如果需要）