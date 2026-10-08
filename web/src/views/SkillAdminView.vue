<template>
  <div class="admin">
    <aside class="list-pane">
      <div class="list-toolbar">
        <el-button type="primary" size="small" @click="uploadVisible = true">⬆ 上传技能</el-button>
      </div>
      <div class="items">
        <div
          v-for="s in skills" :key="s.skill_id" class="item"
          :class="{ active: currentId === s.skill_id }" @click="loadDetail(s.skill_id)"
        >
          <div class="t">{{ s.name }} <el-tag size="small" effect="plain">v{{ s.latest_version }}</el-tag></div>
          <div class="d">{{ s.description }}</div>
          <div class="d tags">#{{ s.tags.join(' #') }}</div>
        </div>
        <div v-if="!skills.length" class="empty">暂无技能</div>
      </div>
    </aside>

    <section class="form-pane">
      <template v-if="detail">
        <h3>
          {{ detail.name }}
          <el-tag type="primary" effect="plain" style="margin-left: 8px">v{{ detail.latest_version }}</el-tag>
        </h3>
        <p class="desc">{{ detail.description }}</p>
        <p class="tags">标签：{{ detail.tags.join('、') || '无' }}</p>

        <div class="sec-title">版本历史</div>
        <div v-for="v in detail.versions" :key="v.version" class="version-row">
          <span class="v-no">v{{ v.version }}</span>
          <span class="v-files">{{ v.files.join('、') }}</span>
          <el-button size="small" @click="viewVersion(v.version)">查看</el-button>
        </div>

        <div class="actions">
          <span style="flex: 1" />
          <el-button type="danger" plain @click="remove">删除技能</el-button>
        </div>
      </template>
      <div v-else class="placeholder">左侧选择技能，或上传新技能</div>
    </section>

    <!-- 上传弹层 -->
    <el-dialog v-model="uploadVisible" title="上传技能（SKILL.md + 附属文件）" width="440px">
      <div class="upload-hint">可多选，必须含 SKILL.md；同名技能将自动创建新版本</div>
      <input type="file" multiple ref="fileInput" />
      <template #footer>
        <el-button @click="uploadVisible = false">取消</el-button>
        <el-button type="primary" @click="doUpload">上传</el-button>
      </template>
    </el-dialog>

    <!-- 版本查看弹层 -->
    <el-dialog v-model="viewVisible" :title="viewTitle" width="640px">
      <pre class="version-pre">{{ viewBody }}</pre>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listSkills, getSkill, getSkillVersion, uploadSkill, deleteSkill } from '@/api/skill'

const skills = ref([])
const currentId = ref('')
const detail = ref(null)
const uploadVisible = ref(false)
const fileInput = ref(null)
const viewVisible = ref(false)
const viewTitle = ref('')
const viewBody = ref('')

async function refresh() {
  skills.value = await listSkills()
}

async function loadDetail(id) {
  currentId.value = id
  detail.value = await getSkill(id)
}

async function doUpload() {
  const files = fileInput.value?.files
  if (!files?.length) return ElMessage.warning('请选择文件')
  const fd = new FormData()
  for (const f of files) fd.append('files', f)
  const r = await uploadSkill(fd)
  uploadVisible.value = false
  ElMessage.success(`已上传 ${r.name} v${r.latest_version}`)
  fileInput.value.value = ''
  await refresh()
  await loadDetail(r.skill_id)
}

async function viewVersion(v) {
  const c = await getSkillVersion(currentId.value, v)
  viewTitle.value = `${c.name} · v${v}`
  viewBody.value =
    `---\nname: ${c.name}\ndescription: ${c.description}\ntags: [${c.tags.join(', ')}]\n---\n\n` + c.body
  viewVisible.value = true
}

async function remove() {
  await ElMessageBox.confirm('确认删除该技能的全部版本？（将同时解除所有 Agent 的绑定）', '删除', { type: 'warning' })
  await deleteSkill(currentId.value)
  currentId.value = ''
  detail.value = null
  await refresh()
  ElMessage.success('已删除')
}

onMounted(refresh)
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
.item .d.tags { color: #a29bfe; }
.empty { text-align: center; color: #b2bec3; font-size: 13px; padding: 32px 0; }
.form-pane { flex: 1; padding: 24px 32px; overflow-y: auto; }
.form-pane h3 { margin: 0 0 10px; font-size: 16px; display: flex; align-items: center; }
.desc { color: #636e72; font-size: 13px; max-width: 640px; }
.tags { color: #b2bec3; font-size: 12px; }
.sec-title { font-size: 13px; color: var(--text-sub); margin: 20px 0 8px; }
.version-row {
  display: flex; align-items: center; gap: 12px; padding: 8px 0;
  border-bottom: 1px solid #f1f2f6; font-size: 13px; max-width: 640px;
}
.v-no { color: var(--primary); font-weight: 600; width: 36px; }
.v-files { flex: 1; color: var(--text-sub); }
.actions { display: flex; gap: 10px; margin-top: 24px; max-width: 640px; }
.placeholder { color: #b2bec3; text-align: center; margin-top: 120px; }
.upload-hint { font-size: 12px; color: var(--text-sub); margin-bottom: 10px; }
.version-pre {
  background: #f5f6fa; border: 1px solid var(--border); border-radius: 8px;
  padding: 12px; font-size: 12px; max-height: 55vh; overflow: auto;
  white-space: pre-wrap; word-break: break-word; margin: 0;
}
</style>
