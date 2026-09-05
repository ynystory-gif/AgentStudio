const fs=require('fs');
const path=require('path');
let ts;
try{ts=require('typescript')}catch{
  try{ts=require('/opt/nvm/versions/node/v22.16.0/lib/node_modules/typescript/lib/typescript.js')}catch{
    console.log('[SKIP] TypeScript package is not installed in this runtime. npm typecheck can be run after npm install.');
    process.exit(0);
  }
}
const root=__dirname;
const files=[
  'src/app/App.tsx',
  'src/features/rag/components/RagStudio.tsx',
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
