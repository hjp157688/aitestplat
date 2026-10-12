<template>
  <div class="page-container task-detail">
    <PageHeader :title="$t('taskDetail.title')" :desc="task.title">
      <template #actions>
        <el-button
          v-if="testCases.length > 0"
          type="primary"
          plain
          @click="exportToExcel"
          :loading="isExporting">
          {{ $t('taskDetail.exportBtn') }}
        </el-button>
      </template>
    </PageHeader>

    <div class="task-info">
      <span class="task-id">{{ $t('taskDetail.taskId') }}: {{ taskId }}</span>
      <span class="status-tag" :class="task.status">
        <span class="status-tag__dot"></span>
        {{ getStatusText(task.status) }}
      </span>
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
            <div class="requirement-text" v-html="task.requirement_text"></div>
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

      <!-- WeKnora 智能体（思考过程 vs 结果，WeKnora 风格） -->
      <WeKnoraAgentTrace
        v-if="task.weknora_answer || (task.weknora_references && task.weknora_references.length) || (task.weknora_steps && task.weknora_steps.length)"
        :answer="task.weknora_answer || ''"
        :references="task.weknora_references || []"
        :steps="task.weknora_steps || []"
        class="stream-section"
      />

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
          <span class="selected-count" v-if="selectedCases.length > 0">
            {{ $t('taskDetail.selectedCount', { count: selectedCases.length }) }}
          </span>
        </div>
        <div class="batch-buttons">
          <el-button
            type="success"
            :disabled="selectedCases.length === 0"
            @click="batchAdopt">
            {{ $t('taskDetail.batchAdopt', { count: selectedCases.length }) }}
          </el-button>
          <el-button
            type="danger"
            plain
            :disabled="selectedCases.length === 0"
            @click="batchDiscard">
            {{ $t('taskDetail.batchDiscard', { count: selectedCases.length }) }}
          </el-button>
        </div>
      </div>

      <!-- 测试用例列表 -->
      <div class="testcases-table" v-if="testCases.length > 0">
        <el-table
          ref="caseTable"
          :data="paginatedTestCases"
          :row-key="caseRowKey"
          @selection-change="onSelectionChange"
          style="width: 100%">
          <el-table-column type="selection" width="46" reserve-selection />
          <el-table-column :label="$t('taskDetail.tableCaseId')" width="130">
            <template #default="scope">
              {{ scope.row.caseId || `TC${String(scope.$index + 1).padStart(3, '0')}` }}
            </template>
          </el-table-column>
          <el-table-column :label="$t('taskDetail.tableScenario')" min-width="200" show-overflow-tooltip>
            <template #default="scope">{{ scope.row.scenario }}</template>
          </el-table-column>
          <el-table-column :label="$t('taskDetail.tablePrecondition')" min-width="140">
            <template #default="scope">
              <span class="cell-clamp">{{ formatTextForList(scope.row.precondition) }}</span>
            </template>
          </el-table-column>
          <!-- 操作步骤列：仅展示步骤描述（编号 + 描述），预期移入预期列，不再混入 -->
          <el-table-column :label="$t('taskDetail.tableSteps')" min-width="240">
            <template #default="scope">
              <span class="cell-clamp cell-clamp-5" :title="stepsText(scope.row)">{{ stepsText(scope.row) }}</span>
            </template>
          </el-table-column>
          <!-- 预期结果列：每步预期与步骤行对齐展示 -->
          <el-table-column :label="$t('taskDetail.tableExpected')" min-width="200">
            <template #default="scope">
              <span class="cell-clamp cell-clamp-5" :title="expectText(scope.row)">{{ expectText(scope.row) }}</span>
            </template>
          </el-table-column>
          <el-table-column :label="$t('taskDetail.tablePriority')" width="90" align="center">
            <template #default="scope">
              <el-tag size="small" :type="priorityTagType(scope.row.priority)">{{ scope.row.priority || 'P2' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="$t('taskDetail.tableActions')" width="200" fixed="right">
            <template #default="scope">
              <div class="action-buttons">
                <el-button link type="primary" size="small" @click="viewCaseDetail(scope.row, scope.$index)">{{ $t('taskDetail.viewDetail') }}</el-button>
                <el-button link type="success" size="small" @click="adoptSingleCase(scope.row, scope.$index)">{{ $t('taskDetail.adopt') }}</el-button>
                <el-button link type="danger" size="small" @click="discardSingleCase(scope.row, scope.$index)">{{ $t('taskDetail.discard') }}</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div v-else class="empty-state">
        <h3>{{ $t('taskDetail.emptyTitle') }}</h3>
        <p>{{ $t('taskDetail.emptyHint') }}</p>
      </div>

      <!-- 分页 -->
      <div v-if="testCases.length > 0" class="pagination-section">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50]"
          :total="testCases.length"
          layout="total, sizes, prev, pager, next" />
      </div>
      </template>
    </div>

    <!-- 用例详情弹窗 -->
    <el-dialog
      v-model="showCaseDetail"
      :title="isEditing ? $t('taskDetail.modalEditTitle') : $t('taskDetail.modalViewTitle')"
      width="760px"
      @close="closeCaseDetail">

      <!-- 查看模式 -->
      <div v-if="!isEditing" class="detail-list">
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
          <!-- 结构化步骤：按步渲染 desc + 内联预期（与流式卡片一致），不再把预期重复到下方字段 -->
          <div v-if="selectedCase.stepsList && selectedCase.stepsList.length" class="detail-steps">
            <div v-for="(step, si) in selectedCase.stepsList" :key="si" class="stream-step">
              <span class="step-order">{{ +si + 1 }}.</span>
              <span class="step-desc">{{ step.desc || '—' }}</span>
              <span v-if="step.expect" class="step-expect">{{ $t('taskDetail.tableExpected') }}：{{ step.expect }}</span>
            </div>
          </div>
          <!-- 旧文本格式（无 stepsList）回退为多行文本展示 -->
          <p v-else class="test-steps" v-html="formatMarkdown(selectedCase.steps)"></p>
        </div>
        <!-- 结构化步骤已内联预期，仅在无 stepsList 且有独立预期文本时才展示该字段 -->
        <div class="detail-item" v-if="!(selectedCase.stepsList && selectedCase.stepsList.length) && selectedCase.expected">
          <label>{{ $t('taskDetail.labelExpected') }}</label>
          <p v-html="formatMarkdown(selectedCase.expected)"></p>
        </div>
        <div class="detail-item">
          <label>{{ $t('taskDetail.labelPriority') }}</label>
          <el-tag size="small" :type="priorityTagType(selectedCase.priority)">{{ selectedCase.priority || 'P2' }}</el-tag>
        </div>
      </div>

      <!-- 编辑模式 -->
      <div v-else class="edit-mode">
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
          <!-- 与测试用例页一致：每行一步骤 + 对应预期，成对编辑 -->
          <div class="steps-editor">
            <div v-for="(step, idx) in editForm.stepsList" :key="idx" class="step-row">
              <span class="step-index">{{ idx + 1 }}</span>
              <el-input v-model="step.desc" type="textarea" :autosize="{ minRows: 1, maxRows: 4 }" :placeholder="$t('testcase.stepDescPlaceholder')" />
              <el-input v-model="step.expect" type="textarea" :autosize="{ minRows: 1, maxRows: 4 }" :placeholder="$t('testcase.stepExpectPlaceholder')" />
              <el-button type="danger" link class="step-remove-btn" :title="$t('taskDetail.deleteStep')" @click="removeStepRow(idx)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </div>
            <el-button type="primary" link class="add-step-btn" @click="addStepRow">
              <el-icon><Plus /></el-icon>
              {{ $t('testcase.addStep') }}
            </el-button>
          </div>
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
      <template #footer>
        <template v-if="!isEditing">
          <el-button type="primary" @click="startEdit">{{ $t('taskDetail.btnEdit') }}</el-button>
          <el-button @click="closeCaseDetail">{{ $t('taskDetail.btnClose') }}</el-button>
        </template>
        <template v-else>
          <el-button type="primary" :loading="isSaving" @click="saveEdit">{{ $t('taskDetail.btnSave') }}</el-button>
          <el-button @click="cancelEdit" :disabled="isSaving">{{ $t('taskDetail.btnCancel') }}</el-button>
        </template>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import api from '@/utils/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { DocumentCopy, Delete, Plus } from '@element-plus/icons-vue'
import * as XLSX from 'xlsx'
import WeKnoraAgentTrace from '@/components/WeKnoraAgentTrace.vue'
import PageHeader from '@/components/common/PageHeader.vue'

export default {
  name: 'TaskDetail',
  components: { WeKnoraAgentTrace, PageHeader },
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
        stepsList: [],
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
    totalPages() {
      return Math.ceil(this.testCases.length / this.pageSize)
    },

    paginatedTestCases() {
      const start = (this.currentPage - 1) * this.pageSize
      const end = start + this.pageSize
      return this.testCases.slice(start, end)
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
        if (['pending', 'generating', 'retrieving', 'reviewing', 'revising'].includes(this.task.status)) {
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
          if (data.status === 'retrieving') {
            // WeKnora 知识检索阶段（生成开始前）
            this.currentStep = 2
          } else if (data.status === 'generating') {
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

    // 提取内容中所有"已闭合"的 JSON 对象（兼容一行 JSONL 与跨行 pretty 对象），
    // 逻辑与需求分析控制台 RequirementAnalysisView._extractJsonObjects 对齐
    extractJsonObjects(content) {
      const out = []
      let depth = 0
      let start = -1
      let inStr = false
      let esc = false
      for (let i = 0; i < content.length; i++) {
        const c = content[i]
        if (inStr) {
          if (esc) esc = false
          else if (c === '\\') esc = true
          else if (c === '"') inStr = false
          continue
        }
        if (c === '"') { inStr = true; continue }
        if (c === '{') { if (depth === 0) start = i; depth++ }
        else if (c === '}') { if (depth > 0) { depth--; if (depth === 0 && start >= 0) { out.push(content.slice(start, i + 1).trim()); start = -1 } } }
      }
      return out
    },

    parseTestCases(content) {
      if (!content) return []

      // JSONL / 多行缩进 JSON 统一解析（AI 偶发输出 pretty-print，
      // 逐行 JSON.parse 会整行失败导致"最终用例无"），与 writer/revise 输出约定一致。
      // 流式增量下解析失败的残缺块直接跳过，等待补齐后再整体重解析
      const testCases = []
      for (const seg of this.extractJsonObjects(content)) {
        try {
          const obj = JSON.parse(seg)
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
          // 不完整对象跳过，等待下次解析
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

    // el-table 选择变化（配合 reserve-selection 跨页保留）
    onSelectionChange(rows) {
      this.selectedCases = rows
    },

    // 行 key：用例无稳定 id，用编号+场景+步骤组合标识
    caseRowKey(row) {
      return `${row.caseId || ''}|${row.scenario || ''}|${row.steps || ''}`
    },

    // 优先级 → el-tag type（P0 危险 / P1 警告 / P2 主色 / P3 信息）
    priorityTagType(priority) {
      const map = { P0: 'danger', P1: 'warning', P2: 'primary', P3: 'info' }
      return map[priority] || 'info'
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
        if (this.$refs.caseTable) this.$refs.caseTable.clearSelection()

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
            if (this.$refs.caseTable) this.$refs.caseTable.clearSelection()
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
        stepsList: [],
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
        // 步骤按行编辑：优先用结构化 stepsList，旧文本记录用 stepsStringToArray 还原
        stepsList: this.buildEditableSteps(this.selectedCase),
        // 直接使用原始优先级值，不转换
        priority: this.selectedCase.priority || 'P2'
      }
    },

    // 构建可编辑的步骤数组（深拷贝，避免直接改动 selectedCase；旧文本格式回退解析）
    buildEditableSteps(testCase) {
      if (testCase.stepsList && testCase.stepsList.length) {
        return testCase.stepsList.map(s => ({ desc: s.desc || '', expect: s.expect || '' }))
      }
      return this.stepsStringToArray(testCase.steps || '', testCase.expected || '')
    },

    addStepRow() {
      if (!Array.isArray(this.editForm.stepsList)) this.editForm.stepsList = []
      this.editForm.stepsList.push({ desc: '', expect: '' })
    },

    removeStepRow(idx) {
      this.editForm.stepsList.splice(idx, 1)
    },

    // 取消编辑
    cancelEdit() {
      this.isEditing = false
      this.editForm = {
        caseId: '',
        scenario: '',
        precondition: '',
        stepsList: [],
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
        // 步骤按行编辑后，重组成结构化列表 + 文本形态，供展示与 generateTestCasesString 使用
        const stepsList = (this.editForm.stepsList || [])
          .filter(s => (s.desc || '').trim() || (s.expect || '').trim())
          .map(s => ({ desc: (s.desc || '').trim(), expect: (s.expect || '').trim() }))

        // JSONL 原生保留换行，无需再转换为 <br>
        const updatedCase = {
          ...this.selectedCase,
          scenario: this.editForm.scenario,
          precondition: this.editForm.precondition,
          stepsList,
          steps: stepsList.map(s => `${s.desc}\n预期: ${s.expect}`).join('\n'),
          expected: stepsList.map(s => s.expect).filter(Boolean).join('\n'),
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

    // 表格列展示：结构化步骤 → 编号 + 描述的多行文本（预期不混入）；旧文本记录回退为原文
    stepsText(testCase) {
      if (testCase.stepsList && testCase.stepsList.length) {
        return testCase.stepsList
          .map((s, i) => `${i + 1}. ${(s.desc || '').trim() || '—'}`)
          .join('\n')
      }
      return this.formatTextForList(testCase.steps)
    },

    // 表格列展示：每步预期 → 与步骤行对齐的多行文本
    expectText(testCase) {
      if (testCase.stepsList && testCase.stepsList.length) {
        return testCase.stepsList
          .map(s => (s.expect || '').trim())
          .filter(Boolean)
          .join('\n')
      }
      return this.formatTextForList(testCase.expected)
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
/* Requirement description collapse card */
.requirement-description-card {
  margin-bottom: var(--aitest-space-4);
  background: var(--aitest-surface);
  border-radius: var(--aitest-card-radius);
  border: 1px solid var(--aitest-card-border);
  box-shadow: var(--aitest-card-shadow);
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

.requirement-text :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: var(--aitest-radius-sm);
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

/* 任务信息条（页头下方） */
.task-info {
  display: flex;
  gap: var(--aitest-space-4);
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: var(--aitest-space-4);
}

.task-id {
  color: var(--aitest-text-2);
  font-family: var(--aitest-font-mono);
  font-size: var(--aitest-font-size-sm);
}

/* 任务状态标签（胶囊外观继承全局 .status-tag，此处只补状态色对） */
.status-tag.pending { background: var(--aitest-warning-bg); color: var(--aitest-warning); }
.status-tag.generating,
.status-tag.retrieving,
.status-tag.reviewing,
.status-tag.revising { background: var(--aitest-info-bg); color: var(--aitest-info); }
.status-tag.cancelled { background: var(--aitest-neutral-bg); color: var(--aitest-neutral); }
.status-tag.completed { background: var(--aitest-success-bg); color: var(--aitest-success); }
.status-tag.failed { background: var(--aitest-danger-bg); color: var(--aitest-danger); }

/* Batch actions */
.batch-actions {
  background: var(--aitest-surface);
  border-radius: var(--aitest-card-radius);
  padding: var(--aitest-space-3) var(--aitest-space-5);
  margin-bottom: var(--aitest-space-4);
  border: 1px solid var(--aitest-card-border);
  box-shadow: var(--aitest-card-shadow);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.selection-info {
  display: flex;
  align-items: center;
  gap: var(--aitest-space-4);
}

.selected-count { color: var(--aitest-primary); font-weight: 600; }

.batch-buttons { display: flex; gap: var(--aitest-space-3); }

/* Test cases table */
.testcases-table {
  margin-bottom: var(--aitest-space-4);
}

/* 单元格多行截断（步骤/预期列允许 5 行，hover 看全文） */
.cell-clamp {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  overflow: hidden;
  white-space: pre-wrap;
  line-height: var(--aitest-line-height-normal);
  word-break: break-word;
}

.cell-clamp-5 {
  -webkit-line-clamp: 5;
  max-height: calc(1.5em * 5);
}

.action-buttons { display: flex; gap: var(--aitest-space-1); flex-wrap: wrap; white-space: nowrap; }

/* 分页 */
.pagination-section {
  margin-top: var(--aitest-space-2);
  display: flex;
  justify-content: flex-end;
}

/* 用例详情弹窗内容 */
.detail-list {
  display: flex;
  flex-direction: column;
  gap: var(--aitest-space-4);
}

.detail-item label {
  display: block;
  font-weight: 600;
  color: var(--aitest-text-2);
  margin-bottom: var(--aitest-space-2);
  font-size: var(--aitest-font-size-sm);
}

.detail-item span, .detail-item p { color: var(--aitest-text-2); line-height: var(--aitest-line-height-normal); }

.test-steps {
  white-space: pre-line;
  background: var(--aitest-canvas);
  padding: var(--aitest-space-4);
  border-radius: var(--aitest-radius);
  border-left: 3px solid var(--aitest-primary);
}

.detail-steps {
  display: flex;
  flex-direction: column;
  gap: var(--aitest-space-2);
  background: var(--aitest-canvas);
  padding: var(--aitest-space-4);
  border-radius: var(--aitest-radius);
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
.edit-mode .form-item { margin-bottom: var(--aitest-space-5); }

.edit-mode .form-item label {
  font-weight: 600;
  color: var(--aitest-text-2);
  display: block;
  margin-bottom: var(--aitest-space-2);
}

.edit-mode .readonly-field {
  color: var(--aitest-text-2);
  padding: var(--aitest-space-2) var(--aitest-space-3);
  background: var(--aitest-canvas);
  border-radius: var(--aitest-radius);
  display: inline-block;
}

/* 步骤/预期成对编辑：每行一步骤 + 对应预期 */
.edit-mode .steps-editor {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--aitest-space-2);
}

.edit-mode .step-row {
  display: flex;
  align-items: flex-start;
  gap: var(--aitest-space-2);
}

.edit-mode .step-row .el-textarea { flex: 1; }
.edit-mode .step-row .el-textarea:first-of-type { flex: 1.4; }

.edit-mode .step-index {
  width: 24px;
  flex-shrink: 0;
  text-align: center;
  color: var(--aitest-text-3);
  font-family: var(--aitest-font-mono);
  font-size: var(--aitest-font-size-sm);
  line-height: var(--aitest-line-height-normal);
  padding-top: 10px;
}

.edit-mode .step-remove-btn {
  flex-shrink: 0;
  margin: 0;
  padding-top: 4px;
}

.edit-mode .add-step-btn {
  align-self: flex-start;
  padding-left: 0;
}

.task-chip {
  font-size: var(--aitest-font-size-xs);
  color: var(--aitest-text-2);
  background: var(--aitest-surface-subtle);
  border: 1px solid var(--aitest-border);
  padding: 2px var(--aitest-space-3);
  border-radius: var(--aitest-radius-full);
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 流式生成面板 */
.streaming-panel {
  background: var(--aitest-surface);
  border: 1px solid var(--aitest-border);
  border-radius: var(--aitest-radius-lg);
  padding: var(--aitest-space-4);
  margin-bottom: var(--aitest-space-4);
}
.stream-steps {
  display: flex;
  gap: var(--aitest-space-2);
  margin-bottom: var(--aitest-space-3);
  font-size: var(--aitest-font-size-sm);
  color: var(--aitest-text-2);
  flex-wrap: wrap;
}
.mini-step {
  padding: var(--aitest-space-1) var(--aitest-space-3);
  border-radius: var(--aitest-radius-full);
  background: var(--aitest-surface-subtle);
  border: 1px solid var(--aitest-border);
}
.mini-step.active {
  background: var(--aitest-primary);
  color: #fff;
  border-color: transparent;
}
.stream-status {
  font-size: var(--aitest-font-size-sm);
  color: var(--aitest-text-2);
  margin-bottom: var(--aitest-space-3);
}
.stream-section {
  margin-top: var(--aitest-space-3);
}
.stream-section-title {
  font-weight: 600;
  font-size: var(--aitest-font-size-sm);
  margin-bottom: var(--aitest-space-2);
  color: var(--aitest-text-1);
}
.stream-content {
  background: var(--aitest-surface);
  border: 1px solid var(--aitest-border);
  border-radius: var(--aitest-radius);
  padding: var(--aitest-space-3);
  font-size: var(--aitest-font-size-base);
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
  border-left: 3px solid var(--aitest-primary);
  border-radius: var(--aitest-radius);
  padding: var(--aitest-space-2) var(--aitest-space-3);
  font-size: var(--aitest-font-size-base);
}
.stream-card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--aitest-space-1);
}
.stream-card-id {
  font-weight: 600;
  color: var(--aitest-text-1);
  font-family: var(--aitest-font-mono);
  font-size: var(--aitest-font-size-sm);
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
  line-height: var(--aitest-line-height-normal);
}
.step-order {
  flex: none;
  color: var(--aitest-text-3);
  font-family: var(--aitest-font-mono);
  font-size: var(--aitest-font-size-xs);
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
  background: var(--aitest-info-bg);
  border: 1px solid var(--aitest-border);
  border-radius: var(--aitest-radius-lg);
  padding: var(--aitest-space-4);
  margin-bottom: var(--aitest-space-4);
}
.review-feedback-title {
  font-weight: 600;
  font-size: var(--aitest-font-size-sm);
  color: var(--aitest-info);
  margin-bottom: var(--aitest-space-2);
}
.terminal-state {
  padding: var(--aitest-space-6);
  text-align: center;
}
</style>