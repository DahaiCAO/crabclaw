from __future__ import annotations
import asyncio
from collections import defaultdict
from typing import Dict, Set
from loguru import logger

class BroadcastManager:
    """
    Manages real-time message broadcasting to multiple subscribers, with user isolation.
    This enables a scoped publish/subscribe pattern.
    """

    def __init__(self):
        # Subscribers for specific scopes (e.g., per-user sessions)
        self._scoped_subscribers: Dict[str, Set[asyncio.Queue]] = defaultdict(set)
        # Subscribers for all messages (e.g., the agent's core processor)
        self._global_subscribers: Set[asyncio.Queue] = set()

    async def subscribe(self, scope: str) -> asyncio.Queue:
        """
        A component calls this to subscribe to a specific scope's broadcasts.
        
        Args:
            scope (str): The scope to subscribe to (e.g., a user_id or session_id).

        Returns:
            asyncio.Queue: A new queue that will receive messages for that scope.
        """
        queue = asyncio.Queue()
        self._scoped_subscribers[scope].add(queue)
        logger.debug(f"New subscriber added to scope '{scope}'. Total subscribers for scope: {len(self._scoped_subscribers[scope])}")
        return queue

    async def subscribe_global(self) -> asyncio.Queue:
        """
        A component calls this to subscribe to ALL broadcasts from every scope.
        This is intended for core components like the IOProcessor.

        Returns:
            asyncio.Queue: A new queue that will receive all published messages.
        """
        queue = asyncio.Queue()
        self._global_subscribers.add(queue)
        logger.debug(f"New global subscriber added. Total global subscribers: {len(self._global_subscribers)}")
        return queue

    async def unsubscribe(self, queue: asyncio.Queue, scope: str):
        """
        Removes a scoped queue from the set of subscribers.

        Args:
            queue (asyncio.Queue): The queue to remove.
            scope (str): The scope the queue was subscribed to.
        """
        if scope in self._scoped_subscribers and queue in self._scoped_subscribers[scope]:
            self._scoped_subscribers[scope].remove(queue)
            logger.debug(f"Subscriber removed from scope '{scope}'. Remaining for scope: {len(self._scoped_subscribers[scope])}")
            # Clean up empty scopes
            if not self._scoped_subscribers[scope]:
                del self._scoped_subscribers[scope]

    async def unsubscribe_global(self, queue: asyncio.Queue):
        """
        Removes a global queue from the set of subscribers.

        Args:
            queue (asyncio.Queue): The queue to remove.
        """
        if queue in self._global_subscribers:
            self._global_subscribers.remove(queue)
            logger.debug(f"Global subscriber removed. Total global subscribers: {len(self._global_subscribers)}")

    async def publish(self, scope: str, message: dict):
        """
        Publishes a message to a specific scope.
        The message is sent to all subscribers of that scope AND to all global subscribers.

        Args:
            scope (str): The scope to publish to.
            message (dict): The message to broadcast.
        """
        # Add scope to the message for context, especially for global subscribers
        message_with_scope = message.copy()
        message_with_scope['scope'] = scope

        # Get subscribers for the specific scope
        scoped_queues = self._scoped_subscribers.get(scope, set())
        
        # Combine scoped and global subscribers
        all_target_queues = scoped_queues.union(self._global_subscribers)

        if not all_target_queues:
            logger.warning(f"Publish called on scope '{scope}' with no subscribers. Message will be lost.")
            return

        logger.debug(f"Publishing message to {len(all_target_queues)} subscribers for scope '{scope}': {message}")
        for queue in all_target_queues:
            await queue.put(message_with_scope)
