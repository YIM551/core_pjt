import { flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ChatPage from './ChatPage.vue'

const { post } = vi.hoisted(() => ({ post: vi.fn() }))
vi.mock('../api/client', () => ({
  api: { post },
  unwrap: (response) => response.data,
}))

const global = {
  stubs: {
    AppLayout: { template: '<main><slot /></main>' },
    RouterLink: { template: '<a><slot /></a>' },
  },
}

describe('ChatPage', () => {
  beforeEach(() => post.mockReset())

  it('개인 채팅 API에 question만 전송하고 빈 근거를 표시한다', async () => {
    post.mockResolvedValue({ data: { answer: '근거가 없습니다.', sources: [] } })
    const wrapper = mount(ChatPage, { global })
    await wrapper.get('textarea').setValue('  내 강점은?  ')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(post).toHaveBeenCalledWith('/candidate/chat', { question: '내 강점은?' })
    expect(wrapper.text()).toContain('검색된 문서 근거가 없습니다.')
  })

  it('응답 대기 중에는 중복 전송하지 않는다', async () => {
    let resolvePost
    post.mockReturnValue(new Promise((resolve) => { resolvePost = resolve }))
    const wrapper = mount(ChatPage, { global })
    await wrapper.get('textarea').setValue('질문')
    const firstSubmit = wrapper.get('form').trigger('submit')
    await nextTick()
    await wrapper.get('form').trigger('submit')

    expect(post).toHaveBeenCalledTimes(1)
    expect(wrapper.get('.send-button').attributes('disabled')).toBeDefined()
    resolvePost({ data: { answer: '답변', sources: [] } })
    await firstSubmit
    await flushPromises()
  })
})
