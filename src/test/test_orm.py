import pytest
import pytest_asyncio
import os
from dotenv import load_dotenv
from ..orm.model import BaseModel, Field, FieldType
from ..orm.db import Database

# 加载环境变量
load_dotenv()

# 方式1: 使用Field描述符定义模型
class User(BaseModel):
    """用户模型 - 使用Field描述符"""
    id = Field(FieldType.INT, primary_key=True, nullable=False)
    username = Field(FieldType.VARCHAR, unique=True, nullable=False)
    email = Field(FieldType.TEXT, unique=True, nullable=False)
    age = Field(FieldType.INT, nullable=True)
    is_active = Field(FieldType.BOOLEAN, default=True, nullable=False)

# 方式2: 使用类型注解自动推断
class Product(BaseModel):
    """产品模型 - 使用类型注解"""
    id: int
    name: str
    price: float
    description: str
    in_stock: bool

# 方式3: 复杂命名测试（驼峰转蛇形）
class UserProfile(BaseModel):
    """用户配置模型 - 测试命名转换"""
    id = Field(FieldType.INT, primary_key=True)
    full_name = Field(FieldType.TEXT)
    phone_number = Field(FieldType.TEXT, nullable=True)

class HTTPRequest(BaseModel):
    """HTTP请求模型 - 测试复杂命名"""
    id = Field(FieldType.INT, primary_key=True)
    method = Field(FieldType.TEXT)
    url = Field(FieldType.TEXT)

@pytest_asyncio.fixture
async def database():
    """提供数据库连接的fixture"""
    db = Database()
    await db.initialize_pool()
    yield db
    # 清理测试表
    try:
        await db.drop_table("user")
        await db.drop_table("product")
        await db.drop_table("user_profile")
        await db.drop_table("http_request")
    except:
        pass
    await db.close_pool()

# @pytest.mark.asyncio
# async def test_automatic_table_naming():
#     """测试自动表名生成"""
#     # 测试简单类名
#     assert User.get_table_name() == "user"

#     # 测试驼峰命名转换
#     assert UserProfile.get_table_name() == "user_profile"

#     # 测试复杂命名转换
#     assert HTTPRequest.get_table_name() == "http_request"

@pytest.mark.asyncio
async def test_field_descriptor_model(database):
    """测试使用Field描述符的模型"""
    # 验证字段定义
    fields = User.get_fields()
    print(f"User fields: {fields}")

    assert "id" in fields
    assert "username" in fields
    assert "email" in fields
    assert "age" in fields
    assert "is_active" in fields

    # 验证主键
    assert User.get_primary_key() == "id"

    # 创建表
    await User.ensure_table_exists(database)

    # 验证表已创建
    tables = await database._fetch(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'user';"
    )
    assert len(tables) > 0

@pytest.mark.asyncio
async def test_type_annotation_model(database):
    """测试使用类型注解的模型"""
    # 验证字段定义
    fields = Product.get_fields()
    print(f"Product fields: {fields}")

    assert "id" in fields
    assert "name" in fields
    assert "price" in fields
    assert "description" in fields
    assert "in_stock" in fields

    # 创建表
    await Product.ensure_table_exists(database)

    # 验证表已创建
    tables = await database._fetch(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'product';"
    )
    assert len(tables) > 0

@pytest.mark.asyncio
async def test_model_instance_creation():
    """测试模型实例创建和操作"""
    # 创建用户实例
    user = User(
        id=1,
        username="john_doe",
        email="john@example.com",
        age=25,
        is_active=True
    )

    # 测试属性访问
    assert user.id == 1
    assert user.username == "john_doe"
    assert user.email == "john@example.com"
    assert user.age == 25
    assert user.is_active == True

    # 测试to_dict方法
    user_dict = user.to_dict()
    expected = {
        'id': 1,
        'username': 'john_doe',
        'email': 'john@example.com',
        'age': 25,
        'is_active': True
    }
    assert user_dict == expected

    # # 测试from_dict方法
    # user2 = User.from_dict(expected)
    # assert user2.id == user.id
    # assert user2.username == user.username
    # assert user2.email == user.email

# @pytest.mark.asyncio
# async def test_field_default_values():
#     """测试字段默认值"""
#     # 创建用户时不设置is_active，应该使用默认值
#     user = User(id=2, username="jane_doe", email="jane@example.com")

#     # is_active应该有默认值True
#     assert user.is_active == True

# @pytest.mark.asyncio
# async def test_model_repr():
#     """测试模型字符串表示"""
#     user = User(id=1, username="test_user", email="test@example.com", age=30)
#     repr_str = repr(user)

#     assert "User(" in repr_str
#     assert "id=1" in repr_str
#     assert "username='test_user'" in repr_str
#     assert "email='test@example.com'" in repr_str
#     assert "age=30" in repr_str

@pytest.mark.asyncio
async def test_multiple_model_tables(database):
    """测试多个模型的表创建"""
    # 创建所有测试模型的表
    await User.ensure_table_exists(database)
    await Product.ensure_table_exists(database)
    await UserProfile.ensure_table_exists(database)
    await HTTPRequest.ensure_table_exists(database)

    # 验证所有表都已创建
    expected_tables = ["user", "product", "user_profile", "http_request"]

    for table_name in expected_tables:
        tables = await database._fetch(
            f"SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name = '{table_name}';"
        )
        assert len(tables) > 0, f"Table {table_name} was not created"

@pytest.mark.asyncio
async def test_field_sql_generation():
    """测试字段SQL生成"""
    fields = User.get_fields()

    # 验证主键字段
    assert "PRIMARY KEY" in fields["id"]
    assert "NOT NULL" in fields["id"]

    # 验证唯一约束
    assert "UNIQUE" in fields["username"]
    assert "UNIQUE" in fields["email"]
    assert "NOT NULL" in fields["username"]
    assert "NOT NULL" in fields["email"]

    # 验证可空字段
    # age字段应该允许NULL（没有NOT NULL）
    assert "NOT NULL" not in fields["age"]

    # 验证默认值
    assert "DEFAULT" in fields["is_active"]