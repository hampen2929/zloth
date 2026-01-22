"""AI Role services module.

This module provides the base infrastructure for AI Role services:
- BaseRoleService: Abstract base class for all role services
- RoleRegistry: Registry for registering and discovering role services
- Protocols and types for role execution
"""

from zloth_api.roles.base_service import BaseRoleService
from zloth_api.roles.protocol import RoleExecutor
from zloth_api.roles.registry import RoleRegistry

__all__ = [
    "BaseRoleService",
    "RoleExecutor",
    "RoleRegistry",
]
