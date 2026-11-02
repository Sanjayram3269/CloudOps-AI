from sqlalchemy import create_engine
from sqlalchemy.orm import configure_mappers
from backend.platform.models import Base, User, Workspace, OrganizationMembership, WorkspaceMembership, Invitation, UserSession, IngestionCredential, AuditEvent

def test_platform_schema_creates_and_relationships_configure():
    configure_mappers()
    engine=create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    assert set(Base.metadata.tables)=={"users","organizations","workspaces","organization_memberships","workspace_memberships","invitations","user_sessions","ingestion_credentials","audit_events"}
    assert Workspace.__table__.c.organization_id.foreign_keys
    assert OrganizationMembership.__table__.constraints
    assert WorkspaceMembership.__table__.constraints
    assert Invitation.__table__.c.token_hash.unique
    assert UserSession.__table__.c.token_hash.unique
    assert IngestionCredential.__table__.c.secret_hash.unique
    assert AuditEvent.__table__.c.organization_id.foreign_keys
    assert User.__tablename__=="users"
