"""Role Registry for dynamic role service discovery.

This module provides a registry pattern for AI Role services,
enabling dynamic registration and discovery of role implementations.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from dursor_api.roles.base_service import BaseRoleService

logger = logging.getLogger(__name__)


class RoleRegistry:
    """Registry for AI Role services.

    Provides decorator-based registration and lookup of role services.
    This enables:
    - Dynamic discovery of available roles
    - Consistent naming across the codebase
    - Easy addition of new roles

    Usage:
        @RoleRegistry.register("implementation")
        class RunService(BaseRoleService[Run, RunCreate, ImplementationResult]):
            ...

        # Later, get the registered class
        role_cls = RoleRegistry.get("implementation")
    """

    _roles: dict[str, type[BaseRoleService[Any, Any, Any]]] = {}
    _instances: dict[str, BaseRoleService[Any, Any, Any]] = {}

    @classmethod
    def register(cls, name: str) -> Any:
        """Register a role service class.

        Args:
            name: Unique name for the role (e.g., "implementation", "review").

        Returns:
            Decorator function that registers the class.

        Example:
            @RoleRegistry.register("implementation")
            class RunService(BaseRoleService):
                ...
        """

        def decorator(
            role_cls: type[BaseRoleService[Any, Any, Any]],
        ) -> type[BaseRoleService[Any, Any, Any]]:
            if name in cls._roles:
                logger.warning(f"Role '{name}' already registered, overwriting")
            cls._roles[name] = role_cls
            logger.info(f"Registered role: {name} -> {role_cls.__name__}")
            return role_cls

        return decorator

    @classmethod
    def get(cls, name: str) -> type[BaseRoleService[Any, Any, Any]]:
        """Get a registered role service class.

        Args:
            name: Name of the role to retrieve.

        Returns:
            The role service class.

        Raises:
            ValueError: If the role is not registered.
        """
        if name not in cls._roles:
            available = ", ".join(cls._roles.keys()) or "(none)"
            raise ValueError(f"Unknown role: '{name}'. Available: {available}")
        return cls._roles[name]

    @classmethod
    def get_instance(cls, name: str) -> BaseRoleService[Any, Any, Any]:
        """Get a registered role service instance.

        Note: Instances must be set via set_instance() during DI setup.

        Args:
            name: Name of the role.

        Returns:
            The role service instance.

        Raises:
            ValueError: If the role instance is not set.
        """
        if name not in cls._instances:
            available = ", ".join(cls._instances.keys()) or "(none)"
            raise ValueError(f"Role instance not set: '{name}'. Available: {available}")
        return cls._instances[name]

    @classmethod
    def set_instance(cls, name: str, instance: BaseRoleService[Any, Any, Any]) -> None:
        """Set a role service instance.

        Called during dependency injection setup.

        Args:
            name: Name of the role.
            instance: The service instance.
        """
        cls._instances[name] = instance
        logger.debug(f"Set role instance: {name}")

    @classmethod
    def list_roles(cls) -> list[str]:
        """List all registered role names.

        Returns:
            List of role names.
        """
        return list(cls._roles.keys())

    @classmethod
    def list_available_instances(cls) -> list[str]:
        """List roles with available instances.

        Returns:
            List of role names with instances.
        """
        return list(cls._instances.keys())

    @classmethod
    def clear(cls) -> None:
        """Clear all registrations (for testing).

        Warning: This clears all registrations. Use only in tests.
        """
        cls._roles.clear()
        cls._instances.clear()
        logger.debug("Cleared role registry")

    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Check if a role is registered.

        Args:
            name: Role name to check.

        Returns:
            True if registered.
        """
        return name in cls._roles

    @classmethod
    def has_instance(cls, name: str) -> bool:
        """Check if a role instance is available.

        Args:
            name: Role name to check.

        Returns:
            True if instance is available.
        """
        return name in cls._instances
