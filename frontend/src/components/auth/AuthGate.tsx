import { FormEvent, ReactNode, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { api, clearAuthToken, getAuthToken, setAuthToken } from '../../api'
import './auth.css'

type Member={id:string;login_id:string;name:string;email:string;role:string;is_active:boolean;pcs:string[]}
type PcRow={pc_name:string;host_name:string;os_name:string;last_seen_at:string}
type CurrentPcStatus={current_pc_name:string;registered:boolean;member_pcs:string[];machine?:PcRow}

export function AuthGate({children}:{children:ReactNode}){
  const [ready,setReady]=useState(false)
  const [member,setMember]=useState<Member|null>(null)
  const [mode,setMode]=useState<'login'|'signup'>('login')
  const [busy,setBusy]=useState(false)
  const [message,setMessage]=useState('')
  const [remember,setRemember]=useState(true)
  const [manageOpen,setManageOpen]=useState(false)
  const [menuOpen,setMenuOpen]=useState(false)
  const [pcStatus,setPcStatus]=useState<CurrentPcStatus|null>(null)
  const [profileHost,setProfileHost]=useState<HTMLElement|null>(null)
  const [contentHost,setContentHost]=useState<HTMLElement|null>(null)
  const menuRef=useRef<HTMLDivElement|null>(null)

  const loadPcStatus=async()=>{
    const result=await api<any>('/auth/current-pc')
    setPcStatus({current_pc_name:String(result?.current_pc_name||''),registered:Boolean(result?.registered),member_pcs:Array.isArray(result?.member_pcs)?result.member_pcs:[],machine:result?.machine||undefined})
    return result
  }

  useEffect(()=>{
    const token=getAuthToken()
    if(!token){setReady(true);return}
    api<any>('/auth/me').then(async r=>{setMember(r.member);try{await loadPcStatus()}catch{}}).catch(()=>clearAuthToken()).finally(()=>setReady(true))
  },[])

  useEffect(()=>{
    if(!member)return
    let disposed=false
    const locate=()=>{
      if(disposed)return
      setProfileHost(document.querySelector<HTMLElement>('.profile-block'))
      setContentHost(document.querySelector<HTMLElement>('.ux-content'))
    }
    locate()
    const timer=window.setInterval(locate,400)
    return()=>{disposed=true;window.clearInterval(timer)}
  },[member])

  useEffect(()=>{
    if(!profileHost)return
    profileHost.classList.add('agentstudio-auth-profile-anchor')
    profileHost.setAttribute('title',`${member?.name||'사용자'} 사용자 메뉴`)
    profileHost.setAttribute('role','button')
    profileHost.setAttribute('tabindex','0')
    const openMenu=(event:Event)=>{
      const target=event.target as HTMLElement
      if(target.closest('.auth-user-dropdown'))return
      event.preventDefault();event.stopPropagation()
      setMenuOpen(prev=>{
        const next=!prev
        if(next)void loadPcStatus().catch(err=>setMessage(String(err)))
        return next
      })
    }
    const onKey=(event:KeyboardEvent)=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();openMenu(event)}}
    profileHost.addEventListener('click',openMenu,true)
    profileHost.addEventListener('keydown',onKey,true)
    return()=>{
      profileHost.removeEventListener('click',openMenu,true)
      profileHost.removeEventListener('keydown',onKey,true)
      profileHost.classList.remove('agentstudio-auth-profile-anchor')
      profileHost.removeAttribute('role');profileHost.removeAttribute('tabindex')
    }
  },[profileHost,member])

  useEffect(()=>{
    if(!menuOpen)return
    const close=(event:MouseEvent)=>{
      const target=event.target as Node
      if(profileHost?.contains(target)||menuRef.current?.contains(target))return
      setMenuOpen(false)
    }
    window.addEventListener('mousedown',close)
    return()=>window.removeEventListener('mousedown',close)
  },[menuOpen,profileHost])

  useEffect(()=>{
    if(!contentHost)return
    contentHost.classList.toggle('member-admin-active',manageOpen)
    return()=>contentHost.classList.remove('member-admin-active')
  },[contentHost,manageOpen])

  useEffect(()=>{
    if(!manageOpen)return
    const nav=document.querySelector<HTMLElement>('.ux-global-nav')
    if(!nav)return
    const close=()=>setManageOpen(false)
    nav.addEventListener('click',close,true)
    return()=>nav.removeEventListener('click',close,true)
  },[manageOpen])

  const login=async(e:FormEvent<HTMLFormElement>)=>{
    e.preventDefault();setBusy(true);setMessage('')
    const fd=new FormData(e.currentTarget)
    try{
      const r=await api<any>('/auth/login',{method:'POST',body:JSON.stringify({login_id:fd.get('login_id'),password:fd.get('password'),remember_me:remember})})
      setAuthToken(r.token,remember);setMember(r.member)
      setPcStatus({current_pc_name:String(r.current_pc_name||''),registered:Boolean(r.current_pc_registered),member_pcs:r.member?.pcs||[]})
    }catch(err){setMessage(String(err))}finally{setBusy(false)}
  }

  const signup=async(e:FormEvent<HTMLFormElement>)=>{
    e.preventDefault();setBusy(true);setMessage('')
    const fd=new FormData(e.currentTarget)
    const password=String(fd.get('password')||'');const confirm=String(fd.get('password_confirm')||'')
    if(password!==confirm){setMessage('비밀번호 확인이 일치하지 않습니다.');setBusy(false);return}
    try{
      const result=await api<any>('/auth/register',{method:'POST',body:JSON.stringify({login_id:fd.get('login_id'),password,name:fd.get('name'),email:fd.get('email')})})
      setMessage(`회원가입이 완료되었습니다. 현재 PC '${result?.current_pc_name||''}'도 자동 등록되었습니다. 로그인해 주세요.`);setMode('login')
    }catch(err){setMessage(String(err))}finally{setBusy(false)}
  }

  const logout=async()=>{try{await api('/auth/logout',{method:'POST'})}catch{}clearAuthToken();setMember(null);setPcStatus(null);setMenuOpen(false);setManageOpen(false)}
  const registerCurrentPc=async()=>{
    setBusy(true);setMessage('')
    try{
      const result=await api<any>('/auth/current-pc/register',{method:'POST'})
      if(result?.member)setMember(result.member)
      setPcStatus({current_pc_name:String(result?.current_pc_name||''),registered:true,member_pcs:result?.member_pcs||result?.member?.pcs||[]})
      setMessage(`현재 PC '${result?.current_pc_name||''}'가 등록되었습니다.`);setMenuOpen(false)
      window.setTimeout(()=>window.location.reload(),180)
    }catch(err){setMessage(String(err))}finally{setBusy(false)}
  }

  if(!ready)return <div className="auth-splash"><strong>THEANOVA AgentStudio</strong><span>로그인 상태 확인 중...</span></div>
  if(!member)return <div className="auth-page"><section className="auth-card"><div className="auth-brand"><b>THEANOVA</b><strong>AgentStudio</strong><span>AI Agent & MCP Development Studio</span></div><div className="auth-tabs"><button className={mode==='login'?'active':''} onClick={()=>{setMode('login');setMessage('')}}>로그인</button><button className={mode==='signup'?'active':''} onClick={()=>{setMode('signup');setMessage('')}}>회원가입</button></div>{mode==='login'?<form onSubmit={login}><label>아이디<input name="login_id" required autoFocus autoComplete="username"/></label><label>비밀번호<input name="password" type="password" required autoComplete="current-password"/></label><label className="auth-remember"><input type="checkbox" checked={remember} onChange={e=>setRemember(e.target.checked)}/><span>다음부터 자동 로그인</span></label><button className="primary" disabled={busy}>{busy?'로그인 중...':'로그인'}</button></form>:<form onSubmit={signup}><label>아이디<input name="login_id" required minLength={3}/></label><label>이름<input name="name" required/></label><label>이메일<input name="email" type="email" required/></label><label>비밀번호<input name="password" type="password" required minLength={8}/></label><label>비밀번호 확인<input name="password_confirm" type="password" required minLength={8}/></label><button className="primary" disabled={busy}>{busy?'가입 처리 중...':'회원가입'}</button></form>}{message&&<div className="auth-message">{message}</div>}<small className="auth-note">회원가입한 PC는 해당 사용자 계정의 첫 관리 PC로 자동 등록됩니다. 첫 번째 가입 회원은 초기 관리자 권한으로 생성됩니다.</small></section></div>

  const managedPcs=pcStatus?.member_pcs?.length?pcStatus.member_pcs:(member.pcs||[])
  const menu=menuOpen&&profileHost?createPortal(<div className="auth-user-dropdown" ref={menuRef} role="menu" onClick={e=>e.stopPropagation()}>
    <div className="auth-user-summary"><div><strong>{member.name}</strong><small>{member.login_id} · {member.role}</small></div></div>
    <div className={`auth-current-pc ${pcStatus?.registered?'registered':'unregistered'}`}><span>현재 PC</span><strong>{pcStatus?.current_pc_name||'확인 중...'}</strong><em>{pcStatus?.registered?'등록됨':'미등록'}</em></div>
    {!pcStatus?.registered&&<button className="auth-menu-primary" disabled={busy} onClick={registerCurrentPc}>＋ 현재 PC 등록</button>}
    <div className="auth-pc-section"><b>내 PC</b>{managedPcs.length?<div>{managedPcs.map(pc=><span key={pc} className={pc===pcStatus?.current_pc_name?'current':''}>{pc}{pc===pcStatus?.current_pc_name&&<em>현재 PC</em>}</span>)}</div>:<small>등록된 PC가 없습니다.</small>}</div>
    <div className="auth-menu-separator"/>
    {member.role==='ADMIN'&&<button onClick={()=>{setMenuOpen(false);setManageOpen(true)}}>회원 관리</button>}
    <button onClick={logout}>로그아웃</button>
  </div>,profileHost):null

  const adminPage=manageOpen&&contentHost?createPortal(<MemberAdmin onClose={()=>setManageOpen(false)}/>,contentHost):null

  return <div className="auth-root">{children}{menu}{adminPage}{message&&member&&<div className="auth-toast">{message}</div>}</div>
}

function MemberAdmin({onClose}:{onClose:()=>void}){
  const [items,setItems]=useState<Member[]>([])
  const [pcs,setPcs]=useState<PcRow[]>([])
  const [message,setMessage]=useState('')
  const load=async()=>{try{const [m,p]=await Promise.all([api<any>('/auth/members'),api<any>('/auth/pcs')]);setItems(m.items||[]);setPcs(p.items||[])}catch(e){setMessage(String(e))}}
  useEffect(()=>{load()},[])
  const togglePc=(index:number,pcName:string,checked:boolean)=>setItems(v=>v.map((x,n)=>n===index?{...x,pcs:checked?Array.from(new Set([...(x.pcs||[]),pcName])):(x.pcs||[]).filter(p=>p!==pcName)}:x))
  const save=async(row:Member)=>{try{await api(`/auth/members/${row.id}`,{method:'PATCH',body:JSON.stringify({name:row.name,email:row.email,role:row.role,is_active:row.is_active})});await api(`/auth/members/${row.id}/pcs`,{method:'PUT',body:JSON.stringify({pcs:row.pcs})});setMessage(`${row.login_id} 회원 정보가 저장되었습니다.`);await load()}catch(e){setMessage(String(e))}}
  return <section className="member-admin-page"><div className="member-admin"><header><div><strong>회원 관리</strong><small>회원 정보·권한·사용 가능 PC를 관리합니다. 한 사용자가 집 PC, 학원 노트북 등 여러 PC를 동시에 등록할 수 있습니다.</small></div><button onClick={onClose}>본문으로 돌아가기</button></header>{message&&<div className="auth-message">{message}</div>}<div className="member-table"><table><thead><tr><th>아이디</th><th>이름</th><th>이메일</th><th>권한</th><th>사용</th><th>관리 PC</th><th></th></tr></thead><tbody>{items.map((row,i)=><tr key={row.id}><td>{row.login_id}</td><td><input value={row.name} onChange={e=>setItems(v=>v.map((x,n)=>n===i?{...x,name:e.target.value}:x))}/></td><td><input value={row.email} onChange={e=>setItems(v=>v.map((x,n)=>n===i?{...x,email:e.target.value}:x))}/></td><td><select value={row.role} onChange={e=>setItems(v=>v.map((x,n)=>n===i?{...x,role:e.target.value}:x))}><option>USER</option><option>ADMIN</option></select></td><td><input type="checkbox" checked={row.is_active} onChange={e=>setItems(v=>v.map((x,n)=>n===i?{...x,is_active:e.target.checked}:x))}/></td><td><div className="member-pc-list">{pcs.length?pcs.map(pc=><label key={pc.pc_name}><input type="checkbox" checked={(row.pcs||[]).includes(pc.pc_name)} onChange={e=>togglePc(i,pc.pc_name,e.target.checked)}/><span>{pc.pc_name}</span></label>):<small>등록된 PC가 없습니다.</small>}</div></td><td><button onClick={()=>save(row)}>저장</button></td></tr>)}</tbody></table></div></div></section>
}
