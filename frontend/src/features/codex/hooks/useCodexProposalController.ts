import { useCallback } from 'react'
type LegacyValue=any
type LegacyRecord=Record<string,any>

export function useCodexProposalController(options:LegacyRecord){
  const {setCodeDiffReview,setCodeEditProposal,setWorkspaceRightCollapsed,setCodeRightPanelTab}=options
  const registerCodexCodeProposal=useCallback((proposal:LegacyValue)=>{
    if(!proposal?.codeBlockCount||!Array.isArray(proposal?.blocks))return
    setCodeDiffReview(null)
    setCodeEditProposal({
      source:'codex',proposalType:'codex_blocks',path:proposal.activeFile||'',
      instruction:proposal.question||'',responseText:proposal.responseText||'',
      blocks:proposal.blocks,codeBlockCount:Number(proposal.codeBlockCount||0),
      createdAt:proposal.createdAt||new Date().toISOString()
    })
    setWorkspaceRightCollapsed(false)
    setCodeRightPanelTab('PROPOSAL')
  },[setCodeDiffReview,setCodeEditProposal,setWorkspaceRightCollapsed,setCodeRightPanelTab])
  return {registerCodexCodeProposal}
}
