import { FormEvent, ReactNode, useEffect, useState } from 'react'
import { api, clearAuthToken, getAuthToken, setAuthToken } from '../../api'
import './auth.css'

type Member={id:string;login_id:string;name:string;email:string;role:string;is_active:boolean;pcs:string[]}

export function AuthGate({children}:{children:ReactNode}){
  const [ready,setReady]=useState(false)
  const [member,setMember]=useState<Member|null>(null)
  const [mode,setMode]=useState<'login'|'signup'>('login')
  const [busy,setBusy]=useState(false)
  const [message,setMessage]=useState('')
  const [remember,setRemember]=useState(true)
  const [manageOpen,setManageOpen]=useState(false)

  useEffect(()=>{
    const token=getAuthToken()
    if(!token){setReady(true);return}
    api<any>('/auth/me').then(r=>setMember(r.member)).catch(()=>clearAuthToken()).finally(()=>setReady(true))
  },[])

  const login=async(e:FormEvent<HTMLFormElement>)=>{
    e.preventDefault();setBusy(true);setMessage('')
    const fd=new FormData(e.currentTarget)
    try{
      const r=await api<any>('/auth/login',{method:'POST',body:JSON.stringify({login_id:fd.get('login_id'),password:fd.get('password'),remember_me:remember})})
      setAuthToken(r.token,remember);setMember(r.member)
    }catch(err){setMessage(String(err))}finally{setBusy(false)}
  }
  const signup=async(e:FormEvent<HTMLFormElement>)=>{
    e.preventDefault();setBusy(true);setMessage('')
    const fd=new FormData(e.currentTarget)
    const password=String(fd.get('password')||'');const confirm=String(fd.get('password_confirm')||'')
    if(password!==confirm){setMessage('비밀번호 확인이 일치하지 않습니다.');setBusy(false);return}
    try{
      await api('/auth/register',{method:'POST',body:JSON.stringify({login_id:fd.get('login_id'),password,name:fd.get('name'),email:fd.get('email')})})
      setMessage('회원가입이 완료되었습니다. 로그인해 주세요.');setMode('login')
    }catch(err){setMessage(String(err))}finally{setBusy(false)}
  }
  const logout=async()=>{try{await api('/auth/logout',{method:'POST'})}catch{}clearAuthToken();setMember(null);setManageOpen(false)}

  if(!ready)return <div className="auth-splash"><strong>THEANOVA AgentStudio</strong><span>로그인 상태 확인 중...</span></div>
  if(!member)return <div className="auth-page"><section className="auth-card"><div className="auth-brand"><b>THEANOVA</b><strong>AgentStudio</strong><span>AI Agent & MCP Development Studio</span></div><div className="auth-tabs"><button className={mode==='login'?'active':''} onClick={()=>{setMode('login');setMessage('')}}>로그인</button><button className={mode==='signup'?'active':''} onClick={()=>{setMode('signup');setMessage('')}}>회원가입</button></div>{mode==='login'?<form onSubmit={login}><label>아이디<input name="login_id" required autoFocus autoComplete="username"/></label><label>비밀번호<input name="password" type="password" required autoComplete="current-password"/></label><label className="auth-remember"><input type="checkbox" checked={remember} onChange={e=>setRemember(e.target.checked)}/><span>다음부터 자동 로그인</span></label><button className="primary" disabled={busy}>{busy?'로그인 중...':'로그인'}</button></form>:<form onSubmit={signup}><label>아이디<input name="login_id" required minLength={3} autoComplete="username"/></label><label>이름<input name="name" required autoComplete="name"/></label><label>이메일<input name="email" type="email" required autoComplete="email"/></label><label>비밀번호<input name="password" type="password" required minLength={8} autoComplete="new-password"/></label><label>비밀번호 확인<input name="password_confirm" type="password" required minLength={8} autoComplete="new-password"/></label><button className="primary" disabled={busy}>{busy?'가입 처리 중...':'회원가입'}</button></form>}{message&&<div className="auth-message">{message}</div>}<small className="auth-note">첫 번째 가입 회원은 초기 관리자 권한으로 생성됩니다.</small></section></div>

  return <div className="auth-root"><div className="auth-userbar"><span><b>{member.name}</b> <em>{member.role}</em></span>{member.role==='ADMIN'&&<button onClick={()=>setManageOpen(true)}>회원 관리</button>}<button onClick={logout}>로그아웃</button></div>{children}{manageOpen&&<MemberAdmin onClose={()=>setManageOpen(false)}/>}</div>
}

function MemberAdmin({onClose}:{onClose:()=>void}){
  const [items,setItems]=useState<Member[]>([]);const [message,setMessage]=useState('')
  const load=()=>api<any>('/auth/members').then(r=>setItems(r.items||[])).catch(e=>setMessage(String(e)))
  useEffect(()=>{load()},[])
  const save=async(row:Member)=>{try{await api(`/auth/members/${row.id}`,{method:'PATCH',body:JSON.stringify({name:row.name,email:row.email,role:row.role,is_active:row.is_active})});await api(`/auth/members/${row.id}/pcs`,{method:'PUT',body:JSON.stringify({pcs:row.pcs})});setMessage('저장되었습니다.')}catch(e){setMessage(String(e))}}
  return <div className="member-admin-overlay"><section className="member-admin"><header><div><strong>회원 관리</strong><small>회원별 권한과 관리 PC를 설정합니다.</small></div><button onClick={onClose}>✕</button></header>{message&&<div className="auth-message">{message}</div>}<div className="member-table"><table><thead><tr><th>아이디</th><th>이름</th><th>이메일</th><th>권한</th><th>사용</th><th>관리 PC</th><th></th></tr></thead><tbody>{items.map((row,i)=><tr key={row.id}><td>{row.login_id}</td><td><input value={row.name} onChange={e=>setItems(v=>v.map((x,n)=>n===i?{...x,name:e.target.value}:x))}/></td><td><input value={row.email} onChange={e=>setItems(v=>v.map((x,n)=>n===i?{...x,email:e.target.value}:x))}/></td><td><select value={row.role} onChange={e=>setItems(v=>v.map((x,n)=>n===i?{...x,role:e.target.value}:x))}><option>USER</option><option>ADMIN</option></select></td><td><input type="checkbox" checked={row.is_active} onChange={e=>setItems(v=>v.map((x,n)=>n===i?{...x,is_active:e.target.checked}:x))}/></td><td><input value={(row.pcs||[]).join(', ')} onChange={e=>setItems(v=>v.map((x,n)=>n===i?{...x,pcs:e.target.value.split(',').map(s=>s.trim()).filter(Boolean)}:x))} placeholder="A-PC, B-PC"/></td><td><button onClick={()=>save(row)}>저장</button></td></tr>)}</tbody></table></div></section></div>
}
