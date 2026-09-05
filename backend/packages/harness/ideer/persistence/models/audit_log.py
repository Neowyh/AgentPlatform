"""Compatibility import for the AgentPlatform-owned audit model.

Audit logs belong to the enterprise control plane.  Keep this import path for
older callers while ensuring the DeerFlow/ideer model registry does not define
a second SQLAlchemy mapper for the same table.
"""

from app.agentplatform.audit_model import AuditLog

__all__ = ["AuditLog"]
