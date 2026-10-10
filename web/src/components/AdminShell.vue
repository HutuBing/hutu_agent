<template>
  <div class="page">
    <header class="page-head">
      <router-link to="/home" class="brand" style="text-decoration: none">🤖 hutu_agent</router-link>
      <nav class="nav">
        <router-link to="/home">主页</router-link>
        <router-link to="/chat">对话</router-link>
        <router-link to="/agents">Agent 管理</router-link>
        <router-link to="/skills">Skill 管理</router-link>
        <router-link to="/kbs">知识库</router-link>
        <router-link to="/llms">LLM 配置</router-link>
      </nav>
      <el-tag size="small" :type="appStore.llmFake ? 'warning' : 'success'" effect="plain">
        {{ appStore.llmFake ? '演示模式' : 'LLM 已接入' }}
      </el-tag>
    </header>
    <div class="page-body">
      <router-view />
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { appStore, loadHealth } from '@/stores/app'

onMounted(loadHealth)
</script>

<style scoped>
.page-body { flex: 1; min-height: 0; display: flex; }
.page-body :deep(> *) { flex: 1; }
/* router-link 生成的激活类是 .router-link-active（非 .active） */
.nav :deep(a.router-link-active) { background: var(--primary-light); color: var(--primary); font-weight: 600; }
</style>
