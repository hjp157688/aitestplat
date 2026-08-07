<template>
  <div class="requirement-management">
    <PageHeader :title="$t('requirementManagement.title')" />

    <!-- 操作栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <el-input
          v-model="searchKeyword"
          :placeholder="$t('requirementManagement.search')"
          prefix-icon="Search"
          clearable
          @clear="handleSearch"
          @keyup.enter="handleSearch"
          style="width: 260px"
        />
        <el-select
          v-model="filterProject"
          :placeholder="$t('requirementManagement.selectProject')"
          clearable
          @change="loadRequirements"
          style="width: 180px"
        >
          <el-option
            v-for="p in projects"
            :key="p.id"
            :label="p.name"
            :value="p.id"
          />
        </el-select>
        <el-select
          v-model="filterSourceType"
          clearable
          :placeholder="$t('requirementManagement.source')"
          @change="loadRequirements"
          style="width: 140px"
        >
          <el-option value="manual" :label="$t('requirementManagement.sourceManual')" />
          <el-option value="ai_import" :label="$t('requirementManagement.sourceAiImport')" />
          <el-option value="zentao" :label="$t('requirementManagement.sourceZentao')" />
        </el-select>
        <el-button @click="handleSearch">
          <el-icon><Search /></el-icon>
        </el-button>
      </div>
      <div class="toolbar-right">
        <el-button
          v-if="selectedIds.length > 0"
          type="primary"
          @click="openAiGenerate"
        >
          <el-icon><MagicStick /></el-icon>
          {{ $t('requirementManagement.aiGenerate') }} ({{ selectedIds.length }})
        </el-button>
        <el-button
          v-if="selectedIds.length > 0"
          type="danger"
          @click="handleBatchDelete"
          :loading="deleting"
        >
          {{ $t('requirementManagement.batchDelete') }} ({{ selectedIds.length }})
        </el-button>
        <el-button @click="loadRequirements" :loading="loading">
          <el-icon><Refresh /></el-icon>
        </el-button>
        <el-dropdown @command="handleCreateCommand">
          <el-button type="primary">
            <el-icon><Plus /></el-icon>
            {{ $t('requirementManagement.createRequirement') }}
            <el-icon><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="manual">
                <el-icon><Edit /></el-icon>
                {{ $t('requirementManagement.createRequirement') }}
              </el-dropdown-item>
              <el-dropdown-item command="ai">
                <el-icon><Upload /></el-icon>
                {{ $t('requirementManagement.aiImport') }}
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button type="success" @click="openSyncModal">
          <el-icon><Connection /></el-icon>
          {{ $t('requirementManagement.zentaoSync') }}
        </el-button>
      </div>
    </div>

    <!-- 需求列表表格 -->
    <el-table
      :data="requirements"
      v-loading="loading"
      @selection-change="handleSelectionChange"
      style="width: 100%"
    >
      <el-table-column type="selection" width="45" />
      <el-table-column
        prop="zentao_id"
        :label="$t('requirementManagement.zentaoId')"
        width="80"
      />
      <el-table-column
        prop="title"
        :label="$t('requirementManagement.requirementTitle')"
        min-width="200"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          <el-link type="primary" @click="openDetail(row)">{{ row.title }}</el-link>
        </template>
      </el-table-column>
      <el-table-column
        prop="project_name"
        :label="$t('requirementManagement.project')"
        width="120"
        show-overflow-tooltip
      />
      <el-table-column
        prop="priority"
        :label="$t('requirementManagement.priority')"
        width="80"
        align="center"
      >
        <template #default="{ row }">
          <el-tag v-if="row.priority" :type="priorityTagType(row.priority)" size="small">
            {{ row.priority }}
          </el-tag>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column
        prop="status"
        :label="$t('requirementManagement.status')"
        width="100"
        align="center"
      >
        <template #default="{ row }">
          <el-tag v-if="row.status" :type="statusTagType(row.status)" size="small">
            {{ statusLabel(row.status) }}
          </el-tag>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column
        prop="source_type_display"
        :label="$t('requirementManagement.source')"
        width="100"
        align="center"
      >
        <template #default="{ row }">
          <el-tag
            :type="sourceTypeColor(row.source_type)"
            size="small"
          >
            {{ row.source_type_display || sourceTypeLabel(row.source_type) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column
        prop="category"
        :label="$t('requirementManagement.category')"
        width="80"
        align="center"
      >
        <template #default="{ row }">
          {{ categoryLabel(row.category) }}
        </template>
      </el-table-column>
      <el-table-column
        prop="product_name"
        :label="$t('requirementManagement.product')"
        width="120"
        show-overflow-tooltip
      />
      <el-table-column
        prop="estimate"
        :label="$t('requirementManagement.estimate')"
        width="80"
        align="center"
      >
        <template #default="{ row }">
          {{ row.estimate != null ? row.estimate + 'h' : '-' }}
        </template>
      </el-table-column>
      <el-table-column
        prop="assigned_to"
        :label="$t('requirementManagement.assignedTo')"
        width="100"
      />
      <el-table-column
        prop="created_at"
        :label="$t('requirementManagement.createTime')"
        width="160"
      >
        <template #default="{ row }">
          {{ formatDateTime(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column
        :label="$t('requirementManagement.actions')"
        width="140"
        fixed="right"
      >
        <template #default="{ row }">
          <el-button type="primary" link size="small" @click="openDetail(row)">
            {{ $t('requirementManagement.viewDetail') }}
          </el-button>
          <el-button type="danger" link size="small" @click="handleDeleteSingle(row)">
            {{ $t('requirementManagement.delete') }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <div class="pagination-wrapper">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        @change="loadRequirements"
      />
    </div>

    <!-- 手动创建/编辑弹窗 -->
    <el-dialog
      v-model="createVisible"
      :title="isEditing ? $t('requirementManagement.editTitle') : $t('requirementManagement.createTitle')"
      width="640px"
      :close-on-click-modal="false"
    >
      <el-form ref="createFormRef" :model="createForm" :rules="createRules" label-width="100px">
        <el-form-item :label="$t('requirementManagement.selectProject')" prop="project">
          <el-select v-model="createForm.project" style="width: 100%" filterable>
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="$t('requirementManagement.requirementTitle')" prop="title">
          <el-input v-model="createForm.title" />
        </el-form-item>
        <el-form-item :label="$t('requirementManagement.spec')">
          <el-input v-model="createForm.spec" type="textarea" :rows="4" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item :label="$t('requirementManagement.priority')">
              <el-select v-model="createForm.priority" clearable>
                <el-option :value="1" :label="$t('requirementManagement.priority1')" />
                <el-option :value="2" :label="$t('requirementManagement.priority2')" />
                <el-option :value="3" :label="$t('requirementManagement.priority3')" />
                <el-option :value="4" :label="$t('requirementManagement.priority4')" />
                <el-option :value="5" :label="$t('requirementManagement.priority5')" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item :label="$t('requirementManagement.category')">
              <el-select v-model="createForm.category" clearable>
                <el-option value="feature" :label="$t('requirementManagement.feature')" />
                <el-option value="interface" :label="$t('requirementManagement.interface')" />
                <el-option value="performance" :label="$t('requirementManagement.performance')" />
                <el-option value="safe" :label="$t('requirementManagement.safe')" />
                <el-option value="experience" :label="$t('requirementManagement.experience')" />
                <el-option value="improve" :label="$t('requirementManagement.improve')" />
                <el-option value="other" :label="$t('requirementManagement.other')" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item :label="$t('requirementManagement.status')">
              <el-select v-model="createForm.status" clearable>
                <el-option value="draft" :label="$t('requirementManagement.draft')" />
                <el-option value="active" :label="$t('requirementManagement.active')" />
                <el-option value="closed" :label="$t('requirementManagement.closed')" />
                <el-option value="changed" :label="$t('requirementManagement.changed')" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="8">
            <el-form-item :label="$t('requirementManagement.stage')">
              <el-select v-model="createForm.stage" clearable>
                <el-option value="wait" :label="$t('requirementManagement.wait')" />
                <el-option value="planned" :label="$t('requirementManagement.planned')" />
                <el-option value="projected" :label="$t('requirementManagement.projected')" />
                <el-option value="developing" :label="$t('requirementManagement.developing')" />
                <el-option value="developed" :label="$t('requirementManagement.developed')" />
                <el-option value="testing" :label="$t('requirementManagement.testing')" />
                <el-option value="tested" :label="$t('requirementManagement.tested')" />
                <el-option value="verified" :label="$t('requirementManagement.verified')" />
                <el-option value="released" :label="$t('requirementManagement.released')" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item :label="$t('requirementManagement.estimate')">
              <el-input-number v-model="createForm.estimate" :min="0" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item :label="$t('requirementManagement.moduleId')">
              <el-input-number v-model="createForm.module_id" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item :label="$t('requirementManagement.productName')">
              <el-input v-model="createForm.product_name" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item :label="$t('requirementManagement.assignedTo')">
              <el-input v-model="createForm.assigned_to" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item :label="$t('requirementManagement.sourceNote')">
          <el-input v-model="createForm.source_note" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">{{ $t('common.cancel') }}</el-button>
        <el-button type="primary" @click="handleSaveCreate" :loading="saving">
          {{ $t('common.save') }}
        </el-button>
      </template>
    </el-dialog>

    <!-- AI导入弹窗 -->
    <el-dialog
      v-model="aiImportVisible"
      :title="$t('requirementManagement.aiImportTitle')"
      width="800px"
      :close-on-click-modal="false"
    >
      <!-- Step 0: 上传文件 -->
      <div v-if="aiImportStep === 0" class="ai-upload-area">
        <el-upload
          drag
          :auto-upload="false"
          :on-change="handleAiFileChange"
          :limit="1"
          accept=".txt,.md,.pdf,.docx,.xlsx"
          :show-file-list="false"
        >
          <el-icon :size="48"><UploadFilled /></el-icon>
          <div class="el-upload__text">
            {{ $t('requirementManagement.uploadFile') }}
          </div>
          <template #tip>
            <div class="el-upload__tip">
              {{ $t('requirementManagement.uploadHint') }}
            </div>
          </template>
        </el-upload>
        <div v-if="aiUploading" class="ai-parsing">
          <el-icon class="is-loading"><Loading /></el-icon>
          <span>{{ $t('requirementManagement.parsing') }}</span>
        </div>
      </div>

      <!-- Step 1: 确认解析结果 -->
      <div v-else>
        <el-alert
          type="info"
          :title="$t('requirementManagement.parseSuccess', { count: aiParsedItems.length })"
          :closable="false"
          show-icon
          style="margin-bottom: 16px"
        />
        <el-table
          :data="aiParsedItems"
          max-height="400"
          @selection-change="handleAiSelectionChange"
          ref="aiTableRef"
        >
          <el-table-column type="selection" width="45" />
          <el-table-column prop="title" :label="$t('requirementManagement.requirementTitle')" min-width="200" show-overflow-tooltip />
          <el-table-column prop="spec" :label="$t('requirementManagement.spec')" min-width="200" show-overflow-tooltip>
            <template #default="{ row }">{{ row.spec || '-' }}</template>
          </el-table-column>
          <el-table-column prop="category" :label="$t('requirementManagement.category')" width="100">
            <template #default="{ row }">{{ categoryLabel(row.category) }}</template>
          </el-table-column>
          <el-table-column prop="priority" :label="$t('requirementManagement.priority')" width="80" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.priority" :type="priorityTagType(row.priority)" size="small">{{ row.priority }}</el-tag>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column prop="estimate" :label="$t('requirementManagement.estimate')" width="80" align="center">
            <template #default="{ row }">{{ row.estimate != null ? row.estimate + 'h' : '-' }}</template>
          </el-table-column>
        </el-table>
        <div class="ai-import-footer">
          <el-button @click="resetAiImport">{{ $t('requirementManagement.reupload') }}</el-button>
          <div>
            <el-button type="link" @click="selectAllAiItems">{{ $t('requirementManagement.selectAll') }}</el-button>
            <el-button type="link" @click="deselectAllAiItems">{{ $t('requirementManagement.deselectedAll') }}</el-button>
          </div>
          <el-button
            type="primary"
            @click="handleAiImport"
            :loading="aiImporting"
            :disabled="aiSelectedItems.length === 0"
          >
            {{ $t('requirementManagement.confirmImport') }} ({{ aiSelectedItems.length }})
          </el-button>
        </div>
      </div>
    </el-dialog>

    <!-- AI生成用例弹窗 -->
    <el-dialog
      v-model="aiGenVisible"
      :title="$t('requirementManagement.aiGenerateTitle')"
      width="620px"
      :close-on-click-modal="false"
    >
      <div class="ai-gen-selection">
        <div class="ai-gen-selected-label">
          {{ $t('requirementManagement.aiGenerateSelected', { count: selectedIds.length }) }}
        </div>
        <div class="ai-gen-tags">
          <el-tag
            v-for="r in selectedRows"
            :key="r.id"
            type="info"
            effect="plain"
            size="small"
            class="ai-gen-tag"
          >{{ r.title }}</el-tag>
        </div>
        <p class="ai-gen-hint">{{ $t('requirementManagement.aiGenerateHint') }}</p>
      </div>

      <!-- 业务知识检索（按需求逐个检索，各需求独立选择上下文） -->
      <div class="knowledge-section">
        <div class="knowledge-toolbar">
          <el-button size="small" @click="retrieveAllKnowledge" :loading="isRetrievingAll">
            <el-icon><Search /></el-icon>
            {{ isRetrievingAll ? $t('requirementManagement.knowledgeRetrieving') : $t('requirementManagement.retrieveKnowledge') }}
          </el-button>
          <span class="knowledge-toolbar-hint">{{ $t('requirementManagement.perReqKnowledgeHint') }}</span>
        </div>

        <div class="per-req-knowledge">
          <div v-for="r in selectedRows" :key="r.id" class="req-knowledge-block">
            <div class="req-knowledge-head">
              <span class="req-knowledge-title" :title="r.title">{{ r.title }}</span>
              <span v-if="isRetrievingReq[r.id]" class="req-knowledge-status">
                {{ $t('requirementManagement.knowledgeRetrieving') }}
              </span>
              <el-button v-else size="small" text type="primary" @click="retrieveOneKnowledge(r)">
                {{ $t('requirementManagement.reRetrieve') }}
              </el-button>
              <span v-if="(selectedKnowledgeMap[r.id] || []).length" class="req-knowledge-count">
                {{ $t('requirementManagement.selectedKnowledgeCount', { count: selectedKnowledgeMap[r.id].length }) }}
              </span>
            </div>

            <div v-if="(selectedKnowledgeMap[r.id] || []).length" class="selected-knowledge-tags">
              <el-tag
                v-for="k in selectedKnowledgeMap[r.id].slice(0, 3)"
                :key="k.id"
                size="small"
                type="info"
                effect="plain"
                closable
                @close="removeSelectedKnowledge(r, k)"
              >{{ k.name }}</el-tag>
              <el-tag v-if="selectedKnowledgeMap[r.id].length > 3" size="small" type="info" effect="plain">
                +{{ selectedKnowledgeMap[r.id].length - 3 }}
              </el-tag>
            </div>

            <div v-if="knowledgeResultsMap[r.id] !== undefined" class="knowledge-panel">
              <div class="knowledge-panel-header">
                <span>{{ $t('requirementAnalysis.retrieveResults') }}</span>
                <span class="knowledge-count">{{ $t('requirementAnalysis.resultCount', { count: knowledgeResultsMap[r.id].length }) }}</span>
              </div>
              <div class="knowledge-panel-body">
                <div v-if="knowledgeResultsMap[r.id].length === 0" class="knowledge-empty">
                  {{ $t('requirementManagement.noKnowledge') }}
                </div>
                <label
                  v-for="k in knowledgeResultsMap[r.id]"
                  :key="k.id"
                  class="knowledge-item"
                  :class="{ selected: isKnowledgeSelected(r, k) }"
                >
                  <input type="checkbox" :checked="isKnowledgeSelected(r, k)" @change="toggleKnowledge(r, k)" />
                  <span class="knowledge-item-type" :class="k.type">
                    {{ k.type === 'chunk' ? '📄' : '🏷' }} {{ k.type === 'chunk' ? $t('requirementAnalysis.knowledgeChunk') : $t('requirementAnalysis.knowledgeEntry') }}
                  </span>
                  <span class="knowledge-item-name">{{ k.name }}</span>
                  <span class="knowledge-item-score" :class="{ high: k.score >= 7, low: k.score < 6 }">
                    {{ k.score.toFixed(1) }}
                  </span>
                </label>
              </div>
            </div>
          </div>
        </div>
      </div>

      <el-form label-width="96px" class="ai-gen-form">
        <el-form-item :label="$t('requirementManagement.outputMode')">
          <el-radio-group v-model="aiGenForm.output_mode">
            <el-radio value="stream">{{ $t('requirementManagement.outputModeStream') }}</el-radio>
            <el-radio value="complete">{{ $t('requirementManagement.outputModeComplete') }}</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item :label="$t('requirementManagement.granularity')">
          <el-radio-group v-model="aiGenForm.granularity">
            <el-radio value="coarse">{{ $t('requirementManagement.granularityCoarse') }}</el-radio>
            <el-radio value="medium">{{ $t('requirementManagement.granularityMedium') }}</el-radio>
            <el-radio value="fine">{{ $t('requirementManagement.granularityFine') }}</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item :label="$t('requirementManagement.caseType')">
          <el-input
            v-model="aiGenForm.case_type"
            :placeholder="$t('requirementManagement.caseTypePlaceholder')"
            maxlength="120"
          />
        </el-form-item>
        <el-form-item :label="$t('requirementManagement.useReviewer')">
          <el-switch v-model="aiGenForm.use_reviewer_model" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="aiGenVisible = false">{{ $t('common.cancel') }}</el-button>
        <el-button type="primary" @click="handleAiGenerate" :loading="aiGenerating">
          {{ $t('requirementManagement.aiGenerateStart') }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 禅道同步弹窗 -->
    <el-dialog
      v-model="syncVisible"
      :title="$t('requirementManagement.zentaoSyncTitle')"
      width="1000px"
      :close-on-click-modal="false"
    >
      <div class="sync-tabs">
        <el-radio-group v-model="syncMode" @change="resetSync">
          <el-radio-button value="product">{{ $t('requirementManagement.syncByProduct') }}</el-radio-button>
          <el-radio-button value="project">{{ $t('requirementManagement.syncByProject') }}</el-radio-button>
        </el-radio-group>
      </div>

      <div class="sync-toolbar">
        <div class="sync-toolbar-left">
          <el-button
            v-if="syncMode === 'product'"
            @click="loadZentaoProducts"
            :loading="syncingProducts"
          >
            {{ $t('requirementManagement.getProducts') }}
          </el-button>
          <el-button
            v-else
            @click="loadZentaoProjects"
            :loading="syncingProjects"
          >
            {{ $t('requirementManagement.getProjects') }}
          </el-button>
          <el-select
            v-model="syncTargetId"
            :placeholder="syncMode === 'product' ? $t('requirementManagement.selectProduct') : $t('requirementManagement.selectZentaoProject')"
            style="width: 300px"
            filterable
            @change="onSyncTargetChange"
            :loading="syncingStories"
          >
            <el-option
              v-for="item in syncTargetList"
              :key="item.id"
              :label="item.name"
              :value="item.id"
            />
          </el-select>
        </div>
        <el-button
          type="primary"
          @click="handleSync"
          :loading="syncing"
          :disabled="syncSelectedIds.length === 0"
        >
          {{ $t('requirementManagement.syncToLocal') }} ({{ syncSelectedIds.length }})
        </el-button>
      </div>

      <el-table
        :data="syncStories"
        max-height="400"
        @selection-change="handleSyncSelectionChange"
        v-loading="syncingStories"
      >
        <el-table-column type="selection" width="45" />
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="title" :label="$t('requirementManagement.requirementTitle')" min-width="300" show-overflow-tooltip />
        <el-table-column prop="pri" :label="$t('requirementManagement.priority')" width="80" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.pri" :type="priorityTagType(row.pri)" size="small">{{ row.pri }}</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" :label="$t('requirementManagement.status')" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.status" :type="statusTagType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="stage" :label="$t('requirementManagement.stage')" width="100" align="center">
          <template #default="{ row }">{{ stageLabel(row.stage) }}</template>
        </el-table-column>
        <el-table-column prop="category" :label="$t('requirementManagement.category')" width="80" align="center">
          <template #default="{ row }">{{ categoryLabel(row.category) }}</template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- 详情抽屉 -->
    <el-drawer
      v-model="detailVisible"
      :title="$t('requirementManagement.detailTitle')"
      size="600px"
    >
      <template v-if="detailLoading">
        <el-skeleton :rows="8" animated />
      </template>
      <template v-else-if="detail">
        <h3 class="detail-title">{{ detail.title }}</h3>
        <div v-if="detail.spec" class="detail-spec" v-html="detail.spec"></div>
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item :label="$t('requirementManagement.zentaoId')">{{ detail.zentao_id || '-' }}</el-descriptions-item>
          <el-descriptions-item :label="$t('requirementManagement.product')">{{ detail.product_name || '-' }}</el-descriptions-item>
          <el-descriptions-item :label="$t('requirementManagement.priority')">
            <el-tag v-if="detail.priority" :type="priorityTagType(detail.priority)" size="small">{{ detail.priority }}</el-tag>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item :label="$t('requirementManagement.status')">
            <el-tag v-if="detail.status" :type="statusTagType(detail.status)" size="small">{{ statusLabel(detail.status) }}</el-tag>
            <span v-else>-</span>
          </el-descriptions-item>
          <el-descriptions-item :label="$t('requirementManagement.stage')">{{ stageLabel(detail.stage) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('requirementManagement.category')">{{ categoryLabel(detail.category) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('requirementManagement.source')">{{ sourceTypeLabel(detail.source_type) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('requirementManagement.sourceNote')">{{ detail.source_note || '-' }}</el-descriptions-item>
          <el-descriptions-item :label="$t('requirementManagement.estimate')">{{ detail.estimate != null ? detail.estimate + 'h' : '-' }}</el-descriptions-item>
          <el-descriptions-item :label="$t('requirementManagement.moduleId')">{{ detail.module_id || '-' }}</el-descriptions-item>
          <el-descriptions-item :label="$t('requirementManagement.assignedTo')">{{ detail.assigned_to || '-' }}</el-descriptions-item>
          <el-descriptions-item :label="$t('requirementManagement.createTime')">{{ formatDateTime(detail.created_at) }}</el-descriptions-item>
          <el-descriptions-item :label="$t('requirementManagement.syncedAt')">{{ formatDateTime(detail.synced_at) }}</el-descriptions-item>
        </el-descriptions>
      </template>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, Plus, ArrowDown, Edit, Upload, Connection, UploadFilled, Loading, MagicStick } from '@element-plus/icons-vue'
import PageHeader from '@/components/common/PageHeader.vue'
import {
  getRequirements,
  getRequirement,
  createRequirement,
  updateRequirement,
  deleteRequirement,
  batchDeleteRequirements,
  aiParseRequirementsFile,
  aiImportRequirements,
  getZentaoProducts,
  getZentaoProjects,
  getZentaoProductStories,
  getZentaoProjectStories,
  syncZentaoRequirements,
  generateTestCasesForRequirements,
  retrieveKnowledge
} from '@/api/requirement'
import api from '@/utils/api'

const router = useRouter()

// ============ 列表数据 ============
const requirements = ref([])
const loading = ref(false)
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const searchKeyword = ref('')
const filterProject = ref(null)
const filterSourceType = ref('')
const selectedIds = ref([])
const selectedRows = ref([])
const deleting = ref(false)
const projects = ref([])

// ============ AI生成用例 ============
const aiGenVisible = ref(false)
const aiGenerating = ref(false)
const aiGenForm = reactive({
  output_mode: 'stream',
  granularity: 'medium',
  case_type: '',
  use_reviewer_model: true
})

// ============ 业务知识检索（按需求逐个检索，分组上下文） ============
const isRetrievingReq = reactive({})       // { [requirementId]: true }
const knowledgeResultsMap = reactive({})   // { [requirementId]: [检索结果] }
const selectedKnowledgeMap = reactive({})  // { [requirementId]: [{id,type,name,content}] }

// ============ 手动创建/编辑 ============
const createVisible = ref(false)
const isEditing = ref(false)
const editingId = ref(null)
const createFormRef = ref(null)
const saving = ref(false)
const createForm = reactive({
  project: null,
  title: '',
  spec: '',
  priority: null,
  category: '',
  status: 'draft',
  stage: '',
  estimate: null,
  module_id: null,
  product_name: '',
  assigned_to: '',
  source_note: ''
})

const createRules = {
  project: [{ required: true, message: '请选择项目', trigger: 'change' }],
  title: [{ required: true, message: '请输入需求标题', trigger: 'blur' }]
}

// ============ AI导入 ============
const aiImportVisible = ref(false)
const aiImportStep = ref(0)
const aiUploading = ref(false)
const aiParsedItems = ref([])
const aiSelectedItems = ref([])
const aiImporting = ref(false)
const aiTableRef = ref(null)

// ============ 禅道同步 ============
const syncVisible = ref(false)
const syncMode = ref('product')
const syncTargetList = ref([])
const syncTargetId = ref(null)
const syncStories = ref([])
const syncSelectedIds = ref([])
const syncingProducts = ref(false)
const syncingProjects = ref(false)
const syncingStories = ref(false)
const syncing = ref(false)

// ============ 详情 ============
const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref(null)

// ============ 辅助函数 ============
function formatDateTime(dateStr) {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function priorityTagType(pri) {
  if (pri <= 1) return 'danger'
  if (pri <= 2) return 'warning'
  if (pri <= 3) return 'info'
  return ''
}

function statusTagType(status) {
  const map = { active: 'success', closed: 'info', changed: 'warning', draft: '' }
  return map[status] || ''
}

function statusLabel(s) {
  const map = { draft: '草稿', active: '激活', closed: '已关闭', changed: '已变更' }
  return map[s] || s || '-'
}

function sourceTypeLabel(s) {
  const map = { zentao: '禅道同步', manual: '手动创建', ai_import: 'AI导入' }
  return map[s] || s || '-'
}

function sourceTypeColor(s) {
  const map = { zentao: 'success', manual: '', ai_import: 'warning' }
  return map[s] || ''
}

function categoryLabel(c) {
  const map = { feature: '功能', interface: '接口', performance: '性能', safe: '安全', experience: '体验', improve: '改进', other: '其他' }
  return map[c] || c || '-'
}

function stageLabel(s) {
  const map = { wait: '未开始', planned: '已计划', projected: '已立项', developing: '研发中', developed: '研发完毕', testing: '测试中', tested: '测试完毕', verified: '已验收', released: '已发布' }
  return map[s] || s || '-'
}

// ============ 列表操作 ============
async function loadProjects() {
  try {
    const res = await api.get('/projects/')
    projects.value = res.data.results || res.data || []
  } catch (e) {
    console.error('Failed to load projects:', e)
  }
}

async function loadRequirements() {
  loading.value = true
  try {
    const params = { page: currentPage.value, page_size: pageSize.value }
    if (filterProject.value) params.project_id = filterProject.value
    if (searchKeyword.value) params.keyword = searchKeyword.value
    if (filterSourceType.value) params.source_type = filterSourceType.value
    const res = await getRequirements(params)
    requirements.value = res.data.results || res.data || []
    total.value = res.data.count || 0
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '加载需求列表失败')
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  currentPage.value = 1
  loadRequirements()
}

function handleSelectionChange(selection) {
  selectedIds.value = selection.map(r => r.id)
  selectedRows.value = selection
}

// ============ AI生成用例 ============
function openAiGenerate() {
  if (selectedIds.value.length === 0) {
    ElMessage.warning('请先勾选需要生成用例的需求')
    return
  }
  aiGenVisible.value = true
}

async function handleAiGenerate() {
  if (selectedIds.value.length === 0) {
    ElMessage.warning('请先勾选需要生成用例的需求')
    return
  }
  aiGenerating.value = true
  try {
    // 组装的按需求ID分组的业务知识（每条需求只带自己选中的知识）
    const knowledgeMap = {}
    for (const r of selectedRows.value) {
      const list = selectedKnowledgeMap[r.id]
      if (list && list.length) {
        knowledgeMap[r.id] = list
      }
    }
    const res = await generateTestCasesForRequirements(selectedIds.value, {
      output_mode: aiGenForm.output_mode,
      granularity: aiGenForm.granularity,
      case_type: aiGenForm.case_type,
      use_reviewer_model: aiGenForm.use_reviewer_model,
      selected_knowledge: knowledgeMap
    })
    ElMessage.success(res.data?.message || `已创建 ${res.data?.created || 0} 条生成任务`)
    const failedCount = (res.data?.failed || []).length
    aiGenVisible.value = false
    try {
      await ElMessageBox.confirm(
        failedCount > 0
          ? `已为 ${res.data?.created || 0} 条需求创建生成任务，${failedCount} 条失败（${res.data.failed.join('、')}）。是否前往查看「AI用例生成记录」？`
          : `生成任务已创建，生成过程中可在「AI用例生成记录」中实时查看进度与结果。是否前往查看？`,
        '查看生成进度',
        { confirmButtonText: '前往查看', cancelButtonText: '留在本页', type: 'info' }
      )
      router.push('/ai-generation/generated-testcases')
    } catch (e) {
      /* 用户选择留在本页 */
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.error || 'AI生成任务创建失败')
  } finally {
    aiGenerating.value = false
  }
}

// ============ 业务知识检索（按需求逐个，各需求独立选择上下文） ============
const isRetrievingAll = computed(() => Object.values(isRetrievingReq).some(Boolean))

async function fetchKnowledgeForRequirement(r) {
  if (!r) return
  isRetrievingReq[r.id] = true
  try {
    const res = await retrieveKnowledge({
      requirement_text: `需求标题: ${r.title}\n\n需求描述:\n${(r.spec || '').slice(0, 2000)}`,
      project_id: r.project || null,
      top_k: 10
    })
    knowledgeResultsMap[r.id] = res.data.results || []
    // 默认勾选高分结果（score >= 6），与单需求生成页保持一致
    selectedKnowledgeMap[r.id] = knowledgeResultsMap[r.id]
      .filter(k => k.score >= 6)
      .map(k => ({ id: k.id, type: k.type, name: k.name, content: k.content }))
  } catch (e) {
    knowledgeResultsMap[r.id] = []
    ElMessage.error(`「${r.title}」业务知识检索失败：` + (e.response?.data?.error || e.message))
  } finally {
    isRetrievingReq[r.id] = false
  }
}

// 一键为所有选中的需求逐个检索（并发）
async function retrieveAllKnowledge() {
  if (selectedRows.value.length === 0) {
    ElMessage.warning('请先勾选需求')
    return
  }
  await Promise.all(selectedRows.value.map(r => fetchKnowledgeForRequirement(r)))
}

// 单独重搜某条需求
async function retrieveOneKnowledge(r) {
  await fetchKnowledgeForRequirement(r)
}

function toggleKnowledge(r, k) {
  const list = selectedKnowledgeMap[r.id] || (selectedKnowledgeMap[r.id] = [])
  const idx = list.findIndex(x => x.id === k.id)
  if (idx >= 0) {
    list.splice(idx, 1)
  } else {
    list.push({ id: k.id, type: k.type, name: k.name, content: k.content })
  }
}

function isKnowledgeSelected(r, k) {
  return (selectedKnowledgeMap[r.id] || []).some(x => x.id === k.id)
}

function removeSelectedKnowledge(r, k) {
  const list = selectedKnowledgeMap[r.id] || []
  const idx = list.findIndex(x => x.id === k.id)
  if (idx >= 0) {
    list.splice(idx, 1)
  }
}

async function handleBatchDelete() {
  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedIds.value.length} 条需求吗？`,
      '确认删除',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
    deleting.value = true
    await batchDeleteRequirements(selectedIds.value)
    ElMessage.success(`已删除 ${selectedIds.value.length} 条需求`)
    selectedIds.value = []
    loadRequirements()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error(e.response?.data?.error || '删除失败')
    }
  } finally {
    deleting.value = false
  }
}

async function handleDeleteSingle(row) {
  try {
    await ElMessageBox.confirm(
      `确定要删除需求"${row.title}"吗？`,
      '确认删除',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
    await deleteRequirement(row.id)
    ElMessage.success('删除成功')
    loadRequirements()
  } catch (e) {
    if (e !== 'cancel') {
      ElMessage.error(e.response?.data?.error || '删除失败')
    }
  }
}

// ============ 手动创建/编辑 ============
function handleCreateCommand(command) {
  if (command === 'manual') {
    openCreate()
  } else if (command === 'ai') {
    openAiImport()
  }
}

function openCreate() {
  isEditing.value = false
  editingId.value = null
  createForm.project = filterProject.value || null
  createForm.title = ''
  createForm.spec = ''
  createForm.priority = null
  createForm.category = ''
  createForm.status = 'draft'
  createForm.stage = ''
  createForm.estimate = null
  createForm.module_id = null
  createForm.product_name = ''
  createForm.assigned_to = ''
  createForm.source_note = ''
  createVisible.value = true
}

async function openDetail(row) {
  detailVisible.value = true
  detailLoading.value = true
  detail.value = null
  try {
    const res = await getRequirement(row.id)
    detail.value = res.data
  } catch (e) {
    ElMessage.error('加载详情失败')
  } finally {
    detailLoading.value = false
  }
}

async function handleSaveCreate() {
  const valid = await createFormRef.value.validate().catch(() => false)
  if (!valid) return

  saving.value = true
  try {
    const data = {
      project: createForm.project,
      title: createForm.title,
      spec: createForm.spec || '',
      priority: createForm.priority,
      category: createForm.category || '',
      status: createForm.status || 'draft',
      stage: createForm.stage || '',
      estimate: createForm.estimate,
      module_id: createForm.module_id,
      product_name: createForm.product_name || '',
      assigned_to: createForm.assigned_to || '',
      source_note: createForm.source_note || ''
    }
    if (isEditing.value) {
      await updateRequirement(editingId.value, data)
      ElMessage.success('需求更新成功')
    } else {
      await createRequirement(data)
      ElMessage.success('需求创建成功')
    }
    createVisible.value = false
    loadRequirements()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || e.response?.data?.error || '保存失败')
  } finally {
    saving.value = false
  }
}

// ============ AI导入 ============
function openAiImport() {
  aiImportVisible.value = true
  aiImportStep.value = 0
  aiParsedItems.value = []
  aiSelectedItems.value = []
  aiUploading.value = false
}

async function handleAiFileChange(uploadFile) {
  if (!uploadFile?.raw) return
  aiUploading.value = true
  const targetProjectId = filterProject.value || null
  try {
    const res = await aiParseRequirementsFile(targetProjectId, uploadFile.raw)
    if (res.data?.success && res.data.requirements?.length > 0) {
      aiParsedItems.value = res.data.requirements
      aiImportStep.value = 1
      // 默认全选
      setTimeout(() => {
        if (aiTableRef.value) {
          aiTableRef.value.toggleAllSelection()
        }
      }, 100)
    } else {
      ElMessage.error(res.data?.error || 'AI解析失败')
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.error || 'AI解析失败')
  } finally {
    aiUploading.value = false
  }
}

function handleAiSelectionChange(selection) {
  aiSelectedItems.value = selection
}

function selectAllAiItems() {
  if (aiTableRef.value) {
    aiTableRef.value.toggleAllSelection()
  }
}

function deselectAllAiItems() {
  if (aiTableRef.value) {
    aiTableRef.value.clearSelection()
  }
}

function resetAiImport() {
  aiImportStep.value = 0
  aiParsedItems.value = []
  aiSelectedItems.value = []
}

async function handleAiImport() {
  if (aiSelectedItems.value.length === 0) {
    ElMessage.warning('请选择要导入的需求')
    return
  }
  aiImporting.value = true
  const targetProjectId = filterProject.value || null
  try {
    const res = await aiImportRequirements(targetProjectId, aiSelectedItems.value)
    ElMessage.success(res.data?.message || `成功导入 ${res.data?.imported || 0} 条需求`)
    aiImportVisible.value = false
    loadRequirements()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '导入失败')
  } finally {
    aiImporting.value = false
  }
}

// ============ 禅道同步 ============
function openSyncModal() {
  syncVisible.value = true
  resetSync()
}

function resetSync() {
  syncTargetList.value = []
  syncTargetId.value = null
  syncStories.value = []
  syncSelectedIds.value = []
}

async function loadZentaoProducts() {
  syncingProducts.value = true
  try {
    const res = await getZentaoProducts()
    syncTargetList.value = res.data.products || []
    if (syncTargetList.value.length === 0) {
      ElMessage.warning('禅道中没有找到产品')
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '获取产品列表失败')
  } finally {
    syncingProducts.value = false
  }
}

async function loadZentaoProjects() {
  syncingProjects.value = true
  try {
    const res = await getZentaoProjects()
    syncTargetList.value = res.data.projects || []
    if (syncTargetList.value.length === 0) {
      ElMessage.warning('禅道中没有找到项目')
    }
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '获取项目列表失败')
  } finally {
    syncingProjects.value = false
  }
}

async function onSyncTargetChange(targetId) {
  if (!targetId) {
    syncStories.value = []
    return
  }
  syncingStories.value = true
  try {
    let res
    if (syncMode.value === 'product') {
      res = await getZentaoProductStories(targetId)
    } else {
      res = await getZentaoProjectStories(targetId)
    }
    syncStories.value = res.data.stories || []
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '获取需求列表失败')
  } finally {
    syncingStories.value = false
  }
}

function handleSyncSelectionChange(selection) {
  syncSelectedIds.value = selection.map(s => s.id)
}

async function handleSync() {
  if (syncSelectedIds.value.length === 0) {
    ElMessage.warning('请选择要同步的需求')
    return
  }
  syncing.value = true
  try {
    const targetProjectId = filterProject.value || null
    const productName = syncMode.value === 'product'
      ? syncTargetList.value.find(p => p.id === syncTargetId.value)?.name || ''
      : syncTargetList.value.find(p => p.id === syncTargetId.value)?.name || ''
    const res = await syncZentaoRequirements({
      project_id: targetProjectId,
      product_id: syncTargetId.value,
      product_name: productName,
      story_ids: syncSelectedIds.value
    })
    ElMessage.success(res.data?.message || '同步成功')
    syncVisible.value = false
    loadRequirements()
  } catch (e) {
    ElMessage.error(e.response?.data?.error || '同步失败')
  } finally {
    syncing.value = false
  }
}

onMounted(() => {
  loadProjects()
  loadRequirements()
})
</script>

<style scoped>
.requirement-management {
  padding: 28px 24px;
  max-width: 1400px;
  margin: 0 auto;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Inter', Roboto, sans-serif;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 12px;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pagination-wrapper {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.ai-upload-area {
  text-align: center;
  padding: 20px 0;
}

.ai-parsing {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 16px;
  color: var(--aitest-text-2);
}

.ai-import-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
}

.ai-gen-selection {
  background: #F8FAFC;
  border: 1px solid var(--aitest-border);
  border-radius: 8px;
  padding: 14px 16px;
  margin-bottom: 20px;
}

.ai-gen-selected-label {
  font-weight: 600;
  color: #0F172A;
  font-size: 0.9rem;
  margin-bottom: 8px;
}

.ai-gen-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  max-height: 120px;
  overflow: auto;
}

.ai-gen-tag {
  max-width: 320px;
}

.ai-gen-hint {
  margin: 10px 0 0;
  font-size: 0.8rem;
  color: var(--aitest-text-3);
  line-height: 1.6;
}

.ai-gen-form .el-radio-group {
  flex-wrap: wrap;
}

/* ---------- 业务知识检索 ---------- */
.knowledge-section {
  margin-bottom: 20px;
}

.knowledge-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.selected-knowledge-count {
  color: var(--aitest-text-2);
  font-size: 0.85rem;
  font-weight: 500;
}

.knowledge-toolbar-hint {
  color: var(--aitest-text-3);
  font-size: 0.78rem;
  line-height: 1.5;
}

.per-req-knowledge {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 360px;
  overflow: auto;
}

.req-knowledge-block {
  border: 1px solid var(--aitest-border);
  border-radius: 8px;
  padding: 10px 12px;
}

.req-knowledge-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.req-knowledge-title {
  flex: 1;
  font-weight: 600;
  color: #0F172A;
  font-size: 0.85rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.req-knowledge-status {
  font-size: 0.78rem;
  color: var(--aitest-text-3);
}

.req-knowledge-count {
  font-size: 0.78rem;
  color: var(--aitest-primary);
  font-weight: 600;
  background: var(--aitest-primary-subtle);
  padding: 1px 8px;
  border-radius: 10px;
}

.selected-knowledge-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.knowledge-panel {
  border: 1px solid var(--aitest-border);
  border-radius: 8px;
  margin-top: 10px;
  overflow: hidden;
}

.knowledge-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #F8FAFC;
  border-bottom: 1px solid var(--aitest-border);
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--aitest-text-2);
}

.knowledge-count {
  color: var(--aitest-text-3);
  font-family: var(--aitest-font-mono);
}

.knowledge-panel-body {
  max-height: 240px;
  overflow: auto;
}

.knowledge-empty {
  padding: 24px;
  text-align: center;
  color: var(--aitest-text-3);
  font-size: 0.85rem;
}

.knowledge-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  cursor: pointer;
  border-bottom: 1px solid var(--aitest-surface-subtle);
  font-size: 0.85rem;
  transition: background 0.15s;
}

.knowledge-item:hover {
  background: var(--aitest-surface-subtle);
}

.knowledge-item.selected {
  background: var(--aitest-primary-subtle);
}

.knowledge-item input[type="checkbox"] {
  accent-color: var(--aitest-primary);
  flex-shrink: 0;
}

.knowledge-item-type {
  flex-shrink: 0;
  font-size: 0.72rem;
  padding: 1px 6px;
  border-radius: 10px;
  background: var(--aitest-surface-subtle);
  color: var(--aitest-text-3);
  border: 1px solid var(--aitest-border);
}

.knowledge-item-name {
  flex: 1;
  color: var(--aitest-text-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.knowledge-item-score {
  flex-shrink: 0;
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--aitest-text-3);
}

.knowledge-item-score.high {
  color: var(--aitest-success);
}

.knowledge-item-score.low {
  color: var(--aitest-warning);
}

.knowledge-panel-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  border-top: 1px solid var(--aitest-border);
  background: #F8FAFC;
  font-size: 0.82rem;
  color: var(--aitest-text-2);
}

.sync-tabs {
  display: flex;
  justify-content: center;
  margin-bottom: 16px;
}

.sync-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 12px;
}

.sync-toolbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.detail-title {
  margin: 0 0 16px 0;
  font-size: 1.15rem;
  font-weight: 700;
  color: #0F172A;
}

.detail-spec {
  background: #F8FAFC;
  padding: 16px;
  border-radius: 8px;
  margin-bottom: 20px;
  font-size: 14px;
  line-height: 1.8;
  max-height: 300px;
  overflow: auto;
  border: 1px solid var(--aitest-border);
  color: var(--aitest-text-2);
}

.detail-spec :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 4px;
}
</style>