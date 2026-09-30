from __future__ import annotations

import asyncio
import uuid
from typing import Dict

from src.core.config import settings
from src.core.logger import log
from src.models.sse import DoneEvent, SSEEvent


class SSEManager:
    """
    Singleton that manages all active SSE connections.

    connect(user_id)           → (connection_id, queue)
    disconnect(user_id, conn)  → None
    publish(user_id, event)    → None   [fire-and-forget, non-blocking]
    """

    def __init__(self) -> None:
        self._connections: Dict[str, Dict[str, asyncio.Queue]] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    async def _get_user_lock(self, user_id: str) -> asyncio.Lock:
        async with self._global_lock:
            if user_id not in self._locks:
                self._locks[user_id] = asyncio.Lock()
            return self._locks[user_id]

    async def _cleanup_user(self, user_id: str) -> None:
        """Remove user entry if all connections have been closed."""
        async with self._global_lock:
            if user_id in self._connections and not self._connections[user_id]:
                del self._connections[user_id]
            if user_id in self._locks and user_id not in self._connections:
                del self._locks[user_id]


    async def connect(self, user_id: str) -> tuple[str, asyncio.Queue]:
        """
        Register a new SSE connection for *user_id*.
        Returns a unique connection_id and the queue the event generator reads from.
        """
        connection_id = str(uuid.uuid4())
        queue: asyncio.Queue = asyncio.Queue(maxsize=settings.SSE_QUEUE_SIZE)

        lock = await self._get_user_lock(user_id)
        async with lock:
            self._connections.setdefault(user_id, {})[connection_id] = queue

        log.info(
            "sse_connected",
            user_id=user_id,
            connection_id=connection_id,
            active_tabs=len(self._connections.get(user_id, {})),
        )
        return connection_id, queue

    async def disconnect(self, user_id: str, connection_id: str) -> None:
        """
        Deregister a connection.  Sends DoneEvent first so the generator loop
        exits cleanly without timing out on queue.get().
        """
        lock = await self._get_user_lock(user_id)
        async with lock:
            user_conns = self._connections.get(user_id, {})
            queue = user_conns.pop(connection_id, None)

        if queue is not None:
            try:
                queue.put_nowait(DoneEvent())
            except asyncio.QueueFull:
                pass

        await self._cleanup_user(user_id)
        log.info("sse_disconnected", user_id=user_id, connection_id=connection_id)

    async def publish(self, user_id: str, event: SSEEvent) -> None:
        """
        Deliver an event to all active connections for *user_id*.
        """
        lock = await self._get_user_lock(user_id)
        async with lock:
            user_conns = self._connections.get(user_id)
            if not user_conns:
                log.debug("sse_no_connections", user_id=user_id, event_type=event.event)
                return

            dead: list[str] = []
            for conn_id, queue in user_conns.items():
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    log.warning(
                        "sse_queue_full_drop",
                        user_id=user_id,
                        connection_id=conn_id,
                        event_type=event.event,
                    )
                except Exception:
                    dead.append(conn_id)

            for conn_id in dead:
                user_conns.pop(conn_id, None)
                log.warning("sse_dead_connection_pruned", user_id=user_id, connection_id=conn_id)

    @property
    def active_connection_count(self) -> int:
        return sum(len(conns) for conns in self._connections.values())

sse_manager = SSEManager()
