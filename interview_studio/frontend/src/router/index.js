import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import LoginPage from '../pages/LoginPage.vue'
import DashboardPage from '../pages/DashboardPage.vue'
import DocumentsPage from '../pages/DocumentsPage.vue'
import ChatPage from '../pages/ChatPage.vue'
import InterviewPage from '../pages/InterviewPage.vue'
import StudioPage from '../pages/StudioPage.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: LoginPage, meta: { public: true } },
    { path: '/', component: StudioPage },
    { path: '/dashboard', component: DashboardPage },
    { path: '/studio', component: StudioPage },
    { path: '/documents', component: DocumentsPage },
    { path: '/chat', component: ChatPage },
    { path: '/interview', component: InterviewPage },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (!auth.ready) await auth.restore()
  if (!to.meta.public && !auth.authenticated) return '/login'
  if (to.path === '/login' && auth.authenticated) return '/'
})

export default router

