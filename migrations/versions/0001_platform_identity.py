"""Create multi-tenant control-plane tables."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision="0001_platform_identity"
down_revision=None
branch_labels=None
depends_on=None

def upgrade():
    op.create_table("users",sa.Column("id",postgresql.UUID(as_uuid=True),primary_key=True),sa.Column("email",sa.String(320),nullable=False,unique=True),sa.Column("password_hash",sa.String(512),nullable=False),sa.Column("display_name",sa.String(120),nullable=False),sa.Column("is_active",sa.Boolean(),nullable=False,server_default=sa.true()),sa.Column("email_verified_at",sa.DateTime(timezone=True)),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_index("ix_users_email","users",["email"],unique=True)
    op.create_table("organizations",sa.Column("id",postgresql.UUID(as_uuid=True),primary_key=True),sa.Column("name",sa.String(160),nullable=False),sa.Column("slug",sa.String(80),nullable=False,unique=True),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_index("ix_organizations_slug","organizations",["slug"],unique=True)
    op.create_table("workspaces",sa.Column("id",postgresql.UUID(as_uuid=True),primary_key=True),sa.Column("organization_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),sa.Column("name",sa.String(160),nullable=False),sa.Column("slug",sa.String(80),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.UniqueConstraint("organization_id","slug",name="uq_workspace_org_slug"))
    op.create_index("ix_workspaces_organization_id","workspaces",["organization_id"])
    op.create_table("organization_memberships",sa.Column("id",postgresql.UUID(as_uuid=True),primary_key=True),sa.Column("organization_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),sa.Column("user_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("role",sa.Enum("owner","admin","responder","viewer",name="organization_role"),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.UniqueConstraint("organization_id","user_id",name="uq_org_membership"))
    op.create_index("ix_organization_memberships_organization_id","organization_memberships",["organization_id"])
    op.create_index("ix_organization_memberships_user_id","organization_memberships",["user_id"])
    op.create_table("workspace_memberships",sa.Column("id",postgresql.UUID(as_uuid=True),primary_key=True),sa.Column("workspace_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("workspaces.id",ondelete="CASCADE"),nullable=False),sa.Column("user_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("role",sa.Enum("admin","responder","viewer",name="workspace_role"),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.UniqueConstraint("workspace_id","user_id",name="uq_workspace_membership"))
    op.create_index("ix_workspace_memberships_workspace_id","workspace_memberships",["workspace_id"])
    op.create_index("ix_workspace_memberships_user_id","workspace_memberships",["user_id"])
    op.create_table("invitations",sa.Column("id",postgresql.UUID(as_uuid=True),primary_key=True),sa.Column("organization_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),sa.Column("email",sa.String(320),nullable=False),sa.Column("role",sa.Enum("admin","responder","viewer",name="invitation_role"),nullable=False),sa.Column("token_hash",sa.String(128),nullable=False,unique=True),sa.Column("expires_at",sa.DateTime(timezone=True),nullable=False),sa.Column("accepted_at",sa.DateTime(timezone=True)),sa.Column("revoked_at",sa.DateTime(timezone=True)),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_index("ix_invitations_organization_id","invitations",["organization_id"])
    op.create_index("ix_invitations_email","invitations",["email"])
    op.create_table("user_sessions",sa.Column("id",postgresql.UUID(as_uuid=True),primary_key=True),sa.Column("user_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("token_hash",sa.String(128),nullable=False,unique=True),sa.Column("csrf_token_hash",sa.String(128),nullable=False),sa.Column("expires_at",sa.DateTime(timezone=True),nullable=False),sa.Column("revoked_at",sa.DateTime(timezone=True)),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False),sa.Column("last_seen_at",sa.DateTime(timezone=True)))
    op.create_index("ix_user_sessions_user_id","user_sessions",["user_id"])
    op.create_table("ingestion_credentials",sa.Column("id",postgresql.UUID(as_uuid=True),primary_key=True),sa.Column("workspace_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("workspaces.id",ondelete="CASCADE"),nullable=False),sa.Column("name",sa.String(120),nullable=False),sa.Column("secret_hash",sa.String(128),nullable=False,unique=True),sa.Column("scopes",postgresql.JSONB(),nullable=False,server_default=sa.text("'[]'::jsonb")),sa.Column("expires_at",sa.DateTime(timezone=True)),sa.Column("revoked_at",sa.DateTime(timezone=True)),sa.Column("last_used_at",sa.DateTime(timezone=True)),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    op.create_index("ix_ingestion_credentials_workspace_id","ingestion_credentials",["workspace_id"])
    op.create_table("audit_events",sa.Column("id",postgresql.UUID(as_uuid=True),primary_key=True),sa.Column("organization_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("organizations.id",ondelete="CASCADE"),nullable=False),sa.Column("workspace_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("workspaces.id",ondelete="SET NULL")),sa.Column("actor_user_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("users.id",ondelete="SET NULL")),sa.Column("action",sa.String(120),nullable=False),sa.Column("resource_type",sa.String(80),nullable=False),sa.Column("resource_id",sa.String(80)),sa.Column("details",postgresql.JSONB(),nullable=False,server_default=sa.text("'{}'::jsonb")),sa.Column("occurred_at",sa.DateTime(timezone=True),server_default=sa.func.now(),nullable=False))
    for table,column in [("audit_events","organization_id"),("audit_events","workspace_id"),("audit_events","actor_user_id"),("audit_events","occurred_at")]:
        op.create_index("ix_"+table+"_"+column,table,[column])

def downgrade():
    for table in ["audit_events","ingestion_credentials","user_sessions","invitations","workspace_memberships","organization_memberships","workspaces","organizations","users"]:
        op.drop_table(table)
    for name in ["invitation_role","workspace_role","organization_role"]:
        sa.Enum(name=name).drop(op.get_bind(),checkfirst=True)
