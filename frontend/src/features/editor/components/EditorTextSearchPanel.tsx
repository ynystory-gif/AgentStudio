export function EditorTextSearchPanel({editorTextSearchScope,setEditorTextSearchScope,setEditorTextSearchResults,setEditorTextSearchMeta,runEditorTextSearch,editorTextSearchInputRef,editorTextSearchQuery,setEditorTextSearchQuery,editorTextSearchBusy,setEditorTextSearchOpen,editorTextSearchError,editorTextSearchMeta,editorTextSearchResults,revealEditorTextSearchResult}:LegacyRecord){
  return <div className="editor-text-search-panel">
            <div className="editor-text-search-head">
              <div className="editor-text-search-scope">
                <button type="button" className={editorTextSearchScope==='CURRENT'?'active':''} onClick={()=>{setEditorTextSearchScope('CURRENT');setEditorTextSearchResults([]);setEditorTextSearchMeta(null)}}>현재 파일</button>
                <button type="button" className={editorTextSearchScope==='PROJECT'?'active':''} onClick={()=>{setEditorTextSearchScope('PROJECT');setEditorTextSearchResults([]);setEditorTextSearchMeta(null)}}>프로젝트 전체</button>
              </div>
              <form onSubmit={(e: LegacyValue)=>{e.preventDefault();runEditorTextSearch()}}>
                <input
                  ref={editorTextSearchInputRef}
                  value={editorTextSearchQuery}
                  onChange={(e: LegacyValue)=>setEditorTextSearchQuery(e.target.value)}
                  placeholder={editorTextSearchScope==='CURRENT'?'현재 파일에서 찾을 텍스트':'프로젝트에서 찾을 텍스트'}
                />
                <button type="submit" disabled={editorTextSearchBusy||!editorTextSearchQuery.trim()}>{editorTextSearchBusy?'검색 중…':'찾기'}</button>
                <button type="button" className="close" onClick={()=>setEditorTextSearchOpen(false)} title="검색 닫기">×</button>
              </form>
            </div>
            {editorTextSearchError&&<div className="editor-text-search-error">{editorTextSearchError}</div>}
            {!editorTextSearchError&&editorTextSearchMeta&&<div className="editor-text-search-summary">
              <strong>{editorTextSearchResults.length}개 결과</strong>
              {editorTextSearchScope==='PROJECT'&&<span> · 파일 {Number(editorTextSearchMeta?.files_scanned||0)}개 검색</span>}
              {editorTextSearchMeta?.live_buffer&&<span> · 저장 전 편집 내용 포함</span>}
              {editorTextSearchMeta?.document_type==='pdf'&&<span> · PDF {Number(editorTextSearchMeta?.pdf_pages_scanned||0)}쪽 검색</span>}
              {editorTextSearchMeta?.document_type==='pdf'&&<span> · 텍스트 {Number(editorTextSearchMeta?.pdf_text_pages||0)}쪽 추출</span>}
              {editorTextSearchMeta?.document_type==='pdf'&&Number(editorTextSearchMeta?.pdf_duplicate_matches_removed||0)>0&&<span> · 중복 {Number(editorTextSearchMeta.pdf_duplicate_matches_removed)}개 정리</span>}
              {Number(editorTextSearchMeta?.skipped_large||0)>0&&<span> · 큰 파일 {Number(editorTextSearchMeta.skipped_large)}개 제외</span>}
              {Number(editorTextSearchMeta?.skipped_binary||0)>0&&<span> · 바이너리 {Number(editorTextSearchMeta.skipped_binary)}개 제외</span>}
              {editorTextSearchMeta?.truncated&&<span> · 결과 상한에 도달</span>}
            </div>}
            <div className="editor-text-search-results">
              {editorTextSearchResults.map((row: LegacyValue,index: LegacyValue)=><button
                type="button"
                className="editor-text-search-result"
                key={`${row.path}-${row.cell_index??''}-${row.line_number}-${row.column}-${index}`}
                onClick={()=>revealEditorTextSearchResult(row)}
              >
                <span className="path">{row.path}</span>
                <span className="location">{Number(row?.page_number||0)>0?`페이지 ${Number(row.page_number)}${Number(row?.page_match_index||0)>1?` · 페이지 내 결과 ${Number(row.page_match_index)}`:''}`:`${Number.isInteger(row.cell_index)?`셀 ${Number(row.cell_index)+1} · `:''}L${row.line_number}:C${row.column}`}</span>
                <code>{row.snippet||'(빈 줄)'}</code>
              </button>)}
              {editorTextSearchMeta&&!editorTextSearchBusy&&!editorTextSearchResults.length&&!editorTextSearchError&&<div className="editor-text-search-empty">검색 결과가 없습니다.</div>}
            </div>
          </div>
}
