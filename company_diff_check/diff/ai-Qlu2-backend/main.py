from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware

from app.api import router as api_router

from app.core.events import (
    PostgresMiddleware,
    ElasticsearchMiddleware,
    MySQLMiddleware,
    RedisMiddleware,
    QdrantMiddleware,
    ExceptionMiddleware,
    create_start_app_handler,
    create_stop_app_handler,
)

from app.core.auth import AuthMiddleware, API_KEY_NAME

import uvicorn

app = FastAPI()

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*", API_KEY_NAME],
)

app.add_middleware(AuthMiddleware)

app.add_middleware(ExceptionMiddleware)

app.add_middleware(PostgresMiddleware)

app.add_middleware(ElasticsearchMiddleware)

app.add_middleware(MySQLMiddleware)

app.add_middleware(RedisMiddleware)

app.add_middleware(QdrantMiddleware)

app.add_event_handler("startup", create_start_app_handler(app))

app.add_event_handler("shutdown", create_stop_app_handler(app))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
