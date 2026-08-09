<template>
  <div class="task-detail">
    <div class="page-header">
      <div class="header-left">
        <h2 class="page-title">{{ $t('taskDetail.title') }} <span v-if="task.title">- {{ task.title }}</span></h2>
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

      <!-- 生成中：初版用例预览（JSONL 解析为卡片；非 JSON 输出时回退展示原文） -->
      <div v-if="streamedContent && !streamedReviewContent && !finalCasesStream" class="stream-section">
        <div class="stream-section-title">
          {{ $t('taskDetail.generatedContent') }}<template v-if="streamedWriterCases.length">（{{ streamedWriterCases.length }}）</template>
        </div>
        <div v-if="streamedWriterCases.length" class="stream-cards">
          <div v-for="(tc, idx) in streamedWriterCases" :key="idx" class="stream-card">
            <div class="stream-card-head">
              <span class="stream-card-id">{{ tc.caseId || 'TC' + String(idx + 1).padStart(3, '0') }}</span>
              <span class="priority-tag" :class="(tc.priority || 'P2').toLowerCase()">{{ tc.priority || 'P2' }}</span>
            </div>
            <div class="stream-card-scenario">{{ tc.scenario }}</div>
            <div v-if="tc.stepsList && tc.stepsList.length" class="stream-card-steps">
              <div v-for="(step, si) in tc.stepsList" :key="si" class="stream-step">
                <span class="step-order">{{ +si + 1 }}.</span>
                <span class="step-desc">{{ step.desc || '—' }}</span>
                <span v-if="step.expect" class="step-expect">{{ $t('taskDetail.tableExpected') }}：{{ step.expect }}</span>
              </div>
            </div>
            <div v-else-if="tc.steps || tc.expected" class="stream-card-body">
              <span v-if="tc.steps">{{ $t('taskDetail.tableSteps') }}：{{ tc.steps }}</span>
              <span v-if="tc.expected">{{ $t('taskDetail.tableExpected') }}：{{ tc.expected }}</span>
            </div>
          </div>
        </div>
        <div v-else class="stream-content" v-html="formatMarkdown(formatStreamForDisplay(streamedContent))"></div>
      </div>

      <div v-if="streamedReviewContent" class="stream-section">
        <div class="stream-section-title">{{ $t('taskDetail.reviewFeedback') }}</div>
        <div class="stream-content" v-html="formatMarkdown(streamedReviewContent)"></div>
      </div>

      <!-- 最终用例：JSONL 解析为卡片；非 JSON 输出时回退展示原文 -->
      <div v-if="finalCasesStream" class="stream-section">
        <div class="stream-section-title">{{ $t('taskDetail.finalCases') }}（{{ streamedCases.length }}）</div>
        <div v-if="streamedCases.length" class="stream-cards">
          <div v-for="(tc, idx) in streamedCases" :key="idx" class="stream-card">
            <div class="stream-card-head">
              <span class="stream-card-id">{{ tc.caseId || 'TC' + String(idx + 1).padStart(3, '0') }}</span>
              <span class="priority-tag" :class="(tc.priority || 'P2').toLowerCase()">{{ tc.priority || 'P2' }}</span>
            </div>
            <div class="stream-card-scenario">{{ tc.scenario }}</div>
            <div v-if="tc.stepsList && tc.stepsList.length" class="stream-card-steps">
              <div v-for="(step, si) in tc.stepsList" :key="si" class="stream-step">
                <span class="step-order">{{ +si + 1 }}.</span>
                <span class="step-desc">{{ step.desc || '—' }}</span>
                <span v-if="step.expect" class="step-expect">{{ $t('taskDetail.tableExpected') }}：{{ step.expect }}</span>
              </div>
            </div>
            <div v-else-if="tc.steps || tc.expected" class="stream-card-body">
              <span v-if="tc.steps">{{ $t('taskDetail.tableSteps') }}：{{ tc.steps }}</span>
              <span v-if="tc.expected">{{ $t('taskDetail.tableExpected') }}：{{ tc.expected }}</span>
            </div>
          </div>
        </div>
        <div v-else class="stream-content" v-html="formatMarkdown(formatStreamForDisplay(finalCasesStream))"></div>
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
      streamedCases: [],         // 流式解析出的最终用例卡片预览
      streamedWriterCases: [],   // 流式解析出的初版用例卡片预览（生成阶段）
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
    this.taskId = String(this.$route.params.taskId)
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
          this.streamedWriterCases = this.parseTestCases(this.streamedContent)
          this.currentStep = 2
        } else if (data.type === 'review_content') {
          this.streamedReviewContent += data.content
          this.streamedReviewContent = this.streamedReviewContent.replace(/\n+$/, '')
          this.currentStep = 3
        } else if (data.type === 'final_content') {
          this.finalCasesStream += data.content
          this.streamedCases = this.parseTestCases(this.finalCasesStream)
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

      // JSONL 解析（每行一个独立 JSON），与 writer/revise 的 JSONL 输出约定一致
      // 流式增量下解析失败的残缺行直接跳过，等待补齐后再整体重解析
      const testCases = []
      for (const line of content.split('\n')) {
        const trimmed = line.trim()
        if (!trimmed) continue
        try {
          const obj = JSON.parse(trimmed)
          if (!(obj && typeof obj === 'object') || (obj.case_id === undefined && obj.title === undefined)) continue
          const stepsList = Array.isArray(obj.steps) ? obj.steps.map(s => ({ desc: s.desc || '', expect: s.expect || '' })) : []
          testCases.push({
            caseId: obj.case_id || '',
            scenario: obj.title || '',
            precondition: obj.precondition || '',
            stepsList,
            steps: stepsList.map(s => `${s.desc}\n预期: ${s.expect}`).join('\n'),
            expected: stepsList.map(s => s.expect).filter(Boolean).join('\n'),
            priority: obj.priority || 'P2',
          })
        } catch (e) {
          // 不完整行跳过，等待下次解析
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
        // JSONL 原生保留换行，无需再转换为 <br>
        const updatedCase = {
          ...this.selectedCase,
          scenario: this.editForm.scenario,
          precondition: this.editForm.precondition,
          steps: this.editForm.steps,
          expected: this.editForm.expected,
          priority: this.editForm.priority
        }

        // 更新本地数组中的数据
        const index = this.testCases.findIndex(tc => tc === this.selectedCase)
        if (index !== -1) {
          this.testCases[index] = updatedCase
          this.selectedCase = updatedCase
        }

        // 重新生成 JSONL 格式的测试用例字符串
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

    // 将 testCases 数组重新生成为 JSONL 字符串（与后端 _reconstruct_test_cases_content 一致）
    generateTestCasesString() {
      if (this.testCases.length === 0) return ''

      return this.testCases.map((testCase) => JSON.stringify({
        case_id: testCase.caseId || '',
        title: testCase.scenario || '',
        precondition: this.convertBrToNewline(testCase.precondition || ''),
        steps: Array.isArray(testCase.stepsList) && testCase.stepsList.length
          ? testCase.stepsList
          : this.stepsStringToArray(testCase.steps || '', testCase.expected || ''),
        priority: testCase.priority || '',
        test_type: testCase.test_type || '',
        module: testCase.module || '',
      })).join('\n')
    },

    // 将展示用的 steps 多行文本（"desc\n预期: expect"）还原为 [{desc, expect}]
    // 兼容 <br> 换行；无描述只有预期时生成单步
    stepsStringToArray(stepsStr, expected) {
      const raw = this.convertBrToNewline(stepsStr)
      if (!raw) {
        return expected ? [{ desc: '', expect: this.convertBrToNewline(expected) }] : []
      }

      const steps = []
      for (const line of raw.split('\n')) {
        const expectMatch = line.match(/^\s*预期[:：]\s*(.*)$/)
        if (expectMatch && steps.length) {
          steps[steps.length - 1].expect = expectMatch[1].trim()
        } else if (line.trim()) {
          steps.push({ desc: line.trim(), expect: '' })
        }
      }

      // 旧数据的整行“预期结果”兜底挂到最后一步（与后端 _reconstruct 行为一致）
      if (expected && steps.length && !steps[steps.length - 1].expect) {
        steps[steps.length - 1].expect = this.convertBrToNewline(expected)
      }
      return steps
    },

    // 将HTML的<br>标签转换为换行符
    convertBrToNewline(text) {
      if (!text) return ''
      return text.replace(/<br\s*\/?>/gi, '\n')
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
  padding: 28px var(--aitest-space-6);
  max-width: 1400px;
  margin: 0 auto;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Inter', Roboto, sans-serif;
}

/* Requirement description collapse card */
.requirement-description-card {
  margin-bottom: var(--aitest-space-5);
  background: var(--aitest-surface);
  border-radius: 12px;
  border: 1px solid var(--aitest-border);
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  overflow: hidden;
}

.collapse-title {
  display: flex;
  align-items: center;
  gap: var(--aitest-space-2);
  font-size: var(--aitest-font-size-md);
  font-weight: 500;
  position: relative;
  padding-left: var(--aitest-space-5);
}

.collapse-title::before { content: none; }

.title-icon { font-size: 18px; }

.title-text {
  color: var(--aitest-text-1);
  font-weight: 600;
}

.title-hint {
  font-size: var(--aitest-font-size-base);
  color: var(--aitest-text-3);
  font-weight: normal;
}

.requirement-content { padding: var(--aitest-space-4) 0; }

.requirement-text {
  background: var(--aitest-canvas);
  border-radius: var(--aitest-radius-lg);
  padding: var(--aitest-space-4);
  line-height: 1.8;
  color: var(--aitest-text-2);
  white-space: pre-wrap;
  word-wrap: break-word;
  max-height: 400px;
  overflow-y: auto;
  font-family: 'SF Mono', 'Monaco', 'Menlo', 'Consolas', monospace;
  font-size: var(--aitest-font-size-base);
  border-left: 3px solid var(--aitest-primary);
}

.requirement-actions {
  margin-top: var(--aitest-space-3);
  display: flex;
  justify-content: flex-end;
}

.requirement-description-card :deep(.el-collapse) { border: none; }

.requirement-description-card :deep(.el-collapse-item__header) {
  background: var(--aitest-canvas);
  border-bottom: 1px solid var(--aitest-border);
  padding: var(--aitest-space-4) var(--aitest-space-5);
  font-size: var(--aitest-font-size-md);
}

.requirement-description-card :deep(.el-collapse-item__header .el-icon) { display: none !important; }
.requirement-description-card :deep(.el-collapse-item__arrow) { display: none !important; }
.requirement-description-card :deep(.el-collapse-item__wrap) { border-bottom: none; }
.requirement-description-card :deep(.el-collapse-item__content) { padding: 0 var(--aitest-space-5) var(--aitest-space-4); }

/* Page header */
.page-header {
  margin-bottom: var(--aitest-space-5);
  padding-bottom: var(--aitest-space-4);
  border-bottom: 1px solid var(--aitest-border);
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.header-left { flex: 1; }

.page-header .page-title {
  color: var(--aitest-text-1);
  margin: 0 0 var(--aitest-space-2) 0;
  font-size: 1.4rem;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.task-info {
  display: flex;
  gap: var(--aitest-space-5);
  align-items: center;
}

.task-id {
  color: var(--aitest-text-2);
  font-family: 'SF Mono', 'Monaco', 'Menlo', 'Consolas', monospace;
  font-size: 0.85rem;
}

.task-status {
  padding: 3px var(--aitest-space-3);
  border-radius: var(--aitest-radius-sm);
  font-size: 0.82rem;
  font-weight: 600;
}

.task-status.completed { background: var(--aitest-success-bg); color: var(--aitest-success); }

.header-actions { display: flex; gap: var(--aitest-space-3); }

.export-btn {
  background: var(--aitest-success);
  color: #FFFFFF;
  border: none;
  padding: 9px var(--aitest-space-5);
  border-radius: var(--aitest-radius-lg);
  cursor: pointer;
  font-size: 0.85rem;
  font-weight: 600;
  transition: all 0.15s;
  white-space: nowrap;
}

.export-btn:hover:not(:disabled) { background: #047857; }
.export-btn:disabled { background: var(--aitest-border-strong); cursor: not-allowed; }

/* Batch actions */
.batch-actions {
  background: var(--aitest-surface);
  border-radius: 12px;
  padding: var(--aitest-space-4) var(--aitest-space-5);
  margin-bottom: var(--aitest-space-5);
  border: 1px solid var(--aitest-border);
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.selection-info {
  display: flex;
  align-items: center;
  gap: var(--aitest-space-4);
}

.select-all {
  display: flex;
  align-items: center;
  gap: var(--aitest-space-2);
  cursor: pointer;
}

.selected-count { color: var(--aitest-primary); font-weight: 600; }

.batch-buttons { display: flex; gap: var(--aitest-space-3); }

.batch-adopt-btn, .batch-discard-btn {
  padding: var(--aitest-space-2) var(--aitest-space-4);
  border: none;
  border-radius: var(--aitest-radius-lg);
  cursor: pointer;
  font-size: 0.85rem;
  font-weight: 500;
  transition: all 0.15s;
}

.batch-adopt-btn { background: var(--aitest-success); color: #FFFFFF; }
.batch-adopt-btn:hover:not(:disabled) { background: #047857; }
.batch-discard-btn { background: var(--aitest-danger); color: #FFFFFF; }
.batch-discard-btn:hover:not(:disabled) { background: #B91C1C; }
.batch-adopt-btn:disabled, .batch-discard-btn:disabled { background: var(--aitest-border-strong); cursor: not-allowed; }

/* Test cases table */
.testcases-table {
  background: var(--aitest-surface);
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid var(--aitest-border);
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}

.table-header {
  display: grid;
  grid-template-columns: 60px 120px 1fr 1fr 1fr 1fr 80px 150px;
  background: var(--aitest-canvas);
  font-weight: 600;
  color: var(--aitest-text-2);
}

.table-body .table-row {
  display: grid;
  grid-template-columns: 60px 120px 1fr 1fr 1fr 1fr 80px 150px;
  border-bottom: 1px solid var(--aitest-surface-subtle);
  transition: background 0.15s;
}

.table-row:hover { background: var(--aitest-canvas); }

.header-cell, .body-cell {
  padding: var(--aitest-space-4) var(--aitest-space-2);
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
  padding: 3px var(--aitest-space-2);
  border-radius: var(--aitest-radius-sm);
  font-size: 0.75rem;
  font-weight: 600;
}

.priority-tag.low { background: var(--aitest-success-bg); color: var(--aitest-success); }
.priority-tag.p3 { background: var(--aitest-success-bg); color: var(--aitest-success); }
.priority-tag.medium { background: var(--aitest-info-bg); color: var(--aitest-primary); }
.priority-tag.p2 { background: var(--aitest-info-bg); color: var(--aitest-primary); }
.priority-tag.high { background: var(--aitest-warning-bg); color: var(--aitest-warning); }
.priority-tag.p1 { background: var(--aitest-warning-bg); color: var(--aitest-warning); }
.priority-tag.critical { background: var(--aitest-danger-bg); color: var(--aitest-danger); }
.priority-tag.p0 { background: var(--aitest-danger-bg); color: var(--aitest-danger); }

.action-buttons { display: flex; gap: var(--aitest-space-1); flex-wrap: wrap; }

.view-btn, .adopt-btn, .discard-btn {
  padding: var(--aitest-space-1) var(--aitest-space-2);
  border: none;
  border-radius: var(--aitest-radius-sm);
  cursor: pointer;
  font-size: 0.75rem;
  font-weight: 500;
  transition: all 0.15s;
}

.view-btn { background: var(--aitest-primary); color: #FFFFFF; }
.view-btn:hover { background: var(--aitest-primary-hover); }
.adopt-btn { background: var(--aitest-success); color: #FFFFFF; }
.adopt-btn:hover { background: #047857; }
.discard-btn { background: var(--aitest-danger); color: #FFFFFF; }
.discard-btn:hover { background: #B91C1C; }

/* Pagination */
.pagination-section {
  margin-top: var(--aitest-space-5);
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--aitest-surface);
  padding: var(--aitest-space-4) var(--aitest-space-5);
  border-radius: 10px;
  border: 1px solid var(--aitest-border);
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}

.pagination-controls {
  display: flex;
  align-items: center;
  gap: var(--aitest-space-5);
}

.page-size-selector {
  display: flex;
  align-items: center;
  gap: var(--aitest-space-2);
}

.pagination-buttons {
  display: flex;
  align-items: center;
  gap: var(--aitest-space-3);
}

.pagination-buttons button {
  padding: var(--aitest-space-2) var(--aitest-space-3);
  border: 1.5px solid var(--aitest-border);
  background: var(--aitest-surface);
  cursor: pointer;
  border-radius: var(--aitest-radius);
  color: var(--aitest-text-2);
  font-size: 0.85rem;
  transition: all 0.15s;
}

.pagination-buttons button:hover:not(:disabled) { background: var(--aitest-surface-subtle); }
.pagination-buttons button:disabled { color: var(--aitest-border-strong); cursor: not-allowed; }

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
  background: var(--aitest-surface);
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
  padding: var(--aitest-space-5) var(--aitest-space-6);
  border-bottom: 1px solid var(--aitest-border);
}

.modal-header h3 { margin: 0; color: var(--aitest-text-1); font-weight: 700; }

.close-btn {
  background: none;
  border: none;
  font-size: 1.3rem;
  cursor: pointer;
  color: var(--aitest-text-3);
  padding: var(--aitest-space-1) var(--aitest-space-2);
  border-radius: var(--aitest-radius);
  transition: all 0.15s;
}

.close-btn:hover { color: var(--aitest-text-1); background: var(--aitest-surface-subtle); }

.modal-body { padding: var(--aitest-space-6); }

.detail-item { margin-bottom: var(--aitest-space-5); }

.detail-item label {
  font-weight: 600;
  color: var(--aitest-text-2);
  display: block;
  margin-bottom: var(--aitest-space-2);
  font-size: 0.85rem;
}

.detail-item span, .detail-item p { color: var(--aitest-text-2); line-height: 1.6; }

.test-steps {
  white-space: pre-line;
  background: var(--aitest-canvas);
  padding: var(--aitest-space-4);
  border-radius: var(--aitest-radius-lg);
  border-left: 3px solid var(--aitest-primary);
}

.loading-state, .error-state, .empty-state {
  text-align: center;
  padding: 60px var(--aitest-space-5);
  color: var(--aitest-text-2);
}

.error-state h3, .empty-state h3 { color: var(--aitest-text-1); margin-bottom: var(--aitest-space-3); }

.error-state a { color: var(--aitest-primary); text-decoration: none; }
.error-state a:hover { text-decoration: underline; }

/* Edit mode */
.edit-mode {
  .form-item { margin-bottom: var(--aitest-space-5); }
  .form-item label {
    font-weight: 600;
    color: var(--aitest-text-2);
    display: block;
    margin-bottom: var(--aitest-space-2);
  }
  .readonly-field {
    color: var(--aitest-text-2);
    padding: var(--aitest-space-2) var(--aitest-space-3);
    background: var(--aitest-canvas);
    border-radius: var(--aitest-radius);
    display: inline-block;
  }
}

/* Modal footer */
.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--aitest-space-3);
  padding: var(--aitest-space-4) var(--aitest-space-6);
  border-top: 1px solid var(--aitest-border);
  background: var(--aitest-canvas);
  border-radius: 0 0 14px 14px;
}

.action-btn {
  padding: 9px var(--aitest-space-5);
  border: none;
  border-radius: var(--aitest-radius-lg);
  cursor: pointer;
  font-size: var(--aitest-font-size-base);
  font-weight: 500;
  transition: all 0.15s;
  display: inline-flex;
  align-items: center;
  gap: var(--aitest-space-2);
}

.edit-btn { background: var(--aitest-primary); color: #FFFFFF; }
.edit-btn:hover { background: var(--aitest-primary-hover); }

.save-btn { background: var(--aitest-success); color: #FFFFFF; }
.save-btn:hover:not(:disabled) { background: #047857; }
.save-btn:disabled { opacity: 0.6; cursor: not-allowed; }

.cancel-btn { background: var(--aitest-surface-subtle); color: var(--aitest-text-2); border: 1.5px solid var(--aitest-border); }
.cancel-btn:hover:not(:disabled) { background: var(--aitest-surface-subtle); }

.close-btn-footer { background: var(--aitest-surface-subtle); color: var(--aitest-text-2); border: 1.5px solid var(--aitest-border); }
.close-btn-footer:hover { background: var(--aitest-surface-subtle); }

.task-chip {
  font-size: 0.78rem;
  color: var(--aitest-text-2);
  background: var(--aitest-surface-subtle);
  border: 1px solid var(--aitest-border);
  padding: 2px var(--aitest-space-3);
  border-radius: 20px;
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 流式生成面板 */
.streaming-panel {
  background: var(--aitest-canvas);
  border: 1px solid var(--aitest-border);
  border-radius: var(--aitest-radius-lg);
  padding: var(--aitest-space-4);
  margin-bottom: var(--aitest-space-4);
}
.stream-steps {
  display: flex;
  gap: var(--aitest-space-2);
  margin-bottom: var(--aitest-space-3);
  font-size: 0.75rem;
  color: var(--aitest-text-2);
}
.mini-step {
  padding: var(--aitest-space-1) var(--aitest-space-3);
  border-radius: 12px;
  background: var(--aitest-surface-subtle);
  border: 1px solid var(--aitest-border);
}
.mini-step.active {
  background: var(--aitest-primary, var(--el-color-primary));
  color: #fff;
  border-color: transparent;
}
.stream-status {
  font-size: 0.8rem;
  color: var(--aitest-text-2);
  margin-bottom: var(--aitest-space-3);
}
.stream-section {
  margin-top: var(--aitest-space-3);
}
.stream-section-title {
  font-weight: 600;
  font-size: 0.85rem;
  margin-bottom: var(--aitest-space-2);
  color: #334155;
}
.stream-content {
  background: var(--aitest-surface);
  border: 1px solid var(--aitest-border);
  border-radius: var(--aitest-radius);
  padding: var(--aitest-space-3) var(--aitest-space-3);
  font-size: 0.82rem;
  line-height: 1.7;
  color: var(--aitest-text-2);
  max-height: 320px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
}
.stream-cards {
  display: grid;
  gap: var(--aitest-space-2);
  margin-bottom: var(--aitest-space-3);
}
.stream-card {
  background: var(--aitest-surface);
  border: 1px solid var(--aitest-border);
  border-left: 3px solid var(--aitest-primary, var(--el-color-primary));
  border-radius: var(--aitest-radius);
  padding: var(--aitest-space-2) var(--aitest-space-3);
  font-size: 0.8rem;
}
.stream-card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--aitest-space-1);
}
.stream-card-id {
  font-weight: 600;
  color: #334155;
}
.stream-card-scenario {
  color: var(--aitest-text-2);
  margin-bottom: var(--aitest-space-1);
}
.stream-card-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  color: var(--aitest-text-2);
}
.stream-card-steps {
  display: flex;
  flex-direction: column;
  gap: 3px;
  margin-top: 2px;
}
.stream-step {
  display: flex;
  gap: var(--aitest-space-2);
  align-items: baseline;
  line-height: 1.6;
}
.step-order {
  flex: none;
  color: var(--aitest-text-3);
  font-family: 'SF Mono', 'Monaco', 'Menlo', 'Consolas', monospace;
  font-size: 0.72rem;
}
.step-desc {
  color: var(--aitest-text-2);
  word-break: break-word;
}
.step-expect {
  color: var(--aitest-text-2);
  word-break: break-word;
}
.review-feedback-section {
  background: #f0f9ff;
  border: 1px solid #bae6fd;
  border-radius: var(--aitest-radius-lg);
  padding: var(--aitest-space-4) var(--aitest-space-4);
  margin-bottom: var(--aitest-space-4);
}
.review-feedback-title {
  font-weight: 600;
  font-size: 0.85rem;
  color: #075985;
  margin-bottom: var(--aitest-space-2);
}
.terminal-state {
  padding: var(--aitest-space-6);
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