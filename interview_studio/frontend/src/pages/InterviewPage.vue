<script setup>
import { nextTick, onMounted, reactive, ref } from 'vue'
import AppLayout from '../layouts/AppLayout.vue'
import LoadingState from '../components/LoadingState.vue'
import MarkdownContent from '../components/MarkdownContent.vue'
import { api, unwrap } from '../api/client'
import { notify } from '../utils/notify'

const roles = [
  ['FRONTEND', '프론트엔드'],
  ['BACKEND', '백엔드'],
  ['DATA_AI', '데이터·AI'],
  ['EMBEDDED', '임베디드'],
  ['INFRA', '인프라'],
  ['PM', 'PM'],
]
const sessions = ref([])
const active = ref(null)
const message = ref('')
const report = ref(null)
const chatLog = ref(null)
const composer = ref(null)
const loadingSessions = ref(true)
const listError = ref('')
const chatError = ref('')
const starting = ref(false)
const sending = ref(false)
const finishing = ref(false)
const openingId = ref(null)
const reportLoading = ref(false)
const reportError = ref('')
const pendingCandidate = ref('')
const pendingReply = ref('')
const setup = reactive({
  target_role: 'BACKEND',
  interview_type: 'COMPREHENSIVE',
  difficulty: 'INTERMEDIATE',
})
let transitionSequence = 0

async function scrollToLatest() {
  await nextTick()
  if (chatLog.value) chatLog.value.scrollTop = chatLog.value.scrollHeight
}

async function focusComposer() {
  await nextTick()
  composer.value?.focus()
}

async function loadSessions() {
  loadingSessions.value = true
  listError.value = ''
  try {
    sessions.value = unwrap(await api.get('/interviews')) || []
  } catch {
    listError.value = '면접 기록을 불러오지 못했습니다.'
  } finally {
    loadingSessions.value = false
  }
}

async function start() {
  if (starting.value || openingId.value !== null) return
  const transition = ++transitionSequence
  starting.value = true
  chatError.value = ''
  try {
    const data = unwrap(await api.post('/interviews', { ...setup }))
    if (transition !== transitionSequence) return
    active.value = { session: data.session, messages: data.messages || [] }
    report.value = null
    reportError.value = ''
    if (active.value.messages.length) await scrollToLatest()
    else await focusComposer()
  } catch {
    if (transition === transitionSequence) {
      chatError.value = '면접을 시작하지 못했습니다. 삼성전자 면접 자료 상태를 확인해 주세요.'
    }
  } finally {
    if (transition === transitionSequence) starting.value = false
  }
}

async function openSession(session) {
  if (starting.value || openingId.value !== null) return
  const transition = ++transitionSequence
  openingId.value = session.id
  chatError.value = ''
  try {
    const detail = unwrap(await api.get(`/interviews/${session.id}`))
    if (transition !== transitionSequence) return
    active.value = detail
    report.value = null
    reportError.value = ''
    if (detail.session.status === 'COMPLETED') {
      await loadReport(detail.session.id)
    } else if (!detail.messages?.length) {
      await focusComposer()
    } else {
      await scrollToLatest()
    }
  } catch {
    if (transition === transitionSequence) {
      listError.value = '면접 내용을 불러오지 못했습니다.'
    }
  } finally {
    if (transition === transitionSequence) openingId.value = null
  }
}

async function submit() {
  const content = message.value.trim()
  if (!content || content.length > 5000 || sending.value || finishing.value) return
  const transition = transitionSequence
  const sessionId = active.value?.session.id
  if (!sessionId) return
  sending.value = true
  chatError.value = ''
  pendingCandidate.value = content
  pendingReply.value = ''
  await scrollToLatest()
  try {
    let data = null
    if (!api.defaults?.baseURL) {
      data = unwrap(await api.post(`/interviews/${sessionId}/messages`, { content }))
    } else {
      const response = await fetch(
        `${api.defaults.baseURL}/interviews/${sessionId}/messages/stream`,
        {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
          body: JSON.stringify({ content }),
        },
      )
      if (!response.ok || !response.body) {
        const problem = await response.json().catch(() => null)
        const streamError = new Error(problem?.detail || 'stream request failed')
        streamError.status = response.status
        streamError.code = problem?.code
        throw streamError
      }
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      const handleEvent = async (rawEvent) => {
        const eventName = rawEvent.match(/^event:\s*(.+)$/m)?.[1]
        const rawData = rawEvent.match(/^data:\s*(.+)$/m)?.[1]
        if (!eventName || !rawData) return
        const eventData = JSON.parse(rawData)
        if (eventName === 'token') {
          pendingReply.value += eventData.text || ''
          await scrollToLatest()
        } else if (eventName === 'complete') {
          data = eventData
        } else if (eventName === 'error') {
          throw new Error(eventData.message || 'stream failed')
        }
      }
      while (true) {
        const { value, done } = await reader.read()
        buffer += decoder.decode(value || new Uint8Array(), { stream: !done })
        const events = buffer.split(/\r?\n\r?\n/)
        buffer = events.pop() || ''
        for (const rawEvent of events) await handleEvent(rawEvent)
        if (done) {
          if (buffer.trim()) await handleEvent(buffer)
          break
        }
      }
    }
    if (!data) throw new Error('stream completed without a message')
    if (transition !== transitionSequence || active.value?.session.id !== sessionId) return
    active.value.messages.push(data.candidate_message, data.interviewer_message)
    message.value = ''
    await scrollToLatest()
  } catch (error) {
    console.error('[CareerFit Interview] message stream failed', {
      sessionId,
      status: error.status,
      code: error.code,
      message: error.message,
      stack: error.stack,
    })
    if (transition === transitionSequence && active.value?.session.id === sessionId) {
      chatError.value = '메시지를 보내지 못했습니다. 잠시 후 다시 시도해 주세요.'
    }
  } finally {
    pendingCandidate.value = ''
    pendingReply.value = ''
    sending.value = false
  }
}

async function loadReport(id, transition = transitionSequence) {
  reportLoading.value = true
  reportError.value = ''
  try {
    const data = unwrap(await api.get(`/interviews/${id}/report`))
    if (transition !== transitionSequence || active.value?.session.id !== id) return
    report.value = data
  } catch {
    if (transition === transitionSequence && active.value?.session.id === id) {
      report.value = null
      reportError.value = '면접 보고서를 불러오지 못했습니다.'
    }
  } finally {
    if (transition === transitionSequence && active.value?.session.id === id) {
      reportLoading.value = false
    }
  }
}

async function finish() {
  if (finishing.value || sending.value) return
  if (!window.confirm('면접을 종료하고 최종 피드백을 확인할까요?')) return
  const transition = transitionSequence
  const sessionId = active.value?.session.id
  if (!sessionId) return
  finishing.value = true
  chatError.value = ''
  try {
    const completedSession = unwrap(await api.post(`/interviews/${sessionId}/finish`))
    if (transition !== transitionSequence || active.value?.session.id !== sessionId) return
    active.value.session = completedSession
    await loadReport(sessionId, transition)
    if (transition !== transitionSequence || active.value?.session.id !== sessionId) return
    await loadSessions()
    if (transition !== transitionSequence || active.value?.session.id !== sessionId) return
    notify('면접을 종료했습니다.')
  } catch {
    if (transition === transitionSequence && active.value?.session.id === sessionId) {
      chatError.value = '면접을 종료하지 못했습니다. 잠시 후 다시 시도해 주세요.'
    }
  } finally {
    finishing.value = false
  }
}

function closeSession() {
  if (sending.value || finishing.value) return
  transitionSequence += 1
  active.value = null
  report.value = null
  reportError.value = ''
  chatError.value = ''
  message.value = ''
  pendingCandidate.value = ''
  pendingReply.value = ''
  openingId.value = null
}

function handleComposerKeydown(event) {
  if (event.isComposing || event.keyCode === 229) return
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    submit()
  }
}

function sessionScoreLabel(session) {
  if (session.status === 'IN_PROGRESS') return '진행 중'
  if (session.overall_score == null) return '평가 없음'
  return `${session.overall_score}점`
}

onMounted(loadSessions)
</script>

<template>
  <AppLayout title="실전처럼 대화하고, 종료 후 근거로 개선하기">
    <template #actions>
      <button
        v-if="active"
        class="button secondary"
        :disabled="sending || finishing"
        @click="closeSession"
      >
        면접 목록
      </button>
    </template>

    <template v-if="!active">
      <section class="interview-intro">
        <div>
          <p class="eyebrow">SAMSUNG MOCK INTERVIEW</p>
          <h2>정해진 순서 없이<br><em>면접관과 대화</em>해 보세요.</h2>
          <p>개인 문서와 삼성전자 직무 문서를 바탕으로 대화가 자연스럽게 이어집니다.</p>
        </div>
        <div class="interview-quote">답변, 질문, 설명 요청까지<br><strong>자유롭게 이야기하세요.</strong></div>
      </section>

      <section class="card interview-setup">
        <div class="section-head">
          <div><p class="eyebrow">SET YOUR SESSION</p><h2>면접 설정</h2></div>
        </div>
        <form @submit.prevent="start">
          <div class="form-grid">
            <label>대상 직무
              <select v-model="setup.target_role" required>
                <option v-for="[value, label] in roles" :key="value" :value="value">{{ label }}</option>
              </select>
            </label>
            <label>면접 유형
              <select v-model="setup.interview_type">
                <option>COMPREHENSIVE</option><option>TECHNICAL</option><option>PROJECT</option>
                <option>PERSONALITY</option><option>PRESSURE</option>
              </select>
            </label>
            <label>난이도
              <select v-model="setup.difficulty">
                <option>BEGINNER</option><option>INTERMEDIATE</option><option>ADVANCED</option>
              </select>
            </label>
          </div>
          <p v-if="chatError" class="chat-error" role="alert">{{ chatError }}</p>
          <button class="button primary" type="submit" :disabled="starting || openingId !== null">
            {{ starting ? '면접 준비 중…' : '면접 시작하기 →' }}
          </button>
        </form>
      </section>

      <LoadingState v-if="loadingSessions" />
      <section v-else class="card">
        <div class="section-head">
          <div><p class="eyebrow">RECENT SESSIONS</p><h2>최근 면접</h2></div>
          <button v-if="listError" class="text-button" @click="loadSessions">다시 시도</button>
        </div>
        <p v-if="listError" class="empty" role="alert">{{ listError }}</p>
        <div v-else-if="sessions.length" class="session-list interactive">
          <button
            v-for="session in sessions.slice(0, 10)"
            :key="session.id"
            :disabled="starting || openingId !== null"
            @click="openSession(session)"
          >
            <span>{{ session.target_role }} · {{ session.interview_type }}</span>
            <strong>{{ session.status }}</strong>
            <b>{{ sessionScoreLabel(session) }} →</b>
          </button>
        </div>
        <div v-else class="empty">아직 면접 기록이 없습니다.</div>
      </section>
    </template>

    <div v-else class="interview-room">
      <template v-if="active.session.status === 'COMPLETED'">
        <LoadingState v-if="reportLoading" />
        <section v-else-if="reportError" class="card empty-state" role="alert">
          <p>{{ reportError }}</p>
          <button class="button primary" @click="loadReport(active.session.id)">다시 시도</button>
        </section>
        <section v-else-if="report" class="report-card card">
          <p class="eyebrow">INTERVIEW REPORT</p>
          <div class="report-summary">
            <div>
              <strong>{{ report.overall_score ?? '–' }}</strong>
              <span>{{ report.overall_score == null ? '평가 없음' : '/ 100' }}</span>
            </div>
            <div><h2>면접 결과</h2><p>{{ report.summary || '요약이 아직 없습니다.' }}</p></div>
          </div>
          <h3>답변별 평가 {{ report.evaluations?.length || 0 }}개</h3>
          <p v-if="!report.evaluations?.length" class="empty">평가할 답변이 없습니다.</p>
          <details v-for="(item, index) in report.evaluations || []" :key="item.id || index">
            <summary>{{ index + 1 }}번째 답변 · {{ Math.round(item.total_score || 0) }}점</summary>
            <p><b>강점</b> {{ (item.strengths || []).join(', ') || '없음' }}</p>
            <p><b>개선 조언</b> {{ item.improvement_advice || '없음' }}</p>
          </details>
        </section>
      </template>

      <template v-else>
        <section class="interview-chat card" aria-labelledby="interview-chat-title">
          <div class="interview-chat-head">
            <div>
              <p class="eyebrow">LIVE INTERVIEW</p>
              <h2 id="interview-chat-title">삼성전자 {{ active.session.target_role }} 모의면접</h2>
              <small>{{ active.session.interview_type }} · {{ active.session.difficulty }}</small>
            </div>
            <button
              class="button danger"
              type="button"
              :disabled="finishing || sending"
              @click="finish"
            >
              {{ finishing ? '결과 생성 중…' : '면접 종료' }}
            </button>
          </div>

          <div ref="chatLog" class="interview-chat-log" role="log" aria-live="polite">
            <div v-if="!active.messages.length" class="interview-chat-empty">
              <p>간단한 자기소개나 최근 경험부터 편하게 이야기해 주세요.</p>
            </div>
            <article
              v-for="item in active.messages"
              :key="item.id || item.sequence_number"
              class="interview-bubble"
              :class="item.speaker === 'CANDIDATE' ? 'candidate' : 'interviewer'"
            >
              <span>{{ item.speaker === 'CANDIDATE' ? '나' : '면접관' }}</span>
              <MarkdownContent v-if="item.speaker !== 'CANDIDATE'" :content="item.content" />
              <p v-else>{{ item.content }}</p>
            </article>
            <article v-if="pendingCandidate" class="interview-bubble candidate pending">
              <span>지원자</span>
              <p>{{ pendingCandidate }}</p>
            </article>
            <article v-if="sending && !pendingReply" class="interview-bubble interviewer pending">
              <span>면접관</span>
              <div class="thinking-bubble" aria-label="면접관이 답변을 준비 중입니다">생각 중입니다…</div>
            </article>
            <article v-if="pendingReply" class="interview-bubble interviewer pending">
              <span>면접관</span>
              <MarkdownContent :content="pendingReply" streaming />
            </article>
          </div>

          <form class="interview-composer" @submit.prevent="submit">
            <label for="interview-message">메시지</label>
            <textarea
              id="interview-message"
              ref="composer"
              v-model="message"
              rows="3"
              maxlength="5000"
              :disabled="sending || finishing"
              placeholder="간단한 자기소개나 최근 경험부터 편하게 이야기해 주세요."
              @keydown="handleComposerKeydown"
            />
            <div>
              <small>{{ message.length }} / 5000 · Shift+Enter로 줄바꿈</small>
              <button
                class="button primary"
                type="submit"
                :disabled="sending || finishing || !message.trim()"
              >
                {{ sending ? '전송 중…' : '보내기' }}
              </button>
            </div>
          </form>
          <p v-if="chatError" class="chat-error" role="alert">{{ chatError }}</p>
        </section>
      </template>
    </div>
  </AppLayout>
</template>
