import { useCallback,useEffect,useState } from 'react'
import { loadAITrends } from '../services/aiTrendsService'
import type { AITrendsDashboardData } from '../types/aiTrends'

export function useAITrends(active:boolean){
  const [data,setData]=useState<AITrendsDashboardData|null>(null)
  const [busy,setBusy]=useState(false)
  const [error,setError]=useState('')

  const refresh=useCallback(async()=>{
    setBusy(true); setError('')
    try{setData(await loadAITrends())}
    catch(e){setError(e instanceof Error?e.message:String(e))}
    finally{setBusy(false)}
  },[])

  useEffect(()=>{if(active&&!data&&!busy) void refresh()},[active,data,busy,refresh])
  return {data,busy,error,refresh}
}
