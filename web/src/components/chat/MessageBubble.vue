<template>
  <div class="bubble-row" :class="message.role">
    <!-- 用户气泡 -->
    <div v-if="message.role === 'user'" class="bubble user-bubble">
      {{ message.blocks[0]?.content }}
    </div>

    <!-- assistant 卡片 -->
    <div v-else class="assistant-card">
      <!-- 首帧等待态：无任何块时显示"思考中"与计时 -->
      <div v-if="!message.blocks.length && !message.errorMsg && !message.cancelled" class="thinking-row">
        <span class="dot"></span><span class="dot"></span><span class="dot"></span>
        <span class="thinking-text">思考中<span v-if="waitSeconds > 0">… {{ waitSeconds }}s</span></span>
      </div>

      <template v-for="(b, i) in message.blocks" :key="i">
        <ToolCallCard v-if="b.kind === 'tool'" :block="b" />
        <MarkdownContent
          v-else-if="b.content"
          :content="b.content"
          class="assistant-text"
          :class="{ streaming: isStreaming && i === message.blocks.length - 1 && b.kind === 'text' }"
        />
      </template>

      <div v-if="message.usage" class="meta-row">
        tokens：输入 {{ message.usage.prompt_tokens }} / 输出 {{ message.usage.completion_tokens }} / 共 {{ message.usage.total_tokens }}
      </div>
      <div v-if="message.cancelled" class="meta-row warn">⚠ 已取消</div>
      <el-alert v-if="message.errorMsg" :title="message.errorMsg" type="error" :closable="false" class="err" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import ToolCallCard from './ToolCallCard.vue'
import MarkdownContent from './MarkdownContent.vue'

const props = defineProps({ message: { type: Object, required: true } })

// 是否仍在生成中：由父组件在流结束时置 done
const isStreaming = computed(() => !props.message.done)

// 等待首帧计时：从组件挂载到第一个块出现
const waitSeconds = ref(0)
let timer = null
watch(
  () => props.message.blocks.length,
  (n) => {
    if (n > 0 && timer) { clearInterval(timer); timer = null }
  },
  { immediate: true },
)
if (props.message.role === 'assistant') {
  timer = setInterval(() => { waitSeconds.value += 1 }, 1000)
}
onUnmounted(() => timer && clearInterval(timer))
</script>

<style scoped>
.bubble-row { display: flex; }
.bubble-row.user { justify-content: flex-end; }
.assistant-card {
  max-width: 92%;
  background: #fff; border: 1px solid var(--border);
  border-radius: 12px; border-top-left-radius: 4px;
  padding: 12px 16px; display: flex; flex-direction: column; gap: 8px;
}
.user-bubble {
  max-width: 78%; background: var(--primary); color: #fff;
  padding: 10px 14px; border-radius: 12px; border-top-right-radius: 4px;
  white-space: pre-wrap; line-height: 1.7;
}
.assistant-text { font-size: 14px; }
.assistant-text:first-child { margin-top: 0; }
.meta-row { font-size: 11px; color: #b2bec3; }
.meta-row.warn { color: #e17055; }
.err { margin-top: 4px; }

.thinking-row { display: flex; align-items: center; gap: 5px; }
.thinking-text { color: var(--text-sub); font-size: 13px; margin-left: 4px; }
.dot {
  width: 6px; height: 6px; border-radius: 50%; background: var(--primary);
  animation: bounce 1.2s infinite ease-in-out;
}
.dot:nth-child(2) { animation-delay: 0.15s; }
.dot:nth-child(3) { animation-delay: 0.3s; }
@keyframes bounce {
  0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
  30% { transform: translateY(-4px); opacity: 1; }
}

/* 流式生成中的尾部光标 */
.assistant-text.streaming :deep(> :last-child)::after {
  content: "▍";
  color: var(--primary);
  animation: blink 0.9s infinite;
  margin-left: 2px;
}
@keyframes blink { 50% { opacity: 0; } }
</style>
