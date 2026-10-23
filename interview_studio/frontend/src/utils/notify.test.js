import { beforeEach, describe, expect, it, vi } from 'vitest'
import { notify, toasts } from './notify'

describe('notify', () => {
  beforeEach(() => {
    toasts.splice(0)
    vi.useFakeTimers()
  })

  it('publishes and expires a toast', () => {
    notify('저장했습니다.')
    expect(toasts).toHaveLength(1)
    expect(toasts[0]).toMatchObject({ message: '저장했습니다.', type: 'success' })
    vi.advanceTimersByTime(3200)
    expect(toasts).toHaveLength(0)
  })
})
