from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
builder=(ROOT/'frontend/src/features/agent-builder/hooks/useAgentBuilderController.ts').read_text(encoding='utf-8')
development=(ROOT/'frontend/src/features/agent-development/hooks/useAgentDevelopmentController.ts').read_text(encoding='utf-8')
external=(ROOT/'frontend/src/features/external-project/hooks/useExternalProjectController.ts').read_text(encoding='utf-8')
external_service=(ROOT/'frontend/src/features/external-project/services/externalProjectService.ts').read_text(encoding='utf-8')
codex=(ROOT/'frontend/src/features/codex/hooks/useCodexProposalController.ts').read_text(encoding='utf-8')
assert 'useAgentBuilderController({' in app
assert 'useAgentDevelopmentController()' in app
assert 'useExternalProjectController()' in app
assert 'useCodexProposalController({' in app
for token in ['confirmedInterviewRequirements','requirementRecommendations','developmentStagePlan','requirementDraftCandidate']:
    assert token in builder, token
for token in ['developmentProgress','developmentFinalStatus','builderMessagesEndRef','restoredBuildResume','redevelopmentInfo']:
    assert token in development, token
for token in ['externalProjectPath','externalProjectAnalysis','externalProjectProgress']:
    assert token in external, token
for token in ['/system/pick-folder','/projects/analyze-external','/projects/create-agent']:
    assert token in external_service, token
assert 'registerCodexCodeProposal' in codex
assert "AGENTSTUDIO_FRONTEND_VERSION='5.552'" in app
assert len(app.splitlines()) < 21845
print('v5.552 core feature separation: PASS')
print('App.tsx:',len(app.splitlines()))
