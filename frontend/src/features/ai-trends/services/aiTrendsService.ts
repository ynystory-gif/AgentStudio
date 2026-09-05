import { api } from '../../../api'
import type { AITrendsDashboardData } from '../types/aiTrends'

export async function loadAITrends(projectRoot:string=''):Promise<AITrendsDashboardData>{
  const query=projectRoot?`?project_root=${encodeURIComponent(projectRoot)}`:''
  return api(`/ai-trends${query}`)
}
