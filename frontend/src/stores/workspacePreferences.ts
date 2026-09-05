import { readStoredBoolean, readStoredNumber, writeStoredValue } from '../utils/storage'

export const WORKSPACE_PREFERENCE_KEYS={
  leftCollapsed:'agentstudio.workspace.leftCollapsed',
  rightCollapsed:'agentstudio.workspace.rightCollapsed',
  bottomCollapsed:'agentstudio.workspace.bottomCollapsed',
  bottomHeight:'agentstudio.workspace.bottomHeight',
  leftWidth:'agentstudio.workspace.leftWidth',
  rightWidth:'agentstudio.workspace.rightWidth',
  codeToolbarActionWidth:'agentstudio.codeToolbar.actionWidth',
  editorSplitRatio:'agentstudio.editorSplit.ratio',
} as const

export const readWorkspaceBoolean=(key:keyof typeof WORKSPACE_PREFERENCE_KEYS,fallback=false)=>
  readStoredBoolean(WORKSPACE_PREFERENCE_KEYS[key],fallback)

export const readWorkspaceNumber=(key:keyof typeof WORKSPACE_PREFERENCE_KEYS,fallback:number,min?:number,max?:number)=>
  readStoredNumber(WORKSPACE_PREFERENCE_KEYS[key],fallback,min,max)

export const writeWorkspacePreference=(key:keyof typeof WORKSPACE_PREFERENCE_KEYS,value:string|number|boolean)=>
  writeStoredValue(WORKSPACE_PREFERENCE_KEYS[key],value)
