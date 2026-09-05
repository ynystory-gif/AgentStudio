export type AITrendItem={
  id:string
  source:string
  category:string
  title_original:string
  title_ko:string
  summary_original?:string
  summary_ko:string
  developer_point:string
  author:string
  published_at:string
  modified_at:string
  url:string
  likes:number
  downloads:number
  ranking_score:number
  tags:string[]
  pipeline_tag?:string
  library_name?:string
}
export type AITrendCategory={status:'OK'|'ERROR';items:AITrendItem[];message:string}
export type AITrendsDashboardData={
  provider:string
  collection_date:string
  period:{from:string;to:string}
  updated_at:string
  active_model?:string
  dataset_query?:string
  cache:{hit:boolean;daily:boolean}
  translation?:{status:'OK'|'ERROR'|'SKIPPED';translated_items?:number;batch_requests?:number;providers?:string[];warnings?:string[];message:string}
  models:AITrendCategory
  papers:AITrendCategory
  news:AITrendCategory
  spaces:AITrendCategory
  datasets:AITrendCategory
}
