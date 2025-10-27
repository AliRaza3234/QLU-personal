import asyncio
from typing import Dict, Set, Any, Optional
import uuid


class RequestContext:
    """
    Request-scoped context to manage state for a single request.
    This eliminates race conditions by keeping all request-specific data isolated.
    """

    def __init__(self, query_id: Optional[str] = None):
        self.query_id = query_id or str(uuid.uuid4())
        self.tasks: Dict[str, asyncio.Task] = {}
        self.company_buffer: Set[str] = set()
        self.task_lock = asyncio.Lock()
        self.buffer_lock = asyncio.Lock()
        self.cached_results: Dict[str, Any] = {}

    async def add_task(self, task_type: str, task: asyncio.Task) -> None:
        async with self.task_lock:
            self.tasks[task_type] = task

    async def get_task(self, task_type: str) -> Optional[asyncio.Task]:
        async with self.task_lock:
            return self.tasks.get(task_type)

    async def set_tasks(self, tasks_dict: Dict[str, asyncio.Task]) -> None:
        async with self.task_lock:
            self.tasks.update(tasks_dict)

    async def wait_for_task(self, task_type: str) -> Any:
        async with self.task_lock:
            if task_type in self.cached_results:
                return self.cached_results[task_type]

        task = await self.get_task(task_type)
        if not task:
            raise KeyError(
                f"Task type '{task_type}' not found for query {self.query_id}"
            )
        result = await task
        async with self.task_lock:
            self.cached_results[task_type] = result
        return result

    async def has_seen_company(self, company_name: str) -> bool:
        normalized = company_name.lower().strip()
        async with self.buffer_lock:
            return normalized in self.company_buffer

    async def add_company(self, company_name: str) -> bool:
        normalized = company_name.lower().strip()
        async with self.buffer_lock:
            if normalized in self.company_buffer:
                return False
            self.company_buffer.add(normalized)
            return True

    async def get_company_count(self) -> int:
        async with self.buffer_lock:
            return len(self.company_buffer)

    async def cleanup(self) -> None:
        async with self.task_lock:
            for task in self.tasks.values():
                if not task.done():
                    task.cancel()
            self.tasks.clear()

        async with self.buffer_lock:
            self.company_buffer.clear()

        async with self.task_lock:
            self.cached_results.clear()
