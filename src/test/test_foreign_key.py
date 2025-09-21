"""
vibe generate
"""
import pytest
import pytest_asyncio
import os
from dotenv import load_dotenv
from ..orm.model import BaseModel, Field, FieldType, ForeignKey
from ..orm.db import Database

# 加载环境变量
load_dotenv()


# 定义测试模型
class User(BaseModel):
    """用户模型"""
    id = Field(FieldType.INT, primary_key=True, nullable=False)
    username = Field(FieldType.VARCHAR, unique=True, nullable=False)
    email = Field(FieldType.TEXT, unique=True, nullable=False)


class Category(BaseModel):
    """分类模型"""
    id = Field(FieldType.INT, primary_key=True, nullable=False)
    name = Field(FieldType.VARCHAR, unique=True, nullable=False)
    description = Field(FieldType.TEXT, nullable=True)


class Post(BaseModel):
    """文章模型 - 包含外键"""
    id = Field(FieldType.INT, primary_key=True, nullable=False)
    title = Field(FieldType.VARCHAR, nullable=False)
    content = Field(FieldType.TEXT, nullable=True)
    user_id = Field(FieldType.INT, nullable=False, foreign_key=ForeignKey("User", "id"))
    category_id = Field(FieldType.INT, nullable=True, foreign_key=ForeignKey("Category", "id"))


class Comment(BaseModel):
    """评论模型 - 多层外键"""
    id = Field(FieldType.INT, primary_key=True, nullable=False)
    content = Field(FieldType.TEXT, nullable=False)
    post_id = Field(FieldType.INT, nullable=False, foreign_key=ForeignKey("Post", "id"))
    user_id = Field(FieldType.INT, nullable=False, foreign_key=ForeignKey("User", "id"))


@pytest_asyncio.fixture
async def database():
    """提供数据库连接的fixture"""
    db = Database()
    await db.initialize_pool()
    yield db
    # 清理测试表（注意顺序：先删除有外键的表）
    try:
        await db.drop_table("comment")
        await db.drop_table("post")
        await db.drop_table("category")
        await db.drop_table("user")
    except:
        pass
    await db.close_pool()


# @pytest.mark.asyncio
# async def test_foreign_key_definition():
#     """测试外键定义"""
#     # 验证Post模型的外键定义
#     foreign_keys = Post.get_foreign_keys()

#     assert "user_id" in foreign_keys
#     assert "category_id" in foreign_keys

#     user_fk = foreign_keys["user_id"]
#     assert user_fk["reference_table"] == "user"
#     assert user_fk["reference_field"] == "id"
#     assert user_fk["on_delete"] == "CASCADE"
#     assert user_fk["on_update"] == "CASCADE"

#     category_fk = foreign_keys["category_id"]
#     assert category_fk["reference_table"] == "category"
#     assert category_fk["reference_field"] == "id"


# @pytest.mark.asyncio
# async def test_create_tables_with_foreign_keys(database):
#     """测试创建带外键的表"""
#     # 按依赖顺序创建表
#     await User.ensure_table_exists(database)
#     await Category.ensure_table_exists(database)
#     await Post.ensure_table_exists(database)
#     await Comment.ensure_table_exists(database)

#     # 验证表已创建
#     tables = ["user", "category", "post", "comment"]
#     for table_name in tables:
#         result = await database._fetch(
#             f"SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name = '{table_name}';"
#         )
#         assert len(result) > 0, f"Table {table_name} was not created"


@pytest.mark.asyncio
async def test_foreign_key_crud_operations(database):
    """测试外键CRUD操作"""
    # 按依赖顺序创建表
    await User.ensure_table_exists(database)
    await Category.ensure_table_exists(database)
    await Post.ensure_table_exists(database)

    # 1. 创建用户
    user = User(id=1, username="testuser", email="test@example.com")
    await user.save(database)

    # 2. 创建分类
    category = Category(id=1, name="Tech", description="Technology posts")
    await category.save(database)

    # 3. 创建文章（引用用户和分类）
    post = Post(
        id=1,
        title="Test Post",
        content="This is a test post",
        user_id=1,
        category_id=1
    )
    await post.save(database)

    # 4. 验证文章已保存
    saved_post = await Post.find_by_id(1, database)
    assert saved_post is not None
    assert saved_post.title == "Test Post"
    assert saved_post.user_id == 1
    assert saved_post.category_id == 1


@pytest.mark.asyncio
async def test_foreign_key_constraints(database):
    """测试外键约束"""
    # 创建表（按依赖顺序）
    await User.ensure_table_exists(database)
    await Category.ensure_table_exists(database)
    await Post.ensure_table_exists(database)

    # 创建用户
    user = User(id=1, username="testuser", email="test@example.com")
    await user.save(database)

    # 尝试创建引用不存在用户的文章 - 这应该会失败
    invalid_post = Post(
        id=1,
        title="Invalid Post",
        content="This post references non-existent user",
        user_id=999  # 不存在的用户ID
    )

    # 这应该会因为外键约束失败
    with pytest.raises(Exception):  # asyncpg会抛出外键约束错误
        await invalid_post.save(database)


@pytest.mark.asyncio
async def test_find_by_foreign_key(database):
    """测试根据外键查找"""
    # 创建表（按依赖顺序）
    await User.ensure_table_exists(database)
    await Category.ensure_table_exists(database)
    await Post.ensure_table_exists(database)

    # 创建用户
    user = User(id=1, username="author", email="author@example.com")
    await user.save(database)

    # 创建多篇文章
    posts_data = [
        {"id": 1, "title": "Post 1", "content": "Content 1", "user_id": 1},
        {"id": 2, "title": "Post 2", "content": "Content 2", "user_id": 1},
        {"id": 3, "title": "Post 3", "content": "Content 3", "user_id": 1},
    ]

    for post_data in posts_data:
        post = Post(**post_data)
        await post.save(database)

    # 查找用户的所有文章
    user_posts = await Post.find_by_foreign_key("user_id", 1, database)

    assert len(user_posts) == 3
    titles = [post.title for post in user_posts]
    assert "Post 1" in titles
    assert "Post 2" in titles
    assert "Post 3" in titles


@pytest.mark.asyncio
async def test_get_related_object(database):
    """测试获取关联对象"""
    # 创建表（按依赖顺序）
    await User.ensure_table_exists(database)
    await Category.ensure_table_exists(database)
    await Post.ensure_table_exists(database)

    # 创建用户
    user = User(id=1, username="author", email="author@example.com")
    await user.save(database)

    # 创建文章
    post = Post(
        id=1,
        title="Test Post",
        content="Test content",
        user_id=1
    )
    await post.save(database)

    # 获取文章关联的用户
    related_user = await post.get_related("user_id", database)

    assert related_user is not None
    assert related_user["id"] == 1
    assert related_user["username"] == "author"
    assert related_user["email"] == "author@example.com"


@pytest.mark.asyncio
async def test_cascade_delete_behavior(database):
    """测试级联删除行为"""
    # 创建表（按正确的依赖顺序）
    await User.ensure_table_exists(database)
    await Category.ensure_table_exists(database)
    await Post.ensure_table_exists(database)
    await Comment.ensure_table_exists(database)

    # 创建用户
    user = User(id=1, username="author", email="author@example.com")
    await user.save(database)

    # 创建文章
    post = Post(
        id=1,
        title="Test Post",
        content="Test content",
        user_id=1
    )
    await post.save(database)

    # 创建评论
    comment = Comment(
        id=1,
        content="Great post!",
        post_id=1,
        user_id=1
    )
    await comment.save(database)

    # 验证数据存在
    saved_user = await User.find_by_id(1, database)
    saved_post = await Post.find_by_id(1, database)
    saved_comment = await Comment.find_by_id(1, database)

    assert saved_user is not None
    assert saved_post is not None
    assert saved_comment is not None

    # 删除用户（应该级联删除文章和评论）
    await user.delete(database)

    # 验证级联删除
    deleted_user = await User.find_by_id(1, database)
    deleted_post = await Post.find_by_id(1, database)  # 应该被级联删除
    deleted_comment = await Comment.find_by_id(1, database)  # 应该被级联删除

    assert deleted_user is None
    assert deleted_post is None
    assert deleted_comment is None
    #@todo 完善测试
    # 注意：具体的级联行为取决于数据库设置和外键约束
    # 这里可能需要根据实际数据库配置调整断言


#@todo 略过审查
@pytest.mark.asyncio
async def test_complex_foreign_key_relationships(database):
    """测试复杂的外键关系"""
    # 创建所有表
    await User.ensure_table_exists(database)
    await Category.ensure_table_exists(database)
    await Post.ensure_table_exists(database)
    await Comment.ensure_table_exists(database)

    # 创建测试数据
    # 用户
    users_data = [
        {"id": 1, "username": "author1", "email": "author1@example.com"},
        {"id": 2, "username": "author2", "email": "author2@example.com"},
    ]

    for user_data in users_data:
        user = User(**user_data)
        await user.save(database)

    # 分类
    categories_data = [
        {"id": 1, "name": "Tech", "description": "Technology"},
        {"id": 2, "name": "Science", "description": "Science"},
    ]

    for category_data in categories_data:
        category = Category(**category_data)
        await category.save(database)

    # 文章
    posts_data = [
        {"id": 1, "title": "Tech Post 1", "content": "Tech content", "user_id": 1, "category_id": 1},
        {"id": 2, "title": "Science Post 1", "content": "Science content", "user_id": 2, "category_id": 2},
    ]

    for post_data in posts_data:
        post = Post(**post_data)
        await post.save(database)

    # 评论
    comments_data = [
        {"id": 1, "content": "Great tech post!", "post_id": 1, "user_id": 2},
        {"id": 2, "content": "Interesting science!", "post_id": 2, "user_id": 1},
        {"id": 3, "content": "More tech comments", "post_id": 1, "user_id": 1},
    ]

    for comment_data in comments_data:
        comment = Comment(**comment_data)
        await comment.save(database)

    # 测试复杂查询
    # 查找第一篇文章的所有评论
    post1_comments = await Comment.find_by_foreign_key("post_id", 1, database)
    assert len(post1_comments) == 2

    # 查找用户1的所有评论
    user1_comments = await Comment.find_by_foreign_key("user_id", 1, database)
    assert len(user1_comments) == 2  # 用户1有2条评论：id=2 和 id=3

    # 查找用户1的所有文章
    user1_posts = await Post.find_by_foreign_key("user_id", 1, database)
    assert len(user1_posts) == 1
    # 通过 to_dict() 访问字段值
    post_dict = user1_posts[0].to_dict()
    assert post_dict["title"] == "Tech Post 1"