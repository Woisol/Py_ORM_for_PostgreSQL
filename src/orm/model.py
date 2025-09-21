
import os
import re
from typing import Any, Dict, Type, get_type_hints

from src.orm.db import Database, db, FieldType


class ForeignKey:
    """外键关联描述符"""
    def __init__(self, reference_model: str, reference_field: str = "id",
                 on_delete: str = "CASCADE", on_update: str = "CASCADE"):
        self.reference_model = reference_model
        self.reference_field = reference_field
        self.on_delete = on_delete
        self.on_update = on_update
        self.name = None

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return instance.__dict__.get(self.name)

    def __set__(self, instance, value):
        instance.__dict__[self.name] = value


class Field:
    """字段描述符"""
    def __init__(self, field_type: FieldType, nullable: bool = True, default: Any = None,
                 primary_key: bool = False, unique: bool = False, foreign_key: 'ForeignKey | None' = None):
        self.field_type = field_type
        self.nullable = nullable
        self.default = default
        self.primary_key = primary_key
        self.unique = unique
        self.foreign_key = foreign_key
        self.name = None  # 将在元类中设置

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return instance.__dict__.get(self.name, self.default)

    def __set__(self, instance, value):
        instance.__dict__[self.name] = value


class ModelMeta(type):
    """Model元类，用于自动处理表名和字段"""

    @staticmethod
    def _camel_to_snake(name: str) -> str:
        """将驼峰命名转换为蛇形命名"""
        # 处理连续大写字母，如 HTTPRequest -> http_request
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

    def __new__(cls, name, bases, namespace, **kwargs):
        # 跳过BaseModel本身
        if name == 'BaseModel':
            return super().__new__(cls, name, bases, namespace)

        # 自动生成表名
        if '_table_name' not in namespace:
            namespace['_table_name'] = cls._camel_to_snake(name)

        # 自动收集字段和外键
        fields = {}
        foreign_keys = {}
        primary_key = None

        # 从Field对象收集字段信息
        for attr_name, attr_value in namespace.items():
            if isinstance(attr_value, Field):
                # 构建字段SQL定义
                field_def = attr_value.field_type.value
                if not attr_value.nullable:
                    field_def += " NOT NULL"
                if attr_value.primary_key:
                    field_def += " PRIMARY KEY"
                    primary_key = attr_name
                if attr_value.unique:
                    field_def += " UNIQUE"
                if attr_value.default is not None and not attr_value.primary_key:
                    if isinstance(attr_value.default, str):
                        field_def += f" DEFAULT '{attr_value.default}'"
                    else:
                        field_def += f" DEFAULT {attr_value.default}"

                # 处理外键约束
                if attr_value.foreign_key:
                    fk = attr_value.foreign_key
                    foreign_keys[attr_name] = {
                        'reference_table': cls._camel_to_snake(fk.reference_model),
                        'reference_field': fk.reference_field,
                        'on_delete': fk.on_delete,
                        'on_update': fk.on_update
                    }

                fields[attr_name] = field_def

        # 从类型注解推断剩余字段（没有Field定义的）
        annotations = namespace.get('__annotations__', {})
        for attr_name, attr_type in annotations.items():
            if not attr_name.startswith('_') and attr_name not in fields:  # 跳过私有属性和已定义字段
                field_type = cls._infer_field_type(attr_type)
                if field_type:
                    fields[attr_name] = field_type.value

        namespace['_fields'] = fields
        namespace['_foreign_keys'] = foreign_keys
        namespace['_primary_key'] = primary_key

        return super().__new__(cls, name, bases, namespace)

    @staticmethod
    def _infer_field_type(python_type) -> FieldType | None:
        """从Python类型推断FieldType"""
        # 处理Union类型（如 str | None）
        if hasattr(python_type, '__origin__'):
            if python_type.__origin__ is type(int | str):  # Union type
                args = python_type.__args__
                non_none_types = [arg for arg in args if arg is not type(None)]
                if len(non_none_types) == 1:
                    python_type = non_none_types[0]

        # 基础类型映射
        type_mapping = {
            int: FieldType.INT,
            str: FieldType.TEXT,
            bool: FieldType.BOOLEAN,
            float: FieldType.DECIMAL,
        }

        return type_mapping.get(python_type)


class BaseModel(metaclass=ModelMeta):
    """基础模型类，自动处理表名和字段映射"""

    # 类属性声明（用于类型检查）
    _table_name: str
    _fields: Dict[str, str]
    _foreign_keys: Dict[str, Dict]
    _primary_key: str | None

    def __init__(self, **kwargs):
        # 设置默认属性
        self._indexes = []
        self._unique_constraints = []
        self._instance_foreign_keys = []  # 实例级别的外键列表
        self._created_at_field = None
        self._updated_at_field = None
        self._deleted_at_field = None

        # 设置字段值
        for key, value in kwargs.items():
            if key in self._fields:  # 检查是否是定义的字段
                setattr(self, key, value)

    @classmethod
    async def ensure_table_exists(cls, database_instance=None):
        """确保表已创建"""
        #!  行吧必须支持传入 db 示例否则测试报错
        db_instance = database_instance or db
        if db_instance is None:
            raise ValueError("Database instance is not initialized.")
        await db_instance.create_table(cls._table_name, cls._fields, cls._foreign_keys)

    @classmethod
    def get_table_name(cls) -> str:
        """获取表名"""
        return cls._table_name

    @classmethod
    def get_fields(cls) -> Dict[str, str]:
        """获取字段定义"""
        return cls._fields

    @classmethod
    def get_primary_key(cls) -> str | None:
        """获取主键字段名"""
        return cls._primary_key

    @classmethod
    def get_foreign_keys(cls) -> Dict[str, Dict]:
        """获取外键定义"""
        return cls._foreign_keys

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = {}
        for field_name in self.__class__._fields.keys():
            if hasattr(self, field_name):
                result[field_name] = getattr(self, field_name)
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaseModel':
        """从字典创建实例"""
        return cls(**data)

    def __repr__(self):
        class_name = self.__class__.__name__
        attrs = ', '.join(f'{k}={v!r}' for k, v in self.to_dict().items())
        return f'{class_name}({attrs})'

    async def save(self, database_instance=None):
        """保存当前实例到数据库"""
        db_instance = database_instance or db
        if db_instance is None:
            raise ValueError("Database instance is not initialized.")

        data = self.to_dict()
        placeholders = ', '.join(f'${i+1}' for i in range(len(data)))
        columns = ', '.join(f'"{col}"' for col in data.keys())  # 为列名添加引号
        values = list(data.values())
        query = f'INSERT INTO "{self._table_name}" ({columns}) VALUES ({placeholders})'

        return await db_instance._execute(query, *values)

    @classmethod
    async def find_by_id(cls, id_value, database_instance=None):
        """根据主键查找记录"""
        db_instance = database_instance or db
        if db_instance is None:
            raise ValueError("Database instance is not initialized.")

        if not cls._primary_key:
            raise ValueError(f"Model {cls.__name__} has no primary key defined")

        query = f'SELECT * FROM "{cls._table_name}" WHERE "{cls._primary_key}" = $1'
        row = await db_instance._fetchrow(query, id_value)

        if row:
            return cls.from_dict(dict(row))
        return None

    @classmethod
    async def find_all(cls, database_instance=None, limit=None, offset=None):
        """查找所有记录"""
        db_instance = database_instance or db
        if db_instance is None:
            raise ValueError("Database instance is not initialized.")

        query = f'SELECT * FROM "{cls._table_name}"'
        if limit:
            query += f' LIMIT {limit}'
        if offset:
            query += f' OFFSET {offset}'

        rows = await db_instance._fetch(query)
        return [cls.from_dict(dict(row)) for row in rows]

    async def update(self, database_instance=None, **kwargs):
        """更新当前实例"""
        db_instance = database_instance or db
        if db_instance is None:
            raise ValueError("Database instance is not initialized.")

        if not self._primary_key:
            raise ValueError(f"Model {self.__class__.__name__} has no primary key defined")

        # 更新实例属性
        for key, value in kwargs.items():
            if key in self._fields:
                setattr(self, key, value)

        # 构建UPDATE查询
        data = self.to_dict()
        primary_key_value = data.pop(self._primary_key)

        if not data:  # 如果没有要更新的字段
            return

        set_clauses = ', '.join(f'"{col}" = ${i+1}' for i, col in enumerate(data.keys()))
        values = list(data.values()) + [primary_key_value]
        query = f'UPDATE "{self._table_name}" SET {set_clauses} WHERE "{self._primary_key}" = ${len(data)+1}'

        return await db_instance._execute(query, *values)

    async def delete(self, database_instance=None):
        """删除当前实例"""
        db_instance = database_instance or db
        if db_instance is None:
            raise ValueError("Database instance is not initialized.")

        if not self._primary_key:
            raise ValueError(f"Model {self.__class__.__name__} has no primary key defined")

        primary_key_value = getattr(self, self._primary_key)
        query = f'DELETE FROM "{self._table_name}" WHERE "{self._primary_key}" = $1'

        return await db_instance._execute(query, primary_key_value)

    async def get_related(self, field_name: str, database_instance=None):
        """获取外键关联的对象"""
        db_instance = database_instance or db
        if db_instance is None:
            raise ValueError("Database instance is not initialized.")

        if field_name not in self._foreign_keys:
            raise ValueError(f"Field {field_name} is not a foreign key")

        foreign_key_value = getattr(self, field_name)
        if foreign_key_value is None:
            return None

        fk_info = self._foreign_keys[field_name]
        reference_table = fk_info['reference_table']
        reference_field = fk_info['reference_field']

        query = f'SELECT * FROM "{reference_table}" WHERE "{reference_field}" = $1'
        row = await db_instance._fetchrow(query, foreign_key_value)

        if row:
            # 这里简化处理，返回字典，实际应该返回对应的模型实例
            return dict(row)
        return None

    @classmethod
    async def find_by_foreign_key(cls, field_name: str, foreign_key_value, database_instance=None):
        """根据外键值查找所有相关记录"""
        db_instance = database_instance or db
        if db_instance is None:
            raise ValueError("Database instance is not initialized.")

        if field_name not in cls._foreign_keys:
            raise ValueError(f"Field {field_name} is not a foreign key in {cls.__name__}")

        query = f'SELECT * FROM "{cls._table_name}" WHERE "{field_name}" = $1'
        rows = await db_instance._fetch(query, foreign_key_value)

        return [cls.from_dict(dict(row)) for row in rows]