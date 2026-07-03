from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional


class PlatformBase(ABC):
    """Abstract base class for all marketplace platform integrations."""

    platform_name: str = ""

    @abstractmethod
    async def create_listing(self, item: dict, credentials: dict) -> dict:
        """
        Create a listing on this platform.
        Returns: {"platform_listing_id": str, "platform_listing_url": str}
        """
        ...

    @abstractmethod
    async def delete_listing(self, platform_listing_id: str, credentials: dict) -> bool:
        """Remove a listing from this platform. Returns True on success."""
        ...

    @abstractmethod
    async def get_listing_status(self, platform_listing_id: str, credentials: dict) -> str:
        """
        Check current status of a listing.
        Returns: 'active' | 'sold' | 'not_found' | 'error'
        """
        ...

    @abstractmethod
    async def refresh_credentials(self, credentials: dict) -> dict:
        """Refresh OAuth tokens or session cookies. Returns updated credentials."""
        ...
