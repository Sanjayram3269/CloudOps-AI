from __future__ import annotations
import enum, uuid
from datetime import datetime
from typing import Any
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

class Base(DeclarativeBase): pass
class OrganizationRole(str, enum.Enum):
    owner="owner"; admin="admin"; responder="responder"; viewer="viewer"
class WorkspaceRole(str, enum.Enum):
    admin="admin"; responder="responder"; viewer="viewer"

class User(Base):
    __tablename__="users"
    id: Mapped[uuid.UUID]=mapped_column(Uuid,primary_key=True,default=uuid.uuid4)
    email: Mapped[str]=mapped_column(String(320),unique=True,index=True)
    password_hash: Mapped[str]=mapped_column(String(512))
    display_name: Mapped[str]=mapped_column(String(120))
    is_active: Mapped[bool]=mapped_column(Boolean,nullable=False,default=True)
    email_verified_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())

class Organization(Base):
    __tablename__="organizations"
    id: Mapped[uuid.UUID]=mapped_column(Uuid,primary_key=True,default=uuid.uuid4)
    name: Mapped[str]=mapped_column(String(160))
    slug: Mapped[str]=mapped_column(String(80),unique=True,index=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
    workspaces: Mapped[list[Workspace]]=relationship(back_populates="organization",cascade="all, delete-orphan")

class Workspace(Base):
    __tablename__="workspaces"
    __table_args__=(UniqueConstraint("organization_id","slug",name="uq_workspace_org_slug"),)
    id: Mapped[uuid.UUID]=mapped_column(Uuid,primary_key=True,default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True)
    name: Mapped[str]=mapped_column(String(160))
    slug: Mapped[str]=mapped_column(String(80))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
    organization: Mapped[Organization]=relationship(back_populates="workspaces")

class OrganizationMembership(Base):
    __tablename__="organization_memberships"
    __table_args__=(UniqueConstraint("organization_id","user_id",name="uq_org_membership"),)
    id: Mapped[uuid.UUID]=mapped_column(Uuid,primary_key=True,default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True)
    user_id: Mapped[uuid.UUID]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True)
    role: Mapped[OrganizationRole]=mapped_column(Enum(OrganizationRole,name="organization_role"),nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())

class WorkspaceMembership(Base):
    __tablename__="workspace_memberships"
    __table_args__=(UniqueConstraint("workspace_id","user_id",name="uq_workspace_membership"),)
    id: Mapped[uuid.UUID]=mapped_column(Uuid,primary_key=True,default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID]=mapped_column(ForeignKey("workspaces.id",ondelete="CASCADE"),index=True)
    user_id: Mapped[uuid.UUID]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True)
    role: Mapped[WorkspaceRole]=mapped_column(Enum(WorkspaceRole,name="workspace_role"),nullable=False)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())

class Invitation(Base):
    __tablename__="invitations"
    id: Mapped[uuid.UUID]=mapped_column(Uuid,primary_key=True,default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True)
    email: Mapped[str]=mapped_column(String(320),index=True)
    role: Mapped[OrganizationRole]=mapped_column(Enum(OrganizationRole,name="invitation_role"),nullable=False)
    token_hash: Mapped[str]=mapped_column(String(128),unique=True)
    expires_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    accepted_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())

class UserSession(Base):
    __tablename__="user_sessions"
    id: Mapped[uuid.UUID]=mapped_column(Uuid,primary_key=True,default=uuid.uuid4)
    user_id: Mapped[uuid.UUID]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True)
    token_hash: Mapped[str]=mapped_column(String(128),unique=True)
    csrf_token_hash: Mapped[str]=mapped_column(String(128))
    expires_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),nullable=False)
    revoked_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
    last_seen_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))

class IngestionCredential(Base):
    __tablename__="ingestion_credentials"
    id: Mapped[uuid.UUID]=mapped_column(Uuid,primary_key=True,default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID]=mapped_column(ForeignKey("workspaces.id",ondelete="CASCADE"),index=True)
    name: Mapped[str]=mapped_column(String(120))
    secret_hash: Mapped[str]=mapped_column(String(128),unique=True)
    scopes: Mapped[list[str]]=mapped_column(JSON,nullable=False,default=list)
    expires_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())

class AuditEvent(Base):
    __tablename__="audit_events"
    id: Mapped[uuid.UUID]=mapped_column(Uuid,primary_key=True,default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID]=mapped_column(ForeignKey("organizations.id",ondelete="CASCADE"),index=True)
    workspace_id: Mapped[uuid.UUID|None]=mapped_column(ForeignKey("workspaces.id",ondelete="SET NULL"),index=True)
    actor_user_id: Mapped[uuid.UUID|None]=mapped_column(ForeignKey("users.id",ondelete="SET NULL"),index=True)
    action: Mapped[str]=mapped_column(String(120))
    resource_type: Mapped[str]=mapped_column(String(80))
    resource_id: Mapped[str|None]=mapped_column(String(80))
    details: Mapped[dict[str,Any]]=mapped_column(JSON,nullable=False,default=dict)
    occurred_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),index=True)

Index("ix_sessions_user_expiry",UserSession.user_id,UserSession.expires_at)
Index("ix_credentials_workspace_revoked",IngestionCredential.workspace_id,IngestionCredential.revoked_at)
