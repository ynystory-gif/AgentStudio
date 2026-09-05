import { useRef, useState } from 'react'
import {
  isBookmarkableTextEditorFile,
  loadTextEditorLineBookmarks,
  normalizeProjectRelativePath,
  storeTextEditorLineBookmarks,
  textEditorBookmarkStorageKey,
} from '../editorNavigation'

type LegacyValue=any
type LegacyRecord=Record<string,any>

export function useEditorController(){
  const [code,setCode]=useState('')
  const [focusOwner,setFocusOwner]=useState('editor')
  const focusOwnerRef=useRef('editor')
  const editorInstanceRef=useRef<LegacyValue|null>(null)
  const selectedEditorFileRef=useRef('')
  const editorFileRootRef=useRef<LegacyRecord>({})
  const editorBookmarkDecorationIdsRef=useRef<LegacyValue[]>([])
  const [editorBookmarkRevision,setEditorBookmarkRevision]=useState(0)
  const editorTabsScrollRef=useRef<LegacyValue|null>(null)

  const [editorTextSearchOpen,setEditorTextSearchOpen]=useState(false)
  const [editorTextSearchScope,setEditorTextSearchScope]=useState('CURRENT')
  const [editorTextSearchQuery,setEditorTextSearchQuery]=useState('')
  const [editorTextSearchResults,setEditorTextSearchResults]=useState<LegacyValue[]>([])
  const [editorTextSearchBusy,setEditorTextSearchBusy]=useState(false)
  const [editorTextSearchError,setEditorTextSearchError]=useState('')
  const [editorTextSearchMeta,setEditorTextSearchMeta]=useState<LegacyValue|null>(null)
  const editorTextSearchInputRef=useRef<LegacyValue|null>(null)
  const editorTextSearchRequestRef=useRef(0)

  const editorSelectionRef=useRef<LegacyRecord>({})
  const editorScrollStateRef=useRef<LegacyRecord>({})

  const setFocusOwnerSafe=(owner:LegacyValue)=>{
    focusOwnerRef.current=String(owner||'editor')
    setFocusOwner(String(owner||'editor'))
  }
  const rememberSelection=(filePath:string,selection:LegacyValue)=>{
    if(filePath)editorSelectionRef.current[filePath]=selection
  }
  const restoreSelection=(filePath:string)=>editorSelectionRef.current[filePath]??null
  const rememberScroll=(filePath:string,state:LegacyValue)=>{
    if(filePath)editorScrollStateRef.current[filePath]=state
  }
  const restoreScroll=(filePath:string)=>editorScrollStateRef.current[filePath]??null

  const bookmarkKey=(filePath:string,projectRoot:string)=>{
    const path=normalizeProjectRelativePath(filePath)
    return path?textEditorBookmarkStorageKey(String(projectRoot||''),path):''
  }
  const getBookmarks=(filePath:string,projectRoot:string)=>{
    if(!isBookmarkableTextEditorFile(filePath))return []
    const key=bookmarkKey(filePath,projectRoot)
    return key?loadTextEditorLineBookmarks(key):[]
  }
  const toggleBookmark=(filePath:string,projectRoot:string,lineNumber:number)=>{
    if(!isBookmarkableTextEditorFile(filePath)||!Number.isInteger(lineNumber)||lineNumber<1)return []
    const key=bookmarkKey(filePath,projectRoot)
    const current=loadTextEditorLineBookmarks(key)
    const next=current.includes(lineNumber)
      ? current.filter((line:number)=>line!==lineNumber)
      : [...current,lineNumber]
    storeTextEditorLineBookmarks(key,next)
    setEditorBookmarkRevision(v=>v+1)
    return next
  }
  const clearBookmarks=(filePath:string,projectRoot:string)=>{
    const key=bookmarkKey(filePath,projectRoot)
    if(!key)return
    storeTextEditorLineBookmarks(key,[])
    setEditorBookmarkRevision(v=>v+1)
  }
  const buildCurrentFileSearchResults=(text:string,query:string)=>{
    const needle=String(query||'')
    if(!needle)return []
    const lower=needle.toLowerCase()
    return String(text||'').split(/\r?\n/).flatMap((line,index)=>{
      const column=line.toLowerCase().indexOf(lower)
      return column<0?[]:[{line:index+1,column:column+1,text:line}]
    })
  }

  return {
    code,setCode,focusOwner,setFocusOwner,setFocusOwnerSafe,focusOwnerRef,
    editorInstanceRef,selectedEditorFileRef,editorFileRootRef,
    editorBookmarkDecorationIdsRef,editorBookmarkRevision,setEditorBookmarkRevision,
    editorTabsScrollRef,
    editorTextSearchOpen,setEditorTextSearchOpen,
    editorTextSearchScope,setEditorTextSearchScope,
    editorTextSearchQuery,setEditorTextSearchQuery,
    editorTextSearchResults,setEditorTextSearchResults,
    editorTextSearchBusy,setEditorTextSearchBusy,
    editorTextSearchError,setEditorTextSearchError,
    editorTextSearchMeta,setEditorTextSearchMeta,
    editorTextSearchInputRef,editorTextSearchRequestRef,
    editorSelectionRef,editorScrollStateRef,
    rememberSelection,restoreSelection,rememberScroll,restoreScroll,
    bookmarkKey,getBookmarks,toggleBookmark,clearBookmarks,buildCurrentFileSearchResults,
  }
}
