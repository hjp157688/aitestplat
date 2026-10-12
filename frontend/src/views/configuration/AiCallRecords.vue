<template>
  <div class="ai-call-records page-container page-container--full">
    <PageHeader :title="$t('configuration.aiCallRecords.title')" />

    <div class="card-container">
    <!-- 统计概览 -->
    <div class="stats-grid">
      <div v-for="s in statCards" :key="s.key" class="stat-card" :class="s.tone || ''">
        <div class="stat-label">{{ s.label }}</div>
        <div class="stat-value">{{ s.value }}</div>
      </div>
    </div>

    <!-- 筛选 -->
    <div class="filter-bar">
      <el-select v-model="filters.status" clearable :placeholder="$t('configuration.aiCallRecords.filterStatus')" class="filter-item">
        <el-option :label="$t('configuration.aiCallRecords.statusSuccess')" value="success" />
        <el-option :label="$t('configuration.aiCallRecords.statusFailed')" value="failed" />
      </el-select>

      <el-select v-model="filters.provider" clearable filterable :placeholder="$t('configuration.aiCallRecords.filterProvider')" class="filter-item">
        <el-option v-for="p in providerOptions" :key="p.value" :label="p.label" :value="p.value" />
      </el-select>

      <el-select v-model="filters.role" clearable filterable :placeholder="$t('configuration.aiCallRecords.filterRole')" class="filter-item">
        <el-option v-for="r in roleOptions" :key="r.value" :label="r.label" :value="r.value" />
      </el-select>

      <el-input v-model="filters.scenario" clearable :placeholder="$t('configuration.aiCallRecords.filterScenario')" class="filter-item" />

      <el-button type="primary" :icon="Search" @click="load(1)">{{ $t('configuration.common.search') }}</el-button>
      <el-button :icon="Refresh" @click="load()">{{ $t('configuration.aiCallRecords.refresh') }}</el-button>
    </div>

    <!-- 记录表 -->
    <div class="table-container">
      <el-table :data="records" v-loading="loading" class="records-table" height="100%">
      <el-table-column :label="$t('configuration.aiCallRecords.colTime')" width="170">
        <template #default="{ row }">
          <span class="mono">{{ formatTime(row.created_at) }}</span>
        </template>
      </el-table-column>
      <el-table-column :label="$t('configuration.aiCallRecords.colProvider')" min-width="120">
        <template #default="{ row }">
          {{ row.provider_display || row.provider }}
        </template>
      </el-table-column>
      <el-table-column prop="model_name" :label="$t('configuration.aiCallRecords.colModel')" min-width="140" />
      <el-table-column prop="role" :label="$t('configuration.aiCallRecords.colRole')" min-width="120" />
      <el-table-column prop="scenario" :label="$t('configuration.aiCallRecords.colScenario')" min-width="140" />
      <el-table-column :label="$t('configuration.aiCallRecords.colStatus')" width="90">
        <template #default="{ row }">
          <el-tag :type="row.status === 'success' ? 'success' : 'danger'" size="small">
            {{ row.status_display }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column :label="$t('configuration.aiCallRecords.colLatency')" width="100">
        <template #default="{ row }">
          <span class="mono">{{ row.latency_ms != null ? (row.latency_ms / 1000).toFixed(2) + 's' : '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column :label="$t('configuration.aiCallRecords.colTokens')" width="150">
        <template #default="{ row }">
          <span v-if="row.total_tokens != null" class="mono">{{ row.total_tokens }}</span>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column :label="$t('configuration.aiCallRecords.colCost')" width="110">
        <template #default="{ row }">
          <span class="mono">{{ row.cost_estimate != null ? '$' + row.cost_estimate : '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column :label="$t('configuration.aiCallRecords.colError')" min-width="180">
        <template #default="{ row }">
          <span v-if="row.error_message" class="error-text">{{ row.error_message }}</span>
          <span v-else>-</span>
        </template>
      </el-table-column>
    </el-table>
    </div>

    <div class="pagination-container">
      <el-pagination
        class="records-pagination"
        layout="total, prev, pager, next"
        :total="total"
        :page-size="pageSize"
        :current-page="page"
        @current-change="onPageChange"
      />
    </div>
    </div>
  </div>
</template>

<script>
import { ElMessage } from 'element-plus'
import { Search, Refresh } from '@element-plus/icons-vue'
import api from '@/utils/api'
import PageHeader from '@/components/common/PageHeader.vue'

export default {
  name: 'AiCallRecords',
  components: { PageHeader },
  data() {
    return {
      records: [],
      loading: false,
      page: 1,
      pageSize: 20,
      total: 0,
      stats: {
        total: 0, success: 0, failed: 0, success_rate: 1.0,
        avg_latency_ms: null, today_count: 0,
      },
      filters: {
        status: '',
        provider: '',
        role: '',
        scenario: ''
      },
      providerOptions: [
        { value: 'deepseek', label: 'DeepSeek' },
        { value: 'qwen', label: '通义千问' },
        { value: 'siliconflow', label: '硅基流动' },
        { value: 'zhipu', label: '智谱' },
        { value: 'xiaomi', label: '小米' },
        { value: 'xiaomi_coding_plan', label: '小米coding plan' },
        { value: 'openai', label: 'OpenAI' },
        { value: 'azure_openai', label: 'Azure OpenAI' },
        { value: 'anthropic', label: 'Anthropic' },
        { value: 'google_gemini', label: 'Google Gemini' },
        { value: 'other', label: '其他' }
      ],
      roleOptions: [
        { value: 'writer', label: 'writer' },
        { value: 'reviewer', label: 'reviewer' },
        { value: 'browser_use_text', label: 'browser_use_text' },
        { value: 'api_testcase_generator', label: 'api_testcase_generator' }
      ]
    }
  },
  computed: {
    statCards() {
      return [
        { key: 'total', label: this.$t('configuration.aiCallRecords.statTotal'), value: this.stats.total },
        { key: 'success', label: this.$t('configuration.aiCallRecords.statSuccess'), value: this.stats.success, tone: 'success' },
        { key: 'failed', label: this.$t('configuration.aiCallRecords.statFailed'), value: this.stats.failed, tone: 'danger' },
        { key: 'rate', label: this.$t('configuration.aiCallRecords.statRate'), value: Math.round((this.stats.success_rate || 0) * 100) + '%' },
        { key: 'avg', label: this.$t('configuration.aiCallRecords.statAvgLatency'), value: this.stats.avg_latency_ms != null ? (this.stats.avg_latency_ms / 1000).toFixed(2) + 's' : '-' },
        { key: 'today', label: this.$t('configuration.aiCallRecords.statToday'), value: this.stats.today_count }
      ]
    }
  },
  mounted() {
    this.load()
    this.loadStats()
  },
  methods: {
    formatTime(value) {
      if (!value) return '-'
      const d = new Date(value)
      const pad = n => String(n).padStart(2, '0')
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
    },
    buildParams(page) {
      const params = { page }
      if (this.filters.status) params.status = this.filters.status
      if (this.filters.provider) params.provider = this.filters.provider
      if (this.filters.role) params.role = this.filters.role
      if (this.filters.scenario) params.scenario = this.filters.scenario
      return params
    },
    async load(page = this.page) {
      this.loading = true
      try {
        const res = await api.get('/ai/ai-call-records/', { params: this.buildParams(page) })
        this.page = page
        this.total = res.data.count || 0
        this.records = (res.data.results || []).map(r => r.status === 'failed' ? r : r)
      } catch (e) {
        ElMessage.error(this.$t('configuration.aiCallRecords.loadFailed', { error: e.message }))
      } finally {
        this.loading = false
      }
    },
    async loadStats() {
      try {
        const params = {}
        if (this.filters.status) params.status = this.filters.status
        if (this.filters.provider) params.provider = this.filters.provider
        const res = await api.get('/ai/ai-call-records/stats/', { params })
        this.stats = res.data
      } catch (e) {
        console.error('load stats failed', e)
      }
    },
    onPageChange(p) {
      this.load(p)
    }
  }
}
</script>

<style scoped>
/* 页面骨架使用全局 .page-container--full 变体（工具栏/分页固定、表体内部滚动），本地不覆盖 */
.stats-grid {
  flex-shrink: 0;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: var(--aitest-space-3);
  margin-bottom: var(--aitest-space-4);
}
.stat-card {
  background: var(--aitest-canvas);
  border: 1px solid var(--aitest-border);
  border-radius: var(--aitest-radius-lg);
  padding: var(--aitest-space-3) var(--aitest-space-4);
}
.stat-card.success .stat-value { color: var(--aitest-success); }
.stat-card.danger .stat-value { color: var(--aitest-danger); }
.stat-label {
  font-size: var(--aitest-font-size-sm);
  color: var(--aitest-text-2);
  margin-bottom: var(--aitest-space-1);
}
.stat-value {
  font-size: var(--aitest-font-size-2xl);
  font-weight: 700;
  color: var(--aitest-primary);
  font-variant-numeric: tabular-nums;
}
.filter-item { width: 170px; }
.records-table { border: 1px solid var(--aitest-border); }
.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: var(--aitest-font-size-sm);
  color: var(--aitest-text-2);
}
.error-text {
  color: var(--aitest-danger);
  font-size: var(--aitest-font-size-sm);
  word-break: break-all;
  display: block;
  max-height: 40px;
  overflow: hidden;
}
</style>
