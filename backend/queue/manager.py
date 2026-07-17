import asyncio
import logging
from typing import Callable, Any, Dict, List
from backend.config.settings import settings

logger = logging.getLogger(__name__)

class DLQItem:
    def __init__(self, task_id: str, payload: Any, error: str):
        self.task_id = task_id
        self.payload = payload
        self.error = error

class TaskQueueManager:
    """
    Manages the async worker pool, exponential backoff retries, and the Dead Letter Queue.
    """
    def __init__(self):
        self.queue = asyncio.Queue(maxsize=settings.QUEUE_SIZE)
        self.dlq: List[DLQItem] = []
        self.workers = []
        self._running = False

    async def add_task(self, task_func: Callable, task_id: str, payload: Any, retries: int = 3):
        await self.queue.put({"func": task_func, "id": task_id, "payload": payload, "retries": retries})

    async def _worker_loop(self):
        while self._running:
            try:
                task = await self.queue.get()
                func = task["func"]
                task_id = task["id"]
                payload = task["payload"]
                retries_left = task["retries"]

                try:
                    await func(payload)
                except Exception as e:
                    logger.error(f"Task {task_id} failed: {e}")
                    if retries_left > 0:
                        # Exponential backoff retry
                        backoff = (4 - retries_left) ** 2  # 1, 4, 9 seconds
                        logger.info(f"Retrying task {task_id} in {backoff} seconds...")
                        await asyncio.sleep(backoff)
                        await self.queue.put({
                            "func": func, 
                            "id": task_id, 
                            "payload": payload, 
                            "retries": retries_left - 1
                        })
                    else:
                        logger.warning(f"Task {task_id} exceeded max retries. Moving to DLQ.")
                        self.dlq.append(DLQItem(task_id, payload, str(e)))
                finally:
                    self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker encountered an error: {e}")

    def start_workers(self):
        self._running = True
        for _ in range(settings.MAX_WORKERS):
            worker = asyncio.create_task(self._worker_loop())
            self.workers.append(worker)

    async def stop_workers(self):
        self._running = False
        for worker in self.workers:
            worker.cancel()
        await asyncio.gather(*self.workers, return_exceptions=True)

task_queue = TaskQueueManager()
