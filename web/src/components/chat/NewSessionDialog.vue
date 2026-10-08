<template>
  <el-dialog v-model="visible" title="新建会话" width="400px">
    <div class="label">选择 Agent</div>
    <el-select v-model="agentId" style="width: 100%">
      <el-option label="默认助手（全局配置）" value="default" />
      <el-option v-for="a in appStore.agents" :key="a.agent_id" :label="`${a.name}（${a.llm_name || '全局回退'}）`" :value="a.agent_id" />
    </el-select>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" @click="create">创建</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { appStore } from '@/stores/app'
import { createSession } from '@/api/session'

const emit = defineEmits(['created', 'update:modelValue'])
const props = defineProps({ modelValue: Boolean })
const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})
const agentId = ref('default')

async function create() {
  const s = await createSession({
    title: '会话 ' + new Date().toLocaleString('zh-CN', { hour12: false }),
    agent_id: agentId.value,
  })
  visible.value = false
  ElMessage.success('会话已创建')
  emit('created', s)
}
</script>

<style scoped>
.label { font-size: 13px; color: var(--text-sub); margin-bottom: 6px; }
</style>
