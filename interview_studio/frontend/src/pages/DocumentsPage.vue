<script setup>
import { onMounted, ref } from 'vue'
import AppLayout from '../layouts/AppLayout.vue'
import LoadingState from '../components/LoadingState.vue'
import { api, unwrap } from '../api/client'
import { notify } from '../utils/notify'
const MAX_SIZE = 10 * 1024 * 1024
const ACCEPTED = ['.pdf', '.docx', '.txt', '.md', '.markdown', '.csv', '.json']
const documents = ref([]), file = ref(null), title = ref(''), type = ref('OTHER'), uploading = ref(false), loading = ref(true), loadError = ref(''), busyId = ref(null)
async function load() {
  loading.value = true; loadError.value = ''
  try { documents.value = unwrap(await api.get('/candidate/documents')) || [] }
  catch { loadError.value = '문서 목록을 불러오지 못했습니다.' }
  finally { loading.value = false }
}
function chooseFile(event) {
  const selected = event.target.files?.[0]
  if (!selected) return
  const extension = `.${selected.name.split('.').pop()?.toLowerCase()}`
  if (!ACCEPTED.includes(extension)) { event.target.value = ''; file.value = null; return notify('지원하지 않는 파일 형식입니다.', 'error') }
  if (selected.size > MAX_SIZE) { event.target.value = ''; file.value = null; return notify('파일은 10MB 이하여야 합니다.', 'error') }
  file.value = selected
}
async function upload() {
  if (!file.value || uploading.value) return notify('업로드할 파일을 선택해 주세요.', 'error')
  const form = new FormData(); form.append('file', file.value); if (title.value.trim()) form.append('title', title.value.trim()); form.append('document_type', type.value)
  uploading.value = true
  try { await api.post('/candidate/documents', form); notify('문서를 처리했습니다.'); file.value = null; title.value = ''; type.value = 'OTHER'; await load() }
  finally { uploading.value = false }
}
async function reprocess(id) { if (busyId.value) return; busyId.value=id; try { await api.post(`/candidate/documents/${id}/reprocess`); notify('문서를 다시 처리했습니다.'); await load() } finally { busyId.value=null } }
async function remove(id) { if (busyId.value || !confirm('문서를 삭제할까요?')) return; busyId.value=id; try { await api.delete(`/candidate/documents/${id}`); notify('문서를 삭제했습니다.'); await load() } finally { busyId.value=null } }
onMounted(load)
</script>
<template>
  <AppLayout title="AI가 참고할 나의 문서">
    <section class="upload-zone card"><div><span class="upload-icon">⇧</span><div><p class="eyebrow">PERSONAL KNOWLEDGE</p><h2>이력서와 포트폴리오를 추가하세요.</h2><p>PDF, DOCX, TXT, Markdown, CSV, JSON · 최대 10MB</p></div></div>
      <div class="upload-form"><label><span class="sr-only">문서 제목</span><input v-model="title" :disabled="uploading" placeholder="문서 제목 (선택)"></label><label><span class="sr-only">문서 유형</span><select v-model="type" :disabled="uploading"><option>OTHER</option><option>RESUME</option><option>COVER_LETTER</option><option>PORTFOLIO</option><option>PROJECT_REPORT</option></select></label><label class="file-button"><input type="file" :disabled="uploading" accept=".pdf,.docx,.txt,.md,.markdown,.csv,.json" @change="chooseFile"><span>{{ file?.name || '파일 선택' }}</span></label><button class="button primary" :disabled="uploading || !file" @click="upload">{{ uploading ? '처리 중…' : '업로드' }}</button></div>
    </section>
    <LoadingState v-if="loading" />
    <section v-else-if="loadError" class="card empty-state" role="alert"><p>{{ loadError }}</p><button class="button primary" @click="load">다시 시도</button></section>
    <section v-else class="card"><div class="section-head"><div><p class="eyebrow">DOCUMENT LIBRARY</p><h2>내 문서 {{ documents.length }}개</h2></div></div>
      <div class="document-list"><article v-for="doc in documents" :key="doc.id"><span class="doc-icon">DOC</span><div><h3>{{ doc.title }}</h3><p>{{ doc.document_type }} · {{ doc.processing_status }}</p></div><span class="tag" :class="{success:doc.processing_status==='COMPLETED'}">{{ doc.processing_status }}</span><button class="text-button" :disabled="busyId === doc.id" @click="reprocess(doc.id)">재처리</button><button class="icon-button danger" :disabled="busyId === doc.id" aria-label="문서 삭제" @click="remove(doc.id)">×</button></article><div v-if="!documents.length" class="empty">업로드한 문서가 없습니다.</div></div>
    </section>
  </AppLayout>
</template>
