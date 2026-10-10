<template>
  <div class="admin">
    <aside class="list-pane">
      <div class="list-toolbar">
        <el-button type="primary" size="small" @click="startCreate">＋ 新建 Agent</el-button>
      </div>
      <div class="items">
        <div
          v-for="a in agents" :key="a.agent_id" class="item"
          :class="{ active: currentId === a.agent_id }" @click="loadForm(a)"
        >
          <div class="t">{{ a.name }}</div>
          <div class="d">技能 {{ a.skill_names.length }} 个 · 知识库 {{ (a.kb_names || []).length }} 个 · 模型 {{ a.llm_name || '全局回退' }}</div>
        </div>
        <div v-if="!agents.length" class="empty">暂无 Agent</div>
      </div>
    </aside>

    <section class="form-pane">
      <template v-if="form">
        <h3>{{ currentId ? '编辑 Agent' : '新建 Agent' }}</h3>
        <el-form label-position="top" class="form">
          <el-form-item label="名称"><el-input v-model="form.name" placeholder="如：运维助手" /></el-form-item>
          <el-form-item label="描述"><el-input v-model="form.description" /></el-form-item>
          <el-form-item label="System Prompt">
            <el-input v-model="form.system_prompt" type="textarea" :rows="4" placeholder="留空则使用全局默认" />
          </el-form-item>
          <el-form-item label="绑定技能（对话中作为可调用工具）">
            <el-checkbox-group v-model="form.skill_ids" class="skill-checks">
              <el-checkbox v-for="s in skills" :key="s.skill_id" :value="s.skill_id">
                {{ s.name }} <span class="hint">{{ s.description.slice(0, 30) }}</span>
              </el-checkbox>
            </el-checkbox-group>
            <div v-if="!skills.length" class="hint">请先到 Skill 管理页上传技能</div>
          </el-form-item>
          <el-form-item label="挂载知识库（对话中可检索其中文档）">
            <el-checkbox-group v-model="form.kb_ids" class="skill-checks">
              <el-checkbox v-for="k in kbs" :key="k.kb_id" :value="k.kb_id">
                {{ k.name }} <span class="hint">{{ (k.description || '').slice(0, 30) || `${k.doc_count} 个文档` }}</span>
              </el-checkbox>
            </el-checkbox-group>
            <div v-if="!kbs.length" class="hint">请先到知识库页创建并上传文档</div>
          </el-form-item>
          <el-form-item label="绑定大模型">
            <el-select v-model="form.config_id" clearable placeholder="全局回退（.env 配置）" style="max-width: 400px">
              <el-option v-for="l in llms" :key="l.config_id" :label="`${l.name}（${l.model_identifier}）`" :value="l.config_id" />
            </el-select>
          </el-form-item>
          <div class="actions">
            <el-button v-if="currentId" type="danger" plain @click="remove">删除</el-button>
            <span style="flex: 1" />
            <el-button type="primary" @click="save">保存</el-button>
          </div>
        </el-form>
      </template>
      <div v-else class="placeholder">左侧选择或新建 Agent</div>
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listAgents, createAgent, updateAgent, deleteAgent } from '@/api/agent'
import { listSkills } from '@/api/skill'
import { listKbs } from '@/api/kb'
import { listLlms } from '@/api/llm'
import { appStore, loadAgents } from '@/stores/app'

const agents = ref([])
const skills = ref([])
const kbs = ref([])
const llms = ref([])
const currentId = ref('')
const form = ref(null)

async function refresh() {
  agents.value = await listAgents()
  appStore.agents = agents.value
}

function startCreate() {
  currentId.value = ''
  form.value = { name: '', description: '', system_prompt: '', skill_ids: [], kb_ids: [], config_id: null }
}

async function loadForm(a) {
  currentId.value = a.agent_id
  form.value = {
    name: a.name, description: a.description, system_prompt: a.system_prompt,
    skill_ids: [...a.skill_ids], kb_ids: [...(a.kb_ids || [])], config_id: a.config_id,
  }
}

async function save() {
  if (!form.value.name.trim()) return ElMessage.warning('请填写名称')
  const payload = { ...form.value, name: form.value.name.trim() }
  const saved = currentId.value
    ? await updateAgent(currentId.value, payload)
    : await createAgent(payload)
  await refresh()
  currentId.value = saved.agent_id
  ElMessage.success('已保存')
}

async function remove() {
  await ElMessageBox.confirm('确认删除该 Agent？（会话不受影响，仅回退全局配置）', '删除', { type: 'warning' })
  await deleteAgent(currentId.value)
  currentId.value = ''
  form.value = null
  await refresh()
  ElMessage.success('已删除')
}

onMounted(async () => {
  await refresh()
  skills.value = await listSkills()
  kbs.value = await listKbs()
  llms.value = await listLlms()
  if (agents.value.length) loadForm(agents.value[0])
  else startCreate()
})
</script>

<style scoped>
.admin { display: flex; height: 100%; }
.list-pane { width: 320px; border-right: 1px solid var(--border); background: #fff; display: flex; flex-direction: column; }
.list-toolbar { padding: 12px 16px; border-bottom: 1px solid var(--border); }
.items { flex: 1; overflow-y: auto; }
.item { padding: 12px 16px; cursor: pointer; border-bottom: 1px solid #f1f2f6; }
.item:hover { background: #f5f6fa; }
.item.active { background: var(--primary-light); }
.item .t { font-size: 14px; font-weight: 600; }
.item .d { font-size: 12px; color: var(--text-sub); margin-top: 3px; }
.empty { text-align: center; color: #b2bec3; font-size: 13px; padding: 32px 0; }
.form-pane { flex: 1; padding: 24px 32px; overflow-y: auto; }
.form-pane h3 { margin: 0 0 16px; font-size: 16px; }
.form { max-width: 640px; }
.skill-checks { display: flex; flex-direction: column; gap: 2px; }
.hint { color: #b2bec3; font-size: 12px; }
.actions { display: flex; gap: 10px; margin-top: 8px; }
.placeholder { color: #b2bec3; text-align: center; margin-top: 120px; }
</style>
