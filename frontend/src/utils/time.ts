export const formatMediaElapsed=(value:unknown=0):string=>{
  const total=Math.max(0,Math.floor(Number(value||0)))
  const hh=String(Math.floor(total/3600)).padStart(2,'0')
  const mm=String(Math.floor((total%3600)/60)).padStart(2,'0')
  const ss=String(total%60).padStart(2,'0')
  return `${hh}:${mm}:${ss}`
}
