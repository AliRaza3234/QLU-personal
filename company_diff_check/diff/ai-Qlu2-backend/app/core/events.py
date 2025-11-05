import os
import asyncio
import logging
from typing import Callable
from elasticsearch import ApiError
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from qutils.database.post_gres import DatabaseConnection
from qutils.database.elastic_search import ElasticsearchConnection
from asyncio import current_task
import aiomysql
import redis.asyncio as aioredis
from qdrant_client import AsyncQdrantClient
from sqlalchemy.engine.url import URL
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_scoped_session,
    create_async_engine,
)

from app.utils.search.aisearch.company.generation.p2p import init_background_processes
from app.core.config import (
    POOL_SIZE,
    POOL_OVERFLOW,
    POOL_TIMEOUT,
    POOL_RECYCLE,
    POOL_PRE_PING,
)

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger("app")
logger.setLevel(logging.INFO)

for noisy in ("httpx", "elastic_transport", "elasticsearch", "urllib3"):
    logging.getLogger(noisy).setLevel(logging.WARNING)


async def _close_mysql_pool(pool, *, timeout: float = 3.0) -> None:
    if not pool:
        return

    pool.close()
    try:
        await asyncio.wait_for(pool.wait_closed(), timeout=timeout)
    except (RuntimeError, asyncio.TimeoutError) as exc:
        logger.warning(
            "MySQL pool could not complete graceful shutdown (%s). "
            "Continuing teardown.",
            exc.__class__.__name__,
        )


async def _close_redis_client(redis_client, *, timeout: float = 3.0) -> None:
    if not redis_client:
        return

    try:
        await asyncio.wait_for(redis_client.aclose(), timeout=timeout)
    except (RuntimeError, asyncio.TimeoutError, AttributeError) as exc:
        logger.warning(
            "Redis client could not complete graceful shutdown (%s). "
            "Continuing teardown.",
            exc.__class__.__name__,
        )


async def _close_qdrant_client(qdrant_client, *, timeout: float = 3.0) -> None:
    if not qdrant_client:
        return

    try:
        await asyncio.wait_for(qdrant_client.close(), timeout=timeout)
    except (RuntimeError, asyncio.TimeoutError, AttributeError) as exc:
        logger.warning(
            "Qdrant client could not complete graceful shutdown (%s). "
            "Continuing teardown.",
            exc.__class__.__name__,
        )


class ExceptionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as e:
            return JSONResponse(status_code=500, content={"detail": str(e)})


class ElasticsearchMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        app = request.app
        if not getattr(app.state, "elasticsearch", None):
            await self._reinitialize_es(app)

        try:
            await app.state.elasticsearch.ping()
        except ApiError:
            logger.warning("Elasticsearch client is unavailable. Reconnecting…")
            await self._reinitialize_es(app)

        return await call_next(request)

    async def _reinitialize_es(self, app: FastAPI):
        es_connection = ElasticsearchConnection()
        app.state.elasticsearch = await es_connection.get_elasticsearch_client()
        logger.info("ELASTICSEARCH CLIENT HAS BEEN RE-INSTANTIATED 🛸")


class PostgresMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        app = request.app
        if not getattr(app.state, "postgres", None):
            await self._reinitialize_db(app)

        try:
            async with app.state.postgres.cursor() as cursor:
                await cursor.execute("SELECT 1")
                await cursor.fetchone()
        except Exception as e:
            logger.warning(f"Database connection is unavailable: {e}. Reconnecting…")
            await self._reinitialize_db(app)

        return await call_next(request)

    async def _reinitialize_db(self, app: FastAPI):
        db_connection = DatabaseConnection()
        app.state.postgres = await db_connection.get_database_connection_fs()
        logger.info("POSTGRES CLIENT HAS BEEN RE-INSTANTIATED 🛸")


class MySQLMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        app = request.app
        if not getattr(app.state, "mysql_pool", None):
            await self._reinitialize_mysql(app)

        try:
            async with app.state.mysql_pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT 1")
                    await cursor.fetchone()
        except Exception as e:
            logger.warning(f"MySQL connection is unavailable: {e}. Reconnecting…")
            await self._reinitialize_mysql(app)

        return await call_next(request)

    async def _reinitialize_mysql(self, app: FastAPI):
        await _close_mysql_pool(getattr(app.state, "mysql_pool", None))

        app.state.mysql_pool = await aiomysql.create_pool(
            host=os.getenv("MYSQL_HOST"),
            port=int(os.getenv("MYSQL_PORT")),
            minsize=50,
            maxsize=100,
            autocommit=True,
        )
        logger.info("MYSQL CONNECTION POOL HAS BEEN INSTANTIATED 🚀")


class RedisMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        app = request.app
        if not getattr(app.state, "redis", None):
            await self._reinitialize_redis(app)

        try:
            await app.state.redis.ping()
        except Exception as e:
            logger.warning(f"Redis connection is unavailable: {e}. Reconnecting…")
            await self._reinitialize_redis(app)

        return await call_next(request)

    async def _reinitialize_redis(self, app: FastAPI):
        await _close_redis_client(getattr(app.state, "redis", None))

        app.state.redis = aioredis.from_url(
            f"redis://{os.getenv('REDIS_IP')}:{os.getenv('REDIS_PORT')}",
            max_connections=int(os.getenv("REDIS_MAX_CONNECTIONS", "50")),
            retry_on_timeout=True,
            decode_responses=True,
            health_check_interval=30,
            socket_connect_timeout=5,
            socket_timeout=5,
        )

        logger.info("REDIS CLIENT WITH CONNECTION POOL HAS BEEN RE-INSTANTIATED 🛸")


class QdrantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        app = request.app
        if not getattr(app.state, "qdrant", None):
            await self._reinitialize_qdrant(app)

        try:
            await app.state.qdrant.get_collections()
        except Exception as e:
            logger.warning(f"Qdrant connection is unavailable: {e}. Reconnecting…")
            await self._reinitialize_qdrant(app)

        return await call_next(request)

    async def _reinitialize_qdrant(self, app: FastAPI):
        await _close_qdrant_client(getattr(app.state, "qdrant", None))

        app.state.qdrant = AsyncQdrantClient(
            url=os.getenv("QDRANT_URL"),
            https=False,
            timeout=10,
            check_compatibility=False,
        )
        logger.info("QDRANT CLIENT HAS BEEN RE-INSTANTIATED 🛸")


def create_start_app_handler(app: FastAPI) -> Callable:
    async def start_app() -> None:
        es_connection = ElasticsearchConnection()
        app.state.elasticsearch = await es_connection.get_elasticsearch_client()
        logger.info("ELASTICSEARCH CLIENT HAS BEEN INSTANTIATED 🚀")

        db_connection = DatabaseConnection()
        app.state.postgres = await db_connection.get_database_connection_fs()
        logger.info("POSTGRES CLIENT HAS BEEN INSTANTIATED 🚀")

        app.state.mysql_pool = await aiomysql.create_pool(
            host=os.getenv("MYSQL_HOST"),
            port=int(os.getenv("MYSQL_PORT")),
            minsize=50,
            maxsize=100,
            autocommit=True,
        )
        logger.info("MYSQL CONNECTION POOL HAS BEEN INSTANTIATED 🚀")

        app.state.redis = aioredis.from_url(
            f"redis://{os.getenv('REDIS_IP')}:{os.getenv('REDIS_PORT')}",
            max_connections=int(os.getenv("REDIS_MAX_CONNECTIONS", "50")),
            retry_on_timeout=True,
            decode_responses=True,
            health_check_interval=30,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        logger.info("REDIS CLIENT WITH CONNECTION POOL HAS BEEN INSTANTIATED 🚀")

        app.state.qdrant = AsyncQdrantClient(
            url=os.getenv("QDRANT_URL"),
            https=False,
            timeout=10,
            check_compatibility=False,
        )
        logger.info("QDRANT CLIENT HAS BEEN INSTANTIATED 🚀")

        app.state.sqlalchemy_engine_ai = create_async_engine(
            URL.create(
                drivername="postgresql+asyncpg",
                username=os.getenv("DB_USERNAME"),
                password=os.getenv("DB_PASSWORD"),
                host=os.getenv("DB_HOST"),
                database=os.getenv("DB_DATABASE"),
                port="5432",
            ),
            pool_size=POOL_SIZE,
            max_overflow=POOL_OVERFLOW,
            pool_timeout=POOL_TIMEOUT,
            pool_recycle=POOL_RECYCLE,
            pool_pre_ping=POOL_PRE_PING,
        )
        app.state.sqlalchemy_session_ai = async_scoped_session(
            sessionmaker(
                bind=app.state.sqlalchemy_engine_ai,
                class_=AsyncSession,
                expire_on_commit=False,
            ),
            scopefunc=current_task,
        )
        logger.info("SQLALCHEMY ENGINE AND SESSION HAVE BEEN INSTANTIATED 🚀")

        await init_background_processes(app)
        logger.info("BACKGROUND COMPANY INGESTION PIPELINE HAS BEEN INSTANTIATED 🚀")

    return start_app


def create_stop_app_handler(app: FastAPI) -> Callable:
    async def stop_app() -> None:
        for task_name in ("ingestion_task", "scheduled_check_task"):
            task = getattr(app.state, task_name, None)
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        if getattr(app.state, "elasticsearch", None):
            await app.state.elasticsearch.close()
            logger.info("ELASTICSEARCH CLIENT HAS BEEN CLOSED 🚫")

        if getattr(app.state, "postgres", None):
            await app.state.postgres.close()
            logger.info("POSTGRES CLIENT HAS BEEN CLOSED 🚫")

        if getattr(app.state, "sqlalchemy_engine_ai", None):
            await app.state.sqlalchemy_engine_ai.dispose()
            logger.info("SQLALCHEMY ENGINE HAS BEEN DISPOSED 🚫")

        await _close_mysql_pool(getattr(app.state, "mysql_pool", None))
        app.state.mysql_pool = None
        logger.info("MYSQL POOL HAS BEEN CLOSED 🚫")

        await _close_redis_client(getattr(app.state, "redis", None))
        app.state.redis = None
        logger.info("REDIS CLIENT HAS BEEN CLOSED 🚫")

        await _close_qdrant_client(getattr(app.state, "qdrant", None))
        app.state.qdrant = None
        logger.info("QDRANT CLIENT HAS BEEN CLOSED 🚫")

    return stop_app
