from __future__ import annotations
import base64, hashlib, hmac, os, secrets, uuid
from datetime import datetime, timedelta
from sqlalchemy import func, select
from app.core.database import SessionLocal
from app.core.machine_identity import current_pc_name
from app.models.auth_entities import AgentStudioAuthSession, AgentStudioMember, AgentStudioMemberPc

PBKDF2_ITERATIONS=310_000
SESSION_HOURS=12
REMEMBER_DAYS=30

def _hash_password(password:str, salt:bytes|None=None)->str:
    if not password or len(password)<8: raise ValueError('비밀번호는 8자 이상이어야 합니다.')
    salt=salt or os.urandom(16)
    digest=hashlib.pbkdf2_hmac('sha256',password.encode(),salt,PBKDF2_ITERATIONS)
    return f'pbkdf2_sha256${PBKDF2_ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}'

def _verify_password(password:str, encoded:str)->bool:
    try:
        _,iterations,salt,digest=encoded.split('$',3)
        actual=hashlib.pbkdf2_hmac('sha256',password.encode(),base64.b64decode(salt),int(iterations))
        return hmac.compare_digest(actual,base64.b64decode(digest))
    except Exception:return False

def _token_hash(token:str)->str:return hashlib.sha256(token.encode()).hexdigest()

def _member(row:AgentStudioMember,pcs:list[str]|None=None)->dict:
    return {'id':row.id,'login_id':row.login_id,'name':row.name,'email':row.email,'role':row.role,'is_active':row.is_active,'pcs':pcs or []}

async def register_member(payload:dict)->dict:
    login_id=str(payload.get('login_id') or '').strip()
    name=str(payload.get('name') or '').strip();email=str(payload.get('email') or '').strip().lower()
    password=str(payload.get('password') or '')
    if len(login_id)<3: raise ValueError('아이디는 3자 이상이어야 합니다.')
    if not name: raise ValueError('이름을 입력하세요.')
    if '@' not in email: raise ValueError('올바른 이메일을 입력하세요.')
    async with SessionLocal() as s:
        if (await s.execute(select(AgentStudioMember).where((AgentStudioMember.login_id==login_id)|(AgentStudioMember.email==email)))).scalar_one_or_none():
            raise ValueError('이미 사용 중인 아이디 또는 이메일입니다.')
        count=int((await s.execute(select(func.count()).select_from(AgentStudioMember))).scalar() or 0)
        row=AgentStudioMember(id=uuid.uuid4().hex,login_id=login_id,password_hash=_hash_password(password),name=name,email=email,role='ADMIN' if count==0 else 'USER',is_active=True)
        s.add(row);await s.flush()
        pc=current_pc_name();s.add(AgentStudioMemberPc(id=uuid.uuid4().hex,member_id=row.id,pc_name=pc,can_manage=True))
        await s.commit();return {'ok':True,'member':_member(row,[pc]),'first_admin':count==0}

async def login(login_id:str,password:str,remember_me:bool)->dict:
    async with SessionLocal() as s:
        row=(await s.execute(select(AgentStudioMember).where(AgentStudioMember.login_id==login_id.strip()))).scalar_one_or_none()
        if not row or not row.is_active or not _verify_password(password,row.password_hash): raise ValueError('아이디 또는 비밀번호가 올바르지 않습니다.')
        token=secrets.token_urlsafe(48);expires=datetime.utcnow()+timedelta(days=REMEMBER_DAYS) if remember_me else datetime.utcnow()+timedelta(hours=SESSION_HOURS)
        s.add(AgentStudioAuthSession(id=uuid.uuid4().hex,member_id=row.id,token_hash=_token_hash(token),remember_me=remember_me,expires_at=expires))
        pc=current_pc_name();mapping=(await s.execute(select(AgentStudioMemberPc).where(AgentStudioMemberPc.member_id==row.id,AgentStudioMemberPc.pc_name==pc))).scalar_one_or_none()
        if mapping is None:s.add(AgentStudioMemberPc(id=uuid.uuid4().hex,member_id=row.id,pc_name=pc,can_manage=True))
        pcs=list((await s.execute(select(AgentStudioMemberPc.pc_name).where(AgentStudioMemberPc.member_id==row.id))).scalars().all())
        await s.commit();return {'ok':True,'token':token,'remember_me':remember_me,'expires_at':expires.isoformat(),'member':_member(row,pcs)}

async def authenticate_token(token:str)->dict|None:
    if not token:return None
    async with SessionLocal() as s:
        session=(await s.execute(select(AgentStudioAuthSession).where(AgentStudioAuthSession.token_hash==_token_hash(token),AgentStudioAuthSession.revoked==False))).scalar_one_or_none()
        if not session or session.expires_at<=datetime.utcnow():return None
        row=await s.get(AgentStudioMember,session.member_id)
        if not row or not row.is_active:return None
        session.last_used_at=datetime.utcnow();pcs=list((await s.execute(select(AgentStudioMemberPc.pc_name).where(AgentStudioMemberPc.member_id==row.id))).scalars().all());await s.commit()
        return _member(row,pcs)

async def logout(token:str)->dict:
    async with SessionLocal() as s:
        row=(await s.execute(select(AgentStudioAuthSession).where(AgentStudioAuthSession.token_hash==_token_hash(token)))).scalar_one_or_none()
        if row:row.revoked=True;await s.commit()
    return {'ok':True}

async def list_members()->dict:
    async with SessionLocal() as s:
        members=(await s.execute(select(AgentStudioMember).order_by(AgentStudioMember.created_at))).scalars().all();items=[]
        for row in members:
            pcs=list((await s.execute(select(AgentStudioMemberPc.pc_name).where(AgentStudioMemberPc.member_id==row.id))).scalars().all());items.append(_member(row,pcs))
        return {'ok':True,'items':items}

async def update_member_admin(member_id:str,payload:dict)->dict:
    async with SessionLocal() as s:
        row=await s.get(AgentStudioMember,member_id)
        if not row: raise KeyError('회원을 찾을 수 없습니다.')
        if 'name' in payload:row.name=str(payload.get('name') or '').strip()
        if 'email' in payload:row.email=str(payload.get('email') or '').strip().lower()
        if 'role' in payload:
            role=str(payload.get('role') or '').upper()
            if role not in {'ADMIN','USER'}:raise ValueError('권한은 ADMIN 또는 USER만 가능합니다.')
            row.role=role
        if 'is_active' in payload:row.is_active=bool(payload.get('is_active'))
        await s.commit();return {'ok':True,'member':_member(row)}

async def set_member_pcs(member_id:str,pcs:list[str])->dict:
    normalized=sorted({str(x).strip() for x in pcs if str(x).strip()})
    async with SessionLocal() as s:
        if not await s.get(AgentStudioMember,member_id):raise KeyError('회원을 찾을 수 없습니다.')
        existing=(await s.execute(select(AgentStudioMemberPc).where(AgentStudioMemberPc.member_id==member_id))).scalars().all()
        for row in existing:await s.delete(row)
        for pc in normalized:s.add(AgentStudioMemberPc(id=uuid.uuid4().hex,member_id=member_id,pc_name=pc,can_manage=True))
        await s.commit();return {'ok':True,'pcs':normalized}
