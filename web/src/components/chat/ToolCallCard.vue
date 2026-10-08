<template>
  <div class="tool-card" :class="{ error: block.status === 'error' }">
    <div class="tool-head" @click="open = !open">
      <span class="icon" :class="{ spinning: block.running }">⚙</span>
      <span class="name">{{ block.name }}</span>
      <span v-if="block.running" class="running">执行中…</span>
      <span v-else class="duration">{{ (block.durationMs / 1000).toFixed(1) }}s</span>
      <span v-if="block.status === 'error'" class="err-tag">失败</span>
      <el-icon class="chevron" :class="{ expanded: open }"><ArrowRight /></el-icon>
    </div>
    <el-collapse-transition>
      <div v-show="open" class="tool-body">
        <div class="sec-label">输入</div>
        <pre class="sec-content">{{ prettyArgs }}</pre>
        <template v-if="block.output">
          <div class="sec-label">输出</div>
          <pre class="sec-content out">{{ block.output }}</pre>
        </template>
      </div>
    </el-collapse-transition>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ArrowRight } from '@element-plus/icons-vue'

const props = defineProps({ block: { type: Object, required: true } })
const open = ref(false)
const prettyArgs = computed(() => {
  try {
    return JSON.stringify(JSON.parse(props.block.args), null, 2)
  } catch {
    return props.block.args || '(无)'
  }
})
</script>

<style scoped>
.tool-card {
  border: 1px solid var(--border); border-radius: 8px;
  background: #fafbfe; overflow: hidden; font-size: 13px;
}
.tool-card.error { border-color: #f5b7b1; }
.tool-head {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 12px; cursor: pointer; user-select: none;
}
.tool-head:hover { background: #f0f1f8; }
.icon { color: var(--primary); font-size: 14px; display: inline-block; }
.icon.spinning { animation: spin 1.2s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.name { font-weight: 600; color: var(--text-main); }
.running { color: var(--primary); font-size: 12px; }
.duration { color: var(--text-sub); font-size: 12px; }
.err-tag {
  color: #c0392b; background: #fdecea; font-size: 11px;
  padding: 1px 8px; border-radius: 8px;
}
.chevron { margin-left: auto; color: #b2bec3; transition: transform 0.2s; }
.chevron.expanded { transform: rotate(90deg); }
.tool-body { padding: 4px 12px 10px; border-top: 1px dashed var(--border); }
.sec-label { font-size: 11px; color: var(--text-sub); margin: 8px 0 4px; }
.sec-content {
  margin: 0; padding: 8px 10px; background: #fff;
  border: 1px solid var(--border); border-radius: 6px;
  font-size: 12px; max-height: 200px; overflow: auto;
  white-space: pre-wrap; word-break: break-word;
  font-family: Consolas, Monaco, monospace;
}
.sec-content.out { background: #f6f7fb; }
</style>
