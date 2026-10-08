<template>
  <div class="admin">
    <aside class="list-pane">
      <div class="list-toolbar">
        <el-button type="primary" size="small" @click="startCreate">＋ 新建配置</el-button>
      </div>
      <div class="items">
        <div
          v-for="l in llms" :key="l.config_id" class="item"
          :class="{ active: currentId === l.config_id }" @click="loadForm(l)"
        >
          <div class="t">
            {{ l.name }}
            <el-tag size="small" :type="l.status === 'enabled' ? 'success' : 'danger'" effect="plain">
              {{ l.status === 'enabled' ? '启用' : '停用' }}
            </el-tag>
          </div>
          <div class="d">{{ l.model_identifier }} · {{ l.api_key_masked }}</div>
        </div>
        <div v-if="!llms.length" class="empty">暂无配置</div>
      </div>
    </aside>

    <section class="form-pane">
      <template v-if="form">
        <h3>{{ currentId ? '编辑配置' : '新建 LLM 配置' }}</h3>
        <el-form label-position="top" class="form">
          <el-form-item label="配置名称"><el-input v-model="form.name" placeholder="如：fuyao-gw" /></el-form-item>
          <el-form-item label="Provider"><el-input v-model="form.provider" placeholder="openai_compatible" /></el-form-item>
          <el-form-item label="API Base URL">
            <el-input v-model="form.api_base_url" placeholder="https://xxx/v1（OpenAI 兼容协议）" />
          </el-form-item>
          <el-form-item label="Model">
            <el-input v-model="form.model_identifier" placeholder="如 gpt-4o-mini / fuyao-coding" />
          </el-form-item>
          <el-form-item :label="currentId ? `API Key（当前 ${currentMasked}，留空不修改）` : 'API Key'">
            <el-input v-model="form.api_key" type="password" show-password
                      :placeholder="currentId ? '不修改请留空' : 'sk-...'" />
          </el-form-item>
          <el-form-item label="每千 token 单价（元，选填）">
            <el-input-number v-model="form.price_per_1k_tokens" :step="0.0001" :min="0" style="width: 200px" />
          </el-form-item>
          <el-form-item label="状态">
            <el-radio-group v-model="form.status">
              <el-radio value="enabled">启用</el-radio>
              <el-radio value="disabled">停用</el-radio>
            </el-radio-group>
          </el-form-item>
          <div class="actions">
            <el-button v-if="currentId" type="danger" plain @click="remove">删除</el-button>
            <span style="flex: 1" />
            <el-button type="primary" @click="save">保存</el-button>
          </div>
        </el-form>
      </template>
      <div v-else class="placeholder">左侧选择或新建配置</div>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listLlms, createLlm, updateLlm, deleteLlm } from '@/api/llm'

const llms = ref([])
const currentId = ref('')
const form = ref(null)

const currentMasked = computed(() =>
  llms.value.find((x) => x.config_id === currentId.value)?.api_key_masked || '')

function startCreate() {
  currentId.value = ''
  form.value = {
    name: '', provider: 'openai_compatible', api_base_url: '', model_identifier: '',
    api_key: '', price_per_1k_tokens: 0, quota_limit: 0, status: 'enabled',
  }
}

function loadForm(l) {
  currentId.value = l.config_id
  form.value = {
    name: l.name, provider: l.provider, api_base_url: l.api_base_url,
    model_identifier: l.model_identifier, api_key: '',
    price_per_1k_tokens: l.price_per_1k_tokens, quota_limit: l.quota_limit, status: l.status,
  }
}

async function save() {
  if (!form.value.name.trim()) return ElMessage.warning('请填写配置名称')
  if (!currentId.value && !form.value.api_key) return ElMessage.warning('新建必须填写 API Key')
  const payload = { ...form.value, name: form.value.name.trim() }
  const saved = currentId.value
    ? await updateLlm(currentId.value, payload)
    : await createLlm(payload)
  llms.value = await listLlms()
  currentId.value = saved.config_id
  form.value.api_key = ''
  ElMessage.success('已保存')
}

async function remove() {
  await ElMessageBox.confirm('确认删除该配置？（绑定它的 Agent 将回退全局配置）', '删除', { type: 'warning' })
  await deleteLlm(currentId.value)
  currentId.value = ''
  form.value = null
  llms.value = await listLlms()
  ElMessage.success('已删除')
}

onMounted(async () => {
  llms.value = await listLlms()
  if (llms.value.length) loadForm(llms.value[0])
  else startCreate()
})
</script>

<style scoped>
.admin { display: flex; height: 100%; }
.list-pane { width: 340px; border-right: 1px solid var(--border); background: #fff; display: flex; flex-direction: column; }
.list-toolbar { padding: 12px 16px; border-bottom: 1px solid var(--border); }
.items { flex: 1; overflow-y: auto; }
.item { padding: 12px 16px; cursor: pointer; border-bottom: 1px solid #f1f2f6; }
.item:hover { background: #f5f6fa; }
.item.active { background: var(--primary-light); }
.item .t { font-size: 14px; font-weight: 600; display: flex; align-items: center; gap: 8px; }
.item .d { font-size: 12px; color: var(--text-sub); margin-top: 3px; }
.empty { text-align: center; color: #b2bec3; font-size: 13px; padding: 32px 0; }
.form-pane { flex: 1; padding: 24px 32px; overflow-y: auto; }
.form-pane h3 { margin: 0 0 16px; font-size: 16px; }
.form { max-width: 560px; }
.actions { display: flex; gap: 10px; margin-top: 8px; }
.placeholder { color: #b2bec3; text-align: center; margin-top: 120px; }
</style>
