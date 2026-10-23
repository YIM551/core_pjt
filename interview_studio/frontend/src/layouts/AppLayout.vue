<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

defineProps({ title: String, eyebrow: { type: String, default: 'CAREERFIT WORKSPACE' } })
const auth = useAuthStore()
const router = useRouter()
const open = ref(false)
const links = [
  ['/', '⌂', '면접 스튜디오'],
  ['/dashboard', '▦', '대시보드'],
  ['/documents', '▤', '문서 보관함'],
  ['/chat', '◌', 'AI 코치'], ['/interview', '◉', '모의면접'],
]
async function logout() { await auth.logout(); router.push('/login') }
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar" :class="{ open }">
      <router-link to="/" class="brand" @click="open = false">
        <span class="brand-mark">CF</span><span>CareerFit <b>AI</b></span>
      </router-link>
      <nav>
        <router-link v-for="[path, icon, label] in links" :key="path" :to="path" @click="open = false">
          <span class="nav-icon">{{ icon }}</span>{{ label }}
        </router-link>
      </nav>
      <div class="sidebar-foot">
        <div class="avatar">{{ auth.user?.name?.slice(0, 1) || 'U' }}</div>
        <div><strong>{{ auth.user?.name }}</strong><small>{{ auth.user?.email }}</small></div>
        <button class="icon-button" aria-label="로그아웃" @click="logout">↗</button>
      </div>
    </aside>
    <div class="mobile-backdrop" :class="{ show: open }" @click="open = false" />
    <main class="main">
      <header class="topbar">
        <button class="menu-button" aria-label="메뉴 열기" @click="open = true">☰</button>
        <div><p class="eyebrow">{{ eyebrow }}</p><h1>{{ title }}</h1></div>
        <slot name="actions" />
      </header>
      <div class="page-content"><slot /></div>
    </main>
  </div>
</template>

