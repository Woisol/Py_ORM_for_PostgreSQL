import os, asyncpg
from enum import Enum
class NoUnlistenConnection(asyncpg.Connection):
  """
  自定义 asyncpg 连接：覆盖 reset 以跳过 UNLISTEN。

  背景：部分 PostgreSQL 兼容实现（例如某些 openGauss 版本）尚不支持 LISTEN/UNLISTEN，
  而 asyncpg 在连接释放/重置时会执行 UNLISTEN * 清理监听，导致报错：
      "UNLISTEN statement is not yet supported"。

  解决：覆盖 reset() 为 no-op，避免向服务器发送 UNLISTEN，从而保证连接释放不报错。

  注意：这会跳过常规的连接状态重置（如 RESET/CLOSE/UNLISTEN 等），
  在严苛的多租户或复用场景中可能导致会话级别设置遗留。若需更严格控制，
  可根据后端能力在此实现最小重置集合，或提供开关按需启用。
  """

  async def reset(self, *, timeout: float | None = None) -> None:  # type: ignore[override]
    # 直接跳过 reset 流程以避免执行 UNLISTEN 等不被支持的语句
    return None
class FieldType(Enum):
  """字段类型枚举"""
  INT = "INTEGER"
  BIGINT = "BIGINT"
  SMALLINT = "SMALLINT"
  VARCHAR = "VARCHAR"
  TEXT = "TEXT"
  BOOLEAN = "BOOLEAN"
  TIMESTAMP = "TIMESTAMP"
  DATE = "DATE"
  DECIMAL = "DECIMAL"
  JSON = "JSON"
  UUID = "UUID"

class ConnectionPool:
  _pool: asyncpg.Pool | None = None
  def __init__(self):
    if self._pool:
      return
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
      raise ValueError("DATABASE_URL environment variable is not set")

    self._pool = asyncpg.create_pool(dsn=dsn, min_size=1, max_size=10, connection_class=NoUnlistenConnection)

  def get_pool(self) -> asyncpg.Pool:
    if not self._pool:
      self.__init__()
      if not self._pool:
        raise ValueError("Connection pool failed to initialize")
    return self._pool
  async def close_pool(self):
    if self._pool:
      await self._pool.close()

  async def _execute(self, query: str, *args):
    pool = self.get_pool()
    async with pool.acquire() as con:
      return await con.execute(query, *args)

  # @todo ?
  async def _fetch(self, query: str, *args):
    pool = self.get_pool()
    async with pool.acquire() as con:
      return await con.fetch(query, *args)

  async def _fetchrow(self, query: str, *args):
    pool = self.get_pool()
    async with pool.acquire() as con:
      return await con.fetchrow(query, *args)

  async def create_table(self, table_name: str, columns: dict):
    cols = []
    for col_name, col_desc in columns.items():
      if isinstance(col_desc, FieldType):
        cols.append(f"{col_name} {col_desc}")
      else:
        raise ValueError(f"Unsupported column type: {col_desc}")
    cols_sql = ", ".join(cols)
    query = f"CREATE TABLE IF NOT EXISTS {table_name} ({cols_sql});"
    await self._execute(query)

  async def drop_table(self, table_name: str):
    query = f"DROP TABLE IF EXISTS {table_name};"
    await self._execute(query)

  async def create_index(self, table_name: str, index_name: str, column_name: str):
    query = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({column_name});"
    await self._execute(query)

  async def drop_index(self, index_name: str):
    query = f"DROP INDEX IF EXISTS {index_name};"
    await self._execute(query)

  async def create(self, table_name: str, data: dict):
    cols = ", ".join(data.keys())
    vals = ", ".join(f"${i+1}" for i in range(len(data)))
    query = f"INSERT INTO {table_name} ({cols}) VALUES ({vals}) RETURNING *;"
    return await self._fetchrow(query, *data.values())

  async def read(self, table_name: str, query_name:str = "*", conditions: dict = {}):
    conds = " AND ".join(f"{k} = ${i+1}" for i, k in enumerate(conditions.keys()))
    query = f"SELECT {query_name} FROM {table_name} WHERE {conds};"
    return await self._fetch(query, *conditions.values())

  async def update(self, table_name: str, data: dict, conditions: dict = {}):
    set_clause = ", ".join(f"{k} = ${i+1}" for i, k in enumerate(data.keys()))
    conds = " AND ".join(f"{k} = ${i+1+len(data)}" for i, k in enumerate(conditions.keys()))
    query = f"UPDATE {table_name} SET {set_clause} WHERE {conds} RETURNING *;"
    return await self._fetchrow(query, *(list(data.values()) + list(conditions.values())))

  async def delete(self, table_name: str, conditions: dict = {}):
    conds = " AND ".join(f"{k} = ${i+1}" for i, k in enumerate(conditions.keys()))
    query = f"DELETE FROM {table_name} WHERE {conds} RETURNING *;"
    return await self._fetchrow(query, *conditions.values())