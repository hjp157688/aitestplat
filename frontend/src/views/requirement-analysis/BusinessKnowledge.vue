<template>
  <div class="business-knowledge">
    <!-- 页头 -->
    <div class="page-header">
      <h1>{{ $t('businessKnowledge.title') }}</h1>
      <p>{{ $t('businessKnowledge.subtitle') }}</p>
    </div>

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

    <!-- 分类索引 -->
    <nav class="category-filter">
      <div class="category-filter__chips">
        <button
          v-for="cat in taxonomy"
          :key="cat.value || 'all'"
          type="button"
          class="filter-chip"
          :class="{ 'is-active': entryFilter.category === cat.value, 'is-dim': cat.count === 0 && entryFilter.category !== cat.value }"
          @click="selectCategory(cat.value)"
        >
          <span class="filter-chip__glyph" :class="'cat-' + (cat.value || 'all')">{{ cat.glyph }}</span>
          <span class="filter-chip__name">{{ cat.label }}</span>
          <span class="filter-chip__count">{{ cat.count }}</span>
        </button>
      </div>
    </nav>

    <el-tabs v-model="activeTab">
      <!-- 知识文档 -->
      <el-tab-pane :label="$t('businessKnowledge.documentsTab')" name="documents">
        <div class="section-header">
          <h2>{{ $t('businessKnowledge.documents') }}</h2>
          <button class="btn btn--primary" type="button" @click="showUploadDialog = true">
            {{ $t('businessKnowledge.uploadDocument') }}
          </button>
        </div>

        <div class="cards-grid">
          <article v-for="doc in documents" :key="doc.id" class="card doc-card">
            <div class="card__stamp" :class="'ext-' + docExt(doc.name)">{{ docExt(doc.name) }}</div>
            <div class="card__main">
              <div class="card__top">
                <h3 class="card__name" :title="doc.name">{{ doc.name }}</h3>
                <div class="card__tags">
                  <span class="tag tag--level" :class="doc.knowledge_level">{{ levelLabel(doc.knowledge_level) }}</span>
                  <span class="tag tag--status" :class="['is-' + (doc.status || 'uploaded')]">
                    <i class="status-dot" aria-hidden="true"></i>{{ doc.status_display || doc.status }}
                  </span>
                </div>
              </div>

              <dl class="ledger">
                <div v-if="doc.project_name" class="ledger__row">
                  <dt>{{ $t('businessKnowledge.project') }}</dt>
                  <dd>{{ doc.project_name }}</dd>
                </div>
                <div class="ledger__row">
                  <dt>{{ $t('businessKnowledge.chunks') }}</dt>
                  <dd>{{ doc.chunk_count }}</dd>
                </div>
                <div class="ledger__row">
                  <dt>{{ $t('businessKnowledge.entryCount') }}</dt>
                  <dd>{{ doc.entry_count }}</dd>
                </div>
                <div v-if="doc.error_message" class="ledger__row">
                  <dt class="is-err">{{ $t('businessKnowledge.error') }}</dt>
                  <dd class="is-err">{{ doc.error_message }}</dd>
                </div>
              </dl>

              <div class="card__actions">
                <button
                  v-if="doc.status === 'uploaded'"
                  type="button"
                  class="btn btn--primary btn--sm"
                  @click="processDocument(doc.id)"
                >{{ $t('businessKnowledge.process') }}</button>
                <button
                  v-if="doc.status === 'ready'"
                  type="button"
                  class="btn btn--primary btn--sm"
                  @click="extractEntries(doc.id)"
                >{{ $t('businessKnowledge.llmExtract') }}</button>
                <button type="button" class="btn btn--ghost btn--sm btn--danger" @click="deleteDocument(doc.id)">
                  {{ $t('businessKnowledge.delete') }}
                </button>
              </div>
            </div>
          </article>

          <div v-if="documents.length === 0" class="empty-state">
            <h4 class="empty-state__title">{{ $t('businessKnowledge.emptyDocsTitle') }}</h4>
            <p class="empty-state__body">{{ $t('businessKnowledge.emptyDocsBody') }}</p>
            <button type="button" class="btn btn--primary" @click="showUploadDialog = true">
              {{ $t('businessKnowledge.uploadDocument') }}
            </button>
          </div>
        </div>
      </el-tab-pane>

      <!-- 知识条目 -->
      <el-tab-pane :label="$t('businessKnowledge.entriesTab')" name="entries">
        <div class="section-header">
          <h2>{{ $t('businessKnowledge.entries') }}</h2>
          <button class="btn btn--primary" type="button" @click="openEntryForm()">
            {{ $t('businessKnowledge.createEntry') }}
          </button>
        </div>

        <div class="cards-grid">
          <article v-for="entry in filteredEntries" :key="entry.id" class="card entry-card">
            <div class="card__stamp" :class="'cat-' + (entry.category || 'other')">{{ entryGlyph(entry.category) }}</div>
            <div class="card__main">
              <div class="card__top">
                <h3 class="card__name" :title="entry.name">{{ entry.name }}</h3>
                <div class="card__tags">
                  <span class="tag tag--cat" :class="'cat-' + (entry.category || 'other')">
                    {{ entry.category_display || (entry.category ? $t('businessKnowledge.category' + entryCategoryKey(entry.category)) : $t('businessKnowledge.categoryOther')) }}
                  </span>
                  <span class="tag tag--source" :class="entry.source || 'manual'">{{ sourceLabel(entry.source) }}</span>
                </div>
              </div>

              <blockquote class="entry-quote">{{ entry.content }}</blockquote>

              <div class="entry-provenance">
                <span v-if="entry.source_document_name" class="prov prov--doc">《{{ entry.source_document_name }}》</span>
                <span class="prov">{{ levelLabel(entry.knowledge_level) }}</span>
              </div>

              <div class="card__actions">
                <button type="button" class="btn btn--ghost btn--sm" @click="openEntryForm(entry)">
                  {{ $t('businessKnowledge.edit') }}
                </button>
                <button type="button" class="btn btn--ghost btn--sm btn--danger" @click="deleteEntry(entry.id)">
                  {{ $t('businessKnowledge.delete') }}
                </button>
              </div>
            </div>
          </article>

          <div v-if="filteredEntries.length === 0" class="empty-state">
            <h4 class="empty-state__title">{{ $t('businessKnowledge.emptyEntriesTitle') }}</h4>
            <p class="empty-state__body">{{ $t('businessKnowledge.emptyEntriesBody') }}</p>
            <button type="button" class="btn btn--primary" @click="openEntryForm()">
              {{ $t('businessKnowledge.createEntry') }}
            </button>
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- 上传文档弹窗 -->
    <div v-if="showUploadDialog" class="modal-overlay" @click.self="showUploadDialog = false">
      <div class="modal">
        <div class="modal-header">
          <h3>{{ $t('businessKnowledge.uploadDocument') }}</h3>
          <button class="close-btn" type="button" aria-label="Close" @click="showUploadDialog = false">×</button>
        </div>
        <div class="modal-body">
          <form @submit.prevent="uploadDocument">
            <div class="form-group">
              <label for="bk-doc-name">{{ $t('businessKnowledge.docName') }} <span class="required">*</span></label>
              <input id="bk-doc-name" v-model="uploadForm.name" type="text" class="form-input" required>
            </div>
            <div class="form-group">
              <label for="bk-doc-file">{{ $t('businessKnowledge.selectFile') }} <span class="required">*</span></label>
              <input id="bk-doc-file" type="file" ref="fileInput" class="form-input form-input--file" @change="onFileSelected" accept=".pdf,.docx,.doc,.txt,.md,.xlsx">
            </div>
            <div class="form-group">
              <label for="bk-doc-level">{{ $t('businessKnowledge.knowledgeLevel') }}</label>
              <select id="bk-doc-level" v-model="uploadForm.knowledge_level" class="form-input">
                <option value="global">{{ $t('businessKnowledge.global') }}</option>
                <option value="project">{{ $t('businessKnowledge.project') }}</option>
              </select>
            </div>
            <div v-if="uploadForm.knowledge_level === 'project'" class="form-group">
              <label for="bk-doc-project">{{ $t('businessKnowledge.project') }}</label>
              <select id="bk-doc-project" v-model="uploadForm.project" class="form-input">
                <option value="">{{ $t('businessKnowledge.selectProject') }}</option>
                <option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</option>
              </select>
            </div>
            <div class="modal-actions">
              <button type="button" class="btn btn--ghost" @click="showUploadDialog = false">
                {{ $t('businessKnowledge.cancel') }}
              </button>
              <button type="submit" class="btn btn--primary" :disabled="uploading">
                {{ uploading ? $t('businessKnowledge.uploading') : $t('businessKnowledge.upload') }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <!-- 创建/编辑条目弹窗 -->
    <div v-if="showEntryForm" class="modal-overlay" @click.self="showEntryForm = false">
      <div class="modal">
        <div class="modal-header">
          <h3>{{ editingEntry ? $t('businessKnowledge.editEntry') : $t('businessKnowledge.createEntryTitle') }}</h3>
          <button class="close-btn" type="button" aria-label="Close" @click="showEntryForm = false">×</button>
        </div>
        <div class="modal-body">
          <form @submit.prevent="saveEntry">
            <div class="form-group">
              <label for="bk-entry-name">{{ $t('businessKnowledge.entryName') }} <span class="required">*</span></label>
              <input id="bk-entry-name" v-model="entryForm.name" type="text" class="form-input" required>
            </div>
            <div class="form-group">
              <label for="bk-entry-cat">{{ $t('businessKnowledge.category') }}</label>
              <select id="bk-entry-cat" v-model="entryForm.category" class="form-input">
                <option value="module">{{ $t('businessKnowledge.categoryModule') }}</option>
                <option value="data_model">{{ $t('businessKnowledge.categoryDataModel') }}</option>
                <option value="interface">{{ $t('businessKnowledge.categoryInterface') }}</option>
                <option value="business_rule">{{ $t('businessKnowledge.categoryBusinessRule') }}</option>
                <option value="naming">{{ $t('businessKnowledge.categoryNaming') }}</option>
                <option value="constraint">{{ $t('businessKnowledge.categoryConstraint') }}</option>
                <option value="other">{{ $t('businessKnowledge.categoryOther') }}</option>
              </select>
            </div>
            <div class="form-group">
              <label for="bk-entry-content">{{ $t('businessKnowledge.content') }} <span class="required">*</span></label>
              <textarea id="bk-entry-content" v-model="entryForm.content" class="form-input form-textarea" rows="8" required></textarea>
            </div>
            <div class="form-group">
              <label for="bk-entry-level">{{ $t('businessKnowledge.knowledgeLevel') }}</label>
              <select id="bk-entry-level" v-model="entryForm.knowledge_level" class="form-input">
                <option value="global">{{ $t('businessKnowledge.global') }}</option>
                <option value="project">{{ $t('businessKnowledge.project') }}</option>
              </select>
            </div>
            <div v-if="entryForm.knowledge_level === 'project'" class="form-group">
              <label for="bk-entry-project">{{ $t('businessKnowledge.project') }}</label>
              <select id="bk-entry-project" v-model="entryForm.project" class="form-input">
                <option value="">{{ $t('businessKnowledge.selectProject') }}</option>
                <option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</option>
              </select>
            </div>
            <div class="modal-actions">
              <button type="button" class="btn btn--ghost" @click="showEntryForm = false">
                {{ $t('businessKnowledge.cancel') }}
              </button>
              <button type="submit" class="btn btn--primary" :disabled="saving">
                {{ saving ? $t('businessKnowledge.saving') : $t('businessKnowledge.save') }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import api from '@/utils/api'
import { ElMessage } from 'element-plus'
import {
  getKnowledgeDocuments, uploadKnowledgeDocument, deleteKnowledgeDocument,
  processKnowledgeDocument, extractKnowledgeEntries,
  getKnowledgeEntries, createKnowledgeEntry, updateKnowledgeEntry, deleteKnowledgeEntry
} from '@/api/requirement'

// 文档类型 → 印章代号
const EXT_GLYPH = {
  pdf: 'PDF', docx: 'DOC', doc: 'DOC', txt: 'TXT', md: 'MD',
  xlsx: 'XLS', xls: 'XLS', csv: 'CSV', json: 'JSON', yaml: 'YML', yml: 'YML'
}

// 条目分类定义（分类印章 / 标签）
const CATEGORY_DEFS = [
  { value: 'module', glyphKey: 'categoryGlyphModule', labelKey: 'categoryModule' },
  { value: 'data_model', glyphKey: 'categoryGlyphDataModel', labelKey: 'categoryDataModel' },
  { value: 'interface', glyphKey: 'categoryGlyphInterface', labelKey: 'categoryInterface' },
  { value: 'business_rule', glyphKey: 'categoryGlyphBusinessRule', labelKey: 'categoryBusinessRule' },
  { value: 'naming', glyphKey: 'categoryGlyphNaming', labelKey: 'categoryNaming' },
  { value: 'constraint', glyphKey: 'categoryGlyphConstraint', labelKey: 'categoryConstraint' },
  { value: 'other', glyphKey: 'categoryGlyphOther', labelKey: 'categoryOther' }
]

export default {
  name: 'BusinessKnowledge',
  data() {
    return {
      activeTab: 'documents',
      documents: [],
      entries: [],
      projects: [],
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
      selectedFile: null,
    }
  },

  computed: {
    filteredEntries() {
      if (!this.entryFilter.category) return this.entries
      return this.entries.filter(e => e.category === this.entryFilter.category)
    },

    stats() {
      const readyDocs = this.documents.filter(d => d.status === 'ready').length
      const llmEntries = this.entries.filter(e => e.source === 'llm_extract').length
      return {
        totalDocs: this.documents.length,
        readyDocs,
        totalEntries: this.entries.length,
        llmEntries,
      }
    },

    taxonomy() {
      const counts = {}
      this.entries.forEach(e => {
        const c = e.category || 'other'
        counts[c] = (counts[c] || 0) + 1
      })
      return [
        {
          value: '',
          glyph: this.$t('businessKnowledge.categoryGlyphAll'),
          label: this.$t('businessKnowledge.allCategories'),
          count: this.entries.length,
        },
        ...CATEGORY_DEFS.map(def => ({
          value: def.value,
          glyph: this.$t('businessKnowledge.' + def.glyphKey),
          label: this.$t('businessKnowledge.' + def.labelKey),
          count: counts[def.value] || 0,
        })),
      ]
    },
  },

  mounted() {
    this.loadDocuments()
    this.loadEntries()
    this.loadProjects()
  },

  methods: {
    selectCategory(value) {
      this.entryFilter.category = value
      if (value && this.activeTab !== 'entries') {
        this.activeTab = 'entries'
      }
    },

    levelLabel(level) {
      return level === 'project'
        ? this.$t('businessKnowledge.project')
        : this.$t('businessKnowledge.global')
    },

    sourceLabel(source) {
      return source === 'llm_extract'
        ? this.$t('businessKnowledge.llmExtracted')
        : this.$t('businessKnowledge.manual')
    },

    entryCategoryKey(category) {
      const def = CATEGORY_DEFS.find(d => d.value === category)
      return def ? def.labelKey.replace('category', '') : 'Other'
    },

    entryGlyph(category) {
      const def = CATEGORY_DEFS.find(d => d.value === category)
      return def ? this.$t('businessKnowledge.' + def.glyphKey) : this.$t('businessKnowledge.categoryGlyphOther')
    },

    docExt(name) {
      const m = (name || '').toLowerCase().match(/\.([a-z0-9]+)$/)
      if (!m) return 'FILE'
      return EXT_GLYPH[m[1]] || m[1].toUpperCase().slice(0, 3)
    },

    async loadDocuments() {
      try {
        const res = await getKnowledgeDocuments()
        this.documents = res.data.results || res.data || []
      } catch (e) {
        console.error('Failed to load documents:', e)
      }
    },

    async loadEntries() {
      try {
        const res = await getKnowledgeEntries()
        this.entries = res.data.results || res.data || []
      } catch (e) {
        console.error('Failed to load entries:', e)
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

    onFileSelected(e) {
      this.selectedFile = e.target.files[0]
    },

    async uploadDocument() {
      if (!this.selectedFile) {
        ElMessage.error(this.$t('businessKnowledge.selectFileRequired'))
        return
      }
      this.uploading = true
      try {
        const formData = new FormData()
        formData.append('name', this.uploadForm.name || this.selectedFile.name)
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
        this.loadDocuments()
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
      } catch (e) {
        ElMessage.error(this.$t('businessKnowledge.processFailed') + ': ' + (e.response?.data?.error || e.message))
      }
    },

    async extractEntries(id) {
      try {
        await extractKnowledgeEntries(id)
        ElMessage.success(this.$t('businessKnowledge.extractStarted'))
        this.loadDocuments()
        this.loadEntries()
      } catch (e) {
        ElMessage.error(this.$t('businessKnowledge.extractFailed') + ': ' + (e.response?.data?.error || e.message))
      }
    },

    async deleteDocument(id) {
      if (!confirm(this.$t('businessKnowledge.deleteConfirm'))) return
      try {
        await deleteKnowledgeDocument(id)
        ElMessage.success(this.$t('businessKnowledge.deleteSuccess'))
        this.loadDocuments()
      } catch (e) {
        ElMessage.error(this.$t('businessKnowledge.deleteFailed') + ': ' + (e.response?.data?.error || e.message))
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
      } catch (e) {
        ElMessage.error(this.$t('businessKnowledge.saveFailed') + ': ' + (e.response?.data?.error || e.message))
      } finally {
        this.saving = false
      }
    },

    async deleteEntry(id) {
      if (!confirm(this.$t('businessKnowledge.deleteConfirm'))) return
      try {
        await deleteKnowledgeEntry(id)
        ElMessage.success(this.$t('businessKnowledge.deleteSuccess'))
        this.loadEntries()
      } catch (e) {
        ElMessage.error(this.$t('businessKnowledge.deleteFailed') + ': ' + (e.response?.data?.error || e.message))
      }
    },
  }
}
</script>

<style scoped>
/* ── 设计令牌：使用全局 --aitest-* 令牌 ────────────── */
.business-knowledge {
  /* 保留仅本页使用的分类色（全局令牌中无对应项） */
  --purple: #7C3AED;
  --purple-tint: #F5F3FF;
  --cyan: #0891B2;
  --cyan-tint: #ECFEFF;
  --radius: 10px;

  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;
  font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Segoe UI', Roboto, sans-serif;
  color: var(--aitest-text-1);
}

/* ── 页头（与应用一致：居中标题+副标题） ────────────── */
.page-header {
  text-align: center;
  margin-bottom: 20px;
}
.page-header h1 {
  font-size: 1.6rem;
  font-weight: 700;
  color: var(--aitest-text-1);
  margin: 0 0 6px;
  letter-spacing: -0.01em;
}
.page-header p {
  color: var(--aitest-text-2);
  font-size: 0.95rem;
  margin: 0;
}

/* ── 语料总览：卡片式统计 ──────────────────────────── */
.overview-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.overview-stat {
  background: var(--aitest-surface);
  border: 1px solid var(--aitest-border);
  border-radius: var(--radius);
  padding: 14px 18px;
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
.overview-stat__num--go { color: var(--aitest-success); }
.overview-stat__label {
  font-size: 0.8rem;
  color: var(--aitest-text-2);
}

/* ── 分类索引：筛选切片 ────────────────────────────── */
.category-filter {
  margin-bottom: 4px;
}
.category-filter__chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.filter-chip {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 5px 12px 5px 6px;
  border: 1px solid var(--aitest-border);
  border-radius: 8px;
  background: var(--aitest-surface);
  cursor: pointer;
  font-family: inherit;
  font-size: 0.84rem;
  color: var(--aitest-text-2);
  transition: border-color 0.18s ease, background-color 0.18s ease, transform 0.18s ease;
}
.filter-chip:hover { border-color: var(--aitest-primary); transform: translateY(-1px); }
.filter-chip.is-active {
  border-color: var(--aitest-primary);
  background: var(--aitest-primary-subtle);
  color: var(--aitest-text-1);
}
.filter-chip.is-dim { opacity: 0.55; }

.filter-chip__glyph {
  width: 22px;
  height: 22px;
  border-radius: 5px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 0.72rem;
  font-weight: 700;
  color: var(--aitest-text-2);
  background: var(--aitest-surface-subtle);
}
.filter-chip.is-active .filter-chip__glyph { color: var(--aitest-primary); background: var(--aitest-surface); }
.filter-chip__name { font-weight: 500; }
.filter-chip__count {
  font-size: 0.74rem;
  color: var(--aitest-text-3);
}
.filter-chip.is-active .filter-chip__count { color: var(--aitest-primary); }

/* ── Tabs ───────────────────────────────────────────── */
.el-tabs :deep(.el-tabs__header) { margin-bottom: 14px; }
.el-tabs :deep(.el-tabs__item) { font-family: inherit; }

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}
.section-header h2 {
  margin: 0;
  color: var(--aitest-text-1);
  font-size: 1.1rem;
  font-weight: 700;
}

/* ── 卡片网格 ───────────────────────────────────────── */
.cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(440px, 1fr));
  gap: 14px;
}

.card {
  display: flex;
  gap: 14px;
  background: var(--aitest-surface);
  border: 1px solid var(--aitest-border);
  border-radius: var(--radius);
  padding: 18px;
  box-shadow: var(--aitest-shadow-sm);
  transition: box-shadow 0.2s ease, transform 0.2s ease, border-color 0.2s ease;
}
.card:hover {
  border-color: var(--aitest-border-strong);
  box-shadow: var(--aitest-shadow-md);
  transform: translateY(-1px);
}

/* 印章（分类 / 文件类型） */
.card__stamp {
  flex: 0 0 44px;
  width: 44px;
  height: 44px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: var(--aitest-text-2);
  background: var(--aitest-surface-subtle);
  border: 1px solid var(--aitest-border);
}

/* 分类印章色（与应用标签色一致） */
.card__stamp.cat-module { background: var(--aitest-success-bg); color: var(--aitest-success); border-color: #D1E8DA; }
.card__stamp.cat-data_model { background: var(--aitest-primary-subtle); color: var(--aitest-primary); border-color: #D7E3FA; }
.card__stamp.cat-interface { background: var(--aitest-warning-bg); color: var(--aitest-warning); border-color: #F0E2C6; }
.card__stamp.cat-business_rule { background: var(--aitest-danger-bg); color: var(--aitest-danger); border-color: #F4D4CE; }
.card__stamp.cat-naming { background: var(--purple-tint); color: var(--purple); border-color: #E2D9F1; }
.card__stamp.cat-constraint { background: var(--cyan-tint); color: var(--cyan); border-color: #CDE7ED; }
.card__stamp.cat-other { background: var(--aitest-canvas); color: var(--aitest-text-2); border-color: #E5E8ED; }

/* 文档印章按类型着色 */
.card__stamp.ext-PDF { background: var(--aitest-danger-bg); color: var(--aitest-danger); border-color: #F4D4CE; }
.card__stamp.ext-DOC { background: var(--aitest-primary-subtle); color: var(--aitest-primary); border-color: #D7E3FA; }
.card__stamp.ext-XLS { background: var(--aitest-success-bg); color: var(--aitest-success); border-color: #D1E8DA; }
.card__stamp.ext-TXT,
.card__stamp.ext-MD,
.card__stamp.ext-FILE { background: var(--aitest-canvas); color: var(--aitest-text-2); border-color: #E5E8ED; }

.card__main { flex: 1; min-width: 0; }

.card__top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 10px;
}

.card__name {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
  color: var(--aitest-text-1);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.4;
}

.card__tags { display: flex; gap: 6px; flex-wrap: wrap; flex-shrink: 0; }

.tag {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 9px;
  border-radius: 4px;
  font-size: 0.72rem;
  font-weight: 500;
}

.tag--level.global { background: var(--aitest-primary-subtle); color: var(--aitest-primary); }
.tag--level.project { background: var(--purple-tint); color: var(--purple); }

.tag--status.is-ready { background: var(--aitest-success-bg); color: var(--aitest-success); }
.tag--status.is-processing { background: var(--aitest-warning-bg); color: var(--aitest-warning); }
.tag--status.is-failed { background: var(--aitest-danger-bg); color: var(--aitest-danger); }
.tag--status.is-uploaded { background: var(--aitest-canvas); color: var(--aitest-text-2); }

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}
.tag--status.is-processing .status-dot {
  background: var(--aitest-warning);
  animation: dot-pulse 1.6s ease-in-out infinite;
}

.tag--cat.cat-module { background: var(--aitest-success-bg); color: var(--aitest-success); }
.tag--cat.cat-data_model { background: var(--aitest-primary-subtle); color: var(--aitest-primary); }
.tag--cat.cat-interface { background: var(--aitest-warning-bg); color: var(--aitest-warning); }
.tag--cat.cat-business_rule { background: var(--aitest-danger-bg); color: var(--aitest-danger); }
.tag--cat.cat-naming { background: var(--purple-tint); color: var(--purple); }
.tag--cat.cat-constraint { background: var(--cyan-tint); color: var(--cyan); }
.tag--cat.cat-other { background: var(--aitest-canvas); color: var(--aitest-text-2); }

.tag--source.llm_extract { background: var(--aitest-success-bg); color: var(--aitest-success); }
.tag--source.manual { background: var(--aitest-canvas); color: var(--aitest-text-2); }

/* 文档台账行 */
.ledger {
  margin: 0;
  display: grid;
  gap: 3px;
}
.ledger__row {
  display: flex;
  gap: 8px;
  font-size: 0.82rem;
}
.ledger__row dt {
  color: var(--aitest-text-3);
  min-width: 52px;
  font-weight: 500;
}
.ledger__row dd { margin: 0; color: var(--aitest-text-2); }
.ledger__row dt.is-err, .ledger__row dd.is-err { color: var(--aitest-danger); }

/* 条目引用块 */
.entry-quote {
  margin: 0 0 8px;
  padding: 2px 0 2px 12px;
  border-left: 3px solid var(--aitest-border-strong);
  color: var(--aitest-text-2);
  font-size: 0.88rem;
  line-height: 1.7;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.entry-provenance {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  font-size: 0.76rem;
  color: var(--aitest-text-3);
  margin-bottom: 8px;
}
.prov--doc { color: var(--aitest-text-2); }

/* 卡片操作 */
.card__actions {
  display: flex;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid var(--aitest-border);
}

/* ── 按钮 ───────────────────────────────────────────── */
.btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 9px 18px;
  border-radius: 6px;
  border: 1px solid transparent;
  font-family: inherit;
  font-size: 0.88rem;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.18s ease, border-color 0.18s ease, color 0.18s ease, transform 0.18s ease;
}
.btn--primary { background: var(--aitest-primary); color: var(--aitest-surface); }
.btn--primary:hover { background: var(--aitest-primary-hover); }
.btn--primary:disabled { background: var(--aitest-border-strong); cursor: not-allowed; }
.btn--ghost { background: var(--aitest-surface); border-color: var(--aitest-border); color: var(--aitest-text-2); }
.btn--ghost:hover { border-color: var(--aitest-border-strong); background: var(--aitest-canvas); color: var(--aitest-text-1); }
.btn--danger:hover { border-color: var(--aitest-danger); color: var(--aitest-danger); background: var(--aitest-danger-bg); }
.btn--sm { padding: 6px 14px; font-size: 0.8rem; }

/* ── 空状态 ─────────────────────────────────────────── */
.empty-state {
  grid-column: 1 / -1;
  text-align: center;
  padding: 56px 24px;
  background: var(--aitest-surface);
  border: 1px dashed var(--aitest-border-strong);
  border-radius: var(--radius);
}
.empty-state__title {
  margin: 0 0 8px;
  font-size: 1.05rem;
  color: var(--aitest-text-1);
}
.empty-state__body {
  margin: 0 0 20px;
  color: var(--aitest-text-2);
  font-size: 0.88rem;
}

/* ── 弹窗 ───────────────────────────────────────────── */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.5);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: var(--aitest-surface);
  border-radius: 14px;
  max-width: 600px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
  border: 1px solid var(--aitest-border);
  box-shadow: var(--aitest-shadow-lg);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid var(--aitest-border);
}
.modal-header h3 {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--aitest-text-1);
}

.close-btn {
  background: none;
  border: none;
  font-size: 1.3rem;
  cursor: pointer;
  color: var(--aitest-text-3);
  padding: 4px 8px;
  border-radius: 6px;
  line-height: 1;
  transition: all 0.15s;
}
.close-btn:hover { color: var(--aitest-text-1); background: var(--aitest-surface-subtle); }

.modal-body { padding: 24px; }

.form-group { margin-bottom: 16px; }
.form-group label {
  display: block;
  margin-bottom: 6px;
  font-weight: 600;
  color: var(--aitest-text-2);
  font-size: 0.85rem;
}

.form-input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--aitest-border);
  border-radius: 6px;
  font-size: 0.9rem;
  box-sizing: border-box;
  color: var(--aitest-text-1);
  background: var(--aitest-surface);
  font-family: inherit;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}
.form-input:focus {
  outline: none;
  border-color: var(--aitest-primary);
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
}
.form-input:focus-visible {
  outline: 2px solid var(--aitest-primary);
  outline-offset: 1px;
}
.form-textarea { resize: vertical; min-height: 120px; }
.form-input--file { background: var(--aitest-canvas); }

.required { color: var(--aitest-danger); }

.modal-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  margin-top: 24px;
}

/* ── 可访问性 & 动效 ────────────────────────────────── */
button:focus-visible {
  outline: 2px solid var(--aitest-primary);
  outline-offset: 2px;
}

@media (prefers-reduced-motion: no-preference) {
  .overview-stats, .category-filter, .card { animation: rise 0.4s ease-out both; }
  .overview-stats { animation-delay: 0.04s; }
  .category-filter { animation-delay: 0.08s; }
}

@keyframes rise {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes dot-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.35; transform: scale(0.75); }
}

@media (prefers-reduced-motion: reduce) {
  .card { animation: none; }
  .tag--status.is-processing .status-dot { animation: none; }
}

/* ── 响应式 ─────────────────────────────────────────── */
@media (max-width: 900px) {
  .overview-stats { grid-template-columns: repeat(2, 1fr); }
}

@media (max-width: 700px) {
  .business-knowledge { padding: 16px; }
  .cards-grid { grid-template-columns: 1fr; }
}
</style>
