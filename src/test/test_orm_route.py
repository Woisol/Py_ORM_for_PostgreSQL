import pytest
import pytest_asyncio
import os
from dotenv import load_dotenv
from src.orm.db import FieldType, Database
from src.orm.model import BaseModel, Field

# 加载环境变量
load_dotenv()

class User(BaseModel):
    """用户模型 - 使用Field描述符"""
    id = Field(FieldType.INT, primary_key=True, nullable=False)
    username = Field(FieldType.VARCHAR, unique=True, nullable=False)
    email = Field(FieldType.TEXT, unique=True, nullable=False)
    age = Field(FieldType.INT, nullable=True)
    is_active = Field(FieldType.BOOLEAN, default=True, nullable=False)



@pytest.mark.asyncio
async def test_route1():
    """ORM 使用路径1"""
    # 确保表存在
    await User.ensure_table_exists()

    # 创建并保存用户
    user1 = User(
        id=1,
        username="testuser",
        email="test@example.com",
        age=25,
        is_active=True
    )
    await user1.save()

    # 测试find_all方法
    res = await User.find_all()
    assert res is not None
    assert isinstance(res, list)
    assert len(res) >= 1  # 至少有我们刚插入的用户

    # 查找我们插入的用户
    found_user = None
    for user in res:
        if user.id == 1:
            found_user = user
            break

    assert found_user is not None
    assert found_user.id == 1
    assert found_user.username == "testuser"
    assert found_user.email == "test@example.com"
    assert found_user.age == 25
    assert found_user.is_active == True


@pytest.mark.asyncio
async def test_route2():
    """ORM 使用路径2"""
    # 确保表存在
    await User.ensure_table_exists()

    # 1. Create - 创建用户
    user = User(
        id=100,
        username="workflow_user",
        email="workflow@example.com",
        age=30,
        is_active=True
    )
    await user.save()

    # 2. Read - 读取用户
    found_user = await User.find_by_id(100)
    assert found_user is not None
    assert found_user.username == "workflow_user"

    # 3. Update - 更新用户
    await found_user.update(None, age=35, username="updated_workflow_user")

    # 验证更新
    updated_user = await User.find_by_id(100)
    assert updated_user.username == "updated_workflow_user"
    assert updated_user.age == 35
    assert updated_user.email == "workflow@example.com"  # 未更新字段保持不变

    # 4. Delete - 删除用户
    await updated_user.delete()

    # 验证删除
    deleted_user = await User.find_by_id(100)
    assert deleted_user is None

