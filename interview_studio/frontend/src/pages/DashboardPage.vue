<script setup>
import { computed, onMounted, ref } from 'vue'
import AppLayout from '../layouts/AppLayout.vue'
import LoadingState from '../components/LoadingState.vue'
import { api, unwrap } from '../api/client'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const loading = ref(true)
const error = ref('')
const documents = ref([])
const interviews = ref([])
const completedInterviews = computed(() => interviews.value.filter((item) => item.status === 'COMPLETED'))

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [docs, sessions] = await Promise.all([
      api.get('/candidate/documents'), api.get('/interviews'),
    ])
    documents.value = unwrap(docs) || []
    interviews.value = unwrap(sessions) || []
  } catch {
    error.value = '대시보드 정보를 불러오지 못했습니다.'
  } finally {
    loading.value = false
  }
}
onMounted(load)
</script>

<template>
  <AppLayout :title="`${auth.user?.name || '지원자'}님의 오늘 할 일`">
    <LoadingState v-if="loading" />
    <section v-else-if="error" class="card empty-state" role="alert">
      <h2>정보를 불러올 수 없습니다.</h2><p>{{ error }}</p><button class="button primary" @click="load">다시 시도</button>
    </section>
    <template v-else>
      <section class="hero-panel">
        <div><p class="eyebrow">TODAY'S FOCUS</p><h2>경험을 정리하고,<br><em>나만의 면접 근거</em>를 만드세요.</h2>
          <div class="hero-actions"><router-link class="button light" to="/documents">경험 자료 추가하기 →</router-link><router-link class="text-link" to="/interview">면접 연습 시작</router-link></div>
        </div>
      </section>
      <section class="metric-grid">
        <article><span class="metric-icon coral">▣</span><div><small>개인 문서</small><strong>{{ documents.length }}</strong></div><router-link to="/documents">관리 →</router-link></article>
        <article><span class="metric-icon blue">▤</span><div><small>전체 면접</small><strong>{{ interviews.length }}</strong></div><router-link to="/interview">보기 →</router-link></article>
        <article><span class="metric-icon gold">✓</span><div><small>완료 면접</small><strong>{{ completedInterviews.length }}</strong></div><router-link to="/interview">결과 →</router-link></article>
      </section>
      <div class="dashboard-grid">
        <section class="card"><div class="section-head"><div><p class="eyebrow">RECENT PRACTICE</p><h2>최근 면접</h2></div><router-link to="/interview">전체 보기 →</router-link></div>
          <div v-if="interviews.length" class="session-list"><div v-for="session in interviews.slice(0, 3)" :key="session.id"><span>{{ session.target_role }}</span><strong>{{ session.status }}</strong><b>{{ session.overall_score ?? '–' }}점</b></div></div>
          <div v-else class="empty">아직 면접 기록이 없습니다.</div>
        </section>
        <section class="card action-card"><p class="eyebrow">NEXT ACTION</p><h2>{{ documents.length ? '내 문서를 근거로 답변을 다듬어 보세요.' : '첫 경험 자료를 업로드해 보세요.' }}</h2><p>{{ documents.length ? 'AI 코치는 업로드한 개인 문서에서 근거를 찾아 답변합니다.' : '이력서나 포트폴리오를 올리면 AI 코치와 모의면접에서 경험 근거로 활용할 수 있습니다.' }}</p><router-link class="button primary" :to="documents.length ? '/chat' : '/documents'">{{ documents.length ? 'AI에게 물어보기' : '문서 업로드' }} →</router-link></section>
      </div>
    </template>
  </AppLayout>
</template>
