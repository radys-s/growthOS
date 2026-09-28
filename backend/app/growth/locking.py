"""Serialize mutations in the supported single-process local deployment."""

from threading import RLock

WRITE_LOCK = RLock()
