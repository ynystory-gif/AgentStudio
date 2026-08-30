import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { AuthGate } from './components/auth/AuthGate'
import { LlmLearningCenter } from './components/learning/LlmLearningCenter'
import { LearningProblemProgressEnhancer } from './components/learning/LearningProblemProgressEnhancer'
import { LearningPageStateRestoreEnhancer } from './components/learning/LearningPageStateRestoreEnhancer'
import { LearningFullApplyEnhancer } from './components/learning/LearningFullApplyEnhancer'
import { LearningWeightFinetuneEnhancer } from './components/learning/LearningWeightFinetuneEnhancer'
import { LearningModelStackEnhancer } from './components/learning/LearningModelStackEnhancer'
import { LearningUnlearnedListEnhancer } from './components/learning/LearningUnlearnedListEnhancer'
import { LearningCollectionLimitEnhancer } from './components/learning/LearningCollectionLimitEnhancer'
import { LearningDatasetTraceEnhancer } from './components/learning/LearningDatasetTraceEnhancer'
import { LayoutThemeDynamicSourceV2 } from './components/layout/LayoutThemeDynamicSourceV2'
import { ImportedThemePreviewEnhancer } from './components/layout/ImportedThemePreviewEnhancer'
import { LargeLayoutPreviewEnhancer } from './components/layout/LargeLayoutPreviewEnhancer'
import './styles.css'
import './components/learning/llm-learning.css'
import './components/learning/learning-case-list-cleanup.css'
import './components/learning/nav-order-fix.css'
import './components/learning/learning-weight-finetune.css'
import './components/layout/large-layout-preview.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AuthGate><App /><LlmLearningCenter /><LearningProblemProgressEnhancer /><LearningPageStateRestoreEnhancer /><LearningFullApplyEnhancer /><LearningWeightFinetuneEnhancer /><LearningModelStackEnhancer /><LearningUnlearnedListEnhancer /><LearningCollectionLimitEnhancer /><LearningDatasetTraceEnhancer /><LayoutThemeDynamicSourceV2 /><ImportedThemePreviewEnhancer /><LargeLayoutPreviewEnhancer /></AuthGate>
  </React.StrictMode>
)
