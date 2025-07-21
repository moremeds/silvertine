"""
Redis integration module for Silvertine trading framework.

This module provides Redis-based implementations for event persistence,
caching, and distributed communication.
"""

from .redis_streams import RedisStreamManager

__all__ = ["RedisStreamManager"]
