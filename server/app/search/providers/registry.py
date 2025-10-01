"""Utilities for registering and resolving model providers."""
from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Dict, Generic, Optional, Tuple, TypeVar

P = TypeVar("P")


class ProviderRegistry(Generic[P]):
    """Simple registry that supports aliases and fallback resolution."""

    def __init__(self, default_key: str):
        if not default_key or not default_key.strip():
            raise ValueError("default_key must be a non-empty string")
        self._default_key = default_key.strip().lower()
        self._factories: Dict[str, Callable[..., P]] = {}
        self._canonical_keys: Dict[str, str] = {}

    @property
    def default_key(self) -> str:
        """Return the canonical default provider key."""

        return self._default_key

    def register(
        self,
        key: str,
        *,
        aliases: Sequence[str] | None = None,
    ) -> Callable[[Callable[..., P]], Callable[..., P]]:
        """Register a factory under the provided key and optional aliases."""

        canonical = self._normalize(key)
        normalized_keys = {canonical}
        if aliases:
            normalized_keys.update(self._normalize(alias) for alias in aliases)

        def decorator(factory: Callable[..., P]) -> Callable[..., P]:
            for normalized in normalized_keys:
                self._factories[normalized] = factory
                self._canonical_keys[normalized] = canonical
            return factory

        return decorator

    def create(self, key: str | None, *args, **kwargs) -> Tuple[P, str, Optional[str]]:
        """Instantiate a provider, returning metadata for fallback handling.

        Returns a tuple of ``(instance, resolved_key, fallback_from)`` where
        ``resolved_key`` is the canonical key that produced the provider and
        ``fallback_from`` is the originally requested key if a fallback was
        required (``None`` otherwise).
        """

        requested = self._normalize(key)
        lookup_key = requested or self._default_key
        factory = self._factories.get(lookup_key)
        fallback_from: str | None = None

        if factory is None:
            fallback_from = lookup_key
            factory = self._factories.get(self._default_key)
            lookup_key = self._default_key
            if factory is None:
                raise ValueError(
                    f"Default provider '{self._default_key}' is not registered"
                )

        instance = factory(*args, **kwargs)
        resolved_key = self._canonical_keys.get(lookup_key, lookup_key)
        # If we fell back because the requested key was empty, suppress the
        # fallback marker so callers don't treat the default as an error.
        if fallback_from == self._default_key and requested is None:
            fallback_from = None
        return (
            instance,
            resolved_key,
            fallback_from if requested else fallback_from,
        )

    @staticmethod
    def _normalize(key: str | None) -> Optional[str]:
        if key is None:
            return None
        normalized = key.strip().lower()
        return normalized or None
