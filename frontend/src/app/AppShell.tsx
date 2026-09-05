import React from 'react'
import { SystemPage } from '../features/system/SystemPage'

export interface AppShellProps {
  Workspace: React.ComponentType
}

export function AppShell({ Workspace }: AppShellProps) {
  return location.pathname.startsWith('/system')
    ? <SystemPage />
    : <Workspace />
}
