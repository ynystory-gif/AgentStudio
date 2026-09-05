import type { AITrendCategory,AITrendItem,AITrendsDashboardData } from '../types/aiTrends'

type Props={
  data:AITrendsDashboardData|null
  busy:boolean
  error:string
  onRefresh:()=>void
  onOpen:(url:string)=>void
}
const meta=(item:AITrendItem)=>{
  const parts:string[]=[]
  if(item.likes)parts.push(`♥ ${item.likes.toLocaleString()}`)
  if(item.downloads)parts.push(`↓ ${item.downloads.toLocaleString()}`)
  return parts.join(' · ')
}
const shortDate=(value:string)=>{
  if(!value)return ''
  const d=new Date(value)
  if(Number.isNaN(d.getTime()))return ''
  return new Intl.DateTimeFormat('ko-KR',{month:'numeric',day:'numeric'}).format(d)
}
function StandardCategory({icon,title,category,allUrl,onOpen,limit=3,modelHover=false}:{icon:string;title:string;category?:AITrendCategory;allUrl:string;onOpen:(url:string)=>void;limit?:number;modelHover?:boolean}){
  const items=category?.items||[]
  return <section className="ai-trends-card">
    <header><strong><span>{icon}</span>{title}</strong><button type="button" onClick={()=>onOpen(allUrl)}>전체보기 →</button></header>
    {category?.status==='ERROR'&&<div className="ai-trends-category-error">현재 정보를 가져올 수 없습니다.<small>{category.message}</small></div>}
    {category?.status!=='ERROR'&&items.length===0&&<div className="ai-trends-category-empty">표시할 항목이 없습니다.</div>}
    <div className="ai-trends-items">
      {items.slice(0,limit).map((item,index)=><article key={item.id||`${title}-${index}`} className={modelHover?'ai-trends-model-row':''}>
        <span className="ai-trends-rank">{index+1}</span>
        <div>
          <button type="button" className="ai-trends-title" onClick={()=>onOpen(item.url)}>{item.title_ko||item.title_original}</button>
          {!modelHover&&item.summary_ko&&<p>{item.summary_ko}</p>}
          {!modelHover&&item.developer_point&&<small className="ai-trends-dev">AI 개발 포인트 · {item.developer_point}</small>}
          {meta(item)&&<small>{meta(item)}</small>}
          {modelHover&&<div className="ai-trends-model-hover" role="tooltip">
            <strong>{item.title_original}</strong>
            <p>{item.summary_ko||item.summary_original||'모델 설명 정보가 제공되지 않았습니다.'}</p>
            {(item.pipeline_tag||item.library_name)&&<small>{[item.pipeline_tag,item.library_name].filter(Boolean).join(' · ')}</small>}
            {item.developer_point&&<em>AI 개발 포인트 · {item.developer_point}</em>}
          </div>}
        </div>
      </article>)}
    </div>
  </section>
}
function SpacesCategory({category,onOpen}:{category?:AITrendCategory;onOpen:(url:string)=>void}){
  const items=category?.items||[]
  return <section className="ai-trends-spaces-section">
    <header className="ai-trends-spaces-head"><strong>🚀 인기 Spaces</strong><button type="button" onClick={()=>onOpen('https://huggingface.co/spaces')}>전체보기 →</button></header>
    {category?.status==='ERROR'&&<div className="ai-trends-category-error">현재 Spaces 정보를 가져올 수 없습니다.<small>{category.message}</small></div>}
    <div className="ai-trends-space-grid">
      {items.slice(0,8).map((item,index)=><button key={item.id||index} type="button" className={`ai-trends-space-tile tone-${index%4}`} onClick={()=>onOpen(item.url)}>
        <div className="ai-trends-space-badges"><span>달리기</span>{item.tags?.some(t=>String(t).toLowerCase().includes('mcp'))&&<span>⚙ MCP</span>}<b>🔥 추천</b>{item.likes>0&&<em>♡ {item.likes.toLocaleString()}</em>}</div>
        <strong>{item.title_ko||item.title_original}</strong>
        <p>{item.summary_ko||item.summary_original||'Hugging Face Space'}</p>
        <footer><span>{item.author||'Hugging Face'}</span><time>{shortDate(item.modified_at)}</time></footer>
      </button>)}
    </div>
  </section>
}
export function AITrendsDashboard({data,busy,error,onRefresh,onOpen}:Props){
  const currentQwenModel=String(data?.model_context?.model||data?.active_model||'').trim()
  const datasetTitle=`사용중인 모델 데이터셋${currentQwenModel?` · ${currentQwenModel}`:''}`
  return <section className="ai-trends-section">
    <div className="ai-trends-head">
      <div><small>AI DEVELOPMENT TRENDS</small><strong>🔥 최근 AI 개발 동향</strong>
        <span>Hugging Face 현재 상위 항목 · 오늘 수집 결과</span>
      </div>
      <div><button type="button" onClick={onRefresh} disabled={busy}>{busy?'확인 중...':'↻ 새로고침'}</button></div>
    </div>
    {error&&<div className="ai-trends-error">{error}</div>}
    {data?.translation?.status==='ERROR'&&<div className="ai-trends-error">한국어 자동 번역에 실패했습니다. 잠시 후 새로고침하면 다시 시도합니다.<small>{data.translation.message}</small></div>}
    {!data&&busy&&<div className="ai-trends-loading">오늘 수집된 AI 동향을 확인하고 있습니다...</div>}
    {data&&<>
      <div className="ai-trends-cache-note">
        {data.cache?.hit?'오늘 수집한 데이터를 표시하고 있습니다.':'오늘 데이터가 없어 새로 수집했습니다.'}
        {' · '}수집일 {data.collection_date}{data.active_model?` · 현재 모델 ${data.active_model}`:''}
      </div>
      <div className="ai-trends-grid">
        <StandardCategory icon="🔥" title="인기 모델" category={data.models} allUrl="https://huggingface.co/models?sort=trending" onOpen={onOpen} limit={5} modelHover/>
        <StandardCategory icon="📄" title="최신 논문" category={data.papers} allUrl="https://huggingface.co/papers" onOpen={onOpen}/>
        <StandardCategory icon="📰" title="AI 뉴스" category={data.news} allUrl="https://huggingface.co/blog" onOpen={onOpen}/>
        <StandardCategory icon="🗂️" title={datasetTitle} category={data.datasets} allUrl={`https://huggingface.co/datasets?search=${encodeURIComponent(data.dataset_query||'qwen')}`} onOpen={onOpen}/>
        <div className="ai-trends-wide"><SpacesCategory category={data.spaces} onOpen={onOpen}/></div>
      </div>
      <footer>Hugging Face · 모델/Spaces는 trending 상위 · 논문/뉴스는 최신 3개 · 현재 모델 관련 Dataset 3개 · 한국어 배치 번역{data.translation?.batch_requests?` ${data.translation.batch_requests}회`:''}{data.translation?.providers?.length?` · ${data.translation.providers.join(' → ')}`:''} · 오늘 결과 캐시</footer>
    </>}
  </section>
}
