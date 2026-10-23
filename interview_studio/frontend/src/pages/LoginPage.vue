<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const loading = ref(false)
const auth = useAuthStore()
const router = useRouter()
async function login() {
  loading.value = true
  try { await auth.login(); router.push('/') } finally { loading.value = false }
}
</script>

<template>
  <main class="login-page">
    <section class="login-story">
      <div class="brand light"><span class="brand-mark">CF</span><span>CareerFit <b>AI</b></span></div>
      <div class="story-copy">
        <p class="eyebrow">EVIDENCE-BASED CAREER COACH</p>
        <h1>당신의 경험이<br><em>가장 빛나는 곳</em>을 찾다.</h1>
        <p>흩어진 경험 자료와 개인 문서를 면접 준비에 연결해, 근거 있는 답변 전략을 만듭니다.</p>
      </div>
      <div class="signal-card">
        <span>FIT SIGNAL</span><strong>87</strong><small>내 경험과 목표 기업의 연결도를 한눈에</small>
      </div>
    </section>
    <section class="login-panel">
      <div class="login-box">
        <p class="eyebrow">WELCOME TO CAREERFIT</p>
        <h2>오늘의 커리어 준비를<br>시작해 볼까요?</h2>
        <p>현재 MVP는 안전한 임시 계정으로 시작합니다. 별도의 가입 정보는 필요하지 않아요.</p>
        <button class="button primary wide" :disabled="loading" @click="login">
          {{ loading ? '워크스페이스 준비 중…' : '임시 계정으로 시작하기' }} <span>→</span>
        </button>
        <div class="login-points">
          <span>✓ 개인 데이터 분리</span><span>✓ 근거 기반 AI 답변</span><span>✓ 실전 면접 피드백</span>
        </div>
      </div>
    </section>
  </main>
</template>
