<template>
  <div class="page-container generated-testcase-list">
    <PageHeader :title="$t('generatedTestCases.title')" />

    <div class="card-container filter-card">
      <div class="filter-bar">
        <el-select
          v-model="selectedStatus"
          @change="loadTasks()"
          :placeholder="$t('generatedTestCases.allStatus')"
          class="filter-select">
          <el-option :label="$t('generatedTestCases.allStatus')" value="" />
          <el-option :label="$t('generatedTestCases.statusPending')" value="pending" />
          <el-option :label="$t('generatedTestCases.statusGenerating')" value="generating" />
          <el-option :label="$t('generatedTestCases.statusRetrieving')" value="retrieving" />
          <el-option :label="$t('generatedTestCases.statusReviewing')" value="reviewing" />
          <el-option :label="$t('generatedTestCases.statusCompleted')" value="completed" />
          <el-option :label="$t('generatedTestCases.statusFailed')" value="failed" />
          <el-option :label="$t('generatedTestCases.statusRevising')" value="revising" />
          <el-option :label="$t('generatedTestCases.statusCancelled')" value="cancelled" />
        </el-select>

        <div class="filter-actions">
          <el-button
            v-if="selectedTasks.length > 0"
            type="danger"
            :loading="isDeleting"
            @click="batchDeleteTasks">
            {{ isDeleting ? $t('generatedTestCases.deleting') : $t('generatedTestCases.batchDelete', { count: selectedTasks.length }) }}
          </el-button>
          <el-button :loading="isLoading" @click="loadTasks()">
            {{ $t('generatedTestCases.refresh') }}
          </el-button>
        </div>
      </div>
    </div>

    <!-- 统计信息 -->
    <div class="stats-grid" v-if="allStats.total > 0">
      <div class="stat-card">
        <span class="stat-card__label">{{ $t('generatedTestCases.totalTasks') }}</span>
        <span class="stat-card__value">{{ allStats.total }}</span>
      </div>
      <div class="stat-card stat-card--accent-success">
        <span class="stat-card__label">{{ $t('generatedTestCases.completedCount') }}</span>
        <span class="stat-card__value">{{ allStats.completed }}</span>
      </div>
      <div class="stat-card stat-card--accent-info">
        <span class="stat-card__label">{{ $t('generatedTestCases.runningCount') }}</span>
        <span class="stat-card__value">{{ allStats.running }}</span>
      </div>
      <div class="stat-card stat-card--accent-danger">
        <span class="stat-card__label">{{ $t('generatedTestCases.failedCount') }}</span>
        <span class="stat-card__value">{{ allStats.failed }}</span>
      </div>
    </div>

    <!-- AI任务列表 -->
    <div class="card-container testcases-section">
      <div v-if="!isLoading && tasks.length === 0" class="empty-state">
        <div class="empty-icon"><el-icon><EditPen /></el-icon></div>
        <div class="empty-title">{{ $t('generatedTestCases.noTasks') }}</div>
        <div class="empty-hint">{{ $t('generatedTestCases.emptyHint') }}<router-link to="/ai-generation/requirement-analysis">{{ $t('generatedTestCases.aiGeneration') }}</router-link>{{ $t('generatedTestCases.createTask') }}</div>
      </div>

      <el-table
        v-else
        ref="taskTable"
        v-loading="isLoading"
        :data="tasks"
        @selection-change="onSelectionChange"
        style="width: 100%">
        <el-table-column type="selection" width="46" />
        <el-table-column :label="$t('generatedTestCases.serialNumber')" width="64" align="center">
          <template #default="scope">{{ getSerialNumber(scope.$index) }}</template>
        </el-table-column>
        <el-table-column prop="task_id" :label="$t('generatedTestCases.taskId')" width="180" show-overflow-tooltip />
        <el-table-column :label="$t('generatedTestCases.requirement')" min-width="220">
          <template #default="scope">
            <span class="requirement-name">{{ scope.row.title }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="$t('generatedTestCases.status')" width="130">
          <template #default="scope">
            <div class="status-cell">
              <span class="status-tag" :class="scope.row.status">
                <span class="status-tag__dot"></span>
                {{ getStatusText(scope.row.status) }}
              </span>
              <div v-if="isRunningStatus(scope.row.status)" class="task-progress">
                <div class="progress-track">
                  <div class="progress-fill" :style="{ width: Math.min(scope.row.progress || 0, 100) + '%' }"></div>
                </div>
                <span class="progress-num">{{ Math.round(scope.row.progress || 0) }}%</span>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column :label="$t('generatedTestCases.genOptionsLabel')" width="170">
          <template #default="scope">
            <span class="option-chip">
              <template v-if="scope.row.granularity">
                {{ $t('generatedTestCases.genGranularity') }}：{{ scope.row.granularity_display || scope.row.granularity }}
              </template>
              <template v-if="scope.row.case_type"><span class="option-type">{{ scope.row.case_type }}</span></template>
              <template v-if="!scope.row.granularity && !scope.row.case_type">{{ $t('generatedTestCases.genOptionsEmpty') }}</template>
            </span>
          </template>
        </el-table-column>
        <el-table-column :label="$t('generatedTestCases.caseCount')" width="90" align="center">
          <template #default="scope">
            <span class="count-badge">{{ getTestCaseCount(scope.row) }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="$t('generatedTestCases.generationTime')" width="165">
          <template #default="scope">{{ formatDateTime(scope.row.created_at) }}</template>
        </el-table-column>
        <el-table-column :label="$t('generatedTestCases.actions')" width="210" fixed="right">
          <template #default="scope">
            <div class="action-buttons">
              <el-button link type="primary" size="small" @click="viewTaskDetail(scope.row)">
                {{ $t('generatedTestCases.viewDetail') }}
              </el-button>
              <el-button
                v-if="scope.row.status === 'completed'"
                link
                type="success"
                size="small"
                @click="batchAdoptTask(scope.row)">
                {{ $t('generatedTestCases.batchAdopt') }}
              </el-button>
              <el-button
                v-if="scope.row.status === 'completed'"
                link
                type="danger"
                size="small"
                @click="batchDiscardTask(scope.row)">
                {{ $t('generatedTestCases.batchDiscard') }}
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div v-if="tasks.length > 0" class="pagination-section">
        <el-pagination
          v-model:current-page="pagination.currentPage"
          v-model:page-size="pagination.pageSize"
          :page-sizes="pagination.pageSizeOptions"
          :total="pagination.total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="onPageSizeChange"
          @current-change="goToPage" />
      </div>
    </div>

    <!-- 测试用例详情弹窗 -->
    <el-dialog
      :model-value="!!selectedTestCaseDetail"
      @close="closeTestCaseDetail"
      :title="selectedTestCaseDetail ? selectedTestCaseDetail.title : ''"
      width="720px">
      <div v-if="selectedTestCaseDetail" class="detail-list">
        <div class="detail-item">
          <label>{{ $t('generatedTestCases.caseNumber') }}</label>
          <span>{{ selectedTestCaseDetail.case_id }}</span>
        </div>
        <div class="detail-item">
          <label>{{ $t('generatedTestCases.relatedRequirement') }}</label>
          <span>{{ selectedTestCaseDetail.requirement_name }} ({{ selectedTestCaseDetail.requirement_id_display }})</span>
        </div>
        <div class="detail-item">
          <label>{{ $t('generatedTestCases.priority') }}</label>
          <span class="priority-tag" :class="selectedTestCaseDetail.priority.toLowerCase()">
            {{ selectedTestCaseDetail.priority_display }}
          </span>
        </div>
        <div class="detail-item">
          <label>{{ $t('generatedTestCases.status') }}</label>
          <span class="status-tag" :class="selectedTestCaseDetail.status">
            <span class="status-tag__dot"></span>
            {{ selectedTestCaseDetail.status_display }}
          </span>
        </div>
        <div class="detail-item">
          <label>{{ $t('generatedTestCases.preconditions') }}</label>
          <p>{{ selectedTestCaseDetail.precondition }}</p>
        </div>
        <div class="detail-item">
          <label>{{ $t('generatedTestCases.testSteps') }}</label>
          <p class="test-steps" v-html="selectedTestCaseDetail.test_steps"></p>
        </div>
        <div class="detail-item">
          <label>{{ $t('generatedTestCases.expectedResult') }}</label>
          <p v-html="selectedTestCaseDetail.expected_result"></p>
        </div>
        <div class="detail-item" v-if="selectedTestCaseDetail.review_comments">
          <label>{{ $t('generatedTestCases.reviewComments') }}</label>
          <p>{{ selectedTestCaseDetail.review_comments }}</p>
        </div>
        <div class="detail-item">
          <label>{{ $t('generatedTestCases.generatedAI') }}</label>
          <span>{{ selectedTestCaseDetail.generated_by_ai }}</span>
        </div>
        <div class="detail-item" v-if="selectedTestCaseDetail.reviewed_by_ai">
          <label>{{ $t('generatedTestCases.reviewedAI') }}</label>
          <span>{{ selectedTestCaseDetail.reviewed_by_ai }}</span>
        </div>
        <div class="detail-item">
          <label>{{ $t('generatedTestCases.generatedTime') }}</label>
          <span>{{ formatDateTime(selectedTestCaseDetail.created_at) }}</span>
        </div>
      </div>
    </el-dialog>

    <!-- 采纳用例编辑弹框 -->
    <el-dialog
      v-model="showAdoptModal"
      :title="$t('generatedTestCases.adoptModalTitle')"
      width="840px"
      @closed="onAdoptModalClosed">
      <el-form :model="adoptForm" label-position="top" class="adopt-form">
        <el-row :gutter="16">
          <el-col :span="24">
            <el-form-item :label="$t('generatedTestCases.caseTitle')">
              <el-input v-model="adoptForm.title" :placeholder="$t('generatedTestCases.caseTitlePlaceholder')" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item :label="$t('generatedTestCases.caseDescription')">
              <el-input v-model="adoptForm.description" type="textarea" :rows="3" :placeholder="$t('generatedTestCases.caseDescriptionPlaceholder')" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item :label="$t('generatedTestCases.belongsToProject')" required>
              <el-select v-model="adoptForm.project_id" @change="onAdoptProjectChange" :placeholder="$t('generatedTestCases.selectProject')" style="width: 100%">
                <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item :label="$t('generatedTestCases.relatedVersion')" required>
              <el-select v-model="adoptForm.version_id" :placeholder="$t('generatedTestCases.selectVersion')" style="width: 100%">
                <el-option v-for="version in availableVersions" :key="version.id" :label="version.name + (version.is_baseline ? $t('generatedTestCases.baseline') : '')" :value="version.id" />
              </el-select>
              <div class="form-hint">
                {{ adoptForm.project_id ?
                    $t('generatedTestCases.showingProjectVersions', { project: getProjectName(adoptForm.project_id) }) :
                    $t('generatedTestCases.showingAllVersions') }}
              </div>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item :label="$t('generatedTestCases.priority')">
              <el-select v-model="adoptForm.priority" style="width: 100%">
                <el-option :label="$t('generatedTestCases.priorityLow')" value="low" />
                <el-option :label="$t('generatedTestCases.priorityMedium')" value="medium" />
                <el-option :label="$t('generatedTestCases.priorityHigh')" value="high" />
                <el-option :label="$t('generatedTestCases.priorityCritical')" value="critical" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item :label="$t('generatedTestCases.testType')">
              <el-select v-model="adoptForm.test_type" style="width: 100%">
                <el-option :label="$t('generatedTestCases.testTypeFunctional')" value="functional" />
                <el-option :label="$t('generatedTestCases.testTypeIntegration')" value="integration" />
                <el-option :label="$t('generatedTestCases.testTypeAPI')" value="api" />
                <el-option :label="$t('generatedTestCases.testTypeUI')" value="ui" />
                <el-option :label="$t('generatedTestCases.testTypePerformance')" value="performance" />
                <el-option :label="$t('generatedTestCases.testTypeSecurity')" value="security" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item :label="$t('generatedTestCases.status')">
              <el-select v-model="adoptForm.status" style="width: 100%">
                <el-option :label="$t('generatedTestCases.statusDraft')" value="draft" />
                <el-option :label="$t('generatedTestCases.statusActive')" value="active" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item :label="$t('generatedTestCases.preconditions')">
              <el-input v-model="adoptForm.preconditions" type="textarea" :rows="3" :placeholder="$t('generatedTestCases.preconditionsPlaceholder')" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item :label="$t('generatedTestCases.operationSteps')">
              <el-input v-model="adoptForm.steps" type="textarea" :rows="6" :placeholder="$t('generatedTestCases.operationStepsPlaceholder')" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item :label="$t('generatedTestCases.expectedResult')">
              <el-input v-model="adoptForm.expected_result" type="textarea" :rows="3" :placeholder="$t('generatedTestCases.expectedResultPlaceholder')" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="showAdoptModal = false">{{ $t('generatedTestCases.cancel') }}</el-button>
        <el-button type="primary" :loading="isAdopting" @click="confirmAdopt">
          {{ isAdopting ? $t('generatedTestCases.adopting') : $t('generatedTestCases.confirmAdopt') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import api from '@/utils/api'
import { ElMessage } from 'element-plus'
import PageHeader from '@/components/common/PageHeader.vue'

export default {
  name: 'GeneratedTestCaseList',
  components: { PageHeader },
  data() {
    return {
      isLoading: false,
      tasks: [], // 改为任务列表
      selectedStatus: '',
      selectedTaskDetail: null,
      selectedTestCaseDetail: null,
      showAdoptModal: false,
      isAdopting: false,
      projects: [],
      projectVersions: [],
      allVersions: [], // 存储所有版本列表
      adoptForm: {
        title: '',
        description: '',
        project_id: null,
        priority: 'low', // 修改默认值为"低"
        test_type: 'functional',
        status: 'draft',
        preconditions: '',
        steps: '',
        expected_result: '',
        version_id: null // 改为单选
      },
      currentAdoptingTask: null,
      // 选择相关数据
      selectedTasks: [], // 已选中的任务ID列表
      isDeleting: false, // 是否正在删除
      // 分页相关数据
      pagination: {
        currentPage: 1,
        pageSize: 10, // 改为默认10条
        total: 0,
        pageSizeOptions: [10, 20, 50]
      },
      // 统计数据
      allStats: {
        total: 0,
        completed: 0,
        running: 0,
        failed: 0
      },
      pollTimer: null // 运行中任务列表轮询计时器
    }
  },

  computed: {
    // 可用版本列表 - 根据是否选择项目来决定显示哪些版本
    availableVersions() {
      if (this.adoptForm.project_id) {
        // 如果选择了项目，显示该项目的版本
        return this.projectVersions
      } else {
        // 如果没有选择项目，显示系统所有版本
        return this.allVersions
      }
    },

    // 是否存在运行中的任务（知识检索/生成/评审/改进中）
    hasRunningTasks() {
      return this.tasks.some(t => ['pending', 'generating', 'retrieving', 'reviewing', 'revising'].includes(t.status))
    }
  },

  mounted() {
    this.loadTasks()
    this.fetchProjects()
    this.fetchAllVersions()
  },

  methods: {
    // 判断任务是否处于运行中状态（用于展示进度条）
    isRunningStatus(status) {
      return ['pending', 'generating', 'retrieving', 'reviewing', 'revising'].includes(status)
    },

    // 有运行中任务时启动3秒轮询，全部完成后停止
    syncPolling() {
      if (this.hasRunningTasks) {
        if (!this.pollTimer) {
          this.pollTimer = setInterval(() => this.loadTasks(true), 3000)
        }
      } else if (this.pollTimer) {
        clearInterval(this.pollTimer)
        this.pollTimer = null
      }
    },

    async loadTasks(silent = false) {
      if (!silent) this.isLoading = true
      try {
        let url = '/requirement-analysis/testcase-generation/'
        const params = new URLSearchParams()

        // 添加分页参数
        params.append('page', String(this.pagination.currentPage))
        params.append('page_size', String(this.pagination.pageSize))

        if (this.selectedStatus) {
          params.append('status', this.selectedStatus)
        }

        if (params.toString()) {
          url += '?' + params.toString()
        }

        const response = await api.get(url)

        if (response.data.results) {
          this.tasks = response.data.results
          this.pagination.total = response.data.count || 0
        } else {
          this.tasks = response.data || []
          this.pagination.total = this.tasks.length
        }

        // 更新统计数据（统计所有数据，不只是当前页）
        this.updateStats()

      } catch (error) {
        console.error(this.$t('generatedTestCases.loadTasksFailed'), error)
        this.tasks = []
        this.pagination.total = 0
      } finally {
        if (!silent) this.isLoading = false
        // 清空选择（因为任务列表已更新）
        this.selectedTasks = []
        this.$nextTick(() => {
          if (this.$refs.taskTable) this.$refs.taskTable.clearSelection()
        })
        // 管理运行中任务的轮询
        this.syncPolling()
      }
    },

    // 获取序号
    getSerialNumber(index) {
      return (this.pagination.currentPage - 1) * this.pagination.pageSize + index + 1
    },

    // 表格选择变化（el-table selection 事件）
    onSelectionChange(rows) {
      this.selectedTasks = rows.map(row => row.task_id)
    },

    // 批量删除任务
    async batchDeleteTasks() {
      if (this.selectedTasks.length === 0) {
        ElMessage.warning(this.$t('generatedTestCases.selectTasksFirst'))
        return
      }

      if (!confirm(this.$t('generatedTestCases.batchDeleteConfirm', { count: this.selectedTasks.length }))) {
        return
      }

      this.isDeleting = true
      let successCount = 0
      let failCount = 0

      try {
        // 逐个删除选中的任务
        for (const taskId of this.selectedTasks) {
          try {
            await api.delete(`/requirement-analysis/testcase-generation/${taskId}/`)
            successCount++
          } catch (error) {
            console.error(`删除任务 ${taskId} 失败:`, error)
            failCount++
          }
        }

        // 显示删除结果
        if (successCount > 0) {
          ElMessage.success(this.$t('generatedTestCases.deleteSuccess', { success: successCount, failed: failCount }))
        } else {
          ElMessage.error(this.$t('generatedTestCases.deleteFailed'))
        }

        // 清空选择并重新加载列表
        this.selectedTasks = []
        this.loadTasks()

      } catch (error) {
        console.error(this.$t('generatedTestCases.batchDeleteFailed'), error)
        ElMessage.error(this.$t('generatedTestCases.batchDeleteFailed') + ': ' + (error.message || this.$t('generatedTestCases.unknownError')))
      } finally {
        this.isDeleting = false
      }
    },

    updateStats() {
      // 不再使用当前页数据统计，改为调用专门的统计方法
      this.loadAllStats()
    },

    // 新增方法：获取所有数据的统计信息
    async loadAllStats() {
      try {
        // 构建统计请求URL
        let url = '/requirement-analysis/testcase-generation/'
        const params = new URLSearchParams()

        // 获取所有数据来进行统计
        params.append('page_size', '10000') // 设置足够大的页面大小来获取所有数据
        params.append('page', '1')

        // 如果有状态筛选，也应用到统计中
        if (this.selectedStatus) {
          params.append('status', this.selectedStatus)
        }

        url += '?' + params.toString()

        const response = await api.get(url)
        const allTasks = response.data.results || response.data || []

        // 统计各状态的数量
        this.allStats.total = allTasks.length
        this.allStats.completed = allTasks.filter(t => t.status === 'completed').length
        this.allStats.running = allTasks.filter(t => ['pending', 'generating', 'retrieving', 'reviewing'].includes(t.status)).length
        this.allStats.failed = allTasks.filter(t => t.status === 'failed').length

      } catch (error) {
        console.error(this.$t('generatedTestCases.loadStatsFailed'), error)
        // 如果获取统计失败，使用分页信息的总数作为备选
        this.allStats.total = this.pagination.total || 0
        this.allStats.completed = 0
        this.allStats.running = 0
        this.allStats.failed = 0
      }
    },

    getStatusText(status) {
      const statusMap = {
        'pending': this.$t('generatedTestCases.statusPending'),
        'generating': this.$t('generatedTestCases.statusGenerating'),
        'retrieving': this.$t('generatedTestCases.statusRetrieving'),
        'reviewing': this.$t('generatedTestCases.statusReviewing'),
        'revising': this.$t('generatedTestCases.statusRevising'),
        'cancelled': this.$t('generatedTestCases.statusCancelled'),
        'completed': this.$t('generatedTestCases.statusCompleted'),
        'failed': this.$t('generatedTestCases.statusFailed')
      }
      return statusMap[status] || status
    },

    // 获取测试用例条数
    getTestCaseCount(task) {
      if (!task.final_test_cases) {
        return 0
      }

      // 解析测试用例内容，计算条数
      const content = task.final_test_cases
      const lines = content.split('\n').filter(line => line.trim())

      // 尝试表格格式
      let tableRows = 0
      let isFirstRow = true
      let isTableFormat = false

      for (let line of lines) {
        if (line.includes('|') && !line.includes('--------')) {
          const cells = line.split('|').map(cell => cell.trim()).filter(cell => cell)
          if (cells.length > 1) {
            // 检查第一行是否是表头
            if (isFirstRow) {
              isFirstRow = false
              // 如果第一行包含表头标识，标记为表格格式
              if (line.includes('测试用例编号') || line.includes('ID') || line.includes('用例ID') ||
                  line.includes('场景') || line.includes('步骤')) {
                isTableFormat = true
                continue  // 跳过表头行
              }
            }

            tableRows++
            if (tableRows >= 1) {
              isTableFormat = true
            }
          }
        }
      }

      if (isTableFormat && tableRows > 0) {
        return tableRows
      }

      // 尝试结构化文本格式
      let caseCount = 0
      for (const line of lines) {
        if (line.includes('测试用例') || line.includes('Test Case') || line.match(/^(\d+\.|测试场景)/)) {
          caseCount++
        }
      }

      return caseCount || 0
    },

    viewTaskDetail(task) {
      // 运行中/完成/失败/取消的任务均可进入详情：运行中看流式过程，失败看原因
      this.$router.push({
        name: 'TaskDetail',
        params: { taskId: task.task_id }
      })
    },

    async batchAdoptTask(task) {
      if (!confirm(this.$t('generatedTestCases.adoptConfirm', { title: task.title }))) {
        return
      }

      try {
        // 调用后端API批量采纳该任务的所有测试用例
        // await api.post(`/requirement-analysis/testcase-generation/${task.task_id}/batch-adopt/`)
        await api.post(`/requirement-analysis/testcase-generation/${task.task_id}/batch_adopt/`)
        ElMessage.success(this.$t('generatedTestCases.adoptSuccess'))
        this.loadTasks()
      } catch (error) {
        console.error(this.$t('generatedTestCases.adoptFailed'), error)
        ElMessage.error(this.$t('generatedTestCases.adoptFailed') + ': ' + (error.response?.data?.message || error.message))
      }
    },

    async batchDiscardTask(task) {
      if (!confirm(this.$t('generatedTestCases.discardConfirm', { title: task.title }))) {
        return
      }

      try {
        // 调用后端API批量删除该任务的所有测试用例
        // await api.post(`/requirement-analysis/testcase-generation/${task.task_id}/batch-discard/`)
        await api.post(`/requirement-analysis/testcase-generation/${task.task_id}/batch_discard/`)
        ElMessage.success(this.$t('generatedTestCases.discardSuccess'))
        this.loadTasks()
      } catch (error) {
        console.error(this.$t('generatedTestCases.discardFailed'), error)
        ElMessage.error(this.$t('generatedTestCases.discardFailed') + ': ' + (error.response?.data?.message || error.message))
      }
    },

    formatDateTime(dateString) {
      if (!dateString) return ''
      const date = new Date(dateString)
      return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      })
    },

    // 获取项目列表
    async fetchProjects() {
      try {
        const response = await api.get('/projects/list/')
        this.projects = response.data.results || []
      } catch (error) {
        console.error(this.$t('generatedTestCases.fetchProjectsFailed'), error)
      }
    },

    // 获取所有版本列表
    async fetchAllVersions() {
      try {
        const response = await api.get('/versions/')
        this.allVersions = response.data.results || response.data || []
      } catch (error) {
        console.error(this.$t('generatedTestCases.fetchVersionsFailed'), error)
        this.allVersions = []
      }
    },

    // 获取项目版本列表
    async fetchProjectVersions(projectId) {
      if (!projectId) {
        this.projectVersions = []
        return
      }

      try {
        const response = await api.get(`/versions/projects/${projectId}/versions/`)
        this.projectVersions = response.data || []
      } catch (error) {
        console.error(this.$t('generatedTestCases.fetchProjectVersionsFailed'), error)
        this.projectVersions = []
      }
    },

    // 项目改变时的处理
    async onAdoptProjectChange() {
      if (this.adoptForm.project_id) {
        // 选择了项目，加载该项目的版本
        await this.fetchProjectVersions(this.adoptForm.project_id)

        // 检查当前选择的版本是否属于新项目，如果不属于则清空
        if (this.adoptForm.version_id) {
          const versionExists = this.projectVersions.some(v => v.id === this.adoptForm.version_id)
          if (!versionExists) {
            this.adoptForm.version_id = null
          }
        }
      } else {
        // 清空项目选择时，清空项目版本列表
        // 此时版本下拉会自动切换到显示所有版本（通过computed属性）
        this.projectVersions = []
        // 保持当前版本选择，因为可以从所有版本中选择
      }
    },

    // 确认采纳
    async confirmAdopt() {
      // 必填项验证
      if (!this.adoptForm.project_id) {
        alert(this.$t('generatedTestCases.selectProjectRequired'))
        return
      }

      if (!this.adoptForm.version_id) {
        alert(this.$t('generatedTestCases.selectVersionRequired'))
        return
      }

      if (!this.adoptForm.title.trim()) {
        alert(this.$t('generatedTestCases.enterCaseTitle'))
        return
      }

      if (!this.adoptForm.expected_result.trim()) {
        alert(this.$t('generatedTestCases.enterExpectedResult'))
        return
      }

      this.isAdopting = true

      try {
        // 准备提交的数据，将单选版本转换为数组格式（如果API需要）
        const submitData = {
          title: this.adoptForm.title,
          description: this.adoptForm.description,
          project_id: this.adoptForm.project_id,
          priority: this.adoptForm.priority || 'low',
          test_type: this.adoptForm.test_type,
          status: this.adoptForm.status,
          preconditions: this.adoptForm.preconditions,
          steps: this.adoptForm.steps,
          expected_result: this.adoptForm.expected_result,
          version_ids: this.adoptForm.version_id ? [this.adoptForm.version_id] : []
        }

        // 确保优先级有默认值
        if (!submitData.priority) {
          submitData.priority = 'low'
        }

        // 调用API创建测试用例
        await api.post('/testcases/', submitData)

        // 将AI生成的用例状态更新为"已采纳"
        try {
          await api.patch(`/requirement-analysis/test-cases/${this.currentAdoptingTask.id}/`, {
            status: 'adopted'
          })
        } catch (updateError) {
          console.warn(this.$t('generatedTestCases.updateStatusFailed'), updateError)
          // 即使状态更新失败，用例已成功导入，仍然提示成功
        }

        alert(this.$t('generatedTestCases.adoptModalSuccess'))
        this.closeAdoptModal()
        this.loadTestCases() // 重新加载列表

      } catch (error) {
        console.error(this.$t('generatedTestCases.adoptCaseFailed'), error)
        alert(this.$t('generatedTestCases.adoptCaseFailedRetry'))
      } finally{
        this.isAdopting = false
      }
    },

    // 关闭采纳弹框
    closeAdoptModal() {
      this.showAdoptModal = false
    },

    // 采纳弹框关闭后清理
    onAdoptModalClosed() {
      this.currentAdoptingTask = null
      this.projectVersions = []
    },

    // 关闭测试用例详情弹窗
    closeTestCaseDetail() {
      this.selectedTestCaseDetail = null
    },

    // 加载测试用例列表（别名，与loadTasks一致）
    loadTestCases() {
      this.loadTasks()
    },

    // 获取项目名称的辅助方法
    getProjectName(projectId) {
      const project = this.projects.find(p => p.id === projectId)
      return project ? project.name : ''
    },

    // 分页相关方法
    onPageSizeChange() {
      this.pagination.currentPage = 1
      this.loadTasks()
    },

    goToPage(page) {
      this.pagination.currentPage = page
      this.loadTasks()
    }
  },

  beforeUnmount() {
    if (this.pollTimer) {
      clearInterval(this.pollTimer)
      this.pollTimer = null
    }
  },
}
</script>

<style scoped>
/* 筛选栏 */
.filter-card {
  margin-bottom: var(--aitest-space-4);
}

.filter-bar {
  margin-bottom: 0;
}

.filter-select {
  width: 200px;
}

.filter-actions {
  margin-left: auto;
  display: flex;
  gap: var(--aitest-space-2);
}

/* 统计卡片 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--aitest-space-4);
  margin-bottom: var(--aitest-space-4);
}

/* 任务列表 */
.testcases-section {
  padding: 0;
}

/* 状态列：标签 + 进度条纵向堆叠 */
.status-cell {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--aitest-space-1);
}

.requirement-name {
  color: var(--aitest-text-1);
  line-height: var(--aitest-line-height-normal);
  word-break: break-word;
}

/* 运行中任务进度条 */
.task-progress {
  display: flex;
  align-items: center;
  gap: var(--aitest-space-2);
  width: 100%;
}

.progress-track {
  flex: 1;
  min-width: 0;
  max-width: 72px;
  height: 4px;
  border-radius: var(--aitest-radius-full);
  background: var(--aitest-surface-subtle);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: var(--aitest-radius-full);
  background: var(--aitest-primary);
  transition: width 0.3s ease;
}

.progress-num {
  font-size: var(--aitest-font-size-xs);
  color: var(--aitest-text-2);
  min-width: 30px;
}

/* 任务状态标签（色板：token 语义色对；胶囊外观继承全局 .status-tag） */
.status-tag.pending { background: var(--aitest-warning-bg); color: var(--aitest-warning); }
.status-tag.generating,
.status-tag.retrieving,
.status-tag.reviewing,
.status-tag.revising { background: var(--aitest-info-bg); color: var(--aitest-info); }
.status-tag.cancelled { background: var(--aitest-neutral-bg); color: var(--aitest-neutral); }
.status-tag.completed { background: var(--aitest-success-bg); color: var(--aitest-success); }
.status-tag.failed { background: var(--aitest-danger-bg); color: var(--aitest-danger); }

.count-badge {
  background: var(--aitest-primary-subtle);
  color: var(--aitest-primary);
  padding: 2px 10px;
  border-radius: var(--aitest-radius-full);
  font-size: var(--aitest-font-size-xs);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  display: inline-block;
}

/* 生成选项 chip */
.option-chip {
  display: inline-flex;
  align-items: center;
  gap: var(--aitest-space-2);
  font-size: var(--aitest-font-size-xs);
  color: var(--aitest-text-2);
  background: var(--aitest-surface-subtle);
  border: 1px solid var(--aitest-border);
  border-radius: var(--aitest-radius-full);
  padding: 2px var(--aitest-space-3);
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.option-type {
  color: var(--aitest-text-3);
  font-family: var(--aitest-font-mono);
  font-size: var(--aitest-font-size-xs);
}

.action-buttons {
  display: flex;
  align-items: center;
  white-space: nowrap;
}

/* 分页 */
.pagination-section {
  margin-top: var(--aitest-space-4);
  padding: var(--aitest-space-3) var(--aitest-space-4);
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid var(--aitest-border);
}

/* 详情弹窗 */
.detail-list {
  display: flex;
  flex-direction: column;
  gap: var(--aitest-space-4);
}

.detail-item label {
  display: block;
  font-weight: 600;
  color: var(--aitest-text-2);
  font-size: var(--aitest-font-size-sm);
  margin-bottom: var(--aitest-space-1);
}

.detail-item span,
.detail-item p {
  margin: 0;
  color: var(--aitest-text-1);
  line-height: var(--aitest-line-height-relaxed);
  font-size: var(--aitest-font-size-base);
}

.test-steps {
  white-space: pre-line;
  background: var(--aitest-canvas);
  padding: var(--aitest-space-4);
  border-radius: var(--aitest-radius);
  border-left: 3px solid var(--aitest-primary);
}

/* 采纳弹窗表单 */
.form-hint {
  color: var(--aitest-text-3);
  font-size: var(--aitest-font-size-xs);
  line-height: var(--aitest-line-height-normal);
  margin-top: var(--aitest-space-1);
}

/* 响应式 */
@media (max-width: 1024px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }

  .filter-actions {
    margin-left: 0;
  }

  .pagination-section {
    justify-content: flex-start;
    overflow-x: auto;
  }
}
</style>
