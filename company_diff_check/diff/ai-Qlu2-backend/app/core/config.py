import os

if os.getenv("ENVIRONMENT") == "production":
    POOL_SIZE = 40
    POOL_OVERFLOW = 20
else:
    POOL_SIZE = 20
    POOL_OVERFLOW = 10
POOL_TIMEOUT = 30
POOL_RECYCLE = 1800
POOL_PRE_PING = True
POOL_SIZE = 10
POOL_OVERFLOW = 20
POOL_TIMEOUT = 30
POOL_RECYCLE = 3600
POOL_PRE_PING = True

REDIS_CONFIG = {
    "host": os.getenv("REDIS_IP", "localhost"),
    "port": int(os.getenv("REDIS_PORT", "6379")),
    "max_connections": int(os.getenv("REDIS_MAX_CONNECTIONS", "50")),
    "min_connections": int(os.getenv("REDIS_MIN_CONNECTIONS", "5")),
    "retry_on_timeout": True,
    "decode_responses": True,
    "health_check_interval": int(os.getenv("REDIS_HEALTH_CHECK_INTERVAL", "30")),
    "socket_connect_timeout": int(os.getenv("REDIS_CONNECT_TIMEOUT", "5")),
    "socket_timeout": int(os.getenv("REDIS_SOCKET_TIMEOUT", "5")),
    "connection_pool_kwargs": {
        "max_connections": int(os.getenv("REDIS_MAX_CONNECTIONS", "50")),
        "retry_on_timeout": True,
        "socket_keepalive": True,
        "socket_keepalive_options": {},
    },
}

REDIS_URL = f"redis://{REDIS_CONFIG['host']}:{REDIS_CONFIG['port']}"

if os.getenv("REDIS_PASSWORD"):
    REDIS_URL = f"redis://:{os.getenv('REDIS_PASSWORD')}@{REDIS_CONFIG['host']}:{REDIS_CONFIG['port']}"

if os.getenv("REDIS_DB"):
    REDIS_URL += f"/{os.getenv('REDIS_DB')}"
