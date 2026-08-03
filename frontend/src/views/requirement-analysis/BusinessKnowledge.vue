<template>
  <div class="business-knowledge">
    <div class="page-header">
      <h1>{{ $t('businessKnowledge.title') }}</h1>
      <p>{{ $t('businessKnowledge.subtitle') }}</p>
    </div>

    <div class="main-content">
      <el-tabs v-model="activeTab" type="card">
        <!-- 知识文档 Tab -->
        <el-tab-pane :label="$t('businessKnowledge.documentsTab')" name="documents">
          <div class="section-header">
            <h2>{{ $t('businessKnowledge.documents') }}</h2>
            <button class="add-btn" @click="showUploadDialog = true">
              {{ $t('businessKnowledge.uploadDocument') }}
            </button>
          </div>

          <div class="cards-grid">
            <div v-for="doc in documents" :key="doc.id" class="card">
              <div class="card-header">
                <div class="card-title">
                  <span class="doc-icon">📄</span>
                  <h3>{{ doc.name }}</h3>
                </div>
                <div class="card-badges">
                  <span class="level-badge" :class="doc.knowledge_level">
                    {{ doc.knowledge_level === 'global' ? $t('businessKnowledge.global') : $t('businessKnowledge.project') }}
                  </span>
                  <span class="status-badge" :class="doc.status">
                    {{ doc.status_display || doc.status }}
                  </span>
                </div>
              </div>

              <div class="card-body">
                <div class="info-row" v-if="doc.project_name">
                  <label>{{ $t('businessKnowledge.project') }}</label>
                  <span>{{ doc.project_name }}</span>
                </div>
                <div class="info-row">
                  <label>{{ $t('businessKnowledge.chunks') }}</label>
                  <span>{{ doc.chunk_count }}</span>
                </div>
                <div class="info-row">
                  <label>{{ $t('businessKnowledge.entryCount') }}</label>
                  <span>{{ doc.entry_count }}</span>
                </div>
                <div class="info-row" v-if="doc.error_message">
                  <label class="error-label">{{ $t('businessKnowledge.error') }}</label>
                  <span class="error-text">{{ doc.error_message }}</span>
                </div>
              </div>

              <div class="card-actions">
                <button
                  v-if="doc.status === 'uploaded'"
                  class="action-btn process-btn"
                  @click="processDocument(doc.id)">
                  {{ $t('businessKnowledge.process') }}
                </button>
                <button
                  v-if="doc.status === 'ready'"
                  class="action-btn extract-btn"
                  @click="extractEntries(doc.id)">
                  {{ $t('businessKnowledge.llmExtract') }}
                </button>
                <button class="action-btn delete-btn" @click="deleteDocument(doc.id)">
                  {{ $t('businessKnowledge.delete') }}
                </button>
              </div>
            </div>

            <div v-if="documents.length === 0" class="empty-state">
              <p>{{ $t('businessKnowledge.noDocuments') }}</p>
            </div>
          </div>
        </el-tab-pane>

        <!-- 知识条目 Tab -->
        <el-tab-pane :label="$t('businessKnowledge.entriesTab')" name="entries">
          <div class="section-header">
            <h2>{{ $t('businessKnowledge.entries') }}</h2>
            <div class="header-actions">
              <select v-model="entryFilter.category" class="filter-select">
                <option value="">{{ $t('businessKnowledge.allCategories') }}</option>
                <option value="module">{{ $t('businessKnowledge.categoryModule') }}</option>
                <option value="data_model">{{ $t('businessKnowledge.categoryDataModel') }}</option>
                <option value="interface">{{ $t('businessKnowledge.categoryInterface') }}</option>
                <option value="business_rule">{{ $t('businessKnowledge.categoryBusinessRule') }}</option>
                <option value="naming">{{ $t('businessKnowledge.categoryNaming') }}</option>
                <option value="constraint">{{ $t('businessKnowledge.categoryConstraint') }}</option>
                <option value="other">{{ $t('businessKnowledge.categoryOther') }}</option>
              </select>
              <button class="add-btn" @click="openEntryForm()">
                {{ $t('businessKnowledge.createEntry') }}
              </button>
            </div>
          </div>

          <div class="cards-grid">
            <div v-for="entry in filteredEntries" :key="entry.id" class="card entry-card">
              <div class="card-header">
                <div class="card-title">
                  <span class="entry-icon">🏷</span>
                  <h3>{{ entry.name }}</h3>
                </div>
                <div class="card-badges">
                  <span class="category-badge" :class="entry.category">
                    {{ entry.category_display || entry.category }}
                  </span>
                  <span class="source-badge" :class="entry.source">
                    {{ entry.source === 'llm_extract' ? $t('businessKnowledge.llmExtracted') : $t('businessKnowledge.manual') }}
                  </span>
                </div>
              </div>

              <div class="card-body">
                <div class="entry-content">{{ entry.content }}</div>
                <div class="entry-meta" v-if="entry.source_document_name">
                  <label>{{ $t('businessKnowledge.sourceDocument') }}</label>
                  <span>{{ entry.source_document_name }}</span>
                </div>
              </div>

              <div class="card-actions">
                <button class="action-btn edit-btn" @click="openEntryForm(entry)">
                  {{ $t('businessKnowledge.edit') }}
                </button>
                <button class="action-btn delete-btn" @click="deleteEntry(entry.id)">
                  {{ $t('businessKnowledge.delete') }}
                </button>
              </div>
            </div>

            <div v-if="filteredEntries.length === 0" class="empty-state">
              <p>{{ $t('businessKnowledge.noEntries') }}</p>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </div>

    <!-- 上传文档弹窗 -->
    <div v-if="showUploadDialog" class="modal-overlay" @click.self="showUploadDialog = false">
      <div class="modal">
        <div class="modal-header">
          <h3>{{ $t('businessKnowledge.uploadDocument') }}</h3>
          <button class="close-btn" @click="showUploadDialog = false">×</button>
        </div>
        <div class="modal-body">
          <form @submit.prevent="uploadDocument">
            <div class="form-group">
              <label>{{ $t('businessKnowledge.docName') }} <span class="required">*</span></label>
              <input v-model="uploadForm.name" type="text" class="form-input" required>
            </div>
            <div class="form-group">
              <label>{{ $t('businessKnowledge.selectFile') }} <span class="required">*</span></label>
              <input type="file" ref="fileInput" @change="onFileSelected" accept=".pdf,.docx,.doc,.txt,.md,.xlsx">
            </div>
            <div class="form-group">
              <label>{{ $t('businessKnowledge.knowledgeLevel') }}</label>
              <select v-model="uploadForm.knowledge_level" class="form-select">
                <option value="global">{{ $t('businessKnowledge.global') }}</option>
                <option value="project">{{ $t('businessKnowledge.project') }}</option>
              </select>
            </div>
            <div class="form-group" v-if="uploadForm.knowledge_level === 'project'">
              <label>{{ $t('businessKnowledge.project') }}</label>
              <select v-model="uploadForm.project" class="form-select">
                <option value="">{{ $t('businessKnowledge.selectProject') }}</option>
                <option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</option>
              </select>
            </div>
            <div class="modal-actions">
              <button type="button" class="cancel-btn" @click="showUploadDialog = false">
                {{ $t('businessKnowledge.cancel') }}
              </button>
              <button type="submit" class="confirm-btn" :disabled="uploading">
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
          <button class="close-btn" @click="showEntryForm = false">×</button>
        </div>
        <div class="modal-body">
          <form @submit.prevent="saveEntry">
            <div class="form-group">
              <label>{{ $t('businessKnowledge.entryName') }} <span class="required">*</span></label>
              <input v-model="entryForm.name" type="text" class="form-input" required>
            </div>
            <div class="form-group">
              <label>{{ $t('businessKnowledge.category') }}</label>
              <select v-model="entryForm.category" class="form-select">
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
              <label>{{ $t('businessKnowledge.content') }} <span class="required">*</span></label>
              <textarea v-model="entryForm.content" class="form-textarea" rows="8" required></textarea>
            </div>
            <div class="form-group">
              <label>{{ $t('businessKnowledge.knowledgeLevel') }}</label>
              <select v-model="entryForm.knowledge_level" class="form-select">
                <option value="global">{{ $t('businessKnowledge.global') }}</option>
                <option value="project">{{ $t('businessKnowledge.project') }}</option>
              </select>
            </div>
            <div class="form-group" v-if="entryForm.knowledge_level === 'project'">
              <label>{{ $t('businessKnowledge.project') }}</label>
              <select v-model="entryForm.project" class="form-select">
                <option value="">{{ $t('businessKnowledge.selectProject') }}</option>
                <option v-for="p in projects" :key="p.id" :value="p.id">{{ p.name }}</option>
              </select>
            </div>
            <div class="modal-actions">
              <button type="button" class="cancel-btn" @click="showEntryForm = false">
                {{ $t('businessKnowledge.cancel') }}
              </button>
              <button type="submit" class="confirm-btn" :disabled="saving">
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
    }
  },

  mounted() {
    this.loadDocuments()
    this.loadEntries()
    this.loadProjects()
  },

  methods: {
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
.business-knowledge {
  padding: 28px 24px;
  max-width: 1400px;
  margin: 0 auto;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Inter', Roboto, sans-serif;
}

.page-header {
  text-align: center;
  margin-bottom: 32px;
}

.page-header h1 {
  font-size: 1.75rem;
  font-weight: 700;
  color: #0F172A;
  margin-bottom: 6px;
  letter-spacing: -0.02em;
}

.page-header p {
  color: #64748B;
  font-size: 0.95rem;
  margin: 0;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.section-header h2 { margin: 0; color: #0F172A; font-size: 1.2rem; font-weight: 700; }

.header-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

.filter-select {
  padding: 8px 12px;
  border: 1.5px solid #E2E8F0;
  border-radius: 8px;
  font-size: 0.85rem;
  color: #334155;
  background: #FFFFFF;
  outline: none;
  transition: border-color 0.2s;
}

.filter-select:focus {
  border-color: #2563EB;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.add-btn {
  background: #2563EB;
  color: #FFFFFF;
  border: none;
  padding: 10px 20px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.88rem;
  font-weight: 600;
  transition: all 0.2s;
}

.add-btn:hover { background: #1D4ED8; transform: translateY(-1px); box-shadow: 0 4px 12px rgba(37, 99, 235, 0.25); }

.cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(480px, 1fr));
  gap: 16px;
}

.card {
  background: #FFFFFF;
  border-radius: 12px;
  padding: 20px;
  border: 1px solid #E2E8F0;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  transition: box-shadow 0.2s ease, transform 0.2s ease;
}

.card:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,0.06);
  transform: translateY(-1px);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-title h3 { margin: 0; font-size: 1.05rem; color: #0F172A; font-weight: 600; }

.doc-icon, .entry-icon { font-size: 1.2rem; }

.card-badges {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.level-badge, .status-badge, .category-badge, .source-badge {
  padding: 3px 10px;
  border-radius: 12px;
  font-size: 0.72rem;
  font-weight: 600;
}

.level-badge.global { background: #EFF6FF; color: #2563EB; }
.level-badge.project { background: #F5F3FF; color: #7C3AED; }
.status-badge.ready { background: #F0FDF4; color: #059669; }
.status-badge.processing { background: #FFFBEB; color: #D97706; }
.status-badge.failed { background: #FEF2F2; color: #DC2626; }
.status-badge.uploaded { background: #F8FAFC; color: #64748B; }
.category-badge.module { background: #F0FDF4; color: #059669; }
.category-badge.data_model { background: #EFF6FF; color: #2563EB; }
.category-badge.interface { background: #FFFBEB; color: #D97706; }
.category-badge.business_rule { background: #FEF2F2; color: #DC2626; }
.category-badge.naming { background: #F5F3FF; color: #7C3AED; }
.category-badge.constraint { background: #ECFEFF; color: #0891B2; }
.source-badge.llm_extract { background: #F0FDF4; color: #059669; }
.source-badge.manual { background: #F8FAFC; color: #64748B; }

.card-body { margin-bottom: 12px; }

.info-row {
  display: flex;
  gap: 8px;
  margin-bottom: 4px;
  font-size: 0.82rem;
}

.info-row label { color: #94A3B8; min-width: 60px; font-weight: 500; }
.info-row span { color: #334155; }

.error-label { color: #DC2626 !important; }
.error-text { color: #DC2626 !important; }

.entry-content {
  color: #334155;
  font-size: 0.88rem;
  line-height: 1.6;
  margin-bottom: 8px;
}

.entry-meta { font-size: 0.78rem; color: #94A3B8; }

.card-actions {
  display: flex;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid #F1F5F9;
}

.action-btn {
  padding: 6px 14px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.78rem;
  font-weight: 500;
  transition: all 0.15s;
}

.process-btn { background: #2563EB; color: #FFFFFF; }
.process-btn:hover { background: #1D4ED8; }
.extract-btn { background: #7C3AED; color: #FFFFFF; }
.extract-btn:hover { background: #6D28D9; }
.edit-btn { background: #F59E0B; color: #FFFFFF; }
.edit-btn:hover { background: #D97706; }
.delete-btn { background: #DC2626; color: #FFFFFF; }
.delete-btn:hover { background: #B91C1C; }

.empty-state { text-align: center; padding: 60px; color: #94A3B8; }

/* Modal */
.modal-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(15, 23, 42, 0.5);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: #FFFFFF;
  border-radius: 14px;
  max-width: 600px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
  border: 1px solid #E2E8F0;
  box-shadow: 0 25px 50px rgba(0,0,0,0.12);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid #E2E8F0;
}

.modal-header h3 { margin: 0; color: #0F172A; font-weight: 700; }

.close-btn {
  background: none;
  border: none;
  font-size: 1.3rem;
  cursor: pointer;
  color: #94A3B8;
  padding: 4px 8px;
  border-radius: 6px;
  transition: all 0.15s;
}

.close-btn:hover { color: #0F172A; background: #F1F5F9; }

.modal-body { padding: 24px; }

.form-group { margin-bottom: 16px; }

.form-group label {
  display: block;
  margin-bottom: 6px;
  font-weight: 600;
  color: #334155;
  font-size: 0.85rem;
}

.form-input, .form-select, .form-textarea {
  width: 100%;
  padding: 10px 12px;
  border: 1.5px solid #E2E8F0;
  border-radius: 8px;
  font-size: 0.9rem;
  box-sizing: border-box;
  color: #0F172A;
  background: #FFFFFF;
  transition: border-color 0.2s;
  font-family: inherit;
}

.form-input:focus, .form-select:focus, .form-textarea:focus {
  outline: none;
  border-color: #2563EB;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
}

.form-textarea {
  resize: vertical;
  min-height: 120px;
}

.required { color: #DC2626; }

.modal-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  margin-top: 24px;
}

.cancel-btn {
  background: #F1F5F9;
  color: #475569;
  border: 1.5px solid #E2E8F0;
  padding: 10px 20px;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 500;
  font-size: 0.9rem;
  transition: all 0.15s;
}

.cancel-btn:hover { background: #E2E8F0; }

.confirm-btn {
  background: #2563EB;
  color: #FFFFFF;
  border: none;
  padding: 10px 20px;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.9rem;
  transition: all 0.15s;
}

.confirm-btn:hover { background: #1D4ED8; }
.confirm-btn:disabled { background: #CBD5E1; cursor: not-allowed; }

@media (max-width: 768px) {
  .cards-grid { grid-template-columns: 1fr; }
}
</style>