<template>
  <div class="task-detail">
    <div class="page-header">
      <div class="header-left">
        <h2>{{ $t('taskDetail.title') }} <span v-if="task.title">- {{ task.title }}</span></h2>
        <div class="task-info">
          <span class="task-id">{{ $t('taskDetail.taskId') }}: {{ taskId }}</span>
          <span class="task-status" :class="task.status">{{ getStatusText(task.status) }}</span>
          <span
            v-if="task.granularity"
            class="task-chip"
            :title="task.granularity === 'coarse'
              ? $t('requirementAnalysis.granularityCoarseHint')
              : (task.granularity === 'fine'
                ? $t('requirementAnalysis.granularityFineHint')
                : $t('requirementAnalysis.granularityMediumHint'))">
            {{ $t('requirementAnalysis.granularityDisplay') }}：{{ task.granularity_display || task.granularity }}
          </span>
          <span v-if="task.case_type" class="task-chip">
            {{ $t('requirementAnalysis.caseTypeLabel') }}：{{ task.case_type }}
          </span>
        </div>
      </div>
      <div class="header-actions">
        <button
          v-if="testCases.length > 0"
          class="export-btn"
          @click="exportToExcel"
          :disabled="isExporting">
          <span v-if="isExporting">{{ $t('taskDetail.exporting') }}</span>
          <span v-else>{{ $t('taskDetail.exportBtn') }}</span>
        </button>
      </div>
    </div>

    <!-- 需求描述折叠卡片 -->
    <div v-if="task.requirement_text" class="requirement-description-card">
      <el-collapse>
        <el-collapse-item name="requirement">
          <template #title>
            <div class="collapse-title">
              <span class="title-text">{{ $t('taskDetail.requirementTitle') }}</span>
              <span class="title-hint">{{ $t('taskDetail.requirementHint') }}</span>
            </div>
          </template>
          <div class="requirement-content">
            <div class="requirement-text">
              {{ task.requirement_text }}
            </div>
            <div class="requirement-actions">
              <el-button size="small" @click="copyRequirementText">
                <el-icon><DocumentCopy /></el-icon>
                {{ $t('taskDetail.copyRequirement') }}
              </el-button>
            </div>
          </div>
        </el-collapse-item>
      </el-collapse>
    </div>

    <!-- 流式生成面板（任务运行中） -->
    <div v-if="isStreaming" class="streaming-panel">
      <div class="stream-steps">
        <div class="mini-step" :class="{ active: currentStep >= 1 }">
          {{ $t('taskDetail.stepGenerating') }}
        </div>
        <div class="mini-step" :class="{ active: currentStep >= 2 }">
          {{ $t('taskDetail.stepReviewing') }}
        </div>
        <div class="mini-step" :class="{ active: currentStep >= 3 }">
          {{ $t('taskDetail.stepRevising') }}
        </div>
        <div class="mini-step" :class="{ active: currentStep >= 4 }">
          {{ $t('taskDetail.stepComplete') }}
        </div>
      </div>
      <div class="stream-status">
        {{ getStatusText(task.status) }} · {{ Math.round(task.progress || 0) }}%
      </div>

      <div v-if="streamedContent" class="stream-section">
        <div class="stream-section-title">{{ $t('taskDetail.generatedContent') }}</div>
        <div class="stream-content" v-html="formatMarkdown(formatStreamForDisplay(streamedContent))"></div>
      </div>

      <div v-if="streamedReviewContent" class="stream-section">
        <div class="stream-section-title">{{ $t('taskDetail.reviewFeedback') }}</div>
        <div class="stream-content" v-html="formatMarkdown(streamedReviewContent)"></div>
      </div>

      <div v-if="finalCasesStream" class="stream-section">
        <div class="stream-section-title">{{ $t('taskDetail.finalCases') }}（{{ streamedCases.length }}）</div>
        <div v-if="streamedCases.length" class="stream-cards">
          <div v-for="(tc, idx) in streamedCases" :key="idx" class="stream-card">
            <div class="stream-card-head">
              <span class="stream-card-id">{{ tc.caseId || 'TC' + String(idx + 1).padStart(3, '0') }}</span>
              <span class="priority-tag" :class="(tc.priority || 'P2').toLowerCase()">{{ tc.priority || 'P2' }}</span>
            </div>
            <div class="stream-card-scenario">{{ tc.scenario }}</div>
            <div class="stream-card-body" v-if="tc.steps || tc.expected">
              <span v-if="tc.steps">{{ $t('taskDetail.tableSteps') }}：{{ tc.steps }}</span>
              <span v-if="tc.expected">{{ $t('taskDetail.tableExpected') }}：{{ tc.expected }}</span>
            </div>
          </div>
        </div>
        <div class="stream-content" v-html="formatMarkdown(formatStreamForDisplay(finalCasesStream))"></div>
      </div>
    </div>

    <div v-if="isLoading" class="loading-state">
      <p>{{ $t('taskDetail.loading') }}</p>
    </div>

    <div v-else-if="!task.task_id" class="error-state">
      <h3>{{ $t('taskDetail.taskNotExist') }}</h3>
      <router-link to="/ai-generation/generated-testcases">{{ $t('taskDetail.backToList') }}</router-link>
    </div>

    <div v-else class="task-content">
      <!-- 完成态：AI评审反馈 -->
      <div v-if="!isStreaming && showReviewFeedback && task.review_feedback" class="review-feedback-section">
        <div class="review-feedback-title">{{ $t('taskDetail.reviewFeedback') }}</div>
        <div class="stream-content" v-html="formatMarkdown(task.review_feedback)"></div>
      </div>

      <!-- 失败态 -->
      <div v-if="task.status === 'failed'" class="error-state terminal-state">
        <h3>{{ $t('taskDetail.failedTitle') }}</h3>
        <p class="error-message">{{ task.error_message || $t('taskDetail.failedUnknownReason') }}</p>
        <router-link to="/ai-generation/generated-testcases">{{ $t('taskDetail.backToList') }}</router-link>
      </div>
      <!-- 取消态 -->
      <div v-else-if="task.status === 'cancelled'" class="error-state terminal-state">
        <h3>{{ $t('taskDetail.cancelledTitle') }}</h3>
        <p>{{ $t('taskDetail.cancelledHint') }}</p>
        <router-link to="/ai-generation/generated-testcases">{{ $t('taskDetail.backToList') }}</router-link>
      </div>
      <template v-else>
      <!-- 批量操作区域 -->
      <div class="batch-actions" v-if="testCases.length > 0">
        <div class="selection-info">
          <label class="select-all">
            <input
              type="checkbox"
              :checked="isAllSelected"
              @change="toggleSelectAll">
            {{ $t('taskDetail.selectAll') }}
          </label>
          <span class="selected-count" v-if="selectedCases.length > 0">
            {{ $t('taskDetail.selectedCount', { count: selectedCases.length }) }}
          </span>
        </div>
        <div class="batch-buttons">
          <button
            class="batch-adopt-btn"
            :disabled="selectedCases.length === 0"
            @click="batchAdopt">
            {{ $t('taskDetail.batchAdopt', { count: selectedCases.length }) }}
          </button>
          <button
            class="batch-discard-btn"
            :disabled="selectedCases.length === 0"
            @click="batchDiscard">
            {{ $t('taskDetail.batchDiscard', { count: selectedCases.length }) }}
          </button>
        </div>
      </div>

      <!-- 测试用例列表 -->
      <div class="testcases-table" v-if="testCases.length > 0">
        <div class="table-header">
          <div class="header-cell checkbox-cell">{{ $t('taskDetail.tableSelect') }}</div>
          <div class="header-cell">{{ $t('taskDetail.tableCaseId') }}</div>
          <div class="header-cell">{{ $t('taskDetail.tableScenario') }}</div>
          <div class="header-cell">{{ $t('taskDetail.tablePrecondition') }}</div>
          <div class="header-cell">{{ $t('taskDetail.tableSteps') }}</div>
          <div class="header-cell">{{ $t('taskDetail.tableExpected') }}</div>
          <div class="header-cell">{{ $t('taskDetail.tablePriority') }}</div>
          <div class="header-cell">{{ $t('taskDetail.tableActions') }}</div>
        </div>

        <div class="table-body">
          <div
            v-for="(testCase, index) in paginatedTestCases"
            :key="testCase.id || index"
            class="table-row">
            <div class="body-cell checkbox-cell">
              <input
                type="checkbox"
                :value="testCase"
                v-model="selectedCases"
                @change="updateSelectAll">
            </div>
            <div class="body-cell">{{ testCase.caseId || `TC${String(index + 1).padStart(3, '0')}` }}</div>
            <div class="body-cell">{{ testCase.scenario }}</div>
            <div class="body-cell text-truncate">
              {{ formatTextForList(testCase.precondition) }}
            </div>
            <div class="body-cell text-truncate">
              {{ formatTextForList(testCase.steps) }}
            </div>
            <div class="body-cell text-truncate">
              {{ formatTextForList(testCase.expected) }}
            </div>
            <div class="body-cell">
              <span class="priority-tag" :class="testCase.priority?.toLowerCase()">{{ testCase.priority || 'P2' }}</span>
            </div>
            <div class="body-cell">
              <div class="action-buttons">
                <button class="view-btn" @click="viewCaseDetail(testCase, index)">{{ $t('taskDetail.viewDetail') }}</button>
                <button class="adopt-btn" @click="adoptSingleCase(testCase, index)">{{ $t('taskDetail.adopt') }}</button>
                <button class="discard-btn" @click="discardSingleCase(testCase, index)">{{ $t('taskDetail.discard') }}</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="empty-state">
        <h3>{{ $t('taskDetail.emptyTitle') }}</h3>
        <p>{{ $t('taskDetail.emptyHint') }}</p>
      </div>

      <!-- 分页 -->
      <div v-if="testCases.length > 0" class="pagination-section">
        <div class="pagination-info">
          {{ $t('taskDetail.paginationInfo', { start: paginationStart, end: paginationEnd, total: testCases.length }) }}
        </div>
        <div class="pagination-controls">
          <div class="page-size-selector">
            <label>{{ $t('taskDetail.pageSizeLabel') }}</label>
            <select v-model="pageSize" @change="currentPage = 1">
              <option value="10">{{ $t('taskDetail.pageSizeOption', { size: 10 }) }}</option>
              <option value="20">{{ $t('taskDetail.pageSizeOption', { size: 20 }) }}</option>
              <option value="50">{{ $t('taskDetail.pageSizeOption', { size: 50 }) }}</option>
            </select>
          </div>
          <div class="pagination-buttons">
            <button :disabled="currentPage <= 1" @click="currentPage--">{{ $t('taskDetail.previousPage') }}</button>
            <span class="current-page">{{ $t('taskDetail.currentPageInfo', { current: currentPage, total: totalPages }) }}</span>
            <button :disabled="currentPage >= totalPages" @click="currentPage++">{{ $t('taskDetail.nextPage') }}</button>
          </div>
        </div>
      </div>
      </template>
    </div>

    <!-- 用例详情弹窗 -->
    <div v-if="showCaseDetail" class="case-detail-modal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>{{ isEditing ? $t('taskDetail.modalEditTitle') : $t('taskDetail.modalViewTitle') }}</h3>
          <button class="close-btn" @click="closeCaseDetail">×</button>
        </div>

        <!-- 查看模式 -->
        <div v-if="!isEditing" class="modal-body">
          <div class="detail-item">
            <label>{{ $t('taskDetail.labelCaseId') }}</label>
            <span>{{ selectedCase.caseId || `TC${String(selectedCaseIndex + 1).padStart(3, '0')}` }}</span>
          </div>
          <div class="detail-item">
            <label>{{ $t('taskDetail.labelScenario') }}</label>
            <p v-html="formatMarkdown(selectedCase.scenario)"></p>
          </div>
          <div class="detail-item">
            <label>{{ $t('taskDetail.labelPrecondition') }}</label>
            <p v-html="formatMarkdown(selectedCase.precondition || $t('taskDetail.labelNone'))"></p>
          </div>
          <div class="detail-item">
            <label>{{ $t('taskDetail.labelSteps') }}</label>
            <p class="test-steps" v-html="formatMarkdown(selectedCase.steps)"></p>
          </div>
          <div class="detail-item">
            <label>{{ $t('taskDetail.labelExpected') }}</label>
            <p v-html="formatMarkdown(selectedCase.expected)"></p>
          </div>
          <div class="detail-item">
            <label>{{ $t('taskDetail.labelPriority') }}</label>
            <span class="priority-tag" :class="selectedCase.priority?.toLowerCase()">{{ selectedCase.priority || 'P2' }}</span>
          </div>
        </div>

        <!-- 编辑模式 -->
        <div v-else class="modal-body edit-mode">
          <div class="form-item">
            <label>{{ $t('taskDetail.labelCaseId') }}</label>
            <span class="readonly-field">{{ editForm.caseId || `TC${String(selectedCaseIndex + 1).padStart(3, '0')}` }}</span>
          </div>
          <div class="form-item">
            <label>{{ $t('taskDetail.labelScenario') }}</label>
            <el-input v-model="editForm.scenario" type="textarea" :rows="2" :placeholder="$t('taskDetail.placeholderScenario')" />
          </div>
          <div class="form-item">
            <label>{{ $t('taskDetail.labelPrecondition') }}</label>
            <el-input v-model="editForm.precondition" type="textarea" :rows="3" :placeholder="$t('taskDetail.placeholderPrecondition')" />
          </div>
          <div class="form-item">
            <label>{{ $t('taskDetail.labelSteps') }}</label>
            <el-input v-model="editForm.steps" type="textarea" :rows="6" :placeholder="$t('taskDetail.placeholderSteps')" />
          </div>
          <div class="form-item">
            <label>{{ $t('taskDetail.labelExpected') }}</label>
            <el-input v-model="editForm.expected" type="textarea" :rows="4" :placeholder="$t('taskDetail.placeholderExpected')" />
          </div>
          <div class="form-item">
            <label>{{ $t('taskDetail.labelPriority') }}</label>
            <el-select v-model="editForm.priority" :placeholder="$t('taskDetail.placeholderPriority')">
              <el-option label="P0" value="P0"></el-option>
              <el-option label="P1" value="P1"></el-option>
              <el-option label="P2" value="P2"></el-option>
              <el-option label="P3" value="P3"></el-option>
            </el-select>
          </div>
        </div>

        <!-- 底部操作栏 -->
        <div class="modal-footer">
          <template v-if="!isEditing">
            <button class="action-btn edit-btn" @click="startEdit">
              <span>{{ $t('taskDetail.btnEdit') }}</span>
            </button>
            <button class="action-btn close-btn-footer" @click="closeCaseDetail">{{ $t('taskDetail.btnClose') }}</button>
          </template>
          <template v-else>
            <button class="action-btn save-btn" @click="saveEdit" :disabled="isSaving">
              <span v-if="isSaving">{{ $t('taskDetail.btnSaveing') }}</span>
              <span v-else>{{ $t('taskDetail.btnSave') }}</span>
            </button>
            <button class="action-btn cancel-btn" @click="cancelEdit" :disabled="isSaving">{{ $t('taskDetail.btnCancel') }}</button>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import api from '@/utils/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { DocumentCopy } from '@element-plus/icons-vue'
import * as XLSX from 'xlsx'

export default {
  name: 'TaskDetail',
  data() {
    return {
      taskId: '',
      task: {},
      testCases: [],
      selectedCases: [],
      isLoading: true,
      showCaseDetail: false,
      selectedCase: {},
      selectedCaseIndex: 0,
      currentPage: 1,
      pageSize: 10,
      isExporting: false,
      // 编辑相关状态
      isEditing: false,
      isSaving: false,
      editForm: {
        caseId: '',
        scenario: '',
        precondition: '',
        steps: '',
        expected: '',
        priority: 'P2'
      },
      // 流式生成相关
      isStreaming: false,        // 任务是否运行中（展示流式面板）
      currentStep: 0,            // 1生成 2评审 3改进 4完成
      streamedContent: '',       // 流式原始生成内容
      streamedReviewContent: '', // 流式评审反馈
      finalCasesStream: '',      // 流式最终用例（原始文本）
      streamedCases: [],         // 流式解析出的用例卡片预览
      eventSource: null,         // SSE 连接
      pollTimer: null,           // 轮询降级定时器
      showReviewFeedback: false, // 完成态是否展示评审反馈
    }
  },

  computed: {
    isAllSelected() {
      return this.testCases.length > 0 && this.selectedCases.length === this.testCases.length
    },

    totalPages() {
      return Math.ceil(this.testCases.length / this.pageSize)
    },

    paginatedTestCases() {
      const start = (this.currentPage - 1) * this.pageSize
      const end = start + this.pageSize
      return this.testCases.slice(start, end)
    },

    paginationStart() {
      return (this.currentPage - 1) * this.pageSize + 1
    },

    paginationEnd() {
      return Math.min(this.currentPage * this.pageSize, this.testCases.length)
    }
  },

  mounted() {
    this.taskId = this.$route.params.taskId
    this.loadTaskDetail()
  },

  beforeUnmount() {
    this.cleanupStreaming()
  },

  methods: {
    // 复制需求描述文本
    async copyRequirementText() {
      try {
        await navigator.clipboard.writeText(this.task.requirement_text)
        ElMessage.success(this.$t('taskDetail.copySuccess'))
      } catch (error) {
        // 如果 navigator.clipboard 不可用，使用备用方法
        const textArea = document.createElement('textarea')
        textArea.value = this.task.requirement_text
        textArea.style.position = 'fixed'
        textArea.style.opacity = '0'
        document.body.appendChild(textArea)
        textArea.select()
        try {
          document.execCommand('copy')
          ElMessage.success(this.$t('taskDetail.copySuccess'))
        } catch (err) {
          ElMessage.error(this.$t('taskDetail.copyFailed'))
        }
        document.body.removeChild(textArea)
      }
    },

    async loadTaskDetail() {
      try {
        // 获取任务基本信息
        const taskResponse = await api.get(`/requirement-analysis/testcase-generation/${this.taskId}/`)
        this.task = taskResponse.data

        // 运行中：进入流式/轮询模式
        if (['pending', 'generating', 'reviewing', 'revising'].includes(this.task.status)) {
          this.isStreaming = true
          this.$nextTick(() => {
            if (this.task.output_mode === 'stream') {
              this.startStreaming()
            } else {
              this.startPolling()
            }
          })
        } else if (this.task.status === 'completed') {
          // 完成态：解析最终用例
          if (this.task.final_test_cases) {
            this.testCases = this.parseTestCases(this.task.final_test_cases)
          }
          if (this.task.review_feedback) {
            this.showReviewFeedback = true
          }
        }
        // failed / cancelled：模板直接渲染终态卡片
      } catch (error) {
        console.error('Failed to load task details:', error)
        ElMessage.error(this.$t('taskDetail.loadFailed'))
      } finally {
        this.isLoading = false
      }
    },

    startStreaming() {
      // EventSource 不用 axios 代理，直接指向后端
      const currentOrigin = window.location.origin
      const url = `${currentOrigin}/api/requirement-analysis/testcase-generation/${this.taskId}/stream_progress/`
      this.eventSource = new EventSource(url, { withCredentials: true })

      this.eventSource.onmessage = (event) => {
        let data
        try {
          data = JSON.parse(event.data)
        } catch (e) {
          return
        }

        if (data.type === 'progress') {
          // 仅更新步骤与进度，不直接赋值 task.status（最终以 progress 接口为准）
          this.task.progress = data.progress
          if (data.status === 'generating') {
            this.currentStep = 2
          } else if (data.status === 'reviewing') {
            this.currentStep = 3
          } else if (data.status === 'revising') {
            this.currentStep = 3
          }
        } else if (data.type === 'content') {
          this.streamedContent += data.content
          this.streamedCases = this.parseStreamingTestCases(this.streamedContent)
          this.currentStep = 2
        } else if (data.type === 'review_content') {
          this.streamedReviewContent += data.content
          this.streamedReviewContent = this.streamedReviewContent.replace(/\n+$/, '')
          this.currentStep = 3
        } else if (data.type === 'final_content') {
          this.finalCasesStream += data.content
          this.streamedCases = this.parseStreamingTestCases(this.finalCasesStream)
          this.currentStep = 3
        } else if (data.type === 'status') {
          if (data.status === 'completed') {
            this.finalizeTask()
          } else if (data.status === 'failed' || data.status === 'cancelled') {
            this.finalizeTask()
          }
        } else if (data.type === 'done') {
          if (this.eventSource) {
            this.eventSource.close()
            this.eventSource = null
          }
          this.finalizeTask()
        }
      }

      this.eventSource.onerror = () => {
        // readyState=2 为永久关闭，降级轮询；readyState=0 等待自动重连
        if (!this.eventSource) return
        if (this.eventSource.readyState === 2) {
          this.eventSource.close()
          this.eventSource = null
          ElMessage.warning(this.$t('taskDetail.streamInterrupted'))
          this.startPolling()
        } else if (this.eventSource.readyState === 0) {
          setTimeout(() => {
            if (this.eventSource && this.eventSource.readyState === 0) {
              this.eventSource.close()
              this.eventSource = null
              ElMessage.warning(this.$t('taskDetail.streamInterrupted'))
              this.startPolling()
            }
          }, 5000)
        }
      }
    },

    startPolling() {
      if (this.pollTimer) clearInterval(this.pollTimer)
      this.pollTimer = setInterval(async () => {
        try {
          const response = await api.get(`/requirement-analysis/testcase-generation/${this.taskId}/progress/`)
          const task = response.data
          this.task = { ...this.task, ...task }
          if (task.status === 'completed' || task.status === 'failed' || task.status === 'cancelled') {
            clearInterval(this.pollTimer)
            this.pollTimer = null
            this.finalizeTask()
          }
        } catch (e) {
          console.error('轮询任务进度失败:', e)
        }
      }, 2000)
    },

    async finalizeTask() {
      try {
        const response = await api.get(`/requirement-analysis/testcase-generation/${this.taskId}/progress/`)
        this.task = response.data
      } catch (e) {
        console.error('获取最终任务结果失败:', e)
      }
      if (this.eventSource) {
        this.eventSource.close()
        this.eventSource = null
      }
      if (this.pollTimer) {
        clearInterval(this.pollTimer)
        this.pollTimer = null
      }
      this.isStreaming = false
      this.currentStep = 4

      if (this.task.status === 'completed') {
        if (this.task.final_test_cases) {
          this.finalCasesStream = this.task.final_test_cases
          this.testCases = this.parseTestCases(this.task.final_test_cases)
        }
        if (this.task.review_feedback) {
          this.showReviewFeedback = true
        }
        if (!this.streamedReviewContent && this.task.review_feedback) {
          this.streamedReviewContent = this.task.review_feedback
        }
      }
      // failed / cancelled：模板已用 task.status 渲染终态
    },

    cleanupStreaming() {
      if (this.eventSource) {
        this.eventSource.close()
        this.eventSource = null
      }
      if (this.pollTimer) {
        clearInterval(this.pollTimer)
        this.pollTimer = null
      }
    },

    formatStreamForDisplay(content) {
      if (!content) return ''
      return content.replace(/\n{3,}/g, '\n\n').trim()
    },

    parseTestCases(content) {
      if (!content) return []

      const testCases = []

      // 优先 JSONL 解析（每行一个 JSON）
      const lines = content.split('\n')
      let hasJsonL = false
      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed) continue
        try {
          const obj = JSON.parse(trimmed)
          testCases.push({
            caseId: obj.case_id || '',
            scenario: obj.title || '',
            precondition: obj.precondition || '',
            steps: Array.isArray(obj.steps) ? obj.steps.map(s => `${s.desc || ''}\n预期: ${s.expect || ''}`).join('\n') : '',
            expected: (obj.steps || []).map(s => s.expect || '').filter(Boolean).join('\n'),
            priority: obj.priority || 'P2',
          })
          hasJsonL = true
        } catch (e) {
          // 不完整行跳过，下次轮询再处理
        }
      }
      if (hasJsonL) return testCases

      // 回退：旧表格格式解析
      let cleanContent = content.replace(/\*\*([^*]+)\*\*/g, '$1')
      const legacyLines = cleanContent.split('\n').filter(line => line.trim())
      let isTableFormat = false
      const tableData = []

      for (let line of legacyLines) {
        const trimmedLine = line.trim()
        if (trimmedLine.includes('|') && !trimmedLine.includes('--------')) {
          const cells = trimmedLine.split('|').map(cell => cell.trim()).filter(cell => cell)
          if (cells.length > 1) {
            tableData.push(cells)
            isTableFormat = true
          }
        }
      }

      if (isTableFormat && tableData.length > 1) {
        const headers = tableData[0]
        for (let i = 1; i < tableData.length; i++) {
          const row = tableData[i]
          const testCase = {}
          headers.forEach((header, index) => {
            const value = (row[index] || '').replace(/<br\s*\/?>/gi, '\n')
            const cleanHeader = header.trim().toLowerCase()
            if (cleanHeader === '优先级' || cleanHeader === 'priority' || cleanHeader.includes('优先级')) {
              testCase.priority = value
            } else if (cleanHeader.includes('用例id') || cleanHeader === '编号' || cleanHeader === 'id') {
              testCase.caseId = value
            } else if (cleanHeader.includes('测试目标') || cleanHeader === '测试场景' || cleanHeader === '场景' || cleanHeader === '标题') {
              testCase.scenario = value
            } else if (cleanHeader === '前置条件' || cleanHeader === '前置' || cleanHeader === '前提条件') {
              testCase.precondition = value
            } else if ((cleanHeader === '测试步骤' || cleanHeader === '操作步骤' || cleanHeader === '步骤') && !cleanHeader.includes('预期')) {
              testCase.steps = value
            } else if (cleanHeader === '预期结果' || cleanHeader === '预期' || cleanHeader.includes('预期结果')) {
              testCase.expected = value
            }
          })
          if (testCase.scenario || testCase.caseId) {
            if (!testCase.steps && testCase.scenario) testCase.steps = testCase.scenario
            if (!testCase.priority) testCase.priority = 'P2'
            testCases.push(testCase)
          }
        }
      }
      return testCases
    },

    getStatusText(status) {
      if (!status) return ''
      const statusKey = 'status' + status.charAt(0).toUpperCase() + status.slice(1)
      return this.$t('taskDetail.' + statusKey) || status
    },

    // 格式化列表中的文本，将<br>转换为换行
    formatTextForList(text) {
      if (!text) return ''
      // 将<br>、<br/>、<br />等标签替换为换行符
      return text.replace(/<br\s*\/?>/gi, '\n')
    },

    // 格式化Markdown为HTML（简化版）
    formatMarkdown(content) {
      if (!content) return '';

      // 先去除"新增"标记，在markdown转换之前处理
      // 这样可以避免markdown转换后无法匹配的问题
      let html = content
          .replace(/\*\*新增\*\*-/g, '')  // **新增**-xxx -> xxx (保留xxx的原有格式)
          .replace(/新增-/g, '');  // 新增-xxx -> xxx (保留xxx的原有格式)

      // 转义HTML特殊字符
      html = html
          .replace(/&/g, '&amp;')
          .replace(/</g, '&lt;')
          .replace(/>/g, '&gt;');

      // 转换Markdown语法
      // 标题 #
      html = html.replace(/^#{6}\s+(.+)$/gm, '<h6>$1</h6>');
      html = html.replace(/^#{5}\s+(.+)$/gm, '<h5>$1</h5>');
      html = html.replace(/^#{4}\s+(.+)$/gm, '<h4>$1</h4>');
      html = html.replace(/^#{3}\s+(.+)$/gm, '<h3>$1</h3>');
      html = html.replace(/^#{2}\s+(.+)$/gm, '<h2>$1</h2>');
      html = html.replace(/^#{1}\s+(.+)$/gm, '<h1>$1</h1>');

      // 粗体 **text** 或 __text__
      html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
      html = html.replace(/__(.+?)__/g, '<strong>$1</strong>');

      // 斜体 *text* 或 _text_
      html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
      html = html.replace(/_(.+?)_/g, '<em>$1</em>');

      // 代码块 ```code```
      html = html.replace(/```([\s\S]+?)```/g, '<pre><code>$1</code></pre>');

      // 行内代码 `code`
      html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

      // 换行符转换为<br>
      html = html.replace(/\n/g, '<br>');

      return html;
    },

    // 增量解析流式文本为用例卡片数据
    parseStreamingTestCases(content) {
      if (!content) return []

      // 去除 markdown 加粗标记
      const cleanContent = content.replace(/\*\*([^*]+)\*\*/g, '$1')
      const lines = cleanContent.split('\n').filter(line => line.trim())
      if (lines.length === 0) return []

      // 检测表格格式 (| col1 | col2 | ...)
      const tableLines = lines.filter(l => l.includes('|') && !l.includes('---'))
      if (tableLines.length >= 2) {
        return this.parseTableToCards(tableLines)
      }

      // 检测结构化格式
      return this.parseStructuredToCards(lines)
    },

    // 解析表格格式为卡片数据
    parseTableToCards(tableLines) {
      const headers = tableLines[0].split('|').map(c => c.trim()).filter(c => c)
      const cases = []

      const cleanBr = (text) => {
        if (!text) return ''
        return text.replace(/<br\s*\/?>/gi, '\n')
      }

      for (let i = 1; i < tableLines.length; i++) {
        const cells = tableLines[i].split('|').map(c => c.trim()).filter(c => c)
        const tc = { _incomplete: false, _justArrived: false }

        // 如果当前行单元格数不匹配，标记为不完整
        if (cells.length < headers.length && i === tableLines.length - 1) {
          tc._incomplete = true
        }

        headers.forEach((header, index) => {
          const value = cleanBr(cells[index] || '')
          const cleanHeader = header.trim().toLowerCase()

          if (cleanHeader === '优先级' || cleanHeader === 'priority' || cleanHeader.includes('优先级')) {
            tc.priority = value || 'P2'
          } else if (cleanHeader === '用例id' || cleanHeader === '编号' || cleanHeader === 'id' || cleanHeader.includes('用例id')) {
            tc.caseId = value
          } else if (cleanHeader === '测试目标' || cleanHeader === '测试场景' || cleanHeader === '场景' || cleanHeader === '标题' || cleanHeader.includes('测试目标') || cleanHeader.includes('测试场景')) {
            tc.scenario = value
          } else if (cleanHeader === '前置条件' || cleanHeader === '前置' || cleanHeader === '前提条件') {
            tc.precondition = value
          } else if (cleanHeader === '测试步骤' || cleanHeader === '操作步骤' || cleanHeader === '步骤') {
            if (!cleanHeader.includes('预期') && !cleanHeader.includes('结果')) {
              tc.steps = value
            }
          } else if (cleanHeader === '预期结果' || cleanHeader === '预期' || cleanHeader === '结果' || cleanHeader.includes('预期结果')) {
            tc.expected = value
          }
        })

        // 只添加有实际内容的卡片
        if (tc.scenario || tc.caseId || tc.precondition || tc.steps || tc.expected) {
          if (!tc.priority) tc.priority = 'P2'
          cases.push(tc)
        }
      }

      return cases
    },

    // 解析结构化文本格式为卡片数据
    parseStructuredToCards(lines) {
      const cases = []
      let currentCase = null
      let caseNumber = 1

      for (const line of lines) {
        const trimmed = line.trim()

        // 检测新用例开始
        if (trimmed.includes('测试用例') || trimmed.includes('Test Case') ||
            trimmed.match(/^(\d+\.|\*|\-|\d+、)/)) {

          if (currentCase && Object.keys(currentCase).length > 1) {
            cases.push(currentCase)
            caseNumber++
          }

          currentCase = {
            caseId: `TC${String(caseNumber).padStart(3, '0')}`,
            scenario: trimmed.replace(/^(\d+\.|\*|\-|\d+、)\s*/, '').replace(/测试用例\d*[:：]?\s*/, '').replace(/Test Case\s*\d*[:：]?\s*/i, ''),
            precondition: '',
            steps: '',
            expected: '',
            priority: 'P2',
            _incomplete: true,
            _justArrived: false
          }
        } else if (currentCase) {
          // 匹配字段
          if (trimmed.includes('前置条件') || trimmed.includes('前提') || trimmed.includes('Precondition')) {
            currentCase.precondition = trimmed.replace(/.*?[:：]\s*/, '')
            currentCase._incomplete = false
          } else if ((trimmed.includes('测试步骤') || trimmed.includes('操作步骤') || trimmed.includes('步骤')) &&
                     !trimmed.includes('预期') && !trimmed.includes('结果')) {
            currentCase.steps = trimmed.replace(/.*?[:：]\s*/, '')
            currentCase._incomplete = false
          } else if (trimmed.includes('预期结果') || trimmed.includes('Expected') || trimmed.includes('期望')) {
            currentCase.expected = trimmed.replace(/.*?[:：]\s*/, '')
            currentCase._incomplete = false
          } else if (trimmed.includes('优先级') || trimmed.includes('Priority')) {
            currentCase.priority = trimmed.replace(/.*?[:：]\s*/, '')
            currentCase._incomplete = false
          }
          // 如果用例至少有了场景和步骤/预期，就标记为完成
          if (currentCase.scenario && (currentCase.steps || currentCase.expected)) {
            currentCase._incomplete = false
          }
        }
      }

      // 保存最后一个
      if (currentCase && Object.keys(currentCase).length > 1) {
        cases.push(currentCase)
      }

      return cases
    },

    toggleSelectAll() {
      if (this.isAllSelected) {
        this.selectedCases = []
      } else {
        this.selectedCases = [...this.testCases]
      }
    },

    updateSelectAll() {
      // 这个方法会在单个checkbox变化时触发，用于更新全选状态
      // Vue的v-model会自动处理selectedCases数组的更新
    },

    async batchAdopt() {
      if (this.selectedCases.length === 0) {
        ElMessage.warning(this.$t('taskDetail.pleaseSelectFirst', { action: this.$t('taskDetail.adopt') }))
        return
      }

      try {
        await ElMessageBox.confirm(
          this.$t('taskDetail.confirmAdopt', { count: this.selectedCases.length }),
          this.$t('taskDetail.confirmAdoptTitle'),
          {
            confirmButtonText: this.$t('taskDetail.btnConfirm'),
            cancelButtonText: this.$t('taskDetail.btnCancelOperation'),
            type: 'success'
          }
        )
      } catch {
        return
      }

      try {
        const casesData = this.selectedCases.map((testCase, index) => ({
          title: testCase.scenario || `Test Case ${index + 1}`,
          description: testCase.scenario || '',
          preconditions: testCase.precondition || '',
          steps: testCase.steps || '',
          expected_result: testCase.expected || '',
          priority: this.mapPriority(testCase.priority),
          test_type: 'functional',
          status: 'draft'
        }))

        await api.post(`/requirement-analysis/testcase-generation/${this.taskId}/batch-adopt-selected/`, {
          test_cases: casesData
        })

        ElMessage.success(this.$t('taskDetail.adoptSuccess', { count: this.selectedCases.length }))
        this.selectedCases = []

        // Keep adopted cases in the list for multiple adoptions
        // this.testCases = this.testCases.filter(tc => !this.selectedCases.includes(tc))

      } catch (error) {
        console.error('Batch adopt failed:', error)
        ElMessage.error(this.$t('taskDetail.batchAdoptFailed') + ': ' + (error.response?.data?.message || error.message))
      }
    },

    async batchDiscard() {
      if (this.selectedCases.length === 0) {
        ElMessage.warning(this.$t('taskDetail.pleaseSelectFirst', { action: this.$t('taskDetail.discard') }))
        return
      }

      try {
        await ElMessageBox.confirm(
          this.$t('taskDetail.confirmDiscard', { count: this.selectedCases.length }),
          this.$t('taskDetail.confirmDiscardTitle'),
          {
            confirmButtonText: this.$t('taskDetail.btnConfirm'),
            cancelButtonText: this.$t('taskDetail.btnCancelOperation'),
            type: 'warning',
            confirmButtonClass: 'el-button--danger'
          }
        )
      } catch {
        return
      }

      try {
        // 获取选中用例的全局索引（不是分页索引）
        const caseIndices = this.selectedCases.map(selectedCase => {
          // 在完整列表中查找索引
          const globalIndex = this.testCases.findIndex(tc =>
            tc.scenario === selectedCase.scenario &&
            tc.steps === selectedCase.steps &&
            tc.expected === selectedCase.expected
          )
          return globalIndex
        }).filter(index => index !== -1) // 过滤掉未找到的(-1)

        const response = await api.post(`/requirement-analysis/testcase-generation/${this.taskId}/discard-selected-cases/`, {
          case_indices: caseIndices
        })

        if (response.data.task_deleted) {
          ElMessage.success(this.$t('taskDetail.allDiscardedSuccess'))
          // 返回到AI生成用例记录列表
          this.$router.push('/generated-testcases')
        } else {
          ElMessage.success(this.$t('taskDetail.discardSuccess', { count: response.data.discarded_count }))

          // 重新解析更新后的测试用例
          if (response.data.updated_test_cases) {
            this.testCases = this.parseTestCases(response.data.updated_test_cases)
            this.selectedCases = []
            this.currentPage = 1 // 重置到第一页
          }
        }

      } catch (error) {
        console.error('Batch discard failed:', error)
        ElMessage.error(this.$t('taskDetail.batchDiscardFailed') + ': ' + (error.response?.data?.error || error.message))
      }
    },

    viewCaseDetail(testCase, index) {
      this.selectedCase = testCase
      this.selectedCaseIndex = index
      this.showCaseDetail = true
    },

    closeCaseDetail() {
      this.showCaseDetail = false
      this.selectedCase = {}
      this.isEditing = false
      this.editForm = {
        caseId: '',
        scenario: '',
        precondition: '',
        steps: '',
        expected: '',
        priority: 'P2'
      }
    },

    // 开始编辑
    startEdit() {
      this.isEditing = true

      this.editForm = {
        caseId: this.selectedCase.caseId || '',
        scenario: this.selectedCase.scenario || '',
        // 将<br>转换为换行符以便编辑
        precondition: this.convertBrToNewline(this.selectedCase.precondition || ''),
        steps: this.convertBrToNewline(this.selectedCase.steps || ''),
        expected: this.convertBrToNewline(this.selectedCase.expected || ''),
        // 直接使用原始优先级值，不转换
        priority: this.selectedCase.priority || 'P2'
      }
    },

    // 取消编辑
    cancelEdit() {
      this.isEditing = false
      this.editForm = {
        caseId: '',
        scenario: '',
        precondition: '',
        steps: '',
        expected: '',
        priority: 'P2'
      }
    },

    // 保存编辑
    async saveEdit() {
      // 简单验证
      if (!this.editForm.scenario?.trim()) {
        ElMessage.warning(this.$t('taskDetail.enterScenario'))
        return
      }

      this.isSaving = true

      try {
        // 将换行符转换回<br>
        const updatedCase = {
          ...this.selectedCase,
          scenario: this.editForm.scenario,
          precondition: this.convertNewlineToBr(this.editForm.precondition),
          steps: this.convertNewlineToBr(this.editForm.steps),
          expected: this.convertNewlineToBr(this.editForm.expected),
          priority: this.editForm.priority
        }

        // 更新本地数组中的数据
        const index = this.testCases.findIndex(tc => tc === this.selectedCase)
        if (index !== -1) {
          this.testCases[index] = updatedCase
          this.selectedCase = updatedCase
        }

        // 重新生成表格格式的测试用例字符串
        const updatedTestCases = this.generateTestCasesString()

        // 调用后端API保存（使用自定义action接口）
        await api.post(`/requirement-analysis/testcase-generation/${this.taskId}/update-test-cases/`, {
          final_test_cases: updatedTestCases
        })

        // 更新内存中的task数据
        this.task.final_test_cases = updatedTestCases

        ElMessage.success(this.$t('taskDetail.updateSuccess'))
        this.isEditing = false
      } catch (error) {
        console.error('Update failed:', error)
        ElMessage.error(this.$t('taskDetail.updateFailed') + ': ' + (error.response?.data?.error || error.message))
      } finally {
        this.isSaving = false
      }
    },

    // 将testCases数组重新生成为表格格式的字符串
    generateTestCasesString() {
      if (this.testCases.length === 0) return ''

      // 表头
      const headers = [
        this.$t('taskDetail.tableCaseId'),
        this.$t('taskDetail.tableScenario'),
        this.$t('taskDetail.tablePrecondition'),
        this.$t('taskDetail.tableSteps'),
        this.$t('taskDetail.tableExpected'),
        this.$t('taskDetail.tablePriority')
      ]
      let result = headers.join(' | ') + '\n'
      result += '|'.repeat(headers.length) + '\n'

      // 数据行
      this.testCases.forEach((testCase, index) => {
        const row = [
          testCase.caseId || `TC${String(index + 1).padStart(3, '0')}`,
          testCase.scenario || '',
          testCase.precondition || '',
          testCase.steps || '',
          testCase.expected || '',
          testCase.priority || 'P2'
        ]
        result += row.join(' | ') + '\n'
      })

      return result
    },

    // 将HTML的<br>标签转换为换行符
    convertBrToNewline(text) {
      if (!text) return ''
      return text.replace(/<br\s*\/?>/gi, '\n')
    },

    // 将换行符转换为HTML的<br>标签
    convertNewlineToBr(text) {
      if (!text) return ''
      return text.replace(/\n/g, '<br>')
    },

    async adoptSingleCase(testCase, index) {
      try {
        await ElMessageBox.confirm(
          this.$t('taskDetail.confirmAdoptSingle', { scenario: testCase.scenario }),
          this.$t('taskDetail.confirmAdoptTitle'),
          {
            confirmButtonText: this.$t('taskDetail.btnConfirm'),
            cancelButtonText: this.$t('taskDetail.btnCancelOperation'),
            type: 'success'
          }
        )
      } catch {
        return
      }

      try {
        const caseData = {
          title: testCase.scenario || `测试用例${index + 1}`,
          description: testCase.scenario || '',
          preconditions: testCase.precondition || '',
          steps: testCase.steps || '',
          expected_result: testCase.expected || '',
          priority: this.mapPriority(testCase.priority),
          test_type: 'functional',
          status: 'draft'
        }

        await api.post('/testcases/', caseData)
        ElMessage.success(this.$t('taskDetail.adoptSuccess', { count: 1 }))

        // 不再移除已采纳的用例，保留在列表中供多次采纳
        // this.testCases.splice(this.testCases.indexOf(testCase), 1)

      } catch (error) {
        console.error('Adopt case failed:', error)
        ElMessage.error(this.$t('taskDetail.adoptFailed') + ': ' + (error.response?.data?.message || error.message))
      }
    },

    async discardSingleCase(testCase, index) {
      try {
        await ElMessageBox.confirm(
          this.$t('taskDetail.confirmDiscardSingle', { scenario: testCase.scenario }),
          this.$t('taskDetail.confirmDiscardTitle'),
          {
            confirmButtonText: this.$t('taskDetail.btnConfirm'),
            cancelButtonText: this.$t('taskDetail.btnCancelOperation'),
            type: 'warning',
            confirmButtonClass: 'el-button--danger'
          }
        )
      } catch {
        return
      }

      try {
        // 计算全局索引（当前页面起始位置 + 当前索引）
        const globalIndex = (this.currentPage - 1) * this.pageSize + index

        // 调用后端API弃用单个测试用例
        const response = await api.post(`/requirement-analysis/testcase-generation/${this.taskId}/discard-single-case/`, {
          case_index: globalIndex
        })

        if (response.data.task_deleted) {
          ElMessage.success(this.$t('taskDetail.allDiscardedSuccess'))
          // 返回到AI生成用例记录列表
          this.$router.push('/generated-testcases')
        } else {
          ElMessage.success(this.$t('taskDetail.caseDiscardedSuccess'))

          // 重新解析更新后的测试用例
          if (response.data.updated_test_cases) {
            this.testCases = this.parseTestCases(response.data.updated_test_cases)

            // 如果当前页没有数据了，回到上一页
            if (this.currentPage > 1 && this.paginatedTestCases.length === 0) {
              this.currentPage--
            }
          }
        }

      } catch (error) {
        console.error('Discard case failed:', error)
        ElMessage.error(this.$t('taskDetail.discardFailed') + ': ' + (error.response?.data?.error || error.message))
      }
    },

    mapPriority(priority) {
      const priorityMap = {
        '最高': 'critical',
        '高': 'high',
        '中': 'medium',
        '低': 'low',
        'P0': 'critical',
        'P1': 'high',
        'P2': 'medium',
        'P3': 'low'
      }
      return priorityMap[priority] || 'medium'
    },

    // 将英文优先级转换为本地化显示
    priorityToChinese(priority) {
      const priorityMap = {
        'critical': this.$t('generatedTestCases.priorityCritical'),
        'high': this.$t('generatedTestCases.priorityHigh'),
        'medium': this.$t('generatedTestCases.priorityMedium'),
        'low': this.$t('generatedTestCases.priorityLow')
      }
      return priorityMap[priority] || this.$t('generatedTestCases.priorityMedium')
    },

    // 导出到Excel
    exportToExcel() {
      if (this.testCases.length === 0) {
        ElMessage.warning(this.$t('taskDetail.noCasesToExport'))
        return
      }

      this.isExporting = true

      try {
        // 创建工作簿
        const workbook = XLSX.utils.book_new()

        // 准备数据
        const worksheetData = []

        // 添加表头
        worksheetData.push([
          this.$t('taskDetail.tableCaseId'),
          this.$t('taskDetail.tableScenario'),
          this.$t('taskDetail.tablePrecondition'),
          this.$t('taskDetail.tableSteps'),
          this.$t('taskDetail.tableExpected'),
          this.$t('taskDetail.tablePriority')
        ])

        // 添加数据行
        this.testCases.forEach((testCase, index) => {
          worksheetData.push([
            testCase.caseId || `TC${String(index + 1).padStart(3, '0')}`,
            testCase.scenario || '',
            this.formatTextForList(testCase.precondition || ''),
            this.formatTextForList(testCase.steps || ''),
            this.formatTextForList(testCase.expected || ''),
            testCase.priority || 'P2'
          ])
        })

        // 创建工作表
        const worksheet = XLSX.utils.aoa_to_sheet(worksheetData)

        // 设置列宽
        const colWidths = [
          { wch: 15 }, // 测试用例编号
          { wch: 30 }, // 测试场景
          { wch: 25 }, // 前置条件
          { wch: 50 }, // 操作步骤（增加宽度）
          { wch: 40 }, // 预期结果（增加宽度）
          { wch: 10 }  // 优先级
        ]
        worksheet['!cols'] = colWidths

        // 为所有单元格添加自动换行样式
        const range = XLSX.utils.decode_range(worksheet['!ref'])
        for (let row = range.s.r; row <= range.e.r; row++) {
          for (let col = range.s.c; col <= range.e.c; col++) {
            const cellAddress = XLSX.utils.encode_cell({ r: row, c: col })
            if (!worksheet[cellAddress]) continue
            worksheet[cellAddress].s = {
              alignment: {
                wrapText: true,
                vertical: 'top'
              }
            }
          }
        }

        // 将工作表添加到工作簿
        XLSX.utils.book_append_sheet(workbook, worksheet, this.$t('taskDetail.excelSheetName'))

        // 生成文件名
        const dateStr = new Date().toISOString().slice(0, 10)
        const fileName = this.$t('taskDetail.excelFileName', { taskId: this.taskId, date: dateStr })

        // 导出文件
        XLSX.writeFile(workbook, fileName)

        ElMessage.success(this.$t('taskDetail.exportSuccess'))
      } catch (error) {
        console.error('Export Excel failed:', error)
        ElMessage.error(this.$t('taskDetail.exportFailed') + ': ' + (error.message || ''))
      } finally {
        this.isExporting = false
      }
    }
  }
}
</script>

<style scoped>
.task-detail {
  padding: 28px 24px;
  max-width: 1400px;
  margin: 0 auto;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Inter', Roboto, sans-serif;
}

/* Requirement description collapse card */
.requirement-description-card {
  margin-bottom: 20px;
  background: #FFFFFF;
  border-radius: 12px;
  border: 1px solid var(--aitest-border);
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  overflow: hidden;
}

.collapse-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 500;
  position: relative;
  padding-left: 20px;
}

.collapse-title::before { content: none; }

.title-icon { font-size: 18px; }

.title-text {
  color: #0F172A;
  font-weight: 600;
}

.title-hint {
  font-size: 13px;
  color: #94A3B8;
  font-weight: normal;
}

.requirement-content { padding: 16px 0; }

.requirement-text {
  background: #F8FAFC;
  border-radius: 8px;
  padding: 16px;
  line-height: 1.8;
  color: #475569;
  white-space: pre-wrap;
  word-wrap: break-word;
  max-height: 400px;
  overflow-y: auto;
  font-family: 'SF Mono', 'Monaco', 'Menlo', 'Consolas', monospace;
  font-size: 13px;
  border-left: 3px solid var(--aitest-primary);
}

.requirement-actions {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

.requirement-description-card :deep(.el-collapse) { border: none; }

.requirement-description-card :deep(.el-collapse-item__header) {
  background: #F8FAFC;
  border-bottom: 1px solid var(--aitest-border);
  padding: 16px 20px;
  font-size: 14px;
}

.requirement-description-card :deep(.el-collapse-item__header .el-icon) { display: none !important; }
.requirement-description-card :deep(.el-collapse-item__arrow) { display: none !important; }
.requirement-description-card :deep(.el-collapse-item__wrap) { border-bottom: none; }
.requirement-description-card :deep(.el-collapse-item__content) { padding: 0 20px 16px; }

/* Page header */
.page-header {
  margin-bottom: 20px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--aitest-border);
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.header-left { flex: 1; }

.page-header h2 {
  color: #0F172A;
  margin: 0 0 8px 0;
  font-size: 1.4rem;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.task-info {
  display: flex;
  gap: 20px;
  align-items: center;
}

.task-id {
  color: var(--aitest-text-2);
  font-family: 'SF Mono', 'Monaco', 'Menlo', 'Consolas', monospace;
  font-size: 0.85rem;
}

.task-status {
  padding: 3px 12px;
  border-radius: 4px;
  font-size: 0.82rem;
  font-weight: 600;
}

.task-status.completed { background: #F0FDF4; color: #059669; }

.header-actions { display: flex; gap: 10px; }

.export-btn {
  background: #059669;
  color: #FFFFFF;
  border: none;
  padding: 9px 20px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.85rem;
  font-weight: 600;
  transition: all 0.15s;
  white-space: nowrap;
}

.export-btn:hover:not(:disabled) { background: #047857; }
.export-btn:disabled { background: #CBD5E1; cursor: not-allowed; }

/* Batch actions */
.batch-actions {
  background: #FFFFFF;
  border-radius: 12px;
  padding: 16px 20px;
  margin-bottom: 20px;
  border: 1px solid var(--aitest-border);
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.selection-info {
  display: flex;
  align-items: center;
  gap: 15px;
}

.select-all {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.selected-count { color: var(--aitest-primary); font-weight: 600; }

.batch-buttons { display: flex; gap: 10px; }

.batch-adopt-btn, .batch-discard-btn {
  padding: 8px 16px;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.85rem;
  font-weight: 500;
  transition: all 0.15s;
}

.batch-adopt-btn { background: #059669; color: #FFFFFF; }
.batch-adopt-btn:hover:not(:disabled) { background: #047857; }
.batch-discard-btn { background: #DC2626; color: #FFFFFF; }
.batch-discard-btn:hover:not(:disabled) { background: #B91C1C; }
.batch-adopt-btn:disabled, .batch-discard-btn:disabled { background: #CBD5E1; cursor: not-allowed; }

/* Test cases table */
.testcases-table {
  background: #FFFFFF;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid var(--aitest-border);
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}

.table-header {
  display: grid;
  grid-template-columns: 60px 120px 1fr 1fr 1fr 1fr 80px 150px;
  background: #F8FAFC;
  font-weight: 600;
  color: var(--aitest-text-2);
}

.table-body .table-row {
  display: grid;
  grid-template-columns: 60px 120px 1fr 1fr 1fr 1fr 80px 150px;
  border-bottom: 1px solid var(--aitest-surface-subtle);
  transition: background 0.15s;
}

.table-row:hover { background: #F8FAFC; }

.header-cell, .body-cell {
  padding: 14px 8px;
  display: flex;
  align-items: flex-start;
  border-right: 1px solid var(--aitest-surface-subtle);
  word-break: break-word;
  min-height: 56px;
}

.text-truncate {
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  white-space: pre-wrap;
  line-height: 1.6;
  word-break: break-word;
}

.checkbox-cell { justify-content: center; }
.header-cell:last-child, .body-cell:last-child { border-right: none; }

.priority-tag {
  padding: 3px 8px;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
}

.priority-tag.low { background: #F0FDF4; color: #059669; }
.priority-tag.p3 { background: #F0FDF4; color: #059669; }
.priority-tag.medium { background: #EFF6FF; color: var(--aitest-primary); }
.priority-tag.p2 { background: #EFF6FF; color: var(--aitest-primary); }
.priority-tag.high { background: #FFFBEB; color: #D97706; }
.priority-tag.p1 { background: #FFFBEB; color: #D97706; }
.priority-tag.critical { background: #FEF2F2; color: #DC2626; }
.priority-tag.p0 { background: #FEF2F2; color: #DC2626; }

.action-buttons { display: flex; gap: 5px; flex-wrap: wrap; }

.view-btn, .adopt-btn, .discard-btn {
  padding: 4px 8px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.75rem;
  font-weight: 500;
  transition: all 0.15s;
}

.view-btn { background: var(--aitest-primary); color: #FFFFFF; }
.view-btn:hover { background: var(--aitest-primary-hover); }
.adopt-btn { background: #059669; color: #FFFFFF; }
.adopt-btn:hover { background: #047857; }
.discard-btn { background: #DC2626; color: #FFFFFF; }
.discard-btn:hover { background: #B91C1C; }

/* Pagination */
.pagination-section {
  margin-top: 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #FFFFFF;
  padding: 14px 20px;
  border-radius: 10px;
  border: 1px solid var(--aitest-border);
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}

.pagination-controls {
  display: flex;
  align-items: center;
  gap: 20px;
}

.page-size-selector {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pagination-buttons {
  display: flex;
  align-items: center;
  gap: 12px;
}

.pagination-buttons button {
  padding: 6px 12px;
  border: 1.5px solid var(--aitest-border);
  background: #FFFFFF;
  cursor: pointer;
  border-radius: 6px;
  color: #475569;
  font-size: 0.85rem;
  transition: all 0.15s;
}

.pagination-buttons button:hover:not(:disabled) { background: var(--aitest-surface-subtle); }
.pagination-buttons button:disabled { color: #CBD5E1; cursor: not-allowed; }

/* Case detail modal */
.case-detail-modal {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(15, 23, 42, 0.5);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: #FFFFFF;
  border-radius: 14px;
  max-width: 800px;
  width: 90%;
  max-height: 80vh;
  overflow-y: auto;
  border: 1px solid var(--aitest-border);
  box-shadow: 0 25px 50px rgba(0,0,0,0.12);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid var(--aitest-border);
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

.close-btn:hover { color: #0F172A; background: var(--aitest-surface-subtle); }

.modal-body { padding: 24px; }

.detail-item { margin-bottom: 18px; }

.detail-item label {
  font-weight: 600;
  color: var(--aitest-text-2);
  display: block;
  margin-bottom: 6px;
  font-size: 0.85rem;
}

.detail-item span, .detail-item p { color: #475569; line-height: 1.6; }

.test-steps {
  white-space: pre-line;
  background: #F8FAFC;
  padding: 14px;
  border-radius: 8px;
  border-left: 3px solid var(--aitest-primary);
}

.loading-state, .error-state, .empty-state {
  text-align: center;
  padding: 60px 20px;
  color: var(--aitest-text-2);
}

.error-state h3, .empty-state h3 { color: #0F172A; margin-bottom: 10px; }

.error-state a { color: var(--aitest-primary); text-decoration: none; }
.error-state a:hover { text-decoration: underline; }

/* Edit mode */
.edit-mode {
  .form-item { margin-bottom: 18px; }
  .form-item label {
    font-weight: 600;
    color: var(--aitest-text-2);
    display: block;
    margin-bottom: 6px;
  }
  .readonly-field {
    color: #475569;
    padding: 8px 12px;
    background: #F8FAFC;
    border-radius: 6px;
    display: inline-block;
  }
}

/* Modal footer */
.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 24px;
  border-top: 1px solid var(--aitest-border);
  background: #F8FAFC;
  border-radius: 0 0 14px 14px;
}

.action-btn {
  padding: 9px 20px;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.15s;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.edit-btn { background: var(--aitest-primary); color: #FFFFFF; }
.edit-btn:hover { background: var(--aitest-primary-hover); }

.save-btn { background: #059669; color: #FFFFFF; }
.save-btn:hover:not(:disabled) { background: #047857; }
.save-btn:disabled { opacity: 0.6; cursor: not-allowed; }

.cancel-btn { background: var(--aitest-surface-subtle); color: #475569; border: 1.5px solid var(--aitest-border); }
.cancel-btn:hover:not(:disabled) { background: var(--aitest-surface-subtle); }

.close-btn-footer { background: var(--aitest-surface-subtle); color: #475569; border: 1.5px solid var(--aitest-border); }
.close-btn-footer:hover { background: var(--aitest-surface-subtle); }

.task-chip {
  font-size: 0.78rem;
  color: var(--aitest-text-2);
  background: var(--aitest-surface-subtle);
  border: 1px solid var(--aitest-border);
  padding: 2px 10px;
  border-radius: 20px;
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 流式生成面板 */
.streaming-panel {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
}
.stream-steps {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  font-size: 0.75rem;
  color: #64748b;
}
.mini-step {
  padding: 4px 10px;
  border-radius: 12px;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
}
.mini-step.active {
  background: var(--aitest-primary, #409eff);
  color: #fff;
  border-color: transparent;
}
.stream-status {
  font-size: 0.8rem;
  color: #475569;
  margin-bottom: 12px;
}
.stream-section {
  margin-top: 12px;
}
.stream-section-title {
  font-weight: 600;
  font-size: 0.85rem;
  margin-bottom: 6px;
  color: #334155;
}
.stream-content {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 10px 12px;
  font-size: 0.82rem;
  line-height: 1.7;
  color: #475569;
  max-height: 320px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
}
.stream-cards {
  display: grid;
  gap: 8px;
  margin-bottom: 10px;
}
.stream-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-left: 3px solid var(--aitest-primary, #409eff);
  border-radius: 6px;
  padding: 8px 12px;
  font-size: 0.8rem;
}
.stream-card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}
.stream-card-id {
  font-weight: 600;
  color: #334155;
}
.stream-card-scenario {
  color: #475569;
  margin-bottom: 4px;
}
.stream-card-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  color: #64748b;
}
.review-feedback-section {
  background: #f0f9ff;
  border: 1px solid #bae6fd;
  border-radius: 8px;
  padding: 14px 16px;
  margin-bottom: 16px;
}
.review-feedback-title {
  font-weight: 600;
  font-size: 0.85rem;
  color: #075985;
  margin-bottom: 8px;
}
.terminal-state {
  padding: 24px;
  text-align: center;
}
</style>

<style>
/* 全局样式：隐藏Element Plus折叠面板的默认箭头图标 */
.requirement-description-card .el-collapse-item__header .el-icon {
  display: none !important;
}

.requirement-description-card .el-collapse-item__arrow {
  display: none !important;
}

/* 针对Element Plus不同版本的箭头图标 */
.requirement-description-card .el-collapse-item__header .el-collapse-item__arrow {
  display: none !important;
}

.requirement-description-card .el-collapse-item__header .el-icon-arrow-right {
  display: none !important;
}

.requirement-description-card .el-collapse-item__header .el-icon-arrow-left {
  display: none !important;
}
</style>