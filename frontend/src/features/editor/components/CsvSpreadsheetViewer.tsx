import { useMemo, useState } from 'react'
import Editor from '@monaco-editor/react'

const CSV_SPREADSHEET_EXTENSIONS=new Set(['csv','tsv'])
const spreadsheetFileExtension=(filePath: LegacyValue='')=>{
  const name=String(filePath||'').replace(/\\/g,'/').split('/').pop()||''
  const dot=name.lastIndexOf('.')
  return dot>=0?name.slice(dot+1).toLowerCase():''
}
export const isCsvSpreadsheetFile=(filePath: LegacyValue='')=>CSV_SPREADSHEET_EXTENSIONS.has(spreadsheetFileExtension(filePath))
const spreadsheetColumnLabel=(index: LegacyValue=0)=>{
  let value=Math.max(0,Number(index)||0)+1
  let label=''
  while(value>0){
    const digit=(value-1)%26
    label=String.fromCharCode(65+digit)+label
    value=Math.floor((value-1)/26)
  }
  return label
}
const countDelimiterOutsideQuotes=(line: LegacyValue='',delimiter: LegacyValue=',')=>{
  let inQuotes=false
  let count=0
  for(let index=0;index<line.length;index+=1){
    const char=line[index]
    if(char==='"'){
      if(inQuotes&&line[index+1]==='"') index+=1
      else inQuotes=!inQuotes
      continue
    }
    if(!inQuotes&&char===delimiter) count+=1
  }
  return count
}
const detectSpreadsheetDelimiter=(value: LegacyValue='',filePath: LegacyValue='')=>{
  if(spreadsheetFileExtension(filePath)==='tsv') return '\t'
  const lines=String(value||'').replace(/^\uFEFF/,'').split(/\r?\n/).filter((line: LegacyValue)=>line.trim()).slice(0,16)
  if(!lines.length) return ','
  const candidates=[',','\t',';','|']
  let winner=','
  let winnerScore=-Infinity
  for(const delimiter of candidates){
    const counts=lines.map((line: LegacyValue)=>countDelimiterOutsideQuotes(line,delimiter))
    const positive=counts.filter((count: LegacyValue)=>count>0)
    if(!positive.length) continue
    const average=positive.reduce((sum: LegacyValue,count: LegacyValue)=>sum+count,0)/positive.length
    const variance=positive.reduce((sum: LegacyValue,count: LegacyValue)=>sum+Math.abs(count-average),0)/positive.length
    const score=(positive.length*100)+(average*5)-variance
    if(score>winnerScore){winner=delimiter;winnerScore=score}
  }
  return winner
}
const parseSpreadsheetPreview=(value: LegacyValue='',delimiter: LegacyValue=',',{maxRows=5000,maxColumns=200}:LegacyRecord={})=>{
  const text=String(value||'').replace(/^\uFEFF/,'')
  const rows:LegacyValue[]=[]
  let row:LegacyValue[]=[]
  let cell=''
  let inQuotes=false
  let truncatedRows=false
  let truncatedColumns=false
  const pushCell=()=>{
    if(row.length<maxColumns) row.push(cell)
    else truncatedColumns=true
    cell=''
  }
  const pushRow=()=>{
    pushCell()
    rows.push(row)
    row=[]
    if(rows.length>=maxRows) truncatedRows=true
  }
  for(let index=0;index<text.length;index+=1){
    const char=text[index]
    if(char==='"'){
      if(inQuotes&&text[index+1]==='"'){
        cell+='"'
        index+=1
      }else{
        inQuotes=!inQuotes
      }
      continue
    }
    if(!inQuotes&&char===delimiter){
      pushCell()
      continue
    }
    if(!inQuotes&&(char==='\n'||char==='\r')){
      if(char==='\r'&&text[index+1]==='\n') index+=1
      pushRow()
      if(truncatedRows) break
      continue
    }
    cell+=char
  }
  if(!truncatedRows&&(cell.length>0||row.length>0)) pushRow()
  while(rows.length&&rows[rows.length-1].every((item: LegacyValue)=>String(item||'').length===0)) rows.pop()
  const columnCount=Math.min(maxColumns,rows.reduce((max: LegacyValue,current: LegacyValue)=>Math.max(max,current.length),0))
  const normalized=rows.map((current: LegacyValue)=>Array.from({length:columnCount},(_: LegacyValue,index: LegacyValue)=>current[index]??''))
  return {rows:normalized,columnCount,truncatedRows,truncatedColumns}
}
const spreadsheetDelimiterLabel=(delimiter: LegacyValue)=>delimiter==='\t'?'TAB':delimiter===';'?'세미콜론 (;)':delimiter==='|'?'파이프 (|)':'쉼표 (,)'

export function CsvSpreadsheetViewer({value='',filePath='',onChange=()=>{}}:{value?:string;filePath?:string;onChange?:(next:string)=>void}){
  const [mode,setMode]=useState('GRID')
  const [selectedCell,setSelectedCell]=useState<LegacyValue|null>(null)
  const [wrapCells,setWrapCells]=useState(false)
  const delimiter=useMemo(()=>detectSpreadsheetDelimiter(value,filePath),[value,filePath])
  const parsed=useMemo(()=>parseSpreadsheetPreview(value,delimiter),[value,delimiter])
  const fileName=String(filePath||'CSV').replace(/\\/g,'/').split('/').pop()||'CSV'
  const selectedValue=selectedCell?parsed.rows[selectedCell.row]?.[selectedCell.column]??'':''
  const copySelected=async()=>{
    if(!selectedCell) return
    try{await navigator.clipboard?.writeText?.(String(selectedValue??''))}catch{}
  }
  return <div className="csv-spreadsheet-viewer">
    <div className="csv-spreadsheet-toolbar">
      <div className="csv-spreadsheet-title">
        <strong>▦ CSV 표 보기</strong>
        <span>{fileName}</span>
        <em>{parsed.truncatedRows?`${parsed.rows.length.toLocaleString()}행 이상`: `${parsed.rows.length.toLocaleString()}행`} · {parsed.columnCount.toLocaleString()}열 · {spreadsheetDelimiterLabel(delimiter)}</em>
      </div>
      <div className="csv-spreadsheet-actions">
        <button type="button" className={mode==='GRID'?'active':''} onClick={()=>setMode('GRID')}>▦ 표 보기</button>
        <button type="button" className={mode==='RAW'?'active':''} onClick={()=>setMode('RAW')}>≡ 원문 편집</button>
        {mode==='GRID'&&<label><input type="checkbox" checked={wrapCells} onChange={(event: LegacyValue)=>setWrapCells(event.target.checked)}/> 셀 줄바꿈</label>}
      </div>
    </div>
    {mode==='RAW'
      ? <div className="csv-raw-editor"><Editor
          height="100%"
          language="plaintext"
          value={value}
          onChange={(next: LegacyValue)=>onChange(next??'')}
          theme="vs-dark"
          options={{minimap:{enabled:false},fontSize:13,automaticLayout:true,wordWrap:'off',scrollBeyondLastLine:false}}
        /></div>
      : <>
          <div className={`csv-grid-scroll ${wrapCells?'wrap-cells':''}`}>
            {parsed.rows.length&&parsed.columnCount
              ? <table className="csv-grid-table">
                  <thead><tr>
                    <th className="csv-grid-corner" aria-label="행/열 머리글" />
                    {Array.from({length:parsed.columnCount},(_: LegacyValue,column: LegacyValue)=><th key={`column-${column}`} className="csv-grid-column-head">{spreadsheetColumnLabel(column)}</th>)}
                  </tr></thead>
                  <tbody>{parsed.rows.map((row: LegacyValue,rowIndex: LegacyValue)=><tr key={`row-${rowIndex}`}>
                    <th className="csv-grid-row-head">{rowIndex+1}</th>
                    {row.map((cell: LegacyValue,columnIndex: LegacyValue)=>{
                      const selected=selectedCell?.row===rowIndex&&selectedCell?.column===columnIndex
                      return <td
                        key={`${rowIndex}-${columnIndex}`}
                        className={selected?'selected':''}
                        title={String(cell??'')}
                        onClick={()=>setSelectedCell({row:rowIndex,column:columnIndex})}
                      ><span>{String(cell??'')}</span></td>
                    })}
                  </tr>)}</tbody>
                </table>
              : <div className="csv-grid-empty">표시할 CSV 데이터가 없습니다.</div>}
          </div>
          <div className="csv-spreadsheet-statusbar">
            <span>{selectedCell?`선택 ${spreadsheetColumnLabel(selectedCell.column)}${selectedCell.row+1}`:'셀을 클릭하면 위치와 값을 확인할 수 있습니다.'}</span>
            {selectedCell&&<><span className="csv-selected-value" title={String(selectedValue??'')}>{String(selectedValue??'')}</span><button type="button" onClick={copySelected}>복사</button></>}
            {(parsed.truncatedRows||parsed.truncatedColumns)&&<strong>대용량 CSV는 성능을 위해 최대 5,000행 × 200열까지만 표로 미리봅니다. 원문은 그대로 유지됩니다.</strong>}
          </div>
        </>}
  </div>
}
