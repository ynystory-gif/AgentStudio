const fs=require('fs');
const path=require('path');
const os=require('os');
let ts;
try{ts=require('typescript')}catch{
  try{ts=require('/opt/nvm/versions/node/v22.16.0/lib/node_modules/typescript/lib/typescript.js')}catch{
    console.log('[SKIP] TypeScript package is not installed in this runtime.');
    process.exit(0);
  }
}
const root=__dirname;
const files=[
  'src/app/App.tsx',
  'src/features/rag/components/RagStudio.tsx',
  'src/features/rag/components/RagOperationPanel.tsx',
  'src/features/rag/ragApi.ts',
  'src/features/rag/ragTypes.ts',
];
for(const relative of files){
  const file=path.join(root,relative);
  const source=fs.readFileSync(file,'utf8');
  const out=ts.transpileModule(source,{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext},reportDiagnostics:true,fileName:file});
  const errors=(out.diagnostics||[]).filter(d=>d.category===ts.DiagnosticCategory.Error);
  if(errors.length){
    console.error(`[FAIL] ${relative}`);
    for(const d of errors)console.error(ts.flattenDiagnosticMessageText(d.messageText,'\n'));
    process.exit(1);
  }
  console.log(`[PASS] ${relative}`);
}
const ragSource=fs.readFileSync(path.join(root,'src/features/rag/components/RagStudio.tsx'),'utf8');
const operationSource=fs.readFileSync(path.join(root,'src/features/rag/components/RagOperationPanel.tsx'),'utf8');
for(const required of ['RagOperationPanel','security_context:securityContext','Security Filter','search_audit_log_id']){
  if(!ragSource.includes(required)){console.error('[FAIL] missing RagStudio phase-6 contract: '+required);process.exit(1);}
}
if(!ragSource.includes('testRagAgentTool(selectedAgentTool.id,{query:retrievalQuery.trim(),security_context:securityContext})')){console.error('[FAIL] RAG Tool Test security context propagation missing');process.exit(1);}
if(!operationSource.includes('startRagEvaluation(projectRoot,securityContext)')){console.error('[FAIL] Evaluation security-context propagation missing');process.exit(1);}
for(const required of ['Sync / 변경 감지 / 증분 Re-index','Version / Rollback / Disable / 문서 보안등급','Role / Access Rule','Search Audit Log','반복 Evaluation / 품질 Metric']){
  if(!operationSource.includes(required)){console.error('[FAIL] missing RagOperationPanel contract: '+required);process.exit(1);}
}
for(const unsafe of ['if(toolItems.length)setSelectedAgentToolId(toolItems[0].id)','if(collectionItems.length)setToolCollectionId(collectionItems[0].id)']){
  if(ragSource.includes(unsafe)){console.error('[FAIL] unsafe noUncheckedIndexedAccess pattern: '+unsafe);process.exit(1);}
}

// Semantic guard for RAG files with strictNullChecks + noUncheckedIndexedAccess.
const temp=fs.mkdtempSync(path.join(os.tmpdir(),'agentstudio-rag-v5594-'));
try{
  const copy=(src,dst,transform=(value)=>value)=>fs.writeFileSync(path.join(temp,dst),transform(fs.readFileSync(path.join(root,src),'utf8')),'utf8');
  copy('src/features/rag/components/RagStudio.tsx','RagStudio.tsx',(value)=>value
    .replace("from '../../../components/common/OptionHelp'","from './OptionHelp'")
    .replace("from '../../../utils/errors'","from './errors'")
    .replace("from '../ragApi'","from './ragApi'")
    .replace("from '../ragTypes'","from './ragTypes'")
    .replace("from './RagOperationPanel'","from './RagOperationPanel'")
    .replace("import '../ragStudio.css'","import './ragStudio.css'"));
  copy('src/features/rag/components/RagOperationPanel.tsx','RagOperationPanel.tsx',(value)=>value
    .replace("from '../../../components/common/OptionHelp'","from './OptionHelp'")
    .replace("from '../../../utils/errors'","from './errors'")
    .replace("from '../ragApi'","from './ragApi'")
    .replace("from '../ragTypes'","from './ragTypes'"));
  copy('src/features/rag/ragApi.ts','ragApi.ts',(value)=>value.replace("from '../../api'","from './apiStub'"));
  copy('src/features/rag/ragTypes.ts','ragTypes.ts');
  fs.writeFileSync(path.join(temp,'OptionHelp.tsx'),"import React from 'react'\nexport interface OptionHelpProps{title:string;summary:string;detail?:string;recommendedFor?:string[];example?:string;aiReason?:string}\nexport function OptionHelp(_:OptionHelpProps){return null}\n");
  fs.writeFileSync(path.join(temp,'errors.ts'),"export function asLegacyError(value:unknown):{message?:string}{return typeof value==='object'&&value?value as {message?:string}:{message:String(value??'')}}\n");
  fs.writeFileSync(path.join(temp,'apiStub.ts'),"export async function api<T=unknown>(_path:string,_options:RequestInit={}):Promise<T>{throw new Error('stub')}\n");
  fs.writeFileSync(path.join(temp,'global.d.ts'),"declare module '*.css'\ndeclare namespace JSX { interface IntrinsicElements { [elemName:string]: any } }\n");
  fs.mkdirSync(path.join(temp,'node_modules','react'),{recursive:true});
  fs.writeFileSync(path.join(temp,'node_modules','react','index.d.ts'),[
    'export type SetStateAction<S> = S | ((prevState:S)=>S)',
    'export type Dispatch<A> = (value:A)=>void',
    'export function useState<S>(initial:S|(()=>S)):[S,Dispatch<SetStateAction<S>>]',
    'export function useEffect(effect:()=>void|(()=>void),deps?:readonly unknown[]):void',
    'export function useMemo<T>(factory:()=>T,deps:readonly unknown[]):T',
    'declare const React:{createElement:unknown}',
    'export default React',
  ].join('\n'));
  fs.writeFileSync(path.join(temp,'node_modules','react','jsx-runtime.d.ts'),"export const Fragment:any\nexport function jsx(type:any,props:any,key?:any):any\nexport function jsxs(type:any,props:any,key?:any):any\n");
  const options={target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ESNext,moduleResolution:ts.ModuleResolutionKind.Bundler,jsx:ts.JsxEmit.ReactJSX,strict:true,noImplicitAny:false,noUncheckedIndexedAccess:true,skipLibCheck:true,lib:['lib.es2022.d.ts','lib.dom.d.ts'],types:[],noEmit:true};
  const roots=['RagStudio.tsx','RagOperationPanel.tsx','ragApi.ts','ragTypes.ts','OptionHelp.tsx','errors.ts','apiStub.ts','global.d.ts'].map((name)=>path.join(temp,name));
  const program=ts.createProgram(roots,options);
  const diagnostics=ts.getPreEmitDiagnostics(program).filter((d)=>d.category===ts.DiagnosticCategory.Error);
  if(diagnostics.length){
    for(const d of diagnostics){
      const where=d.file&&typeof d.start==='number'?`${path.basename(d.file.fileName)}:${d.file.getLineAndCharacterOfPosition(d.start).line+1}`:'RAG semantic';
      console.error(`[FAIL] ${where} TS${d.code}: ${ts.flattenDiagnosticMessageText(d.messageText,'\n')}`);
    }
    process.exit(1);
  }
  console.log('[PASS] RAG phase-6 strictNullChecks + noUncheckedIndexedAccess semantic guard');
} finally {fs.rmSync(temp,{recursive:true,force:true});}
console.log('[PASS] v5.594 RagStudio phase-6 TypeScript syntax + strict-safe contracts');
