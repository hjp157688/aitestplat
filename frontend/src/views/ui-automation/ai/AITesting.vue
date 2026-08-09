<template>
  <div class="page-container">
    <PageHeader :title="$t('uiAutomation.ai.title')" />

    <div class="card-container">
      <el-row :gutter="20">
        <el-col :span="12">
          <div class="section-title">{{ $t('uiAutomation.ai.taskInput') }}</div>
          <el-form :model="taskForm" label-position="top">
            <el-form-item :label="$t('uiAutomation.ai.taskDescription')" required>
              <el-input
                v-model="taskForm.description"
                type="textarea"
                :rows="10"
                :placeholder="$t('uiAutomation.ai.taskPlaceholder')"
                maxlength="2000"
                show-word-limit
              />
            </el-form-item>

            <el-form-item :label="$t('uiAutomation.ai.gifRecording')">
              <el-switch
                v-model="taskForm.enableGif"
                :active-text="$t('uiAutomation.ai.on')"
                :inactive-text="$t('uiAutomation.ai.off')"
              />
              <span style="margin-left: 10px; color: var(--el-text-color-secondary); font-size: 12px;">
                {{ $t('uiAutomation.ai.gifTip') }}
              </span>
            </el-form-item>

            <el-form-item>
              <el-button
                type="primary"
                @click="handleRun"
                :loading="running"
                :disabled="!taskForm.description"
              >
                <el-icon><VideoPlay /></el-icon>
                {{ $t('uiAutomation.ai.startExecution') }}
              </el-button>
              <el-button
                type="danger"
                @click="handleStop"
                :disabled="!running || analyzing"
                v-if="running"
              >
                <el-icon><SwitchButton /></el-icon>
                {{ $t('uiAutomation.ai.stopExecution') }}
              </el-button>
              <el-button
                type="success"
                @click="handleSaveAsCase"
                :disabled="!taskForm.description"
              >
                <el-icon><DocumentAdd /></el-icon>
                {{ $t('uiAutomation.ai.saveAsCase') }}
              </el-button>
            </el-form-item>
          </el-form>

          <el-alert
            :title="$t('uiAutomation.ai.tip')"
            type="info"
            :closable="false"
            style="margin-top: 20px;"
          >
            <template #default>
              <div>{{ $t('uiAutomation.ai.tipContent1') }}</div>
              <div>{{ $t('uiAutomation.ai.tipContent2') }}</div>
            </template>
          </el-alert>

          <div class="section-title" style="margin-top: 20px;">{{ $t('uiAutomation.ai.executionLogs') }}</div>
          <div class="log-container" ref="logContainer">
            <div v-if="!logs && !running" class="empty-logs">
              {{ $t('uiAutomation.ai.noLogs') }}
            </div>
            <pre v-else class="log-content">{{ logs }}</pre>
          </div>
        </el-col>

        <el-col :span="12">
          <div class="section-title">{{ $t('uiAutomation.ai.taskDetails') }}</div>
          <div class="task-list-container">
            <div v-if="analyzing" class="analyzing-state">
              <el-icon class="is-loading"><Loading /></el-icon>
              <span>{{ $t('uiAutomation.ai.analyzing') }}</span>
            </div>
            <div v-else-if="plannedTasks.length > 0">
              <div
                v-for="task in plannedTasks"
                :key="task.id"
                class="task-item"
                :class="task.status"
              >
                <div class="task-status-icon">
                  <el-icon v-if="task.status === 'completed'" color="var(--el-color-success)"><CircleCheckFilled /></el-icon>
                  <el-icon v-else-if="task.status === 'in_progress'" class="is-loading" color="var(--el-color-primary)"><Loading /></el-icon>
                  <el-icon v-else color="var(--el-text-color-secondary)"><CircleCheck /></el-icon>
                </div>
                <div class="task-content">
                  <span class="task-id">{{ task.id }}.</span>
                  <span class="task-desc">{{ task.description }}</span>
                </div>
              </div>
            </div>
            <div v-else class="empty-tasks">
              {{ $t('uiAutomation.ai.noTasks') }}
            </div>
          </div>
        </el-col>
      </el-row>
    </div>

    <!-- 保存为用例对话框 -->
    <el-dialog v-model="showSaveDialog" :title="$t('uiAutomation.ai.saveAsCaseTitle')" width="500px" :close-on-click-modal="false">
      <el-form :model="saveForm" :rules="saveRules" ref="saveFormRef" label-width="80px">
        <el-form-item :label="$t('uiAutomation.ai.caseName')" prop="name">
          <el-input v-model="saveForm.name" :placeholder="$t('uiAutomation.ai.caseNamePlaceholder')" />
        </el-form-item>
        <el-form-item :label="$t('uiAutomation.common.description')" prop="description">
          <el-input v-model="saveForm.description" type="textarea" :placeholder="$t('uiAutomation.ai.caseDescPlaceholder')" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showSaveDialog = false">{{ $t('uiAutomation.common.cancel') }}</el-button>
          <el-button type="primary" @click="confirmSaveCase" :loading="saving">{{ $t('uiAutomation.common.save') }}</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, nextTick, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { VideoPlay, DocumentAdd, CircleCheckFilled, CircleCheck, Loading, SwitchButton } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import PageHeader from '@/components/common/PageHeader.vue'
import {
  runAdhocAITask,
  createAICase,
  getAIExecutionRecordDetail,
  stopAITask
} from '@/api/ui_automation'

const { t } = useI18n()

const running = ref(false)
const analyzing = ref(false)
const saving = ref(false)
const logs = ref('')
const plannedTasks = ref([])
const currentExecutionId = ref(null)
const logContainer = ref(null)

const taskForm = reactive({
  description: '',
  enableGif: true  // GIF录制开关，默认开启
})

const showSaveDialog = ref(false)
const saveForm = reactive({
  name: '',
  description: ''
})
const saveFormRef = ref(null)

const saveRules = computed(() => ({
  name: [{ required: true, message: t('uiAutomation.ai.rules.nameRequired'), trigger: 'blur' }]
}))

// 执行任务
const handleRun = async () => {
  running.value = true
  analyzing.value = true
  logs.value = t('uiAutomation.ai.messages.initAgent')
  plannedTasks.value = []

  try {
    const response = await runAdhocAITask({
      task_description: taskForm.description,
      execution_mode: 'text',  // 始终使用文本模式
      enable_gif: taskForm.enableGif  // 传递GIF录制开关状态
    })

    // analyzing.value = false // 移除过早设置，改为在轮询获取到任务列表后再取消

    currentExecutionId.value = response.data.execution_id
    ElMessage.success(t('uiAutomation.ai.messages.startSuccess'))

    // 开始轮询日志
    pollLogs()

  } catch (error) {
    console.error('执行失败:', error)
    ElMessage.error(t('uiAutomation.ai.messages.startFailed') + ': ' + (error.response?.data?.error || error.message))
    running.value = false
    analyzing.value = false
  }
}

// 停止任务
const handleStop = async () => {
  if (!currentExecutionId.value) return

  try {
    await stopAITask(currentExecutionId.value)
    ElMessage.warning(t('uiAutomation.ai.messages.stopping'))
    // 不立即设置 running = false，等待轮询检测到状态变化
  } catch (error) {
    console.error('停止失败:', error)
    ElMessage.error(t('uiAutomation.ai.messages.stopFailed'))
  }
}

// 轮询日志
const pollLogs = () => {
  const pollInterval = setInterval(async () => {
    if (!currentExecutionId.value) {
      clearInterval(pollInterval)
      return
    }
    
    try {
      const response = await getAIExecutionRecordDetail(currentExecutionId.value)
      const record = response.data
      
      logs.value = record.logs || ''
      plannedTasks.value = record.planned_tasks || []
      
      // 如果获取到了任务列表，则取消“分析中”状态
      if (plannedTasks.value.length > 0) {
        analyzing.value = false
      }
      
      // 滚动到底部
      nextTick(() => {
        if (logContainer.value) {
          logContainer.value.scrollTop = logContainer.value.scrollHeight
        }
      })
      
      if (record.status === 'passed' || record.status === 'failed' || record.status === 'stopped') {
        clearInterval(pollInterval)
        running.value = false
        analyzing.value = false // 确保结束时必然取消分析状态
        if (record.status === 'passed') {
          ElMessage.success(t('uiAutomation.ai.messages.executionSuccess'))
        } else if (record.status === 'stopped') {
          ElMessage.warning(t('uiAutomation.ai.messages.taskStopped'))
        } else {
          ElMessage.error(t('uiAutomation.ai.messages.executionFailed'))
        }
      }
    } catch (error) {
      console.error('获取日志失败:', error)
      // 不停止轮询，可能是临时网络问题
    }
  }, 2000) // 每2秒轮询一次
}

// 保存为用例
const handleSaveAsCase = () => {
  showSaveDialog.value = true
  saveForm.name = ''
  saveForm.description = ''
}

const confirmSaveCase = async () => {
  if (!saveFormRef.value) return

  await saveFormRef.value.validate(async (valid) => {
    if (valid) {
      saving.value = true
      try {
        await createAICase({
          name: saveForm.name,
          description: saveForm.description,
          task_description: taskForm.description
        })

        ElMessage.success(t('uiAutomation.ai.messages.saveSuccess'))
        showSaveDialog.value = false
      } catch (error) {
        console.error('保存失败:', error)
        ElMessage.error(t('uiAutomation.ai.messages.saveFailed'))
      } finally {
        saving.value = false
      }
    }
  })
}
</script>

<style lang="scss" scoped>
.page-container {
  padding: var(--aitest-space-5);
}

.card-container {
  background-color: var(--aitest-surface);
  border-radius: var(--aitest-radius-sm);
  padding: var(--aitest-space-5);
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
  min-height: calc(100vh - 140px);
}

.section-title {
  font-size: var(--aitest-font-size-lg);
  font-weight: 600;
  margin-bottom: var(--aitest-space-4);
  padding-left: var(--aitest-space-3);
  border-left: 4px solid var(--el-color-primary);
}

.task-list-container {
  background-color: var(--aitest-canvas);
  border-radius: var(--aitest-radius-sm);
  padding: var(--aitest-space-4);
  margin-bottom: var(--aitest-space-5);
  height: calc(100vh - 200px);
  overflow-y: auto;
  
  .task-item {
    display: flex;
    align-items: flex-start;
    padding: var(--aitest-space-3);
    border-bottom: 1px solid var(--aitest-border);
    transition: all 0.3s;
    
    &:last-child {
      border-bottom: none;
    }
    
    &.completed {
      background-color: var(--aitest-success-bg);
      .task-desc {
        color: var(--el-color-success);
        text-decoration: line-through;
      }
    }
    
    &.in_progress {
      background-color: var(--el-color-primary-light-9);
      .task-desc {
        color: var(--el-color-primary);
        font-weight: bold;
      }
    }
    
    .task-status-icon {
      margin-right: var(--aitest-space-3);
      margin-top: 2px;
      font-size: var(--aitest-font-size-lg);
    }
    
    .task-content {
      flex: 1;
      line-height: 1.5;
      
      .task-id {
        font-weight: bold;
        margin-right: var(--aitest-space-1);
      }
    }
  }
}

.empty-tasks {
  color: var(--el-text-color-secondary);
  text-align: center;
  padding: var(--aitest-space-5);
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.analyzing-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--el-color-primary);
  
  .el-icon {
    font-size: 24px;
    margin-bottom: var(--aitest-space-3);
  }
}

.log-container {
  background-color: #1e1e1e;
  border-radius: var(--aitest-radius-sm);
  height: 300px;
  overflow-y: auto;
  padding: var(--aitest-space-4);
  color: #fff;
  font-family: 'Consolas', 'Monaco', monospace;
  
  .empty-logs {
    color: var(--el-text-color-secondary);
    text-align: center;
    margin-top: 100px;
  }
  
  .log-content {
    margin: 0;
    white-space: pre-wrap;
    word-wrap: break-word;
    font-size: var(--aitest-font-size-md);
    line-height: 1.5;
  }
}
</style>
