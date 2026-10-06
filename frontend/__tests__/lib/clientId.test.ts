import { describe, it, expect, beforeEach, vi } from 'vitest'
import { getClientId } from '@/lib/clientId'

describe('getClientId', () => {
  beforeEach(() => {
    window.localStorage.clear()
    vi.restoreAllMocks()
  })

  it('creates an id once and reuses it', () => {
    const first = getClientId()
    expect(first).toMatch(/^[A-Za-z0-9-]{8,64}$/)
    expect(getClientId()).toBe(first)
  })

  it('still works when storage is blocked', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    const id = getClientId()
    expect(id).toMatch(/^[A-Za-z0-9-]{8,64}$/)
    expect(getClientId()).toBe(id)
  })
})
