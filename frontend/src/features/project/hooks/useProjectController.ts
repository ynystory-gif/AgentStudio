import { useDeferredValue, useRef, useState } from 'react'

type LegacyValue=any
type LegacyRecord=Record<string,any>

export function useProjectController(){
  const [projectSearch,setProjectSearch]=useState('')
  const deferredProjectSearch=useDeferredValue(projectSearch)
  const [projectFilter,setProjectFilter]=useState('ALL')
  const [projectListStatus,setProjectListStatus]=useState('DB 프로젝트 목록을 아직 읽지 않았습니다.')
  const [projectListLogPath,setProjectListLogPath]=useState('')
  const [projectDbDiagnostic,setProjectDbDiagnostic]=useState<LegacyValue|null>(null)
  const [projectLoadMessage,setProjectLoadMessage]=useState('')
  const [projectLoadProgress,setProjectLoadProgress]=useState({active:false,percent:0,message:'',failed:false})
  const projectLoadSequenceRef=useRef(0)

  const beginProjectLoad=(message='프로젝트를 불러오는 중입니다.')=>{
    const token=++projectLoadSequenceRef.current
    setProjectLoadMessage(message)
    setProjectLoadProgress({active:true,percent:5,message,failed:false})
    return token
  }
  const updateProjectLoad=(token:number,percent:number,message:string)=>{
    if(token!==projectLoadSequenceRef.current)return false
    setProjectLoadMessage(message)
    setProjectLoadProgress({active:true,percent:Math.max(0,Math.min(100,percent)),message,failed:false})
    return true
  }
  const completeProjectLoad=(token:number,message='프로젝트 로드 완료')=>{
    if(token!==projectLoadSequenceRef.current)return false
    setProjectLoadMessage(message)
    setProjectLoadProgress({active:false,percent:100,message,failed:false})
    return true
  }
  const failProjectLoad=(token:number,error:unknown)=>{
    if(token!==projectLoadSequenceRef.current)return false
    const message=String(error||'프로젝트 로드 실패')
    setProjectLoadMessage(message)
    setProjectLoadProgress({active:false,percent:0,message,failed:true})
    return true
  }
  const invalidateProjectLoad=()=>{
    projectLoadSequenceRef.current+=1
    setProjectLoadProgress(prev=>({...prev,active:false}))
  }
  const filterProjects=(projects:LegacyValue[]|undefined)=>{
    const q=String(deferredProjectSearch||'').trim().toLowerCase()
    const kind=String(projectFilter||'ALL').toUpperCase()
    return (Array.isArray(projects)?projects:[]).filter((item:LegacyRecord)=>{
      if(kind!=='ALL'){
        const category=String(item?.project_type||item?.type||item?.status||'').toUpperCase()
        if(category&&category!==kind)return false
      }
      if(!q)return true
      const haystack=[item?.name,item?.project_name,item?.description,item?.project_root,item?.root_path]
        .map(v=>String(v||'').toLowerCase()).join(' ')
      return haystack.includes(q)
    })
  }
  return {
    projectSearch,setProjectSearch,deferredProjectSearch,
    projectFilter,setProjectFilter,
    projectListStatus,setProjectListStatus,
    projectListLogPath,setProjectListLogPath,
    projectDbDiagnostic,setProjectDbDiagnostic,
    projectLoadMessage,setProjectLoadMessage,
    projectLoadProgress,setProjectLoadProgress,
    beginProjectLoad,updateProjectLoad,completeProjectLoad,failProjectLoad,invalidateProjectLoad,
    filterProjects,
  }
}
