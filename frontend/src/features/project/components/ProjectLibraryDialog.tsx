export function ProjectLibraryDialog({projectLoadProgress,setProjectListOpen,externalProjectPath,setExternalProjectPath,externalProjectPickerLoading,pickExternalProjectFolder,externalProjectLoading,externalProjectProgress,analyzeExternalProject,externalProjectPickerMessage,externalProjectStatus,externalProjectStep,externalProjectAnalysis,newAgentName,openExternalProjectWorkspace,registerExternalProject,projectListLoading,projectList,startNewProject,loadProject}:LegacyRecord){
  return <div className="project-list-overlay" onClick={()=>setProjectListOpen(false)}>
      <div className="project-list-dialog redesigned" onClick={(e: LegacyValue)=>e.stopPropagation()}>
        <div className="project-list-head">
          <div><span className="eyebrow">PROJECT LIBRARY</span><h2>프로젝트 불러오기</h2>
        {projectLoadProgress.active&&<div className={projectLoadProgress.failed?'project-load-progress modal failed':'project-load-progress modal'}>
          <div className="project-load-progress-head">
            <strong>{projectLoadProgress.message}</strong>
            <span>{projectLoadProgress.percent}%</span>
          </div>
          <div className="project-load-progress-track">
            <div className="project-load-progress-fill" style={{width:`${projectLoadProgress.percent}%`}} />
          </div>
        </div>}<p>저장된 프로젝트를 선택하면 바로 작업공간으로 이동합니다.</p></div>
          <button onClick={()=>setProjectListOpen(false)}>✕</button>
        </div>
        
        <div className="external-project-import">
          <div className="external-import-head">
            <div>
              <strong>DB에 없는 기존 프로젝트 분석</strong>
              <small>저장되지 않은 프로젝트도 폴더를 지정하면 바로 분석하고 열 수 있습니다.</small>
            </div>
          </div>

          <div className="external-path-row">
            <input
              value={externalProjectPath}
              onChange={(e: LegacyValue)=>setExternalProjectPath(e.target.value)}
              placeholder="분석할 기존 프로젝트 경로"
            />
            <button
              type="button"
              className={
                externalProjectPickerLoading
                  ? 'external-path-picker-button busy'
                  : 'external-path-picker-button'
              }
              disabled={externalProjectPickerLoading}
              onClick={pickExternalProjectFolder}
              title="Windows 폴더 선택창 열기"
            >
              {externalProjectPickerLoading?'선택창 여는 중...':'경로 찾기'}
            </button>
            <button
              className="primary-install"
              disabled={externalProjectLoading||!externalProjectPath.trim()}
              onClick={analyzeExternalProject}
            >
              {externalProjectLoading?`${Math.round(externalProjectProgress||0)}% 분석 중...`:'프로젝트 분석'}
            </button>
          </div>

          {externalProjectPickerMessage&&
            <div className={
              externalProjectPickerMessage.startsWith('경로 선택 실패')
                ? 'external-path-picker-message error'
                : 'external-path-picker-message'
            }>
              {externalProjectPickerMessage}
            </div>}

          {(externalProjectLoading||externalProjectStatus)&&<div className={
            externalProjectStatus==='SUCCESS'
              ?'external-progress-box success'
              :externalProjectStatus==='FAILED'
                ?'external-progress-box failed'
                :'external-progress-box running'
          }>
            <div className="external-progress-head">
              <strong>
                {externalProjectStatus==='SUCCESS'
                  ?'분석 완료'
                  :externalProjectStatus==='FAILED'
                    ?'분석 실패'
                    :'프로젝트 분석 중'}
              </strong>
              <b>{Math.round(externalProjectProgress||0)}%</b>
            </div>

            <progress
              max="100"
              value={externalProjectProgress||0}
            />

            <div className="external-progress-step">
              {externalProjectStep||'분석 준비 중...'}
            </div>

            <div className="external-progress-stages">
              <span className={(externalProjectProgress||0)>=5?'done':''}>경로 확인</span>
              <span className={(externalProjectProgress||0)>=15?'done':''}>파일 스캔</span>
              <span className={(externalProjectProgress||0)>=40?'done':''}>소스 분석</span>
              <span className={(externalProjectProgress||0)>=82?'done':''}>DB 저장</span>
              <span className={(externalProjectProgress||0)>=100?'done':''}>완료</span>
            </div>

            {externalProjectStatus==='SUCCESS'&&
              <div className="auto-move-note">
                DB 저장이 완료되었습니다. 작업공간으로 자동 이동합니다.
              </div>}
          </div>}

          {externalProjectStatus==='FAILED'&&externalProjectAnalysis?.ok===false&&
            <div className="external-failure-detail">
              <div className="failure-title">분석 실패 상세</div>
              <div className="failure-message">
                {externalProjectAnalysis.message||externalProjectStep}
              </div>

              <div className="failure-label">로그 파일 전체 경로</div>
              <code className="failure-log-path">
                {externalProjectAnalysis.log_path||'로그 파일 저장에 실패했습니다.'}
              </code>

              {externalProjectAnalysis.traceback&&<details>
                <summary>상세 Traceback 보기</summary>
                <pre>{externalProjectAnalysis.traceback}</pre>
              </details>}
            </div>}

          {externalProjectAnalysis&&externalProjectAnalysis.ok!==false&&<div className="external-analysis-result">
            <div className="external-analysis-title">
              <div>
                <strong>{newAgentName||'기존 프로젝트'}</strong>
                <code>{externalProjectAnalysis.project_root}</code>
              </div>
              <span className="unregistered-chip">
                {externalProjectAnalysis.registered?'DB 등록됨':'DB 미등록'}
              </span>
            </div>

            {externalProjectAnalysis.summary&&<div className="external-summary-box">
              <div><b>프로젝트 요약</b></div>
              <pre>{typeof externalProjectAnalysis.summary==='string'
                ? externalProjectAnalysis.summary
                : JSON.stringify(externalProjectAnalysis.summary,null,2)}</pre>
            </div>}

            <div className="external-analysis-actions">
              <button className="hero-primary" onClick={openExternalProjectWorkspace}>
                분석 결과로 프로젝트 열기
              </button>
              {!externalProjectAnalysis.registered&&
                <button onClick={registerExternalProject}>이 프로젝트를 DB에 등록</button>}
            </div>
          </div>}
        </div>

        {projectListLoading&&<div className="project-list-empty">프로젝트 목록을 불러오는 중...</div>}
        {!projectListLoading&&projectList.length===0&&<div className="project-list-empty">저장된 프로젝트가 없습니다.<br/><button onClick={()=>{setProjectListOpen(false);startNewProject()}}>첫 프로젝트 만들기</button></div>}
        {!projectListLoading&&projectList.length>0&&<div className="project-list-items">
          {projectList.map((p: LegacyValue)=><button key={p.id} className="project-list-item" onClick={()=>loadProject(p.id)}>
            <div className="project-list-title"><strong>{p.name}</strong><span>#{p.id}</span></div>
            <div className="project-list-path">{p.project_root}</div>
            <div className="project-list-meta">
              <span>Cache {p.cache_path?'✓':'-'}</span><span>Models {p.models_path?'✓':'-'}</span>
            </div>
          </button>)}
        </div>}
      </div>
    </div>
}
