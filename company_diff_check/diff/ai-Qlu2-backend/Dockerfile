# syntax=docker/dockerfile:1.4


FROM python:3.11 AS builder

ARG branch

ARG POETRY_VERSION=1.7.1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends git openssh-client curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip setuptools wheel virtualenv==20.26.2 && \
    pip install --no-cache-dir "poetry==1.8.2" && \
    poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock* ./

RUN --mount=type=cache,target=/root/.cache/pip \
    poetry install --only main --no-interaction --no-ansi --no-root

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir hypercorn==0.16.0

RUN mkdir -p -m 0700 /root/.ssh 

RUN --mount=type=cache,target=/root/.cache/pip \
    --mount=type=secret,id=known_hosts,target=/root/.ssh/known_hosts,mode=0400 \
    --mount=type=secret,id=ssh_key,target=/root/.ssh/id_rsa,mode=0400 \
    pip install --no-cache-dir \
    git+ssh://git@github.com/dnnaeinc/ai-Qlu2-library@${branch}#egg=qutils

RUN python3 -c "import qutils.llm.agents.industry"

COPY . .

FROM python:3.11-slim AS runtime

WORKDIR /app

ENV PYTHONPATH="/usr/local/lib/python3.11/site-packages:$PYTHONPATH"

ENV REDIS_IP="10.38.15.115"
ENV REDIS_PORT="6379"

ENV MYSQL_HOST="10.128.0.26"
ENV MYSQL_PORT="9306"

COPY --from=builder /usr/local/lib/python3.11/site-packages \
    /usr/local/lib/python3.11/site-packages

COPY --from=builder /usr/local/bin /usr/local/bin

COPY --from=builder /app .

EXPOSE 8000

CMD ["sh", "-c", "hypercorn main:app --bind 0.0.0.0:${PORT:-8000}"]

FROM runtime AS test

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-cache-dir pytest pytest-xdist pytest-asyncio

ENTRYPOINT ["pytest"]
CMD ["-h"]