import type { RedisKeySummary, RedisTreeNode } from '../types/database'

export function formatRedisBytes(value: unknown): string {
  const bytes = Number(value)
  if (!Number.isFinite(bytes) || bytes < 0) return '-'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(bytes < 10240 ? 1 : 0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function redisTtlLabel(ttl: unknown): string {
  const value = Number(ttl)
  if (value === -1) return 'No limit'
  if (value === -2 || !Number.isFinite(value)) return '-'
  if (value < 60) return `${value}s`
  if (value < 3600) return `${Math.floor(value / 60)}m ${value % 60}s`
  if (value < 86400) return `${Math.floor(value / 3600)}h ${Math.floor((value % 3600) / 60)}m`
  return `${Math.floor(value / 86400)}d ${Math.floor((value % 86400) / 3600)}h`
}

export function redisLiveTtl(ttl: unknown, observedAt: unknown, now: number): number {
  const value = Number(ttl)
  if (!Number.isFinite(value) || value <= 0) return value
  const observed = Number(observedAt)
  if (!Number.isFinite(observed) || observed <= 0) return value
  const elapsed = Math.max(0, Math.floor((now - observed) / 1000))
  return Math.max(0, value - elapsed)
}

interface RedisMutableTreeNode {
  name: string
  path: string
  children: Map<string, RedisMutableTreeNode>
  items: RedisKeySummary[]
}

export function buildRedisKeyTree(keys: RedisKeySummary[] = []): RedisTreeNode {
  const root: RedisMutableTreeNode = { name: '', path: '', children: new Map(), items: [] }
  for (const item of Array.isArray(keys) ? keys : []) {
    const full = String(item?.key || '')
    if (!full) continue
    const parts = full.split(':')
    const leaf = parts.pop() || full
    let node = root
    let path = ''
    for (const part of parts) {
      path = path ? `${path}:${part}` : part
      let child = node.children.get(part)
      if (!child) {
        child = { name: part, path, children: new Map(), items: [] }
        node.children.set(part, child)
      }
      node = child
    }
    node.items.push({ ...item, label: leaf })
  }
  const finalize = (node: RedisMutableTreeNode): RedisTreeNode => ({
    name: node.name,
    path: node.path,
    children: [...node.children.values()]
      .sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }))
      .map(finalize),
    items: node.items.sort((a, b) => String(a.label || '').localeCompare(String(b.label || ''), undefined, { sensitivity: 'base' })),
  })
  return finalize(root)
}

export function countRedisTreeKeys(node: RedisTreeNode | null | undefined): number {
  if (!node) return 0
  return (node.items || []).length + (node.children || []).reduce((sum, child) => sum + countRedisTreeKeys(child), 0)
}

export function firestoreValueText(value: unknown): string {
  if (value === null) return 'null'
  if (value === undefined) return ''
  if (typeof value === 'string') return value
  if (typeof value === 'number' || typeof value === 'boolean') return String(value)
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}
