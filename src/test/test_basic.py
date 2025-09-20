import asyncpg
import pytest
import pytest_asyncio
import os
from dotenv import load_dotenv
from ..orm.db import Database, FieldType

# 加载环境变量
load_dotenv()

@pytest_asyncio.fixture
async def database():
    """提供数据库连接的fixture"""
    db = Database()
    await db.initialize_pool()
    yield db
    await db.close_pool()

@pytest.mark.asyncio
async def test_create_table(database):
    # 使用环境变量中的数据库URL
    database_url = os.getenv("DATABASE_URL")
    print(f"Using database: {database_url}")

    # 先清理可能存在的测试表
    await database.drop_table("test_table")

    await database.create_table("test_table", {
        "id": FieldType.TEXT,
        "name": FieldType.TEXT,
        "age": FieldType.INT
    })

    # 验证表已创建
    tables = await database._fetch("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'test_table';")
    assert len(tables) > 0

@pytest.mark.asyncio
async def test_create(database: Database):
  await database.create("test_table", {
      "id": "id_abc",
      "name": "name_abc",
      "age": 30
  })

  # 验证数据已插入
  row = await database._fetchrow("SELECT * FROM test_table WHERE id = 'id_abc';")
  assert row['id'] == 'id_abc'
  assert row['name'] == 'name_abc'
  assert row['age'] == 30

@pytest.mark.asyncio
async def test_read(database: Database):
  rows = await database.read("test_table", conditions={"id": "id_abc"})
  assert len(rows) > 0
  assert rows[0]['id'] == 'id_abc'
  assert rows[0]['name'] == 'name_abc'
  assert rows[0]['age'] == 30

@pytest.mark.asyncio
async def test_update(database: Database):
  await database.update("test_table", data={"name": "name_updated", "age": 31}, conditions={"id": "id_abc"})

  # 验证数据已更新
  row = await database._fetchrow("SELECT * FROM test_table WHERE id = 'id_abc';")
  assert row['name'] == 'name_updated'
  assert row['age'] == 31

@pytest.mark.asyncio
async def test_delete(database: Database):
  await database.delete("test_table", conditions={"id": "id_abc"})

  # 验证数据已删除
  row = await database._fetchrow("SELECT * FROM test_table WHERE id = 'id_abc';")
  assert row is None

@pytest.mark.asyncio
async def test_drop_table(database):
    # 先创建表
    await database.create_table("test_table", {
        "id": FieldType.TEXT,
        "name": FieldType.TEXT,
        "age": FieldType.INT
    })

    # 删除表
    await database.drop_table("test_table")

    # 验证表已删除
    tables = await database._fetch("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'test_table';")
    assert len(tables) == 0

