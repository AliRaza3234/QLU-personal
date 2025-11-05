import json
from typing import Any, Optional
from datetime import datetime, timedelta

from sqlalchemy.sql import text
from app.routes.dependancies import get_sqlalchemy_session_ai


async def postgres_fetch(query: str) -> Any:
    async with get_sqlalchemy_session_ai() as session:
        try:
            result = await session.execute(text(query))
            return result.fetchone()
        except Exception as e:
            print(f"Error in fetching: {e}, Exception type: {type(e)}")
        return None


async def postgres_fetch_all(query: str) -> Optional[list]:
    async with get_sqlalchemy_session_ai() as session:
        try:
            records = await session.execute(text(query))
            return records.fetchall()
        except Exception as e:
            await session.rollback()
            print(f"An error occurred: {e}")
            return None


async def postgres_insert(query: str) -> bool:
    async with get_sqlalchemy_session_ai() as session:
        try:
            await session.execute(text(query))
            await session.commit()
            return True
        except Exception as e:
            await session.rollback()
            print(f"An error occurred: {e}")
            return False


async def postgres_insert_tuples(query: str, params: tuple) -> bool:
    async with get_sqlalchemy_session_ai() as session:
        try:
            await session.execute(text(query), params)
            await session.commit()
        except Exception as e:
            await session.rollback()
            print(f"An error occurred: {e}")


async def postgres_delete(query: str) -> bool:
    async with get_sqlalchemy_session_ai() as session:
        try:
            await session.execute(text(query))
            await session.commit()
            return True
        except Exception as e:
            await session.rollback()
            print(f"An error occurred: {e}")
            return False


async def delete_cached_data(key: str, table: str) -> None:
    key = key.replace("'", "''")
    async with get_sqlalchemy_session_ai() as session:
        try:
            await session.execute(text(f"DELETE FROM {table} WHERE key='{key}'"))
            await session.commit()
        except Exception as e:
            await session.rollback()
            print(f"An error occurred: {e}")


async def get_cached_data(key: str, table: str) -> Optional[Any]:
    key = key.replace("'", "''")
    async with get_sqlalchemy_session_ai() as session:
        try:
            records = await session.execute(
                text(
                    f"SELECT value, cache_date, expiration_days FROM {table} WHERE key='{key}'"
                )
            )
            record = records.fetchone()

            if record is None or len(record) == 0:
                return None

            value, cache_date, expiration_days = record

            if expiration_days == 2147483647:
                expiration_days = 3650

            expiration = False
            if cache_date and expiration_days:
                expiration_date = cache_date + timedelta(days=expiration_days)
                current_date = datetime.utcnow()
                if current_date > expiration_date:
                    expiration = True

            if expiration:
                await delete_cached_data(key, table)

            return value

        except Exception as e:
            await session.rollback()
            print(f"An error occurred: {e}")
            return None


async def cache_data(
    key: str, value: Any, table: str, expiration_days: Optional[int] = None
) -> None:
    if expiration_days is None:
        expiration_days = 3650

    value_json = json.dumps(value)

    async with get_sqlalchemy_session_ai() as session:
        try:
            await session.execute(
                text(
                    f"""
                    INSERT INTO {table} (key, value, cache_date, expiration_days)
                    VALUES (:key, :value, :cache_date, :expiration_days)
                    ON CONFLICT (key) DO UPDATE
                    SET value = EXCLUDED.value, cache_date = EXCLUDED.cache_date, expiration_days = EXCLUDED.expiration_days;
                    """
                ),
                {
                    "key": key,
                    "value": value_json,
                    "cache_date": datetime.utcnow(),
                    "expiration_days": expiration_days,
                },
            )
            await session.commit()
        except Exception as e:
            await session.rollback()
            print(f"An error occurred: {e}")
