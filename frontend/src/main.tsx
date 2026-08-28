import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { AuthGate } from './components/auth/AuthGate'
import { LlmLearningCenter } from './components/learning/LlmLearningCenter'
import { LearningProblemProgressEnhancer } from './components/learning/LearningProblemProgressEnhancer'
import { LearningPageStateRestoreEnhancer } from './components/learning/LearningPageStateRestoreEnhancer'
import { LearningFullApplyEnhancer } from './components/learning/LearningFullApplyEnhancer'
import { LearningModelStackEnhancer } from './components/learning/LearningModelStackEnhancer'
import { LayoutThemeDynamicSourceEnhancer } from './components/layout/LayoutThemeDynamicSourceEnhancer'
import { ImportedThemePreviewEnhancer } from './components/layout/ImportedThemePreviewEnhancer'
import { LargeLayoutPreviewEnhancer } from './components/layout/LargeLayoutPreviewEnhancer'
import './styles.css'
import './components/learning/llm-learning.css'
import './components/learning/nav-order-fix.css'
import './components/layout/large-layout-preview.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AuthGate><App /><LlmLearningCenter /><LearningProblemProgressEnhancer /><LearningPageStateRestoreEnhancer /><LearningFullApplyEnhancer /><LearningModelStackEnhancer /><LayoutThemeDynamicSourceEnhancer /><ImportedThemePreviewEnhancer /><LargeLayoutPreviewEnhancer /></AuthGate>
  </React.StrictMode>
)
