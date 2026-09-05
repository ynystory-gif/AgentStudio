export const readStoredBoolean=(key:string,fallback=false):boolean=>{
  try{return window.localStorage.getItem(key)==='1'}catch{return fallback}
}

export const readStoredNumber=(key:string,fallback:number,min?:number,max?:number):number=>{
  try{
    const value=Number(window.localStorage.getItem(key))
    if(!Number.isFinite(value)) return fallback
    if(min!==undefined&&value<min) return fallback
    if(max!==undefined&&value>max) return fallback
    return value
  }catch{return fallback}
}

export const writeStoredValue=(key:string,value:string|number|boolean):void=>{
  try{
    const serialized=typeof value==='boolean'?(value?'1':'0'):String(value)
    window.localStorage.setItem(key,serialized)
  }catch{}
}
