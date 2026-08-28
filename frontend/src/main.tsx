import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { AuthGate } from './components/auth/AuthGate'
import { LlmLearningCenter } from './components/learning/LlmLearningCenter'
import { LayoutThemeDynamicSourceEnhancer } from './components/layout/LayoutThemeDynamicSourceEnhancer'
import './styles.css'
import './components/learning/llm-learning.css'
import './components/learning/nav-order-fix.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AuthGate><App /><LlmLearningCenter /><LayoutThemeDynamicSourceEnhancer /></AuthGate>
  </React.StrictMode>
)
