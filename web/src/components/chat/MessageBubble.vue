<template>
  <div class="bubble-row" :class="message.role">
    <!-- 用户气泡 -->
    <div v-if="message.role === 'user'" class="bubble user-bubble">
      {{ message.blocks[0]?.content }}
    </div>

    <!-- assistant 卡片 -->
    <div v-else class="assistant-card">
      <template v-for="(b, i) in message.blocks" :key="i">
        <ToolCallCard v-if="b.kind === 'tool'" :block="b" />
        <MarkdownContent v-else-if="b.content" :content="b.content" class="assistant-text" />
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
import ToolCallCard from './ToolCallCard.vue'
import MarkdownContent from './MarkdownContent.vue'

defineProps({ message: { type: Object, required: true } })
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
</style>
