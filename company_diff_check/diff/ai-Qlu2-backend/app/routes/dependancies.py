from fastapi import Request
from typing import AsyncIterator
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio.session import AsyncSession


def get_es_client(request: Request):
    return request.app.state.elasticsearch


def get_db_client(request: Request):
    return request.app.state.postgres


def get_mysql_pool(request: Request):
    return request.app.state.mysql_pool


def get_redis_client(request: Request):
    return request.app.state.redis


def get_qdrant_client(request: Request) -> AsyncQdrantClient:
    return request.app.state.qdrant


@asynccontextmanager
async def get_redis_connection(request: Request) -> AsyncIterator[aioredis.Redis]:
    redis_client = request.app.state.redis
    try:
        yield redis_client
    finally:
        pass


@asynccontextmanager
async def get_sqlalchemy_session_ai() -> AsyncIterator[AsyncSession]:
    from main import app

    session = app.state.sqlalchemy_session_ai()
    try:
        yield session
    finally:
        await session.close()
