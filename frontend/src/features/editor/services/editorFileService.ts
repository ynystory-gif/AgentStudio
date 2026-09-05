import { api } from '../../../api'

type LegacyRecord=Record<string,any>

export const readEditorTextFile=(root:string,relativePath:string)=>
  api('/files/read',{
    method:'POST',
    body:JSON.stringify({root,relative_path:relativePath}),
  })

export const writeEditorTextFile=(fullPath:string,content:string,options:LegacyRecord={})=>
  api<LegacyRecord>('/file/write',{
    method:'POST',
    body:JSON.stringify({
      path:fullPath,
      content:content??'',
      expected_mtime_ns:options.expected_mtime_ns||null,
      expected_sha256:options.expected_sha256||null,
      force:!!options.force,
    }),
  })

export const searchEditorProjectText=(root:string,query:string)=>
  api('/files/search-text',{
    method:'POST',
    body:JSON.stringify({root,query}),
  })
