from __future__ import annotations
import base64, hashlib, hmac, os, platform, secrets, socket, uuid
from datetime import datetime, timedelta
from sqlalchemy import func, select
from app.core.database import SessionLocal
from app.core.machine_identity import current_pc_name, detect_system_pc_name
from app.models.auth_entities import AgentStudioAuthSession, AgentStudioMember, AgentStudioMemberPc
from app.models.entities import AgentStudioMachine

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

async def _ensure_machine_row(session, pc_name:str)->AgentStudioMachine:
    machine=(await session.execute(select(AgentStudioMachine).where(AgentStudioMachine.pc_name==pc_name))).scalar_one_or_none()
    now=datetime.utcnow()
    if machine is None:
        machine=AgentStudioMachine(
            pc_name=pc_name,
            host_name=socket.gethostname(),
            os_name=platform.platform(),
            created_at=now,
            last_seen_at=now,
        )
        session.add(machine)
    else:
        machine.last_seen_at=now
        if not str(machine.host_name or '').strip(): machine.host_name=socket.gethostname()
        if not str(machine.os_name or '').strip(): machine.os_name=platform.platform()
    return machine


async def _reconcile_current_pc_alias(session, member_id: str, pcs: list[str]) -> list[str]:
    """Repair the v5.511/v5.512 machine-identity split without bypassing PC security.

    Those releases could read the physical Windows host name from backend/.env logic
    while the authoritative project-root .env already contained a user-managed
    AGENTSTUDIO_PC_NAME.  If this member is already registered to this exact physical
    host, add the configured AgentStudio PC alias as the same machine.  No unrelated
    unregistered PC is auto-approved.
    """
    configured = current_pc_name()
    physical = detect_system_pc_name()
    normalized = {str(x or '').strip() for x in pcs if str(x or '').strip()}
    if not configured or configured in normalized or not physical or physical not in normalized:
        return sorted(normalized)
    await _ensure_machine_row(session, configured)
    existing=(await session.execute(select(AgentStudioMemberPc).where(AgentStudioMemberPc.member_id==member_id,AgentStudioMemberPc.pc_name==configured))).scalar_one_or_none()
    if not existing:
        session.add(AgentStudioMemberPc(id=uuid.uuid4().hex,member_id=member_id,pc_name=configured,can_manage=True))
        await session.flush()
    normalized.add(configured)
    print(f"[AUTH] PC 이름 설정 전환 자동 보정: physical={physical} -> configured={configured}")
    return sorted(normalized)

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
        pc=current_pc_name()
        await _ensure_machine_row(s,pc)
        s.add(AgentStudioMemberPc(id=uuid.uuid4().hex,member_id=row.id,pc_name=pc,can_manage=True))
        await s.commit();return {'ok':True,'member':_member(row,[pc]),'first_admin':count==0,'current_pc_name':pc,'current_pc_registered':True}

async def login(login_id:str,password:str,remember_me:bool)->dict:
    async with SessionLocal() as s:
        normalized_login_id=login_id.strip()
        row=(await s.execute(select(AgentStudioMember).where(AgentStudioMember.login_id==normalized_login_id))).scalar_one_or_none()
        if not row:
            from app.services.database_runtime_service import runtime_status
            status=await runtime_status()
            print(f"[AUTH] 로그인 계정 없음: provider={status.get('active_provider','')} target={status.get('supabase_target') if status.get('active_provider')=='supabase' else status.get('local_target')} login_id={normalized_login_id}")
            raise ValueError('아이디 또는 비밀번호가 올바르지 않습니다.')
        if not row.is_active:
            print(f"[AUTH] 비활성 계정 로그인 거부: login_id={normalized_login_id}")
            raise ValueError('아이디 또는 비밀번호가 올바르지 않습니다.')
        if not _verify_password(password,row.password_hash):
            from app.services.database_runtime_service import runtime_status
            status=await runtime_status()
            print(f"[AUTH] 비밀번호 불일치: provider={status.get('active_provider','')} target={status.get('supabase_target') if status.get('active_provider')=='supabase' else status.get('local_target')} login_id={normalized_login_id}")
            raise ValueError('아이디 또는 비밀번호가 올바르지 않습니다.')
        pc=current_pc_name()
        pcs=list((await s.execute(select(AgentStudioMemberPc.pc_name).where(AgentStudioMemberPc.member_id==row.id))).scalars().all())
        pcs=await _reconcile_current_pc_alias(s,row.id,pcs)
        token=secrets.token_urlsafe(48);expires=datetime.utcnow()+timedelta(days=REMEMBER_DAYS) if remember_me else datetime.utcnow()+timedelta(hours=SESSION_HOURS)
        s.add(AgentStudioAuthSession(id=uuid.uuid4().hex,member_id=row.id,token_hash=_token_hash(token),remember_me=remember_me,expires_at=expires))
        await s.commit();return {'ok':True,'token':token,'remember_me':remember_me,'expires_at':expires.isoformat(),'member':_member(row,pcs),'current_pc_name':pc,'current_pc_registered':pc in pcs}

async def authenticate_token(token:str)->dict|None:
    if not token:return None
    async with SessionLocal() as s:
        session=(await s.execute(select(AgentStudioAuthSession).where(AgentStudioAuthSession.token_hash==_token_hash(token),AgentStudioAuthSession.revoked==False))).scalar_one_or_none()
        if not session or session.expires_at<=datetime.utcnow():return None
        row=await s.get(AgentStudioMember,session.member_id)
        if not row or not row.is_active:return None
        session.last_used_at=datetime.utcnow();pcs=list((await s.execute(select(AgentStudioMemberPc.pc_name).where(AgentStudioMemberPc.member_id==row.id))).scalars().all());pcs=await _reconcile_current_pc_alias(s,row.id,pcs);await s.commit()
        return _member(row,pcs)

async def current_pc_status(member_id:str)->dict:
    pc=current_pc_name()
    async with SessionLocal() as s:
        row=await s.get(AgentStudioMember,member_id)
        if not row: raise KeyError('회원을 찾을 수 없습니다.')
        pcs=list((await s.execute(select(AgentStudioMemberPc.pc_name).where(AgentStudioMemberPc.member_id==member_id))).scalars().all())
        machine=(await s.execute(select(AgentStudioMachine).where(AgentStudioMachine.pc_name==pc))).scalar_one_or_none()
        return {
            'ok':True,
            'current_pc_name':pc,
            'registered':pc in pcs,
            'member_pcs':sorted(pcs),
            'machine':{
                'pc_name':pc,
                'host_name':getattr(machine,'host_name','') or '',
                'os_name':getattr(machine,'os_name','') or '',
                'last_seen_at':machine.last_seen_at.isoformat() if machine and machine.last_seen_at else '',
            }
        }

async def register_current_pc_for_member(member_id:str)->dict:
    pc=current_pc_name()
    async with SessionLocal() as s:
        row=await s.get(AgentStudioMember,member_id)
        if not row: raise KeyError('회원을 찾을 수 없습니다.')
        await _ensure_machine_row(s,pc)
        existing=(await s.execute(select(AgentStudioMemberPc).where(AgentStudioMemberPc.member_id==member_id,AgentStudioMemberPc.pc_name==pc))).scalar_one_or_none()
        if not existing:
            s.add(AgentStudioMemberPc(id=uuid.uuid4().hex,member_id=member_id,pc_name=pc,can_manage=True))
        await s.commit()
        pcs=list((await s.execute(select(AgentStudioMemberPc.pc_name).where(AgentStudioMemberPc.member_id==member_id))).scalars().all())
        return {'ok':True,'current_pc_name':pc,'registered':True,'member':_member(row,sorted(pcs)),'member_pcs':sorted(pcs)}

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

async def list_registered_pcs()->dict:
    """Return every PC that can be assigned to a member.

    Runtime DB switching can leave agentstudio_machines sparse while member-PC mappings
    already exist in the shared DB. The management screen therefore uses the union of
    machine registry rows and actual member assignments instead of hiding valid mappings.
    """
    async with SessionLocal() as s:
        machines=(await s.execute(select(AgentStudioMachine).order_by(AgentStudioMachine.pc_name))).scalars().all()
        mapped_names=set((await s.execute(select(AgentStudioMemberPc.pc_name).distinct())).scalars().all())
        by_name={str(r.pc_name):{
            'pc_name':str(r.pc_name),
            'host_name':str(r.host_name or ''),
            'os_name':str(r.os_name or ''),
            'last_seen_at':r.last_seen_at.isoformat() if r.last_seen_at else '',
            'source':'machine_registry',
        } for r in machines}
        for pc_name in sorted(mapped_names):
            if pc_name and pc_name not in by_name:
                by_name[pc_name]={
                    'pc_name':pc_name,
                    'host_name':'',
                    'os_name':'',
                    'last_seen_at':'',
                    'source':'member_mapping',
                }
        current=current_pc_name()
        if current and current not in by_name:
            by_name[current]={
                'pc_name':current,
                'host_name':socket.gethostname(),
                'os_name':platform.platform(),
                'last_seen_at':'',
                'source':'current_pc',
            }
        return {'ok':True,'items':[by_name[name] for name in sorted(by_name)]}

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
        for pc in normalized:
            await _ensure_machine_row(s,pc)
            s.add(AgentStudioMemberPc(id=uuid.uuid4().hex,member_id=member_id,pc_name=pc,can_manage=True))
        await s.commit();return {'ok':True,'pcs':normalized}
