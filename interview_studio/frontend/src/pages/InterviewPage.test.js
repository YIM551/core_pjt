import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import InterviewPage from './InterviewPage.vue'

const { get, post } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
vi.mock('../api/client', () => ({
  api: { get, post },
  unwrap: (response) => response.data,
}))
vi.mock('../utils/notify', () => ({ notify: vi.fn() }))

const global = {
  stubs: {
    AppLayout: { template: '<main><slot name="actions" /><slot /></main>' },
    LoadingState: { template: '<p>loading</p>' },
  },
}

function startedSession(id = 1) {
  return {
    session: {
      id,
      status: 'IN_PROGRESS',
      target_role: 'BACKEND',
      interview_type: 'COMPREHENSIVE',
      difficulty: 'INTERMEDIATE',
    },
    messages: [],
  }
}

describe('InterviewPage', () => {
  beforeEach(() => {
    get.mockReset().mockResolvedValue({ data: [] })
    post.mockReset()
    vi.stubGlobal('confirm', vi.fn(() => true))
  })

  it('질문 수 없이 역할·유형·난이도만 전송하고 채팅 화면을 연다', async () => {
    post.mockResolvedValue({ data: startedSession() })
    const wrapper = mount(InterviewPage, { global, attachTo: document.body })
    await flushPromises()

    await wrapper.get('.interview-setup form').trigger('submit')
    await flushPromises()

    expect(post).toHaveBeenCalledWith('/interviews', {
      target_role: 'BACKEND',
      interview_type: 'COMPREHENSIVE',
      difficulty: 'INTERMEDIATE',
    })
    expect(wrapper.text()).toContain('간단한 자기소개나 최근 경험부터 편하게 이야기해 주세요.')
    expect(wrapper.findAll('.interview-bubble')).toHaveLength(0)
    expect(document.activeElement).toBe(wrapper.get('#interview-message').element)
    expect(wrapper.text()).not.toContain('질문 수')
    expect(wrapper.text()).not.toContain('LIVE FEEDBACK')
    expect(wrapper.find('.interview-progress').exists()).toBe(false)
    wrapper.unmount()
  })

  it('메시지를 /messages로 보내고 평가 없이 두 말풍선을 이어 붙인다', async () => {
    post
      .mockResolvedValueOnce({ data: startedSession() })
      .mockResolvedValueOnce({
        data: {
          candidate_message: {
            id: 11,
            sequence_number: 2,
            speaker: 'CANDIDATE',
            content: '제가 맡은 역할은 API 개발입니다.',
          },
          interviewer_message: {
            id: 12,
            sequence_number: 3,
            speaker: 'INTERVIEWER',
            content: '그 과정의 핵심 판단을 설명해 주세요.',
          },
        },
      })
    const wrapper = mount(InterviewPage, { global })
    await flushPromises()
    await wrapper.get('.interview-setup form').trigger('submit')
    await flushPromises()

    await wrapper.get('#interview-message').setValue('  제가 맡은 역할은 API 개발입니다.  ')
    await wrapper.get('.interview-composer').trigger('submit')
    await flushPromises()

    expect(post).toHaveBeenLastCalledWith('/interviews/1/messages', {
      content: '제가 맡은 역할은 API 개발입니다.',
    })
    expect(wrapper.text()).toContain('그 과정의 핵심 판단을 설명해 주세요.')
    expect(wrapper.findAll('.interview-bubble')).toHaveLength(2)
    expect(wrapper.text()).not.toContain('개선 답변')
  })

  it('진행 중 세션의 저장 대화를 불러와 그대로 계속한다', async () => {
    get.mockImplementation((url) => {
      if (url === '/interviews') {
        return Promise.resolve({
          data: [{ id: 7, target_role: 'BACKEND', interview_type: 'TECHNICAL', status: 'IN_PROGRESS' }],
        })
      }
      if (url === '/interviews/7') {
        return Promise.resolve({
          data: {
            session: {
              id: 7,
              status: 'IN_PROGRESS',
              target_role: 'BACKEND',
              interview_type: 'TECHNICAL',
              difficulty: 'ADVANCED',
            },
            messages: [
              { id: 1, sequence_number: 1, speaker: 'INTERVIEWER', content: '기존 질문' },
              { id: 2, sequence_number: 2, speaker: 'CANDIDATE', content: '기존 답변' },
              { id: 3, sequence_number: 3, speaker: 'INTERVIEWER', content: '기존 후속 질문' },
            ],
          },
        })
      }
      return Promise.resolve({ data: [] })
    })
    const wrapper = mount(InterviewPage, { global })
    await flushPromises()

    await wrapper.get('.session-list button').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('기존 답변')
    expect(wrapper.text()).toContain('기존 후속 질문')
    expect(wrapper.get('#interview-message').attributes('maxlength')).toBe('5000')
  })

  it('메시지가 없는 진행 중 세션을 다시 열면 지원자 입력창에 포커스한다', async () => {
    get.mockImplementation((url) => {
      if (url === '/interviews') {
        return Promise.resolve({
          data: [{ id: 8, target_role: 'BACKEND', interview_type: 'TECHNICAL', status: 'IN_PROGRESS' }],
        })
      }
      if (url === '/interviews/8') {
        return Promise.resolve({
          data: {
            session: {
              id: 8,
              status: 'IN_PROGRESS',
              target_role: 'BACKEND',
              interview_type: 'TECHNICAL',
              difficulty: 'INTERMEDIATE',
            },
            messages: [],
          },
        })
      }
      return Promise.resolve({ data: [] })
    })
    const wrapper = mount(InterviewPage, { global, attachTo: document.body })
    await flushPromises()

    await wrapper.get('.session-list button').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('간단한 자기소개나 최근 경험부터 편하게 이야기해 주세요.')
    expect(document.activeElement).toBe(wrapper.get('#interview-message').element)
    wrapper.unmount()
  })

  it('종료 또는 그만이라는 텍스트도 finish가 아닌 일반 메시지로 보낸다', async () => {
    post
      .mockResolvedValueOnce({ data: startedSession() })
      .mockResolvedValueOnce({
        data: {
          candidate_message: { id: 2, speaker: 'CANDIDATE', content: '종료' },
          interviewer_message: { id: 3, speaker: 'INTERVIEWER', content: '면접을 계속하겠습니다.' },
        },
      })
    const wrapper = mount(InterviewPage, { global })
    await flushPromises()
    await wrapper.get('.interview-setup form').trigger('submit')
    await flushPromises()

    await wrapper.get('#interview-message').setValue('종료')
    await wrapper.get('.interview-composer').trigger('submit')
    await flushPromises()

    expect(post).toHaveBeenLastCalledWith('/interviews/1/messages', { content: '종료' })
    expect(post.mock.calls.some(([url]) => url.endsWith('/finish'))).toBe(false)
  })

  it('종료 확인을 취소하면 아무 일도 없고 승인해야 finish와 보고서를 호출한다', async () => {
    post.mockResolvedValueOnce({ data: startedSession() })
    const wrapper = mount(InterviewPage, { global })
    await flushPromises()
    await wrapper.get('.interview-setup form').trigger('submit')
    await flushPromises()

    window.confirm.mockReturnValueOnce(false)
    await wrapper.get('.interview-chat-head .danger').trigger('click')
    expect(post).toHaveBeenCalledTimes(1)

    post.mockResolvedValueOnce({
      data: { ...startedSession().session, status: 'COMPLETED', overall_score: null },
    })
    get.mockImplementation((url) => {
      if (url === '/interviews/1/report') {
        return Promise.resolve({
          data: {
            overall_score: null,
            summary: '평가할 답변이 부족합니다.',
            evaluations: [],
          },
        })
      }
      return Promise.resolve({ data: [] })
    })
    window.confirm.mockReturnValueOnce(true)
    await wrapper.get('.interview-chat-head .danger').trigger('click')
    await flushPromises()

    expect(post).toHaveBeenLastCalledWith('/interviews/1/finish')
    expect(get).toHaveBeenCalledWith('/interviews/1/report')
    expect(wrapper.text()).toContain('평가할 답변이 부족합니다.')
    expect(wrapper.text()).toContain('평가 없음')
  })

  it('전송 중에는 중복 메시지 제출을 막고 실패 후 입력을 보존한다', async () => {
    let rejectMessage
    post
      .mockResolvedValueOnce({ data: startedSession() })
      .mockReturnValueOnce(new Promise((_, reject) => { rejectMessage = reject }))
    const wrapper = mount(InterviewPage, { global })
    await flushPromises()
    await wrapper.get('.interview-setup form').trigger('submit')
    await flushPromises()

    await wrapper.get('#interview-message').setValue('보존할 메시지')
    const first = wrapper.get('.interview-composer').trigger('submit')
    await wrapper.vm.$nextTick()
    await wrapper.get('.interview-composer').trigger('submit')
    expect(post).toHaveBeenCalledTimes(2)

    rejectMessage(new Error('network'))
    await first
    await flushPromises()
    expect(wrapper.get('#interview-message').element.value).toBe('보존할 메시지')
    expect(wrapper.text()).toContain('메시지를 보내지 못했습니다.')
  })

  it('한글 조합 Enter와 Shift+Enter는 전송하지 않고 일반 Enter만 전송한다', async () => {
    post
      .mockResolvedValueOnce({ data: startedSession() })
      .mockResolvedValueOnce({
        data: {
          candidate_message: { id: 2, speaker: 'CANDIDATE', content: '한글 답변' },
          interviewer_message: { id: 3, speaker: 'INTERVIEWER', content: '후속 질문' },
        },
      })
    const wrapper = mount(InterviewPage, { global })
    await flushPromises()
    await wrapper.get('.interview-setup form').trigger('submit')
    await flushPromises()
    const textarea = wrapper.get('#interview-message')
    await textarea.setValue('한글 답변')

    await textarea.trigger('keydown', { key: 'Enter', isComposing: true })
    await textarea.trigger('keydown', { key: 'Enter', keyCode: 229 })
    await textarea.trigger('keydown', { key: 'Enter', shiftKey: true })
    expect(post).toHaveBeenCalledTimes(1)

    await textarea.trigger('keydown', { key: 'Enter' })
    await flushPromises()
    expect(post).toHaveBeenLastCalledWith('/interviews/1/messages', {
      content: '한글 답변',
    })
  })

  it('전송과 종료 중에는 목록 이동을 막아 늦은 응답이 현재 세션만 갱신한다', async () => {
    let resolveMessage
    post
      .mockResolvedValueOnce({ data: startedSession() })
      .mockReturnValueOnce(new Promise((resolve) => { resolveMessage = resolve }))
    const wrapper = mount(InterviewPage, { global })
    await flushPromises()
    await wrapper.get('.interview-setup form').trigger('submit')
    await flushPromises()

    await wrapper.get('#interview-message').setValue('지연 답변')
    await wrapper.get('.interview-composer').trigger('submit')
    await wrapper.vm.$nextTick()
    const listButton = wrapper.get('main > button')
    expect(listButton.attributes('disabled')).toBeDefined()
    await listButton.trigger('click')
    expect(wrapper.find('.interview-chat').exists()).toBe(true)

    resolveMessage({
      data: {
        candidate_message: { id: 2, speaker: 'CANDIDATE', content: '지연 답변' },
        interviewer_message: { id: 3, speaker: 'INTERVIEWER', content: '지연 후속 질문' },
      },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('지연 후속 질문')

    let resolveFinish
    post.mockReturnValueOnce(new Promise((resolve) => { resolveFinish = resolve }))
    await wrapper.get('.interview-chat-head .danger').trigger('click')
    await wrapper.vm.$nextTick()
    expect(wrapper.get('main > button').attributes('disabled')).toBeDefined()
    await wrapper.get('main > button').trigger('click')
    expect(wrapper.find('.interview-chat').exists()).toBe(true)

    get.mockImplementation((url) => {
      if (url === '/interviews/1/report') {
        return Promise.resolve({ data: { overall_score: null, summary: '종료 결과', evaluations: [] } })
      }
      return Promise.resolve({ data: [] })
    })
    resolveFinish({
      data: { ...startedSession().session, status: 'COMPLETED', overall_score: null },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('종료 결과')
  })

  it('닫힌 세션의 늦은 보고서 응답이 새로 연 세션을 오염시키지 않는다', async () => {
    let resolveOldReport
    get.mockImplementation((url) => {
      if (url === '/interviews') {
        return Promise.resolve({
          data: [
            { id: 1, target_role: 'BACKEND', interview_type: 'TECHNICAL', status: 'COMPLETED' },
            { id: 2, target_role: 'INFRA', interview_type: 'TECHNICAL', status: 'IN_PROGRESS' },
          ],
        })
      }
      if (url === '/interviews/1') {
        return Promise.resolve({
          data: {
            session: { id: 1, status: 'COMPLETED', target_role: 'BACKEND', interview_type: 'TECHNICAL' },
            messages: [],
          },
        })
      }
      if (url === '/interviews/1/report') {
        return new Promise((resolve) => { resolveOldReport = resolve })
      }
      if (url === '/interviews/2') {
        return Promise.resolve({
          data: {
            session: {
              id: 2,
              status: 'IN_PROGRESS',
              target_role: 'INFRA',
              interview_type: 'TECHNICAL',
              difficulty: 'ADVANCED',
            },
            messages: [
              { id: 20, sequence_number: 1, speaker: 'INTERVIEWER', content: '새 세션 질문' },
            ],
          },
        })
      }
      return Promise.resolve({ data: [] })
    })
    const wrapper = mount(InterviewPage, { global })
    await flushPromises()
    await wrapper.findAll('.session-list button')[0].trigger('click')
    await wrapper.vm.$nextTick()
    await wrapper.get('main > button').trigger('click')
    await wrapper.findAll('.session-list button')[1].trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('새 세션 질문')

    resolveOldReport({
      data: { overall_score: 99, summary: '이전 세션의 늦은 보고서', evaluations: [] },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('새 세션 질문')
    expect(wrapper.text()).not.toContain('이전 세션의 늦은 보고서')
  })

  it('세션 목록은 진행·평가 없음·숫자 점수를 구분한다', async () => {
    get.mockResolvedValueOnce({
      data: [
        { id: 1, target_role: 'BACKEND', interview_type: 'TECHNICAL', status: 'IN_PROGRESS', overall_score: null },
        { id: 2, target_role: 'INFRA', interview_type: 'TECHNICAL', status: 'COMPLETED', overall_score: null },
        { id: 3, target_role: 'PM', interview_type: 'PERSONALITY', status: 'COMPLETED', overall_score: 87 },
      ],
    })
    const wrapper = mount(InterviewPage, { global })
    await flushPromises()
    const labels = wrapper.findAll('.session-list b').map((item) => item.text())

    expect(labels).toEqual(['진행 중 →', '평가 없음 →', '87점 →'])
  })

  it('완료 면접 보고서 실패 시 재시도를 표시한다', async () => {
    let reportCalls = 0
    get.mockImplementation((url) => {
      if (url === '/interviews') {
        return Promise.resolve({
          data: [{ id: 12, target_role: 'BACKEND', interview_type: 'TECHNICAL', status: 'COMPLETED' }],
        })
      }
      if (url === '/interviews/12') {
        return Promise.resolve({
          data: {
            session: {
              id: 12,
              status: 'COMPLETED',
              target_role: 'BACKEND',
              interview_type: 'TECHNICAL',
              difficulty: 'INTERMEDIATE',
            },
            messages: [],
          },
        })
      }
      if (url === '/interviews/12/report') {
        reportCalls += 1
        return reportCalls === 1
          ? Promise.reject(new Error('report failed'))
          : Promise.resolve({ data: { overall_score: 88, summary: '좋은 면접', evaluations: [] } })
      }
      return Promise.resolve({ data: [] })
    })
    const wrapper = mount(InterviewPage, { global })
    await flushPromises()
    await wrapper.get('.session-list button').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('면접 보고서를 불러오지 못했습니다.')
    await wrapper.get('.empty-state button').trigger('click')
    await flushPromises()
    expect(reportCalls).toBe(2)
    expect(wrapper.text()).toContain('좋은 면접')
  })
})
