/**
 * Anonymous per-browser id, so feedback votes can be shown again and changed.
 * Not tied to any account; clearing site data gives a new id.
 */

const STORAGE_KEY = 'fashion-rec-client-id'
let memoryId: string | null = null

function newId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) return crypto.randomUUID()
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`
}

export function getClientId(): string {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (stored) return stored
    const id = newId()
    window.localStorage.setItem(STORAGE_KEY, id)
    return id
  } catch {
    // Storage blocked (private mode, etc.): keep an id for this page load only.
    memoryId ??= newId()
    return memoryId
  }
}
