import { createRouter, createWebHashHistory } from 'vue-router'
import AdminShell from '@/components/AdminShell.vue'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      component: AdminShell, // 全局布局壳：顶部导航 + 内容区
      children: [
        { path: '', redirect: '/home' },
        { path: 'home', component: () => import('@/views/HomeView.vue') },
        { path: 'chat', component: () => import('@/views/ChatView.vue') },
        { path: 'agents', component: () => import('@/views/AgentAdminView.vue') },
        { path: 'skills', component: () => import('@/views/SkillAdminView.vue') },
        { path: 'kbs', component: () => import('@/views/KnowledgeBaseAdminView.vue') },
        { path: 'llms', component: () => import('@/views/LlmAdminView.vue') },
      ],
    },
  ],
})

export default router
