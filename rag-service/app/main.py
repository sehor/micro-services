"""
应用入口：初始化 FastAPI 应用、路由与启动事件。
"""
import logging
from fastapi import FastAPI
from sqlalchemy import text
from .config import DB_AUTO_CREATE
from .db import engine, Base
from .routers.ingest import router as ingest_router
from .routers.search import router as search_router
from .routers.docs import router as docs_router


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用"""
    app = FastAPI(title="RAG Service", version="0.1.0")

    # 注册路由
    app.include_router(ingest_router)
    app.include_router(search_router)
    app.include_router(docs_router)

    @app.on_event("startup")
    async def on_startup():
        """启动事件：按需建表并创建向量索引"""
        async with engine.begin() as conn:
            if DB_AUTO_CREATE:
                await conn.run_sync(Base.metadata.create_all)
                logging.getLogger(__name__).info("数据库表已创建/检查完成")

            # 确保 pgvector 扩展存在
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

            # 仅当 documents.embedding 列类型是 vector 时才尝试创建 HNSW 索引；如为 double precision[] 则尝试迁移
            result = await conn.execute(
                text(
                    """
                    SELECT atttypid::regtype::text AS type_name
                    FROM pg_attribute a
                    JOIN pg_class c ON c.oid = a.attrelid
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'public' AND c.relname = 'documents' AND a.attname = 'embedding' AND a.attnum > 0
                    """
                )
            )
            type_name = result.scalar_one_or_none()

            # 若为旧类型（double precision[]），尝试在线迁移到 vector(1024)
            if type_name == "double precision[]":
                try:
                    await conn.execute(
                        text(
                            "ALTER TABLE documents ALTER COLUMN embedding TYPE vector(1024) USING (embedding::vector(1024))"
                        )
                    )
                    logging.getLogger(__name__).info("已将 documents.embedding 从 double precision[] 迁移为 vector(1024)")
                    type_name = "vector(1024)"
                except Exception as e:
                    logging.getLogger(__name__).exception("向量列类型迁移失败: %s", e)
                    # 明确终止启动，避免运行期插入/查询失败
                    raise RuntimeError(
                        "数据库列类型迁移失败：documents.embedding 仍为 double precision[]，请手动迁移或清空后重建。"
                    )

            if type_name and type_name.startswith("vector"):
                # 为 documents.embedding 创建 HNSW 索引（若不存在）
                await conn.execute(
                    text(
                        """
                        DO $$
                        BEGIN
                            IF NOT EXISTS (
                                SELECT 1 FROM pg_class c
                                JOIN pg_namespace n ON n.oid = c.relnamespace
                                WHERE c.relname = 'idx_documents_embedding_hnsw'
                                  AND n.nspname = 'public'
                            ) THEN
                                CREATE INDEX idx_documents_embedding_hnsw
                                ON documents USING hnsw (embedding vector_l2_ops)
                                WITH (m = 16, ef_construction = 64);
                            END IF;
                        END $$;
                        """
                    )
                )
                logging.getLogger(__name__).info("HNSW 向量索引已存在或创建完成")
            else:
                logging.getLogger(__name__).warning(
                    "跳过创建 HNSW 索引：documents.embedding 当前类型为 %s（需要为 vector）",
                    type_name,
                )

    @app.get("/health")
    async def health() -> dict:
        """存活探针：用于容器与网关健康检查"""
        return {"status": "ok"}

    return app


app = create_app()