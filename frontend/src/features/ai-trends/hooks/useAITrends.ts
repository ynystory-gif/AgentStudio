import { useCallback,useEffect,useState } from 'react'
import { loadAITrends } from '../services/aiTrendsService'
import type { AITrendsDashboardData } from '../types/aiTrends'

export function useAITrends(active:boolean,projectRoot:string=''){
  const [data,setData]=useState<AITrendsDashboardData|null>(null)
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')

  const refresh=useCallback(async()=>{
    setBusy(true); setError('')
    try{setData(await loadAITrends(projectRoot))}
    catch(e){setError(e instanceof Error?e.message:String(e))}
    finally{setBusy(false)}
  },[projectRoot])

  useEffect(()=>{if(active&&!busy) void refresh()},[active,projectRoot,refresh])
  return {data,busy,error,refresh}
}
