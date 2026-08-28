from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from app.services.auth_service import authenticate_token, list_members, list_registered_pcs, login, logout, register_member, set_member_pcs, update_member_admin
router=APIRouter(prefix='/auth',tags=['Auth'])

def _bearer(value:str)->str:
    return value[7:].strip() if str(value or '').lower().startswith('bearer ') else ''
async def _current(auth:str)->dict:
    member=await authenticate_token(_bearer(auth))
    if not member:raise HTTPException(status_code=401,detail='로그인이 필요합니다.')
    return member
async def _admin(auth:str)->dict:
    member=await _current(auth)
    if member.get('role')!='ADMIN':raise HTTPException(status_code=403,detail='관리자 권한이 필요합니다.')
    return member
class RegisterReq(BaseModel):login_id:str;password:str;name:str;email:str
class LoginReq(BaseModel):login_id:str;password:str;remember_me:bool=False
class MemberUpdateReq(BaseModel):name:str|None=None;email:str|None=None;role:str|None=None;is_active:bool|None=None
class PcReq(BaseModel):pcs:list[str]=[]
@router.post('/register')
async def register(req:RegisterReq):
    try:return await register_member(req.model_dump())
    except ValueError as e:raise HTTPException(status_code=422,detail=str(e))
@router.post('/login')
async def do_login(req:LoginReq):
    try:return await login(req.login_id,req.password,req.remember_me)
    except ValueError as e:raise HTTPException(status_code=401,detail=str(e))
@router.get('/me')
async def me(authorization:str=Header(default='')):return {'ok':True,'member':await _current(authorization)}
@router.post('/logout')
async def do_logout(authorization:str=Header(default='')):return await logout(_bearer(authorization))
@router.get('/members')
async def members(authorization:str=Header(default='')):await _admin(authorization);return await list_members()
@router.get('/pcs')
async def pcs(authorization:str=Header(default='')):await _admin(authorization);return await list_registered_pcs()
@router.patch('/members/{member_id}')
async def update_member(member_id:str,req:MemberUpdateReq,authorization:str=Header(default='')):
    await _admin(authorization)
    try:return await update_member_admin(member_id,{k:v for k,v in req.model_dump().items() if v is not None})
    except KeyError as e:raise HTTPException(status_code=404,detail=str(e))
    except ValueError as e:raise HTTPException(status_code=422,detail=str(e))
@router.put('/members/{member_id}/pcs')
async def member_pcs(member_id:str,req:PcReq,authorization:str=Header(default='')):
    await _admin(authorization)
    try:return await set_member_pcs(member_id,req.pcs)
    except KeyError as e:raise HTTPException(status_code=404,detail=str(e))
