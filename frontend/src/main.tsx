import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './app/App'
import { AuthGate } from './components/auth/AuthGate'
import { LlmLearningCenter } from './components/learning/LlmLearningCenter'
import { LearningProblemProgressEnhancer } from './components/learning/LearningProblemProgressEnhancer'
import { LearningFullApplyEnhancer } from './components/learning/LearningFullApplyEnhancer'
import { LearningWeightFinetuneEnhancer } from './components/learning/LearningWeightFinetuneEnhancer'
import { LearningModelStackEnhancer } from './components/learning/LearningModelStackEnhancer'
import { LearningUnlearnedListEnhancer } from './components/learning/LearningUnlearnedListEnhancer'
import { LearningCollectionLimitEnhancer } from './components/learning/LearningCollectionLimitEnhancer'
import { LayoutThemeDynamicSourceV2 } from './components/layout/LayoutThemeDynamicSourceV2'
import { ImportedThemePreviewEnhancer } from './components/layout/ImportedThemePreviewEnhancer'
import { LargeLayoutPreviewEnhancer } from './components/layout/LargeLayoutPreviewEnhancer'
import { MediaSessionProvider } from './components/media/MediaSessionProvider'
import './styles.css'
import './components/learning/llm-learning.css'
import './components/learning/learning-case-list-cleanup.css'
import './components/learning/nav-order-fix.css'
import './components/learning/learning-weight-finetune.css'
import './components/layout/large-layout-preview.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AuthGate><MediaSessionProvider><App /><LlmLearningCenter /><LearningProblemProgressEnhancer /><LearningFullApplyEnhancer /><LearningWeightFinetuneEnhancer /><LearningModelStackEnhancer /><LearningUnlearnedListEnhancer /><LearningCollectionLimitEnhancer /><LayoutThemeDynamicSourceV2 /><ImportedThemePreviewEnhancer /><LargeLayoutPreviewEnhancer /></MediaSessionProvider></AuthGate>
  </React.StrictMode>
)
