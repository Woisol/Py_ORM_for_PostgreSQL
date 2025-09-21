
import os
import re
from typing import Any, Dict, Type, get_type_hints

from src.orm.db import Database, db, FieldType


class Field:
    """字段描述符"""
    def __init__(self, field_type: FieldType, nullable: bool = True, default: Any = None,
                 primary_key: bool = False, unique: bool = False):
        self.field_type = field_type
        self.nullable = nullable
        self.default = default
        self.primary_key = primary_key
        self.unique = unique
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

        # 自动收集字段
        fields = {}
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

                fields[attr_name] = field_def

        # 如果没有显式字段，尝试从类型注解推断
        if not fields:
            # 获取类型注解
            annotations = namespace.get('__annotations__', {})
            for attr_name, attr_type in annotations.items():
                if not attr_name.startswith('_'):  # 跳过私有属性
                    field_type = cls._infer_field_type(attr_type)
                    if field_type:
                        fields[attr_name] = field_type.value

        namespace['_fields'] = fields
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
    _primary_key: str | None

    def __init__(self, **kwargs):
        # 设置默认属性
        self._indexes = []
        self._unique_constraints = []
        self._foreign_keys = []
        self._created_at_field = None
        self._updated_at_field = None
        self._deleted_at_field = None

        # 设置字段值
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    @classmethod
    async def ensure_table_exists(cls, database_instance=None):
        """确保表已创建"""
        #!  行吧必须支持传入 db 示例否则测试报错
        db_instance = database_instance or db
        if db_instance is None:
            raise ValueError("Database instance is not initialized.")
        await db_instance.create_table(cls._table_name, cls._fields)

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