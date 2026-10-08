/** 全局共享状态（模块级单例；规模大了再迁 Pinia）。 */
import { reactive } from 'vue'

export const appStore = reactive({
  sessions: [],
  agents: [],
  currentSessionId: '',
  llmFake: false,
})

export async function loadHealth() {
  const r = await fetch('/health').then((x) => x.json())
  appStore.llmFake = !!r.llm_fake
}

export async function loadAgents() {
  appStore.agents = await fetch('/api/agents').then((x) => x.json()).catch(() => [])
}
