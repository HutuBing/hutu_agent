<template>
  <div class="chat-page">
    <aside class="sidebar">
      <div class="brand-row">
        <span class="brand">🤖 hutu_agent</span>
      </div>
      <el-button class="new-btn" type="primary" plain @click="showNew = true">＋ 新建会话</el-button>
      <div class="session-list">
        <div
          v-for="s in appStore.sessions"
          :key="s.session_id"
          class="session-item"
          :class="{ active: s.session_id === appStore.currentSessionId }"
          @click="selectSession(s)"
        >
          <span class="s-agent" v-if="agentName(s.agent_id)">[{{ agentName(s.agent_id) }}]</span>
          <span>{{ s.title || '(无标题)' }}</span>
        </div>
        <div v-if="!appStore.sessions.length" class="empty">暂无会话</div>
      </div>
      <div class="meta">
        <el-tag size="small" :type="appStore.llmFake ? 'warning' : 'success'" effect="plain">
          {{ appStore.llmFake ? '演示模式（技能不生效）' : 'LLM 已接入' }}
        </el-tag>
      </div>
    </aside>

    <main class="chat-main">
      <header class="chat-head">{{ currentTitle }}</header>
      <div class="messages" ref="scrollEl" @scroll="onScroll">
        <div class="msg-col">
          <MessageBubble v-for="m in messages" :key="m.id" :message="m" />
          <div v-if="!messages.length" class="empty-tip">
            左侧新建会话开始对话<br>
            <small>绑定技能的 Agent 会展示工具调用过程</small>
          </div>
        </div>
      </div>
      <footer class="input-bar">
        <el-input
          v-model="input"
          type="textarea"
          :rows="2"
          resize="none"
          placeholder="输入消息，Enter 发送，Shift+Enter 换行"
          @keydown.enter.exact.prevent="send"
        />
        <el-button v-if="!busy" type="primary" :disabled="!appStore.currentSessionId" @click="send">发送</el-button>
        <el-button v-else type="danger" @click="stop">停止</el-button>
      </footer>
    </main>

    <NewSessionDialog v-model="showNew" @created="onCreated" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { appStore, loadHealth, loadAgents } from '@/stores/app'
import { listSessions, createSession, listMessages, chatStream } from '@/api/session'
import MessageBubble from '@/components/chat/MessageBubble.vue'
import NewSessionDialog from '@/components/chat/NewSessionDialog.vue'

const showNew = ref(false)
const input = ref('')
const busy = ref(false)
const messages = ref([])   // [{id, role, blocks:[...], usage}]
const scrollEl = ref(null)
const atBottom = ref(true)
let controller = null

const currentTitle = computed(() => {
  const s = appStore.sessions.find((x) => x.session_id === appStore.currentSessionId)
  return s ? (s.title || '(无标题)') : '选择或新建一个会话'
})

function agentName(agentId) {
  if (!agentId || agentId === 'default') return ''
  const a = appStore.agents.find((x) => x.agent_id === agentId)
  return a ? a.name : agentId.slice(0, 8)
}

async function loadSessions() {
  appStore.sessions = await listSessions()
}

function selectSession(s) {
  if (busy.value) return
  appStore.currentSessionId = s.session_id
  loadHistory()
}

async function loadHistory() {
  const list = await listMessages(appStore.currentSessionId)
  messages.value = list.map((m) => ({
    id: m.message_id,
    role: m.role,
    // 历史消息：工具块在前（ReAct 语义上工具先执行），文本块在后
    blocks: m.role === 'assistant'
      ? [
          ...(m.tool_calls || []).map((t, i) => ({
            kind: 'tool', runId: `${m.message_id}_h${i}`, name: t.tool_name,
            args: t.args_json, output: t.output_preview,
            durationMs: t.duration_ms, status: t.status, running: false,
          })),
          { kind: 'text', content: m.content },
        ]
      : [{ kind: 'text', content: m.content }],
    usage: null,
    done: true, // 历史消息不在生成中
  }))
  scrollBottom(true)
}

function scrollBottom(force = false) {
  if (!force && !atBottom.value) return
  nextTick(() => {
    const el = scrollEl.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

function onScroll() {
  const el = scrollEl.value
  atBottom.value = el.scrollHeight - el.scrollTop - el.clientHeight < 60
}

function onCreated(s) {
  appStore.currentSessionId = s.session_id
  messages.value = []
  loadSessions()
}

function stop() {
  controller?.abort()
}

async function send() {
  const content = input.value.trim()
  if (!content || busy.value || !appStore.currentSessionId) return
  busy.value = true
  input.value = ''
  atBottom.value = true

  messages.value.push({ id: `u_${Date.now()}`, role: 'user', blocks: [{ kind: 'text', content }], usage: null })
  const reply = { id: `a_${Date.now()}`, role: 'assistant', blocks: [], usage: null, done: false }
  messages.value.push(reply)
  scrollBottom(true)

  // 块操作辅助：取最后一个 text 块
  const lastText = () => {
    const b = reply.blocks[reply.blocks.length - 1]
    return b && b.kind === 'text' ? b : null
  }

  controller = new AbortController()
  try {
    await chatStream(appStore.currentSessionId, content, (ev) => {
      switch (ev.type) {
        case 'delta': {
          const b = lastText()
          if (b) b.content += ev.content
          else reply.blocks.push({ kind: 'text', content: ev.content })
          scrollBottom()
          break
        }
        case 'tool_call_start':
          reply.blocks.push({
            kind: 'tool', runId: ev.run_id, name: ev.name, args: ev.args_json,
            output: '', durationMs: 0, status: 'ok', running: true,
          })
          scrollBottom(true)
          break
        case 'tool_call_end': {
          const tb = reply.blocks.find((b) => b.kind === 'tool' && b.runId === ev.run_id && b.running)
          if (tb) {
            tb.output = ev.output_preview
            tb.durationMs = ev.duration_ms
            tb.status = ev.status
            tb.running = false
          }
          scrollBottom()
          break
        }
        case 'usage': reply.usage = ev; break
        case 'cancelled': reply.cancelled = true; break
        case 'error': reply.errorMsg = ev.message; break
      }
    }, controller.signal)
  } catch (e) {
    if (e.name !== 'AbortError') reply.errorMsg = '连接异常: ' + e.message
  } finally {
    reply.done = true // 结束生成中光标
    busy.value = false
    controller = null
    loadSessions() // 刷新侧栏排序
  }
}

onMounted(async () => {
  await Promise.all([loadHealth(), loadAgents()])
  await loadSessions()
  const first = appStore.sessions[0]
  if (first) selectSession(first)
})
</script>

<style scoped>
.chat-page { height: 100%; display: flex; }
.sidebar {
  width: 264px; background: #1e272e; color: #d2dae2;
  display: flex; flex-direction: column; flex-shrink: 0;
}
.brand-row { padding: 18px 18px 12px; }
.brand { color: #fff; font-size: 16px; font-weight: 700; }
.new-btn { margin: 0 16px 12px; width: auto; }
.session-list { flex: 1; overflow-y: auto; padding: 0 8px 12px; }
.session-item {
  padding: 10px 12px; border-radius: 8px; font-size: 13px; cursor: pointer;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 2px;
}
.session-item:hover { background: #2f3640; }
.session-item.active { background: #5b5bd6; color: #fff; }
.s-agent { color: #a29bfe; margin-right: 4px; font-size: 12px; }
.session-item.active .s-agent { color: #dcdcff; }
.empty { text-align: center; color: #636e72; font-size: 12px; padding: 24px 0; }
.meta { padding: 12px 16px; border-top: 1px solid #2f3640; }

.chat-main { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.chat-head {
  padding: 14px 24px; background: #fff; border-bottom: 1px solid var(--border);
  font-size: 15px; font-weight: 600; flex-shrink: 0;
}
.messages { flex: 1; overflow-y: auto; padding: 24px; }
.msg-col { max-width: 760px; margin: 0 auto; display: flex; flex-direction: column; gap: 16px; }
.empty-tip { margin: 80px auto 0; text-align: center; color: #b2bec3; line-height: 2.2; }

.input-bar {
  display: flex; gap: 10px; padding: 14px 24px; background: #fff;
  border-top: 1px solid var(--border); align-items: flex-end; flex-shrink: 0;
}
.input-bar :deep(.el-textarea__inner) { border-radius: 10px; }
.input-bar .el-button { height: 42px; padding: 0 24px; }
</style>
