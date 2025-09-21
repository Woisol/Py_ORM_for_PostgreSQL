"""
vibe generate
"""
import pytest
import pytest_asyncio
import os
from dotenv import load_dotenv
from ..orm.model import BaseModel, Field, FieldType
from ..orm.db import Database, db

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

# 方式2: 使用类型注解自动推断 + Field定义主键
class Product(BaseModel):
    """产品模型 - 混合使用Field和类型注解"""
    id = Field(FieldType.INT, primary_key=True, nullable=False)
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

# CRUD 测试
@pytest.mark.asyncio
async def test_model_create_save(database):
    """测试创建和保存模型实例"""
    # 确保表存在
    await User.ensure_table_exists(database)

    # 创建用户实例
    user = User(
        id=1,
        username="test_user",
        email="test@example.com",
        age=25,
        is_active=True
    )

    # 保存到数据库
    await user.save(database)

    # 验证数据已保存
    result = await database._fetchrow(
        'SELECT * FROM "user" WHERE "id" = $1', 1
    )
    assert result is not None
    assert result['username'] == "test_user"
    assert result['email'] == "test@example.com"
    assert result['age'] == 25
    assert result['is_active'] == True

@pytest.mark.asyncio
async def test_model_find_by_id(database):
    """测试根据ID查找模型"""
    # 确保表存在并插入测试数据
    await User.ensure_table_exists(database)

    # 插入测试数据
    user = User(
        id=2,
        username="find_user",
        email="find@example.com",
        age=30,
        is_active=True
    )
    await user.save(database)

    # 根据ID查找
    found_user = await User.find_by_id(2, database)

    assert found_user is not None
    assert found_user.id == 2
    assert found_user.username == "find_user"
    assert found_user.email == "find@example.com"
    assert found_user.age == 30
    assert found_user.is_active == True

    # 测试查找不存在的记录
    not_found = await User.find_by_id(999, database)
    assert not_found is None

@pytest.mark.asyncio
async def test_model_find_all(database):
    """测试查找所有模型"""
    # 确保表存在
    await User.ensure_table_exists(database)

    # 插入多条测试数据
    users_data = [
        {"id": 10, "username": "user1", "email": "user1@example.com", "age": 20},
        {"id": 11, "username": "user2", "email": "user2@example.com", "age": 25},
        {"id": 12, "username": "user3", "email": "user3@example.com", "age": 30}
    ]

    for user_data in users_data:
        user = User(**user_data)
        await user.save(database)

    # 查找所有用户
    all_users = await User.find_all(database)
    assert len(all_users) >= 3  # 至少包含我们插入的3个用户

    # 验证用户数据
    usernames = [user.username for user in all_users]
    assert "user1" in usernames
    assert "user2" in usernames
    assert "user3" in usernames

    # 测试限制数量
    limited_users = await User.find_all(database, limit=2)
    assert len(limited_users) == 2

@pytest.mark.asyncio
async def test_model_update(database):
    """测试更新模型"""
    # 确保表存在
    await User.ensure_table_exists(database)

    # 创建并保存用户
    user = User(
        id=20,
        username="update_user",
        email="update@example.com",
        age=25,
        is_active=True
    )
    await user.save(database)

    # 更新用户信息
    await user.update(database, age=30, username="updated_user")

    # 验证更新
    updated_user = await User.find_by_id(20, database)
    assert updated_user is not None
    assert updated_user.username == "updated_user"
    assert updated_user.age == 30
    assert updated_user.email == "update@example.com"  # 未更新的字段保持不变
    assert updated_user.is_active == True

@pytest.mark.asyncio
async def test_model_delete(database):
    """测试删除模型"""
    # 确保表存在
    await User.ensure_table_exists(database)

    # 创建并保存用户
    user = User(
        id=30,
        username="delete_user",
        email="delete@example.com",
        age=25,
        is_active=True
    )
    await user.save(database)

    # 验证用户存在
    found_user = await User.find_by_id(30, database)
    assert found_user is not None

    # 删除用户
    await user.delete(database)

    # 验证用户已删除
    deleted_user = await User.find_by_id(30, database)
    assert deleted_user is None

@pytest.mark.asyncio
async def test_product_crud(database):
    """测试Product模型的CRUD操作"""
    # 确保表存在
    await Product.ensure_table_exists(database)

    # 创建产品
    product = Product(
        id=1,
        name="Test Product",
        price=99.99,
        description="A test product",
        in_stock=True
    )

    # 保存
    await product.save(database)

    # 查找
    found_product = await Product.find_by_id(1, database)
    assert found_product is not None
    assert found_product.name == "Test Product"
    assert found_product.price == 99.99
    assert found_product.in_stock == True

    # 更新
    await product.update(database, price=79.99, in_stock=False)
    updated_product = await Product.find_by_id(1, database)
    assert updated_product.price == 79.99
    assert updated_product.in_stock == False

    # 删除
    await product.delete(database)
    deleted_product = await Product.find_by_id(1, database)
    assert deleted_product is None

@pytest.mark.asyncio
async def test_model_error_cases(database):
    """测试错误情况"""
    # 测试没有主键的模型查找
    class NoKeyModel(BaseModel):
        name = Field(FieldType.TEXT)

    await NoKeyModel.ensure_table_exists(database)

    # 测试find_by_id时没有主键
    with pytest.raises(ValueError, match="has no primary key defined"):
        await NoKeyModel.find_by_id(1, database)

    # 测试update时没有主键
    no_key_instance = NoKeyModel(name="test")
    with pytest.raises(ValueError, match="has no primary key defined"):
        await no_key_instance.update(database, name="updated")

    # 测试delete时没有主键
    with pytest.raises(ValueError, match="has no primary key defined"):
        await no_key_instance.delete(database)

