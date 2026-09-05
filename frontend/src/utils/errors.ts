export const asLegacyError=(value:unknown):LegacyRecord=>{
  if(value&&typeof value==='object') return value as LegacyRecord
  return {message:String(value??'')}
}

export const errorMessage=(value:unknown,fallback: LegacyValue='')=>String(asLegacyError(value).message||fallback||value||'')
