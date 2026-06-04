"""Redis-backed job queue for expensive agent workloads.

This queue handles LLM inference, document ingestion, and MCP tool calls with
bounded retries and request-scoped result tracking.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import Any, Awaitable, Callable
from urllib.parse import urlparse

try:
    import redis.asyncio as redis
except ImportError:  # pragma: no cover - optional dependency
    redis = None

try:
    from arq.connections import ArqRedis, RedisSettings, create_pool
    from arq.worker import func
except ImportError:  # pragma: no cover - optional dependency
    ArqRedis = None
    RedisSettings = None
    create_pool = None
    func = None


QUEUE_PREFIX = os.getenv("QUEUE_PREFIX", "ethioclaw:queue")
QUEUE_RESULT_PREFIX = os.getenv("QUEUE_RESULT_PREFIX", "ethioclaw:queue:result")
QUEUE_POLL_INTERVAL = float(os.getenv("QUEUE_POLL_INTERVAL", "0.25"))
QUEUE_JOB_TIMEOUT = int(os.getenv("QUEUE_JOB_TIMEOUT", "120"))
QUEUE_RETRY_LIMIT = int(os.getenv("QUEUE_RETRY_LIMIT", "3"))
LLM_QUEUE_CONCURRENCY = int(os.getenv("LLM_QUEUE_CONCURRENCY", "3"))
DOC_QUEUE_CONCURRENCY = int(os.getenv("DOC_QUEUE_CONCURRENCY", "1"))
MCP_QUEUE_CONCURRENCY = int(os.getenv("MCP_QUEUE_CONCURRENCY", "1"))
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
QUEUE_BACKEND = os.getenv("QUEUE_BACKEND", "local").lower()


def _json_default(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    return str(value)


def _normalize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _normalize_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize_value(item) for item in value]
    if hasattr(value, "model_dump"):
        return _normalize_value(value.model_dump())
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    return value


def _deserialize_bytes(value: str | None) -> bytes:
    if not value:
        return b""
    return base64.b64decode(value.encode("ascii"))


def _redis_settings_from_url(url: str):
    parsed = urlparse(url)
    database = int(parsed.path.lstrip("/") or 0)
    username = parsed.username
    password = parsed.password
    host = parsed.hostname or "localhost"
    port = parsed.port or 6379

    if RedisSettings is None:
        return None

    return RedisSettings(
        host=host,
        port=port,
        database=database,
        username=username,
        password=password,
    )


def _log_queue_event(event: str, payload: dict[str, Any]) -> None:
    print(
        json.dumps(
            {
                "event": event,
                **payload,
            },
            ensure_ascii=False,
        )
    )


@dataclass
class QueueHandler:
    handler: Callable[[dict[str, Any]], Awaitable[Any]]
    concurrency: int = 1


async def job_llm_inference(ctx: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    from services.langchain_service import langchain_service
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

    def _deserialize_messages(serialized_messages: list[dict]) -> list:
        messages = []
        for item in serialized_messages:
            role = item.get("role", "user")
            content = item.get("content", "")
            if role == "system":
                messages.append(SystemMessage(content=content))
            elif role in {"assistant", "ai"}:
                tool_calls = item.get("tool_calls", [])
                if tool_calls:
                    messages.append(AIMessage(content=content, additional_kwargs={"tool_calls": tool_calls}))
                else:
                    messages.append(AIMessage(content=content))
            elif role == "tool":
                messages.append(ToolMessage(content=content, tool_call_id=item.get("tool_call_id", "queued_tool")))
            else:
                messages.append(HumanMessage(content=content))
        return messages

    request_id = payload.get("request_id")
    _log_queue_event(
        "queue_job_start",
        {
            "job_name": "job_llm_inference",
            "job_id": request_id,
            "request_id": request_id,
            "attempt": int(payload.get("attempt", 1)),
        },
    )

    started_at = time.perf_counter()
    try:
        messages = _deserialize_messages(payload.get("messages", []))
        mcp_tools = payload.get("mcp_tools", [])
        response = await langchain_service.call_llm_with_tools(messages, mcp_tools, request_id=request_id)
        result = {
            "content": response.content,
            "tool_calls": getattr(response, "tool_calls", []),
        }
        _log_queue_event(
            "queue_job_success",
            {
                "job_name": "job_llm_inference",
                "job_id": request_id,
                "request_id": request_id,
                "attempt": int(payload.get("attempt", 1)),
                "latency_ms": int((time.perf_counter() - started_at) * 1000),
            },
        )
        return result
    except Exception as exc:
        _log_queue_event(
            "queue_job_failure",
            {
                "job_name": "job_llm_inference",
                "job_id": request_id,
                "request_id": request_id,
                "attempt": int(payload.get("attempt", 1)),
                "latency_ms": int((time.perf_counter() - started_at) * 1000),
                "error": str(exc),
            },
        )
        raise


async def job_mcp_tool(ctx: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    from services.mcp_service import mcp_manager

    request_id = payload.get("request_id")
    _log_queue_event(
        "queue_job_start",
        {
            "job_name": "job_mcp_tool",
            "job_id": request_id,
            "request_id": request_id,
            "attempt": int(payload.get("attempt", 1)),
        },
    )

    started_at = time.perf_counter()
    try:
        server_name = payload["server_name"]
        tool_name = payload["tool_name"]
        arguments = payload.get("arguments", {})
        result = await mcp_manager.call_tool(server_name, tool_name, arguments)
        from services.agent_tools import sanitize_untrusted_text
        sanitized = sanitize_untrusted_text(result, 4000)
        _log_queue_event(
            "queue_job_success",
            {
                "job_name": "job_mcp_tool",
                "job_id": request_id,
                "request_id": request_id,
                "attempt": int(payload.get("attempt", 1)),
                "latency_ms": int((time.perf_counter() - started_at) * 1000),
            },
        )
        return {"result": sanitized}
    except Exception as exc:
        _log_queue_event(
            "queue_job_failure",
            {
                "job_name": "job_mcp_tool",
                "job_id": request_id,
                "request_id": request_id,
                "attempt": int(payload.get("attempt", 1)),
                "latency_ms": int((time.perf_counter() - started_at) * 1000),
                "error": str(exc),
            },
        )
        raise


async def job_document_ingestion(ctx: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    from services.document_service import index_document

    request_id = payload.get("request_id")
    _log_queue_event(
        "queue_job_start",
        {
            "job_name": "job_document_ingestion",
            "job_id": request_id,
            "request_id": request_id,
            "attempt": int(payload.get("attempt", 1)),
        },
    )

    started_at = time.perf_counter()
    try:
        session_id = payload["session_id"]
        filename = payload["filename"]
        raw_bytes = base64.b64decode(payload.get("raw_bytes", "").encode("ascii"))
        result = await index_document(session_id, filename, raw_bytes)
        _log_queue_event(
            "queue_job_success",
            {
                "job_name": "job_document_ingestion",
                "job_id": request_id,
                "request_id": request_id,
                "attempt": int(payload.get("attempt", 1)),
                "latency_ms": int((time.perf_counter() - started_at) * 1000),
            },
        )
        return result.model_dump()
    except Exception as exc:
        _log_queue_event(
            "queue_job_failure",
            {
                "job_name": "job_document_ingestion",
                "job_id": request_id,
                "request_id": request_id,
                "attempt": int(payload.get("attempt", 1)),
                "latency_ms": int((time.perf_counter() - started_at) * 1000),
                "error": str(exc),
            },
        )
        raise


class JobQueue:
    def __init__(self) -> None:
        self._redis_client = None
        self._arq_pool = None
        self._handlers: dict[str, QueueHandler] = {}
        self._worker_tasks: list[asyncio.Task] = []
        self._started = False
        self._lock = asyncio.Lock()
        self._local_queues: dict[str, asyncio.Queue[dict[str, Any]]] = {}
        self._local_results: dict[str, dict[str, Any]] = {}

    def _use_arq_backend(self) -> bool:
        return QUEUE_BACKEND == "arq" and create_pool is not None and RedisSettings is not None

    async def _get_redis_client(self):
        global redis

        if redis is None:
            return None

        if self._redis_client is None:
            self._redis_client = redis.from_url(REDIS_URL, decode_responses=True)

        try:
            await self._redis_client.ping()
            return self._redis_client
        except Exception:
            return None

    async def _get_arq_pool(self):
        if not self._use_arq_backend():
            return None

        if self._arq_pool is None:
            settings = _redis_settings_from_url(REDIS_URL)
            if settings is None:
                return None
            self._arq_pool = await create_pool(settings)
        return self._arq_pool

    def register_handler(
        self,
        name: str,
        handler: Callable[[dict[str, Any]], Awaitable[Any]],
        concurrency: int = 1,
    ) -> None:
        self._handlers[name] = QueueHandler(handler=handler, concurrency=max(1, concurrency))
        self._local_queues.setdefault(name, asyncio.Queue())

    async def start(self) -> None:
        if self._use_arq_backend():
            return

        async with self._lock:
            if self._started:
                return
            self._started = True

            for name, config in self._handlers.items():
                for _ in range(config.concurrency):
                    self._worker_tasks.append(asyncio.create_task(self._worker_loop(name)))

    async def stop(self) -> None:
        if self._use_arq_backend():
            if self._redis_client is not None:
                await self._redis_client.aclose()
                self._redis_client = None
            if self._arq_pool is not None:
                await self._arq_pool.close()
                self._arq_pool = None
            return

        for task in self._worker_tasks:
            task.cancel()
        self._worker_tasks.clear()

    def _queue_key(self, name: str) -> str:
        return f"{QUEUE_PREFIX}:{name}"

    def _result_key(self, job_id: str) -> str:
        return f"{QUEUE_RESULT_PREFIX}:{job_id}"

    async def enqueue(
        self,
        name: str,
        payload: dict[str, Any],
        timeout: int | None = None,
    ) -> dict[str, Any]:
        if self._use_arq_backend():
            pool = await self._get_arq_pool()
            if pool is None:
                raise RuntimeError("ARQ queue backend is not available")

            job_name = f"job_{name}" if not name.startswith("job_") else name
            job = await pool.enqueue_job(
                job_name,
                payload,
                _queue_name=QUEUE_PREFIX,
                _job_id=f"{payload.get('request_id') or uuid.uuid4().hex}_{name}_{uuid.uuid4().hex[:8]}",
                _expires=timeout or QUEUE_JOB_TIMEOUT,
            )
            if job is None:
                raise RuntimeError(f"Duplicate ARQ job id for {job_name}")
            return await job.result(timeout=timeout or QUEUE_JOB_TIMEOUT, poll_delay=QUEUE_POLL_INTERVAL)

        if name not in self._handlers:
            raise ValueError(f"Unknown queue handler: {name}")

        job = {
            "job_id": str(uuid.uuid4()),
            "request_id": payload.get("request_id") or str(uuid.uuid4()),
            "name": name,
            "attempts": 0,
            "payload": _normalize_value(payload),
        }
        wait_timeout = timeout or QUEUE_JOB_TIMEOUT
        deadline = time.monotonic() + wait_timeout

        client = await self._get_redis_client()
        if client is None:
            await self._local_queues[name].put(job)
        else:
            await client.lpush(self._queue_key(name), json.dumps(job, default=_json_default))

        while time.monotonic() < deadline:
            result = await self._read_result(job["job_id"])
            if result is not None:
                if result.get("ok", True):
                    return result.get("result", {})
                raise RuntimeError(result.get("error", "Queue job failed"))
            await asyncio.sleep(QUEUE_POLL_INTERVAL)

        raise TimeoutError(f"Timed out waiting for queue job '{name}'")

    async def _read_result(self, job_id: str) -> dict[str, Any] | None:
        client = await self._get_redis_client()
        if client is None:
            return self._local_results.pop(job_id, None)

        raw = await client.get(self._result_key(job_id))
        if not raw:
            return None
        return json.loads(raw)

    async def _store_result(self, job_id: str, result: dict[str, Any]) -> None:
        client = await self._get_redis_client()
        if client is None:
            self._local_results[job_id] = result
            return

        await client.set(self._result_key(job_id), json.dumps(result, default=_json_default), ex=QUEUE_JOB_TIMEOUT + 60)

    async def _pop_job(self, name: str) -> dict[str, Any] | None:
        client = await self._get_redis_client()
        if client is None:
            queue = self._local_queues.setdefault(name, asyncio.Queue())
            try:
                return await asyncio.wait_for(queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                return None

        item = await client.blpop(self._queue_key(name), timeout=1)
        if not item:
            return None
        _, raw = item
        return json.loads(raw)

    async def _worker_loop(self, name: str) -> None:
        while True:
            job = await self._pop_job(name)
            if not job:
                continue
            await self._process_job(name, job)

    async def _process_job(self, name: str, job: dict[str, Any]) -> None:
        handler = self._handlers[name].handler
        job_id = str(job["job_id"])
        attempts = int(job.get("attempts", 0))
        started_at = time.perf_counter()

        print(
            json.dumps(
                {
                    "event": "queue_job_start",
                    "job_name": name,
                    "job_id": job_id,
                    "request_id": job.get("request_id"),
                    "attempt": attempts + 1,
                },
                ensure_ascii=False,
            )
        )

        try:
            result = await handler(job["payload"])
            latency_ms = int((time.perf_counter() - started_at) * 1000)
            await self._store_result(
                job_id,
                {
                    "ok": True,
                    "request_id": job.get("request_id"),
                    "result": _normalize_value(result),
                },
            )
            print(
                json.dumps(
                    {
                        "event": "queue_job_success",
                        "job_name": name,
                        "job_id": job_id,
                        "request_id": job.get("request_id"),
                        "attempt": attempts + 1,
                        "latency_ms": latency_ms,
                    },
                    ensure_ascii=False,
                )
            )
        except Exception as exc:
            latency_ms = int((time.perf_counter() - started_at) * 1000)
            if attempts + 1 < QUEUE_RETRY_LIMIT:
                retry_job = dict(job)
                retry_job["attempts"] = attempts + 1
                await asyncio.sleep(2 ** attempts)
                client = await self._get_redis_client()
                if client is None:
                    await self._local_queues[name].put(retry_job)
                else:
                    await client.lpush(self._queue_key(name), json.dumps(retry_job, default=_json_default))
                print(
                    json.dumps(
                        {
                            "event": "queue_job_retry",
                            "job_name": name,
                            "job_id": job_id,
                            "request_id": job.get("request_id"),
                            "attempt": attempts + 1,
                            "latency_ms": latency_ms,
                            "error": str(exc),
                        },
                        ensure_ascii=False,
                    )
                )
                return

            await self._store_result(
                job_id,
                {
                    "ok": False,
                    "request_id": job.get("request_id"),
                    "error": str(exc),
                },
            )
            print(
                json.dumps(
                    {
                        "event": "queue_job_failure",
                        "job_name": name,
                        "job_id": job_id,
                        "request_id": job.get("request_id"),
                        "attempt": attempts + 1,
                        "latency_ms": latency_ms,
                        "error": str(exc),
                    },
                    ensure_ascii=False,
                )
            )

    @staticmethod
    def decode_base64(payload: str | None) -> bytes:
        return _deserialize_bytes(payload)


class WorkerSettings:
    """ARQ worker entry point for queued agent workloads."""

    redis_settings = _redis_settings_from_url(REDIS_URL)
    queue_name = QUEUE_PREFIX
    functions = []
    job_timeout = QUEUE_JOB_TIMEOUT
    keep_result = QUEUE_JOB_TIMEOUT + 60
    max_tries = QUEUE_RETRY_LIMIT
    max_jobs = LLM_QUEUE_CONCURRENCY
    poll_delay = QUEUE_POLL_INTERVAL
    on_startup = None

    if func is not None:
        functions = [
            func(job_llm_inference, name="job_llm_inference", timeout=QUEUE_JOB_TIMEOUT, keep_result=QUEUE_JOB_TIMEOUT + 60, max_tries=QUEUE_RETRY_LIMIT),
            func(job_mcp_tool, name="job_mcp_tool", timeout=QUEUE_JOB_TIMEOUT, keep_result=QUEUE_JOB_TIMEOUT + 60, max_tries=QUEUE_RETRY_LIMIT),
            func(job_document_ingestion, name="job_document_ingestion", timeout=QUEUE_JOB_TIMEOUT, keep_result=QUEUE_JOB_TIMEOUT + 60, max_tries=QUEUE_RETRY_LIMIT),
        ]

async def worker_startup(ctx: dict[str, Any]) -> None:
    from services.mcp_service import mcp_manager

    await mcp_manager.start_servers()


WorkerSettings.on_startup = worker_startup


job_queue = JobQueue()
