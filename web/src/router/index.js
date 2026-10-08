import { createRouter, createWebHashHistory } from 'vue-router'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/chat' },
    { path: '/chat', component: () => import('@/views/ChatView.vue') },
    { path: '/agents', component: () => import('@/views/AgentAdminView.vue') },
    { path: '/skills', component: () => import('@/views/SkillAdminView.vue') },
    { path: '/llms', component: () => import('@/views/LlmAdminView.vue') },
  ],
})

export default router
