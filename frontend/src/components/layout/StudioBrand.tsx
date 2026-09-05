import React from 'react'

export interface StudioBrandProps {
  version: string
  onHome: () => void
}

export function StudioBrand({ version, onHome }: StudioBrandProps) {
  return (
    <div className="brand-block" onClick={onHome} title="THEANOVA AgentStudio 홈">
      <img className="brand-symbol-image" src="/branding/theanova-symbol.png" alt="THEANOVA" draggable="false" />
      <img className="brand-wordmark-image" src="/branding/theanova-wordmark.png" alt="THEANOVA" draggable="false" />
      <strong className="brand-product-name">AgentStudio</strong>
      <span className="brand-version-badge" title={`현재 THEANOVA AgentStudio 버전 v${version}`}>
        v{version}
      </span>
    </div>
  )
}
