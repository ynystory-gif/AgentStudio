import { api } from '../../../api'
import type { AITrendsDashboardData } from '../types/aiTrends'

export async function loadAITrends():Promise<AITrendsDashboardData>{
  return api('/ai-trends')
}
