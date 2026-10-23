<script setup>
import { nextTick, ref } from 'vue'
import AppLayout from '../layouts/AppLayout.vue'
import MarkdownContent from '../components/MarkdownContent.vue'
import { api, unwrap } from '../api/client'

const question = ref(''), messages = ref([]), loading = ref(false), error = ref(''), stream = ref(null)
const prompts = ['내 경험 자료에서 강조할 만한 내용은?', '내 문서를 바탕으로 자기소개를 구성해 줘.', '지원 전에 보완할 역량을 알려 줘.']
function sourceCategoryLabel(source) {
  return source?.category === 'PERSONAL' ? '개인 문서' : source?.category || '개인 문서'
}

async function send(text = question.value) {
  const q = text.trim()
  if (!q || loading.value) return
  messages.value.push({ role: 'user', content: q }); question.value = ''; error.value = ''; loading.value = true
  await nextTick()
  if (typeof stream.value?.scrollTo === 'function') {
    stream.value.scrollTo({ top: stream.value.scrollHeight, behavior: 'smooth' })
  }
  try {
    const data = unwrap(await api.post('/candidate/chat', { question: q }))
    messages.value.push({ role: 'ai', content: data.answer, sources: data.sources || [] })
  } catch {
    error.value = '답변을 받지 못했습니다. 잠시 후 다시 시도해 주세요.'
  } finally {
    loading.value = false
    await nextTick()
    if (typeof stream.value?.scrollTo === 'function') {
      stream.value.scrollTo({ top: stream.value.scrollHeight, behavior: 'smooth' })
    }
  }
}
</script>
<template>
  <AppLayout title="내 문서를 근거로 답하는 AI 코치">
    <div class="chat-layout personal-chat">
      <aside class="chat-context card"><p class="eyebrow">ANSWER SCOPE</p><h2>개인 문서 전용</h2><p>업로드 완료된 개인 문서에서만 근거를 검색합니다.</p><div class="privacy-note">근거가 없으면 추측하지 않고 찾지 못했다고 알려드립니다.</div><router-link class="button secondary wide" to="/documents">문서 관리</router-link></aside>
      <section class="chat-panel" aria-label="AI 코칭 대화">
        <div ref="stream" class="chat-stream" aria-live="polite">
          <div v-if="!messages.length" class="chat-welcome"><span>✦</span><p class="eyebrow">CAREERFIT AI</p><h2>어떤 준비가 필요하신가요?</h2><p>등록한 개인 문서에서 근거를 찾아 답하고 출처를 함께 보여드릴게요.</p><button v-for="prompt in prompts" :key="prompt" :disabled="loading" @click="send(prompt)">{{ prompt }} <b>→</b></button></div>
          <div v-for="(message,index) in messages" :key="index" class="message" :class="message.role"><span class="avatar">{{ message.role === 'ai' ? 'AI' : '나' }}</span><div><MarkdownContent v-if="message.role === 'ai'" :content="message.content" /><p v-else>{{ message.content }}</p><div v-if="message.role === 'ai'" class="sources"><small>참고한 문서</small><template v-if="message.sources.length"><span v-for="(source, sourceIndex) in message.sources" :key="`${source.category}-${source.title}-${sourceIndex}`">{{ source.title }} · {{ sourceCategoryLabel(source) }}</span></template><span v-else>검색된 문서 근거가 없습니다.</span></div></div></div>
          <p v-if="error" class="chat-error" role="alert">{{ error }}</p>
          <div v-if="loading" class="message ai"><span class="avatar">AI</span><div class="thinking-bubble" aria-label="답변 생성 중">생각 중입니다…</div></div>
        </div>
        <form class="chat-input" @submit.prevent="send()"><label class="sr-only" for="chat-question">질문</label><textarea id="chat-question" v-model="question" rows="2" :disabled="loading" placeholder="내 문서와 경험 자료에 관해 물어보세요." @keydown.enter.exact.prevent="send()"/><button class="send-button" type="submit" :disabled="loading || !question.trim()" aria-label="메시지 보내기">→</button><small>Enter로 전송 · 개인 문서 근거만 사용합니다.</small></form>
      </section>
    </div>
  </AppLayout>
</template>
