"""AI Role services module.

This module provides the base infrastructure for AI Role services:
- BaseRoleService: Abstract base class for all role services
- RoleRegistry: Registry for registering and discovering role services
- Protocols and types for role execution
"""

from dursor_api.roles.base_service import BaseRoleService
from dursor_api.roles.protocol import RoleExecutor
from dursor_api.roles.registry import RoleRegistry

__all__ = [
    "BaseRoleService",
    "RoleExecutor",
    "RoleRegistry",
]
