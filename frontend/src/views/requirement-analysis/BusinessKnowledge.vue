<template>
  <div class="business-knowledge">
    <!-- 页头 -->
    <PageHeader :title="$t('businessKnowledge.title')" />

    <!-- 语料总览 -->
    <section class="overview-stats">
      <div class="overview-stat">
        <span class="overview-stat__num">{{ stats.totalDocs }}</span>
        <span class="overview-stat__label">{{ $t('businessKnowledge.documents') }}</span>
      </div>
      <div class="overview-stat">
        <span class="overview-stat__num overview-stat__num--go">{{ stats.readyDocs }}</span>
        <span class="overview-stat__label">{{ $t('businessKnowledge.statReady') }}</span>
      </div>
      <div class="overview-stat">
        <span class="overview-stat__num">{{ stats.totalEntries }}</span>
        <span class="overview-stat__label">{{ $t('businessKnowledge.entries') }}</span>
      </div>
      <div class="overview-stat">
        <span class="overview-stat__num">{{ stats.llmEntries }}</span>
        <span class="overview-stat__label">{{ $t('businessKnowledge.statLlmExtracted') }}</span>
      </div>
    </section>

    <el-tabs v-model="activeTab">
      <!-- 知识文档 -->
      <el-tab-pane :label="$t('businessKnowledge.documentsTab')" name="documents">
        <div class="section-toolbar">
          <div class="toolbar-left">
            <el-button :loading="documentsLoading" @click="loadDocuments">
              <el-icon><Refresh /></el-icon>
            </el-button>
          </div>
          <div class="toolbar-right">
            <el-button
              v-if="selectedDocs.length && !hasProcessingDoc"
              type="danger"
              :loading="deleting"
              @click="batchDeleteDocuments"
            >
              {{ $t('businessKnowledge.batchDeleteSelected', { count: selectedDocs.length }) }}
            </el-button>
            <el-button type="primary" @click="showUploadDialog = true">
              <el-icon><Plus /></el-icon>
              {{ $t('businessKnowledge.uploadDocument') }}
            </el-button>
          </div>
        </div>

        <el-table
          :data="documents"
          v-loading="documentsLoading"
          @selection-change="handleDocSelectionChange"
          style="width: 100%"
        >
          <el-table-column type="selection" width="45" :selectable="docSelectable" />
          <el-table-column
            prop="name"
            :label="$t('businessKnowledge.docName')"
            min-width="240"
            show-overflow-tooltip
          >
            <template #default="{ row }">
              <div class="doc-name-cell">
                <el-tag size="small" effect="plain" :type="fileTypeTag(row.file_type)" class="doc-type-tag">
                  {{ (row.file_type || 'file').toUpperCase() }}
                </el-tag>
                <span class="doc-name-cell__text">{{ row.name }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column
            prop="project_name"
            :label="$t('businessKnowledge.project')"
            width="130"
            show-overflow-tooltip
          >
            <template #default="{ row }">{{ row.project_name || '-' }}</template>
          </el-table-column>
          <el-table-column
            :label="$t('businessKnowledge.knowledgeLevel')"
            width="100"
            align="center"
          >
            <template #default="{ row }">
              <el-tag size="small" :type="levelTagType(row.knowledge_level)">
                {{ levelLabel(row.knowledge_level) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            :label="$t('businessKnowledge.status')"
            width="110"
            align="center"
          >
            <template #default="{ row }">
              <el-tag
                size="small"
                :type="statusTagType(row.status)"
                :class="{ 'is-loading-tag': row.status === 'processing' }"
                :title="row.status === 'failed' ? row.error_message : ''"
              >
                {{ statusLabel(row) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="chunk_count" :label="$t('businessKnowledge.chunks')" width="80" align="center" />
          <el-table-column prop="entry_count" :label="$t('businessKnowledge.entryCount')" width="80" align="center" />
          <el-table-column
            :label="$t('businessKnowledge.createdAt')"
            width="160"
          >
            <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column
            :label="$t('businessKnowledge.actions')"
            width="170"
            fixed="right"
          >
            <template #default="{ row }">
              <el-tooltip
                v-if="row.status === 'processing'"
                :content="$t('businessKnowledge.processPending')"
                placement="top"
              >
                <span class="actions-placeholder">{{ $t('businessKnowledge.process') }}…</span>
              </el-tooltip>
              <el-button
                v-else-if="row.status === 'uploaded' || row.status === 'failed'"
                type="primary"
                link
                size="small"
                @click="processDocument(row.id)"
              >{{ $t('businessKnowledge.process') }}</el-button>
              <template v-else-if="row.status === 'ready'">
                <el-button type="primary" link size="small" @click="extractEntries(row)">
                  {{ $t('businessKnowledge.refine') }}
                </el-button>
                <el-button type="primary" link size="small" @click="openChunksDialog(row)">
                  {{ $t('businessKnowledge.edit') }}
                </el-button>
              </template>
              <el-button type="danger" link size="small" @click="deleteDocument(row)">
                {{ $t('businessKnowledge.delete') }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="pagination-wrapper">
          <el-pagination
            v-model:current-page="docPage"
            v-model:page-size="docPageSize"
            :total="docTotal"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next, jumper"
            @change="loadDocuments"
          />
        </div>
      </el-tab-pane>

      <!-- 知识条目 -->
      <el-tab-pane :label="$t('businessKnowledge.entriesTab')" name="entries">
        <div class="section-toolbar">
          <div class="toolbar-left">
            <el-select
              v-model="entryFilter.category"
              :placeholder="$t('businessKnowledge.allCategories')"
              clearable
              style="width: 180px"
              @change="handleCategoryFilter"
            >
              <el-option
                v-for="cat in categoryOptions"
                :key="cat.value"
                :label="cat.label"
                :value="cat.value"
              />
            </el-select>
          </div>
          <div class="toolbar-right">
            <el-button
              v-if="selectedEntries.length"
              type="danger"
              :loading="deleting"
              @click="batchDeleteEntries"
            >
              {{ $t('businessKnowledge.batchDeleteSelected', { count: selectedEntries.length }) }}
            </el-button>
            <el-button type="primary" @click="openEntryForm()">
              <el-icon><Plus /></el-icon>
              {{ $t('businessKnowledge.createEntryTitle') }}
            </el-button>
          </div>
        </div>

        <el-table
          :data="entries"
          v-loading="entriesLoading"
          @selection-change="handleEntrySelectionChange"
          style="width: 100%"
        >
          <el-table-column type="selection" width="45" />
          <el-table-column
            prop="name"
            :label="$t('businessKnowledge.entryName')"
            min-width="180"
            show-overflow-tooltip
          />
          <el-table-column
            :label="$t('businessKnowledge.category')"
            width="110"
            align="center"
          >
            <template #default="{ row }">
              <el-tag size="small" :type="categoryTagType(row.category)">
                {{ entryCategoryLabel(row.category) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            prop="content"
            :label="$t('businessKnowledge.content')"
            min-width="280"
            show-overflow-tooltip
          >
            <template #default="{ row }">
              <span class="entry-content-cell">{{ row.content }}</span>
            </template>
          </el-table-column>
          <el-table-column
            :label="$t('businessKnowledge.source')"
            width="110"
            align="center"
          >
            <template #default="{ row }">
              <el-tag size="small" :type="sourceTagType(row.source)">
                {{ sourceLabel(row.source) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            :label="$t('businessKnowledge.knowledgeLevel')"
            width="100"
            align="center"
          >
            <template #default="{ row }">
              <el-tag size="small" :type="levelTagType(row.knowledge_level)">
                {{ levelLabel(row.knowledge_level) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            prop="source_document_name"
            :label="$t('businessKnowledge.sourceDocument')"
            width="160"
            show-overflow-tooltip
          >
            <template #default="{ row }">{{ row.source_document_name || '-' }}</template>
          </el-table-column>
          <el-table-column
            :label="$t('businessKnowledge.actions')"
            width="130"
            fixed="right"
          >
            <template #default="{ row }">
              <el-button type="primary" link size="small" @click="openEntryForm(row)">
                {{ $t('businessKnowledge.edit') }}
              </el-button>
              <el-button type="danger" link size="small" @click="deleteEntry(row)">
                {{ $t('businessKnowledge.delete') }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <div class="pagination-wrapper">
          <el-pagination
            v-model:current-page="entryPage"
            v-model:page-size="entryPageSize"
            :total="entryTotal"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next, jumper"
            @change="loadEntries"
          />
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 上传文档弹窗 -->
    <el-dialog
      v-model="showUploadDialog"
      :title="$t('businessKnowledge.uploadDocument')"
      width="560px"
      :close-on-click-modal="false"
    >
      <el-alert
        v-if="!tokenizerConfigured"
        type="warning"
        :closable="false"
        show-icon
        class="config-alert"
      >
        <template #default>
          <strong>{{ $t('businessKnowledge.tokenizerNotConfiguredTitle') }}</strong>
          <p>{{ $t('businessKnowledge.tokenizerNotConfiguredBody') }}</p>
          <el-button type="warning" size="small" plain @click="goConfigure">
            {{ $t('businessKnowledge.goConfigure') }}
          </el-button>
        </template>
      </el-alert>
      <el-form :model="uploadForm" label-width="96px" @submit.prevent>
        <el-form-item :label="$t('businessKnowledge.docName')" required>
          <el-input v-model="uploadForm.name" :placeholder="$t('businessKnowledge.docName')" />
        </el-form-item>
        <el-form-item :label="$t('businessKnowledge.selectFile')" required>
          <el-input :model-value="selectedFileName" :placeholder="$t('businessKnowledge.selectFile')" disabled>
            <template #append>
              <el-button @click="triggerFilePick">{{ $t('businessKnowledge.selectFile') }}</el-button>
            </template>
          </el-input>
          <input ref="fileInput" type="file" class="hidden-file-input" :accept="acceptTypes" @change="onFileSelected" />
        </el-form-item>
        <el-form-item :label="$t('businessKnowledge.knowledgeLevel')">
          <el-select v-model="uploadForm.knowledge_level" :placeholder="$t('businessKnowledge.knowledgeLevel')" style="width: 100%">
            <el-option value="global" :label="$t('businessKnowledge.global')" />
            <el-option value="project" :label="$t('businessKnowledge.project')" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="uploadForm.knowledge_level === 'project'" :label="$t('businessKnowledge.project')">
          <el-select v-model="uploadForm.project" :placeholder="$t('businessKnowledge.selectProject')" style="width: 100%">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showUploadDialog = false">{{ $t('businessKnowledge.cancel') }}</el-button>
        <el-button type="primary" :loading="uploading" @click="uploadDocument">
          {{ uploading ? $t('businessKnowledge.uploading') : $t('businessKnowledge.upload') }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 创建/编辑条目弹窗 -->
    <el-dialog
      v-model="showEntryForm"
      :title="editingEntry ? $t('businessKnowledge.editEntry') : $t('businessKnowledge.createEntryTitle')"
      width="640px"
      :close-on-click-modal="false"
    >
      <el-form :model="entryForm" label-width="96px" @submit.prevent>
        <el-form-item :label="$t('businessKnowledge.entryName')" required>
          <el-input v-model="entryForm.name" :placeholder="$t('businessKnowledge.entryName')" />
        </el-form-item>
        <el-form-item :label="$t('businessKnowledge.category')">
          <el-select v-model="entryForm.category" :placeholder="$t('businessKnowledge.category')" style="width: 100%">
            <el-option
              v-for="cat in categoryOptions"
              :key="cat.value"
              :label="cat.label"
              :value="cat.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item :label="$t('businessKnowledge.content')" required>
          <el-input
            v-model="entryForm.content"
            type="textarea"
            :rows="6"
            :placeholder="$t('businessKnowledge.content')"
          />
        </el-form-item>
        <el-form-item :label="$t('businessKnowledge.knowledgeLevel')">
          <el-select v-model="entryForm.knowledge_level" :placeholder="$t('businessKnowledge.knowledgeLevel')" style="width: 100%">
            <el-option value="global" :label="$t('businessKnowledge.global')" />
            <el-option value="project" :label="$t('businessKnowledge.project')" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="entryForm.knowledge_level === 'project'" :label="$t('businessKnowledge.project')">
          <el-select v-model="entryForm.project" :placeholder="$t('businessKnowledge.selectProject')" style="width: 100%">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEntryForm = false">{{ $t('businessKnowledge.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="saveEntry">
          {{ saving ? $t('businessKnowledge.saving') : $t('businessKnowledge.save') }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 分块预览与编辑弹窗 -->
    <el-dialog
      v-model="showChunksDialog"
      :title="`${$t('businessKnowledge.viewChunks')} · ${currentChunkDoc?.name || ''}`"
      width="760px"
      :close-on-click-modal="false"
    >
      <div v-if="chunksLoading" class="chunks-state">{{ $t('businessKnowledge.chunksLoading') }}</div>
      <div v-else-if="chunks.length === 0" class="chunks-state">{{ $t('businessKnowledge.chunksEmpty') }}</div>
      <div v-else class="chunk-list">
        <div v-for="(chunk, idx) in chunks" :key="chunk.id" class="chunk-card">
          <div class="chunk-card__head">
            <span class="chunk-card__title">
              {{ $t('businessKnowledge.chunkSection') }}：{{ chunk.section_title || $t('businessKnowledge.chunkFullText') }}
            </span>
            <span class="chunk-card__idx">#{{ idx + 1 }} · {{ chunk.paragraph_index }}</span>
          </div>
          <el-input
            v-model="chunk.content"
            type="textarea"
            :rows="4"
            :disabled="chunk.saving"
            class="chunk-card__textarea"
          />
          <div class="chunk-card__foot">
            <span class="chunk-card__len">{{ chunk.content.length }} {{ $t('businessKnowledge.chunkChars') }}</span>
            <el-button type="primary" size="small" :loading="chunk.saving" @click="saveChunk(chunk)">
              {{ chunk.saving ? $t('businessKnowledge.savingChunk') : $t('businessKnowledge.saveChunk') }}
            </el-button>
          </div>
        </div>
      </div>
    </el-dialog>

    <!-- LLM 提取进度弹窗 -->
    <el-dialog
      v-model="showExtractProgress"
      :title="`${$t('businessKnowledge.extractingTitle')} · ${extractDocName}`"
      width="480px"
      :close-on-click-modal="false"
      @close="closeExtractProgress"
    >
      <div class="extract-progress">
        <el-progress :percentage="extractProgress" :stroke-width="10" />
        <div class="extract-progress__msg">{{ extractMessage }}</div>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import { ElMessage, ElMessageBox } from 'element-plus'
import PageHeader from '@/components/common/PageHeader.vue'
import {
  getKnowledgeDocuments, getKnowledgeStats, uploadKnowledgeDocument, deleteKnowledgeDocument, batchDeleteKnowledgeDocuments,
  processKnowledgeDocument, extractKnowledgeEntries, getKnowledgeDocumentChunks,
  updateKnowledgeDocumentChunk,
  getKnowledgeEntries, createKnowledgeEntry, updateKnowledgeEntry, deleteKnowledgeEntry,
  batchDeleteKnowledgeEntries, getKnowledgeConfigStatus
} from '@/api/requirement'
import api from '@/utils/api'

// 条目分类定义
const CATEGORY_DEFS = [
  { value: 'module', labelKey: 'categoryModule' },
  { value: 'data_model', labelKey: 'categoryDataModel' },
  { value: 'interface', labelKey: 'categoryInterface' },
  { value: 'business_rule', labelKey: 'categoryBusinessRule' },
  { value: 'naming', labelKey: 'categoryNaming' },
  { value: 'constraint', labelKey: 'categoryConstraint' },
  { value: 'other', labelKey: 'categoryOther' }
]

const ACCEPT_TYPES = '.pdf,.docx,.doc,.txt,.md,.xlsx'

export default {
  name: 'BusinessKnowledge',
  components: { PageHeader },
  data() {
    return {
      activeTab: 'documents',
      documents: [],
      entries: [],
      projects: [],
      documentsLoading: false,
      entriesLoading: false,
      deleting: false,
      docPage: 1,
      docPageSize: 10,
      docTotal: 0,
      entryPage: 1,
      entryPageSize: 10,
      entryTotal: 0,
      showUploadDialog: false,
      showEntryForm: false,
      uploading: false,
      saving: false,
      editingEntry: null,
      uploadForm: {
        name: '',
        knowledge_level: 'global',
        project: '',
      },
      entryForm: {
        name: '',
        content: '',
        category: 'business_rule',
        knowledge_level: 'global',
        project: '',
      },
      entryFilter: {
        category: '',
      },
      tokenizerConfigured: true,
      tokenizerModelName: '',
      showChunksDialog: false,
      chunksLoading: false,
      currentChunkDoc: null,
      chunks: [],
      showExtractProgress: false,
      extractProgress: 0,
      extractMessage: '',
      extractDocName: '',
      selectedDocs: [],
      selectedEntries: [],
      selectedFile: null,
      pollTimer: null,   // 文档分块/向量化状态轮询定时器
      entryTimer: null,  // LLM 提取进度轮询定时器
      stats: {
        totalDocs: 0,
        readyDocs: 0,
        totalEntries: 0,
        llmEntries: 0,
      },
    }
  },

  computed: {
    selectedFileName() {
      return this.selectedFile ? this.selectedFile.name : ''
    },

    acceptTypes() {
      return ACCEPT_TYPES
    },

    hasProcessingDoc() {
      return this.documents.some(d => d.status === 'processing')
    },

    categoryOptions() {
      return CATEGORY_DEFS.map(def => ({
        value: def.value,
        label: this.$t('businessKnowledge.' + def.labelKey),
      }))
    },
  },

  mounted() {
    this.loadStats()
    this.loadDocuments()
    this.loadEntries()
    this.loadProjects()
    this.loadConfigStatus()
  },

  unmounted() {
    this.stopDocumentPolling()
    this.stopEntryPolling()
  },

  methods: {
    async loadStats() {
      try {
        const res = await getKnowledgeStats()
        const data = res.data || {}
        this.stats = {
          totalDocs: data.total_documents || 0,
          readyDocs: data.ready_documents || 0,
          totalEntries: data.total_entries || 0,
          llmEntries: data.llm_entries || 0,
        }
      } catch (e) {
        console.error('Failed to load knowledge stats:', e)
      }
    },

    async loadConfigStatus() {
      try {
        const res = await getKnowledgeConfigStatus()
        const data = res.data || {}
        this.tokenizerConfigured = !!data.tokenizer_configured
        this.tokenizerModelName = data.model_name || ''
      } catch (e) {
        console.error('Failed to load knowledge config status:', e)
      }
    },

    goConfigure() {
      this.showUploadDialog = false
      this.$router.push('/configuration/ai-model')
    },

    async loadDocuments() {
      this.documentsLoading = true
      try {
        const res = await getKnowledgeDocuments({
          page: this.docPage,
          page_size: this.docPageSize,
        })
        this.documents = res.data.results || res.data || []
        this.docTotal = res.data.count || this.documents.length
      } catch (e) {
        ElMessage.error(e.response?.data?.error || this.$t('businessKnowledge.loadFailed'))
      } finally {
        this.documentsLoading = false
      }
    },

    async loadEntries() {
      this.entriesLoading = true
      try {
        const params = { page: this.entryPage, page_size: this.entryPageSize }
        if (this.entryFilter.category) params.category = this.entryFilter.category
        const res = await getKnowledgeEntries(params)
        this.entries = res.data.results || res.data || []
        this.entryTotal = res.data.count || this.entries.length
      } catch (e) {
        ElMessage.error(e.response?.data?.error || this.$t('businessKnowledge.loadFailed'))
      } finally {
        this.entriesLoading = false
      }
    },

    async loadProjects() {
      try {
        const res = await api.get('/projects/')
        this.projects = res.data.results || res.data || []
      } catch (e) {
        console.error('Failed to load projects:', e)
      }
    },

    handleCategoryFilter() {
      this.entryPage = 1
      this.loadEntries()
    },

    handleDocSelectionChange(selection) {
      this.selectedDocs = selection.map(d => d.id)
    },

    handleEntrySelectionChange(selection) {
      this.selectedEntries = selection.map(e => e.id)
    },

    docSelectable(row) {
      return row.status !== 'processing'
    },

    levelLabel(level) {
      return level === 'project'
        ? this.$t('businessKnowledge.project')
        : this.$t('businessKnowledge.global')
    },

    levelTagType(level) {
      return level === 'project' ? 'warning' : 'info'
    },

    sourceLabel(source) {
      return source === 'llm_extract'
        ? this.$t('businessKnowledge.llmExtracted')
        : this.$t('businessKnowledge.manual')
    },

    sourceTagType(source) {
      return source === 'llm_extract' ? 'success' : 'info'
    },

    statusLabel(row) {
      const map = {
        uploaded: this.$t('businessKnowledge.statusUploaded'),
        processing: this.$t('businessKnowledge.statusProcessing'),
        ready: this.$t('businessKnowledge.statusReady'),
        failed: this.$t('businessKnowledge.statusFailed'),
      }
      return map[row.status] || row.status_display || row.status || '-'
    },

    statusTagType(status) {
      const map = { uploaded: 'info', processing: 'warning', ready: 'primary', failed: 'danger' }
      return map[status] || 'info'
    },

    categoryTagType(category) {
      const map = {
        module: 'success',
        data_model: '',
        interface: 'warning',
        business_rule: 'danger',
        naming: 'info',
        constraint: 'info',
        other: 'info',
      }
      return map[category] ?? 'info'
    },

    entryCategoryLabel(category) {
      const def = CATEGORY_DEFS.find(d => d.value === category)
      return def
        ? this.$t('businessKnowledge.' + def.labelKey)
        : this.$t('businessKnowledge.categoryOther')
    },

    fileTypeTag(fileType) {
      const map = { pdf: 'danger', docx: '', doc: '', xlsx: 'success', xls: 'success' }
      return map[fileType] ?? 'info'
    },

    formatDateTime(dateStr) {
      if (!dateStr) return '-'
      const d = new Date(dateStr)
      const pad = (n) => String(n).padStart(2, '0')
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
    },

    triggerFilePick() {
      // $refs 在 JS + checkJs 下类型为 unknown，显式收窄（与 RequirementAnalysisView 一致）
      const fileInput = /** @type {HTMLInputElement | undefined} */ (this.$refs.fileInput)
      if (fileInput) fileInput.click()
    },

    onFileSelected(e) {
      this.selectedFile = e.target.files[0]
    },

    async uploadDocument() {
      if (!this.uploadForm.name.trim()) {
        ElMessage.warning(this.$t('businessKnowledge.docNameRequired'))
        return
      }
      if (!this.selectedFile) {
        ElMessage.error(this.$t('businessKnowledge.selectFileRequired'))
        return
      }
      if (!this.tokenizerConfigured) {
        ElMessage.warning(this.$t('businessKnowledge.tokenizerBlocked'))
        return
      }
      this.uploading = true
      try {
        const formData = new FormData()
        formData.append('name', this.uploadForm.name)
        formData.append('file', this.selectedFile)
        formData.append('knowledge_level', this.uploadForm.knowledge_level)
        if (this.uploadForm.knowledge_level === 'project' && this.uploadForm.project) {
          formData.append('project', this.uploadForm.project)
        }
        await uploadKnowledgeDocument(formData)
        ElMessage.success(this.$t('businessKnowledge.uploadSuccess'))
        this.showUploadDialog = false
        this.uploadForm = { name: '', knowledge_level: 'global', project: '' }
        this.selectedFile = null
        this.docPage = 1
        this.loadDocuments()
        this.loadStats()
      } catch (e) {
        ElMessage.error(this.$t('businessKnowledge.uploadFailed') + ': ' + (e.response?.data?.error || e.message))
      } finally {
        this.uploading = false
      }
    },

    async processDocument(id) {
      try {
        await processKnowledgeDocument(id)
        ElMessage.success(this.$t('businessKnowledge.processStarted'))
        this.loadDocuments()
        this.pollDocumentStatus(id)
      } catch (e) {
        ElMessage.error(this.$t('businessKnowledge.processFailed') + ': ' + (e.response?.data?.error || e.message))
      }
    },

    // 后端分块/向量化在线程中异步执行，轮询状态直到完成
    // 列表为分页加载，直接按 id 拉取单条文档状态
    async refreshSingleDocument(id) {
      try {
        const res = await api.get(`/requirement-analysis/knowledge-documents/${id}/`)
        this.updateDocumentRow(res.data)
        this.loadStats()
        return res.data
      } catch (e) {
        return null
      }
    },

    updateDocumentRow(doc) {
      const i = this.documents.findIndex(d => d.id === doc.id)
      if (i >= 0) this.documents.splice(i, 1, doc)
    },

    pollDocumentStatus(id) {
      this.stopDocumentPolling()
      let ticks = 0
      this.pollTimer = setInterval(async () => {
        ticks += 1
        const doc = await this.refreshSingleDocument(id)
        if (!doc) {
          this.stopDocumentPolling()
          return
        }
        if (doc.status === 'ready') {
          this.stopDocumentPolling()
          ElMessage.success(this.$t('businessKnowledge.processCompleted'))
          return
        }
        if (doc.status === 'failed') {
          this.stopDocumentPolling()
          ElMessage.error(this.$t('businessKnowledge.processFailed') + ': ' + (doc.error_message || ''))
          return
        }
        // 超时保护 ~90s，避免无限轮询
        if (ticks >= 45) {
          this.stopDocumentPolling()
        }
      }, 2000)
    },

    stopDocumentPolling() {
      if (this.pollTimer) {
        clearInterval(this.pollTimer)
        this.pollTimer = null
      }
    },

    async extractEntries(row) {
      const id = row.id
      if (row.is_extracting) {
        ElMessage.warning(this.$t('businessKnowledge.extractingInProgress'))
        return
      }
      try {
        await extractKnowledgeEntries(id)
        this.extractDocName = row.name || ''
        this.extractProgress = 0
        this.extractMessage = this.$t('businessKnowledge.extractStarted')
        this.showExtractProgress = true
        ElMessage.success(this.$t('businessKnowledge.extractStarted'))
        this.loadDocuments()
        this.pollExtractProgress(id)
      } catch (e) {
        ElMessage.error(this.$t('businessKnowledge.extractFailed') + ': ' + (e.response?.data?.error || e.message))
      }
    },

    // LLM 提取进度轮询：驱动进度条
    pollExtractProgress(id) {
      this.stopEntryPolling()
      let ticks = 0
      this.entryTimer = setInterval(async () => {
        ticks += 1
        const doc = await this.refreshSingleDocument(id)
        await this.loadEntries()
        if (!doc) {
          this.stopEntryPolling()
          this.showExtractProgress = false
          return
        }
        this.extractProgress = doc.extract_progress || 0
        this.extractMessage = doc.extract_message || ''
        if (!doc.is_extracting) {
          this.stopEntryPolling()
          this.showExtractProgress = false
          if (doc.entry_count > 0) {
            ElMessage.success(this.$t('businessKnowledge.extractCompleted'))
          } else if (doc.error_message) {
            ElMessage.error(this.$t('businessKnowledge.extractFailed') + ': ' + (doc.error_message || ''))
          } else {
            ElMessage.info(this.$t('businessKnowledge.extractEmpty'))
          }
          return
        }
        // 超时保护 ~6 分钟（多章节/大模型耗时较长）
        if (ticks >= 240) {
          this.stopEntryPolling()
          this.showExtractProgress = false
        }
      }, 1500)
    },

    closeExtractProgress() {
      this.stopEntryPolling()
      this.showExtractProgress = false
    },

    stopEntryPolling() {
      if (this.entryTimer) {
        clearInterval(this.entryTimer)
        this.entryTimer = null
      }
    },

    async openChunksDialog(doc) {
      this.currentChunkDoc = doc
      this.chunks = []
      this.showChunksDialog = true
      this.chunksLoading = true
      try {
        const res = await getKnowledgeDocumentChunks(doc.id)
        this.chunks = (res.data.results || []).map(c => ({ ...c, original: c.content, saving: false }))
      } catch (e) {
        ElMessage.error(this.$t('businessKnowledge.chunksLoadFailed') + ': ' + (e.response?.data?.error || e.message))
      } finally {
        this.chunksLoading = false
      }
    },

    async saveChunk(chunk) {
      if (!chunk.content || !chunk.content.trim()) {
        ElMessage.warning(this.$t('businessKnowledge.chunkContentRequired'))
        return
      }
      chunk.saving = true
      try {
        await updateKnowledgeDocumentChunk(this.currentChunkDoc.id, {
          chunk_id: chunk.id,
          content: chunk.content,
        })
        chunk.original = chunk.content
        ElMessage.success(this.$t('businessKnowledge.chunkSaved'))
      } catch (e) {
        chunk.content = chunk.original
        ElMessage.error(this.$t('businessKnowledge.chunkSaveFailed') + ': ' + (e.response?.data?.error || e.message))
      } finally {
        chunk.saving = false
      }
    },

    async deleteDocument(row) {
      try {
        await ElMessageBox.confirm(
          this.$t('businessKnowledge.deleteConfirmDoc', { name: row.name }),
          this.$t('businessKnowledge.delete'),
          { type: 'warning', confirmButtonText: this.$t('businessKnowledge.delete'), cancelButtonText: this.$t('businessKnowledge.cancel') }
        )
        await deleteKnowledgeDocument(row.id)
        ElMessage.success(this.$t('businessKnowledge.deleteSuccess'))
        this.loadDocuments()
        this.loadStats()
      } catch (e) {
        if (e !== 'cancel') {
          ElMessage.error(this.$t('businessKnowledge.deleteFailed') + ': ' + (e.response?.data?.error || e.message))
        }
      }
    },

    openEntryForm(entry = null) {
      if (entry) {
        this.editingEntry = entry
        this.entryForm = {
          name: entry.name,
          content: entry.content,
          category: entry.category,
          knowledge_level: entry.knowledge_level,
          project: entry.project || '',
        }
      } else {
        this.editingEntry = null
        this.entryForm = {
          name: '', content: '', category: 'business_rule',
          knowledge_level: 'global', project: '',
        }
      }
      this.showEntryForm = true
    },

    async saveEntry() {
      if (!this.entryForm.name.trim()) {
        ElMessage.warning(this.$t('businessKnowledge.entryNameRequired'))
        return
      }
      if (!this.entryForm.content.trim()) {
        ElMessage.warning(this.$t('businessKnowledge.contentRequired'))
        return
      }
      this.saving = true
      try {
        const data = {
          name: this.entryForm.name,
          content: this.entryForm.content,
          category: this.entryForm.category,
          knowledge_level: this.entryForm.knowledge_level,
          project: this.entryForm.knowledge_level === 'project' ? this.entryForm.project : null,
        }
        if (this.editingEntry) {
          await updateKnowledgeEntry(this.editingEntry.id, data)
          ElMessage.success(this.$t('businessKnowledge.updateSuccess'))
        } else {
          await createKnowledgeEntry(data)
          ElMessage.success(this.$t('businessKnowledge.createSuccess'))
        }
        this.showEntryForm = false
        this.loadEntries()
        this.loadStats()
      } catch (e) {
        ElMessage.error(this.$t('businessKnowledge.saveFailed') + ': ' + (e.response?.data?.error || e.message))
      } finally {
        this.saving = false
      }
    },

    async deleteEntry(row) {
      try {
        await ElMessageBox.confirm(
          this.$t('businessKnowledge.deleteConfirmEntry', { name: row.name }),
          this.$t('businessKnowledge.delete'),
          { type: 'warning', confirmButtonText: this.$t('businessKnowledge.delete'), cancelButtonText: this.$t('businessKnowledge.cancel') }
        )
        await deleteKnowledgeEntry(row.id)
        ElMessage.success(this.$t('businessKnowledge.deleteSuccess'))
        this.loadEntries()
        this.loadStats()
      } catch (e) {
        if (e !== 'cancel') {
          ElMessage.error(this.$t('businessKnowledge.deleteFailed') + ': ' + (e.response?.data?.error || e.message))
        }
      }
    },

    async batchDeleteDocuments() {
      if (!this.selectedDocs.length) return
      try {
        await ElMessageBox.confirm(
          this.$t('businessKnowledge.batchDeleteConfirmDocs', { count: this.selectedDocs.length }),
          this.$t('businessKnowledge.delete'),
          { type: 'warning', confirmButtonText: this.$t('businessKnowledge.delete'), cancelButtonText: this.$t('businessKnowledge.cancel') }
        )
        this.deleting = true
        await batchDeleteKnowledgeDocuments([...this.selectedDocs])
        ElMessage.success(this.$t('businessKnowledge.deleteSuccess'))
        this.selectedDocs = []
        this.loadDocuments()
        this.loadStats()
      } catch (e) {
        if (e !== 'cancel') {
          ElMessage.error(this.$t('businessKnowledge.deleteFailed') + ': ' + (e.response?.data?.error || e.message))
        }
      } finally {
        this.deleting = false
      }
    },

    async batchDeleteEntries() {
      if (!this.selectedEntries.length) return
      try {
        await ElMessageBox.confirm(
          this.$t('businessKnowledge.batchDeleteConfirmEntries', { count: this.selectedEntries.length }),
          this.$t('businessKnowledge.delete'),
          { type: 'warning', confirmButtonText: this.$t('businessKnowledge.delete'), cancelButtonText: this.$t('businessKnowledge.cancel') }
        )
        this.deleting = true
        await batchDeleteKnowledgeEntries([...this.selectedEntries])
        ElMessage.success(this.$t('businessKnowledge.deleteSuccess'))
        this.selectedEntries = []
        this.loadEntries()
        this.loadStats()
      } catch (e) {
        if (e !== 'cancel') {
          ElMessage.error(this.$t('businessKnowledge.deleteFailed') + ': ' + (e.response?.data?.error || e.message))
        }
      } finally {
        this.deleting = false
      }
    },
  }
}
</script>

<style scoped>
.business-knowledge {
  padding: 28px var(--aitest-space-6);
  max-width: 1400px;
  margin: 0 auto;
  font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Segoe UI', Roboto, sans-serif;
  color: var(--aitest-text-1);
}

/* ── 语料总览：卡片式统计 ──────────────────────────── */
.overview-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--aitest-space-3);
  margin-bottom: var(--aitest-space-4);
}

.overview-stat {
  background: var(--aitest-surface);
  border: 1px solid var(--aitest-border);
  border-radius: var(--aitest-radius);
  padding: var(--aitest-space-4) var(--aitest-space-5);
  display: flex;
  flex-direction: column;
  gap: 2px;
  box-shadow: var(--aitest-shadow-xs);
}
.overview-stat__num {
  font-size: 1.55rem;
  font-weight: 700;
  color: var(--aitest-text-1);
  line-height: 1.2;
}
.overview-stat__num--go { color: var(--aitest-primary); }
.overview-stat__label {
  font-size: 0.8rem;
  color: var(--aitest-text-2);
}

/* ── Tabs ───────────────────────────────────────────── */
.el-tabs :deep(.el-tabs__header) { margin-bottom: var(--aitest-space-4); }
.el-tabs :deep(.el-tabs__item) { font-family: inherit; }

/* ── 表格操作栏（与其他页面一致） ───────────────────── */
.section-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--aitest-space-4);
  flex-wrap: wrap;
  gap: var(--aitest-space-3);
}
.toolbar-left {
  display: flex;
  align-items: center;
  gap: var(--aitest-space-3);
  flex-wrap: wrap;
}
.toolbar-right {
  display: flex;
  align-items: center;
  gap: var(--aitest-space-2);
}

.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: var(--aitest-space-4);
}

/* 文档名单元格：类型标签 + 名称 */
.doc-name-cell {
  display: flex;
  align-items: center;
  gap: var(--aitest-space-2);
  min-width: 0;
}
.doc-name-cell__text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.doc-type-tag {
  flex-shrink: 0;
  font-family: var(--aitest-font-mono);
  letter-spacing: 0.02em;
}

.entry-content-cell {
  display: block;
  color: var(--aitest-text-2);
}

/* 处理中状态的标签脉冲动效 */
.is-loading-tag {
  animation: dot-pulse 1.6s ease-in-out infinite;
}

/* 处理中占位文本 */
.actions-placeholder {
  font-size: 0.86rem;
  color: var(--aitest-text-3);
  margin-right: var(--aitest-space-2);
}

/* ── 未配置分词模型警告条 ─────────────────────────── */
.config-alert :deep(.el-alert__content) {
  flex: 1;
  min-width: 0;
}
.config-alert strong {
  display: block;
  color: var(--aitest-text-1);
  font-size: 0.9rem;
  margin-bottom: var(--aitest-space-1);
}
.config-alert p {
  margin: 0 0 var(--aitest-space-3);
  color: var(--aitest-text-2);
  font-size: 0.84rem;
  line-height: 1.6;
}

.hidden-file-input {
  display: none;
}

/* ── 分块预览与编辑 ─────────────────────────────── */
.chunks-state {
  padding: var(--aitest-space-10) var(--aitest-space-6);
  text-align: center;
  color: var(--aitest-text-2);
  font-size: 0.9rem;
}
.chunk-list {
  display: flex;
  flex-direction: column;
  gap: var(--aitest-space-4);
}
.chunk-card {
  border: 1px solid var(--aitest-border);
  border-radius: var(--aitest-radius-lg);
  padding: var(--aitest-space-4);
  background: var(--aitest-surface);
}
.chunk-card__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--aitest-space-3);
  flex-wrap: wrap;
  margin-bottom: var(--aitest-space-3);
}
.chunk-card__title {
  font-weight: 600;
  font-size: 0.88rem;
  color: var(--aitest-text-1);
}
.chunk-card__idx {
  font-size: 0.76rem;
  color: var(--aitest-text-3);
}
.chunk-card__foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--aitest-space-3);
  margin-top: var(--aitest-space-2);
}
.chunk-card__len {
  font-size: 0.76rem;
  color: var(--aitest-text-3);
}

/* ── LLM 提取进度 ─────────────────────────────── */
.extract-progress__msg {
  margin-top: var(--aitest-space-3);
  font-size: 0.85rem;
  color: var(--aitest-text-2);
  text-align: center;
}

@keyframes dot-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.45; }
}

@media (prefers-reduced-motion: reduce) {
  .is-loading-tag { animation: none; }
}

/* ── 响应式 ─────────────────────────────────────────── */
@media (max-width: 900px) {
  .overview-stats { grid-template-columns: repeat(2, 1fr); }
}

@media (max-width: 700px) {
  .business-knowledge { padding: var(--aitest-space-4); }
}
</style>
