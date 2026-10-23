import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import DocumentsPage from './DocumentsPage.vue'

const { get, post, notify } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), notify: vi.fn() }))
vi.mock('../api/client', () => ({
  api: { get, post, delete: vi.fn() },
  unwrap: (response) => response.data,
}))
vi.mock('../utils/notify', () => ({ notify }))

const global = {
  stubs: {
    AppLayout: { template: '<main><slot /></main>' },
    LoadingState: { template: '<p>loading</p>' },
  },
}

describe('DocumentsPage', () => {
  beforeEach(() => {
    get.mockReset().mockResolvedValue({ data: [] })
    post.mockReset()
    notify.mockReset()
  })

  it('기본 문서 유형은 OTHER이고 10MB 초과 파일을 거부한다', async () => {
    const wrapper = mount(DocumentsPage, { global })
    await flushPromises()
    expect(wrapper.get('select').element.value).toBe('OTHER')

    const oversized = new File([new Uint8Array(10 * 1024 * 1024 + 1)], 'resume.pdf', { type: 'application/pdf' })
    Object.defineProperty(wrapper.get('input[type=file]').element, 'files', { value: [oversized] })
    await wrapper.get('input[type=file]').trigger('change')

    expect(notify).toHaveBeenCalledWith('파일은 10MB 이하여야 합니다.', 'error')
    expect(post).not.toHaveBeenCalled()
  })

  it('.markdown 파일을 선택할 수 있다', async () => {
    const wrapper = mount(DocumentsPage, { global })
    await flushPromises()
    const input = wrapper.get('input[type=file]')
    expect(input.attributes('accept')).toContain('.markdown')
    const markdown = new File(['# CareerFit'], 'portfolio.markdown', { type: 'text/markdown' })
    Object.defineProperty(input.element, 'files', { value: [markdown] })
    await input.trigger('change')

    expect(notify).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('portfolio.markdown')
    expect(wrapper.get('.upload-form .button').attributes('disabled')).toBeUndefined()
  })
})
