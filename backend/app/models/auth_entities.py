from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

class AgentStudioMember(Base):
    __tablename__='agentstudio_members'
    id: Mapped[str]=mapped_column(String(64),primary_key=True)
    login_id: Mapped[str]=mapped_column(String(100),unique=True,index=True)
    password_hash: Mapped[str]=mapped_column(String(500))
    name: Mapped[str]=mapped_column(String(200))
    email: Mapped[str]=mapped_column(String(320),unique=True,index=True)
    role: Mapped[str]=mapped_column(String(30),default='USER',index=True)
    is_active: Mapped[bool]=mapped_column(Boolean,default=True)
    created_at: Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    updated_at: Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow,onupdate=datetime.utcnow)

class AgentStudioMemberPc(Base):
    __tablename__='agentstudio_member_pcs'
    __table_args__=(UniqueConstraint('member_id','pc_name',name='uq_member_pc'),)
    id: Mapped[str]=mapped_column(String(64),primary_key=True)
    member_id: Mapped[str]=mapped_column(ForeignKey('agentstudio_members.id'),index=True)
    pc_name: Mapped[str]=mapped_column(String(255),index=True)
    can_manage: Mapped[bool]=mapped_column(Boolean,default=True)
    created_at: Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class AgentStudioAuthSession(Base):
    __tablename__='agentstudio_auth_sessions'
    id: Mapped[str]=mapped_column(String(64),primary_key=True)
    member_id: Mapped[str]=mapped_column(ForeignKey('agentstudio_members.id'),index=True)
    token_hash: Mapped[str]=mapped_column(String(128),unique=True,index=True)
    remember_me: Mapped[bool]=mapped_column(Boolean,default=False)
    expires_at: Mapped[datetime]=mapped_column(DateTime,index=True)
    revoked: Mapped[bool]=mapped_column(Boolean,default=False,index=True)
    created_at: Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
    last_used_at: Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
