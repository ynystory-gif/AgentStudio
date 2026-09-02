import type { MouseEventHandler, ReactNode } from 'react'

export interface StatusDotProps {
  ok: boolean
}

export function StatusDot({ ok }: StatusDotProps) {
  return <span className={ok ? 'dot ok' : 'dot bad'} />
}

export interface StudioIconProps {
  children: ReactNode
  active?: boolean
  onClick?: MouseEventHandler<HTMLButtonElement>
  title?: string
  'aria-label'?: string
}

export function StudioIcon({ children, active = false, onClick, title, 'aria-label': ariaLabel }: StudioIconProps) {
  return (
    <button
      type="button"
      className={active ? 'studio-nav-icon active' : 'studio-nav-icon'}
      onClick={onClick}
      title={title}
      aria-label={ariaLabel || title}
    >
      {children}
    </button>
  )
}

export interface MiniBadgeProps {
  children: ReactNode
  tone?: string
}

export function MiniBadge({ children, tone = 'blue' }: MiniBadgeProps) {
  return <span className={`mini-badge ${tone}`}>{children}</span>
}

export interface SectionTitleProps {
  title: ReactNode
  action?: ReactNode
}

export function SectionTitle({ title, action = null }: SectionTitleProps) {
  return <div className="section-title-row"><strong>{title}</strong>{action}</div>
}
