<template>
  <div class="requirement-analysis">
    <div class="page-header">
      <h1>{{ $t('requirementAnalysis.title') }}</h1>
      <p>{{ $t('requirementAnalysis.subtitle') }}</p>
    </div>

    <!-- AI 配置未就绪 · 可关细提醒条 -->
    <div v-if="configLoaded && configNotReady && !bannerDismissed && !checkingConfig" class="config-banner" role="status">
      <el-icon class="config-banner-icon"><WarningFilled /></el-icon>
      <span class="config-banner-text">{{ $t('configGuide.incompleteBanner') }}</span>
      <el-button size="small" type="primary" plain @click.stop="goToConfig">{{ $t('configGuide.goToConfig') }}</el-button>
      <button class="config-banner-close" type="button" @click="bannerDismissed = true" :aria-label="$t('configGuide.configureLater')">
        <el-icon><Close /></el-icon>
      </button>
    </div>

    <div class="main-content">
      <!-- 需求输入卡片（页签：粘贴需求 / 上传文档） -->
      <div class="input-card">
        <el-tabs v-model="activeTab" class="input-tabs">
          <!-- 粘贴需求 -->
          <el-tab-pane :label="$t('requirementAnalysis.inputTabsManual')" name="manual">
            <div class="input-form">
              <div class="form-group">
                <label>{{ $t('requirementAnalysis.requirementTitle') }} <span class="required">*</span></label>
                <input
                  v-model="manualInput.title"
                  type="text"
                  class="form-input"
                  :placeholder="$t('requirementAnalysis.titlePlaceholder')">
              </div>

              <div class="form-group">
                <label>{{ $t('requirementAnalysis.requirementDescription') }} <span class="required">*</span></label>
                <textarea
                  v-model="manualInput.description"
                  class="form-textarea"
                  rows="6"
                  :placeholder="$t('requirementAnalysis.descriptionPlaceholder')"></textarea>
                <div class="char-count">{{ $t('requirementAnalysis.charCount', { count: manualInput.description.length }) }}</div>
              </div>

              <div class="form-group">
                <label>{{ $t('requirementAnalysis.associatedProject') }}</label>
                <select v-model="manualInput.selectedProject" class="form-select">
                  <option value="">{{ $t('requirementAnalysis.selectProject') }}</option>
                  <option v-for="project in projects" :key="project.id" :value="project.id">
                    {{ project.name }}
                  </option>
                </select>
              </div>

              <!-- 业务知识检索 -->
              <div class="knowledge-section">
                <button
                  class="retrieve-knowledge-btn"
                  @click="doRetrieveKnowledge"
                  :disabled="isRetrieving || !(manualInput.title && manualInput.description)">
                  <span v-if="isRetrieving"><el-icon class="btn-icon"><Search /></el-icon> {{ $t('requirementAnalysis.retrieving') }}</span>
                  <span v-else><el-icon class="btn-icon"><Search /></el-icon> {{ $t('requirementAnalysis.retrieveKnowledge') }}</span>
                </button>

                <div v-if="selectedKnowledge.length > 0" class="selected-knowledge-summary">
                  {{ $t('requirementAnalysis.selectedKnowledge', { count: selectedKnowledge.length }) }}
                  <span class="selected-tags">
                    <span v-for="k in selectedKnowledge.slice(0, 3)" :key="k.id" class="knowledge-tag">
                      {{ k.name }}
                    </span>
                    <span v-if="selectedKnowledge.length > 3" class="knowledge-tag">+{{ selectedKnowledge.length - 3 }}</span>
                  </span>
                </div>
              </div>

              <!-- 检索结果面板 -->
              <div v-if="showKnowledgePanel" class="knowledge-panel">
                <div class="knowledge-panel-header">
                  <span>{{ $t('requirementAnalysis.retrieveResults') }}</span>
                  <span class="knowledge-count">{{ $t('requirementAnalysis.resultCount', { count: knowledgeResults.length }) }}</span>
                </div>
                <div class="knowledge-panel-body">
                  <div v-if="knowledgeResults.length === 0 && !isRetrieving" class="knowledge-empty">
                    {{ $t('requirementAnalysis.noResults') }}
                  </div>
                  <div
                    v-for="k in knowledgeResults"
                    :key="k.id"
                    class="knowledge-item"
                    :class="{ selected: isKnowledgeSelected(k) }"
                    @click="toggleKnowledge(k)">
                    <div class="knowledge-item-header">
                      <label class="knowledge-checkbox">
                        <input type="checkbox" :checked="isKnowledgeSelected(k)" @click.stop="toggleKnowledge(k)">
                      </label>
                      <span class="knowledge-item-name">{{ k.name }}</span>
                      <span
                        class="knowledge-item-type"
                        :class="k.type"
                        :title="k.type === 'chunk' ? $t('requirementAnalysis.knowledgeTypeHintChunk') : $t('requirementAnalysis.knowledgeTypeHintEntry')">
                        {{ k.type === 'chunk' ? '📄' : '🏷' }} {{ k.type === 'chunk' ? $t('requirementAnalysis.knowledgeChunk') : $t('requirementAnalysis.knowledgeEntry') }}
                      </span>
                      <span class="knowledge-item-score" :class="{ high: k.score >= 7, low: k.score < 6 }">
                        {{ k.score.toFixed(1) }}
                      </span>
                    </div>
                    <div class="knowledge-item-content">{{ k.content }}</div>
                  </div>
                </div>
                <div class="knowledge-panel-footer">
                  <span>{{ $t('requirementAnalysis.selected', { count: selectedKnowledge.length }) }}</span>
                  <button class="confirm-knowledge-btn" @click="confirmKnowledgeSelection">
                    {{ $t('requirementAnalysis.confirmSelection') }}
                  </button>
                </div>
              </div>
            </div>
          </el-tab-pane>

          <!-- 上传文档 -->
          <el-tab-pane :label="$t('requirementAnalysis.inputTabsUpload')" name="upload">
            <div class="input-form">
              <div class="upload-area"
                   @dragover.prevent
                   @drop="handleDrop"
                   :class="{ 'drag-over': isDragOver }"
                   @dragenter="isDragOver = true"
                   @dragleave="isDragOver = false">
                <div v-if="!selectedFile" class="upload-placeholder">
                  <el-icon class="upload-icon"><Upload /></el-icon>
                  <p>{{ $t('requirementAnalysis.dragDropText') }}</p>
                  <p class="upload-hint">{{ $t('requirementAnalysis.supportedFormats') }}</p>
                  <input
                    type="file"
                    ref="fileInput"
                    @change="handleFileSelect"
                    accept=".pdf,.doc,.docx,.txt,.md"
                    style="display: none;">
                  <button class="select-file-btn" @click="triggerFileInput">
                    {{ $t('requirementAnalysis.selectFile') }}
                  </button>
                </div>

                <div v-else class="file-selected">
                  <div class="file-info">
                    <el-icon class="file-icon"><Document /></el-icon>
                    <div class="file-details">
                      <p class="file-name">{{ selectedFile.name }}</p>
                      <p class="file-size">{{ formatFileSize(selectedFile.size) }}</p>
                    </div>
                    <button class="remove-file" @click="removeFile"><el-icon><CircleClose /></el-icon></button>
                  </div>
                </div>
              </div>

              <div v-if="selectedFile" class="document-info">
                <div class="form-group">
                  <label>{{ $t('requirementAnalysis.documentTitle') }}</label>
                  <input
                    v-model="documentTitle"
                    type="text"
                    class="form-input"
                    :placeholder="$t('requirementAnalysis.documentPlaceholder')">
                </div>

                <div class="form-group">
                  <label>{{ $t('requirementAnalysis.associatedProject') }}</label>
                  <select v-model="selectedProject" class="form-select">
                    <option value="">{{ $t('requirementAnalysis.selectProject') }}</option>
                    <option v-for="project in projects" :key="project.id" :value="project.id">
                      {{ project.name }}
                    </option>
                  </select>
                </div>
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>

        <!-- 统一生成条：输出模式 + 生成按钮 -->
        <div class="generate-bar">
          <div class="output-mode-compact">
            <span class="output-mode-label">{{ $t('requirementAnalysis.outputModeDesc') }}</span>
            <div class="segmented" role="radiogroup" :aria-label="$t('requirementAnalysis.outputModeTitle')">
              <button
                type="button"
                class="segmented-option"
                :class="{ active: globalOutputMode === 'stream' }"
                role="radio"
                :aria-checked="globalOutputMode === 'stream'"
                @click="globalOutputMode = 'stream'">
                <span class="segmented-radio" :class="{ on: globalOutputMode === 'stream' }"></span>
                {{ $t('requirementAnalysis.realtimeStream') }}
              </button>
              <button
                type="button"
                class="segmented-option"
                :class="{ active: globalOutputMode === 'complete' }"
                role="radio"
                :aria-checked="globalOutputMode === 'complete'"
                @click="globalOutputMode = 'complete'">
                <span class="segmented-radio" :class="{ on: globalOutputMode === 'complete' }"></span>
                {{ $t('requirementAnalysis.completeOutput') }}
              </button>
            </div>
          </div>
          <div class="case-type-field">
            <span class="output-mode-label">{{ $t('requirementAnalysis.caseTypeLabel') }}</span>
            <input
              v-model="caseType"
              type="text"
              class="form-input case-type-input"
              maxlength="120"
              :placeholder="$t('requirementAnalysis.caseTypePlaceholder')">
          </div>

          <div class="granularity-field">
            <span class="output-mode-label">{{ $t('requirementAnalysis.granularityLabel') }}</span>
            <div class="segmented" role="radiogroup" :aria-label="$t('requirementAnalysis.granularityLabel')">
              <button
                type="button"
                class="segmented-option"
                :class="{ active: granularity === 'coarse' }"
                role="radio"
                :aria-checked="granularity === 'coarse'"
                :title="$t('requirementAnalysis.granularityCoarseHint')"
                @click="granularity = 'coarse'">
                {{ $t('requirementAnalysis.granularityCoarse') }}
              </button>
              <button
                type="button"
                class="segmented-option"
                :class="{ active: granularity === 'medium' }"
                role="radio"
                :aria-checked="granularity === 'medium'"
                :title="$t('requirementAnalysis.granularityMediumHint')"
                @click="granularity = 'medium'">
                {{ $t('requirementAnalysis.granularityMedium') }}
              </button>
              <button
                type="button"
                class="segmented-option"
                :class="{ active: granularity === 'fine' }"
                role="radio"
                :aria-checked="granularity === 'fine'"
                :title="$t('requirementAnalysis.granularityFineHint')"
                @click="granularity = 'fine'">
                {{ $t('requirementAnalysis.granularityFine') }}
              </button>
            </div>
          </div>
          <button
            class="generate-manual-btn"
            @click="handleGenerate"
            :disabled="!canGenerate || isGenerating">
            <span v-if="isGenerating">{{ $t('requirementAnalysis.generating') }}</span>
            <span v-else><el-icon class="btn-icon"><Lightning /></el-icon> {{ $t('requirementAnalysis.generateButton') }}</span>
          </button>
        </div>
      </div>

      <!-- 生成结果区：常驻，空态/进度/结果就地呈现 -->
      <div class="results-area">
        <!-- 空态 -->
        <div v-if="!isGenerating && !showResults && !generationError && !taskCancelled" class="results-empty">
          <div class="results-empty-icon"><el-icon><MagicStick /></el-icon></div>
          <p class="results-empty-title">{{ $t('requirementAnalysis.resultsEmptyTitle') }}</p>
          <p class="results-empty-desc">{{ $t('requirementAnalysis.resultsEmptyDesc') }}</p>
          <el-button v-if="configNotReady" type="primary" size="small" @click="goToConfig">
            {{ $t('configGuide.goToConfig') }}
          </el-button>
        </div>

        <!-- 生成中 / 已出结果 -->
        <div v-if="isGenerating || showResults || taskCancelled || generationError" class="generation-panel" :class="{ 'is-generating': isGenerating && !showResults }">
          <!-- 结果头 -->
          <div class="result-header">
            <div class="result-header-row">
              <span class="result-kicker">{{ $t('requirementAnalysis.resultsTitle') }}</span>
              <span v-if="currentTaskId" class="mono result-task-id">#{{ currentTaskId }}</span>
              <span class="result-header-spacer"></span>
              <span class="status-chip" :class="statusChipClass">
                <span class="status-dot"></span>
                {{ statusChipText }}
              </span>
            </div>

            <div class="mini-steps">
              <div class="mini-step" :class="{ active: currentStep >= 1 }">
                <span class="mini-step-num mono">1</span>
                <span class="mini-step-text">{{ $t('requirementAnalysis.stepAnalysis') }}</span>
              </div>
              <div class="mini-step" :class="{ active: currentStep >= 2 }">
                <span class="mini-step-num mono">2</span>
                <span class="mini-step-text">{{ $t('requirementAnalysis.stepWriting') }}</span>
              </div>
              <div v-if="showReviewStep" class="mini-step" :class="{ active: currentStep >= 3 }">
                <span class="mini-step-num mono">3</span>
                <span class="mini-step-text">{{ $t('requirementAnalysis.stepReview') }}</span>
              </div>
              <div class="mini-step" :class="{ active: currentStep >= (showReviewStep ? 4 : 3) }">
                <span class="mini-step-num mono">{{ showReviewStep ? 4 : 3 }}</span>
                <span class="mini-step-text">{{ $t('requirementAnalysis.stepComplete') }}</span>
              </div>
            </div>

            <!-- 常驻动作条（完成后常驻在结果头下） -->
            <div v-if="showResults" class="action-bar">
              <el-button type="primary" plain @click="downloadTestCases">
                <el-icon class="btn-icon"><Download /></el-icon>{{ $t('requirementAnalysis.downloadExcel') }}
              </el-button>
              <el-button v-if="!savedToRecords" type="primary" @click="saveToTestCaseRecords">
                <el-icon class="btn-icon"><Tickets /></el-icon>{{ $t('requirementAnalysis.saveToRecords') }}
              </el-button>
              <el-button v-else type="success" disabled>
                <el-icon class="btn-icon"><CircleCheckFilled /></el-icon>{{ $t('requirementAnalysis.savedTag') }}
              </el-button>
              <el-button @click="handleGenerate">
                <el-icon class="btn-icon"><RefreshRight /></el-icon>{{ $t('requirementAnalysis.againGenerate') }}
              </el-button>
              <el-button text @click="openHistory">
                <el-icon class="btn-icon"><Clock /></el-icon>{{ $t('requirementAnalysis.historyEntry') }}
              </el-button>
            </div>
            <!-- 生成中：取消 -->
            <div v-else-if="isGenerating" class="cancel-row-wrap">
              <button class="cancel-generation-btn" @click="cancelGeneration">
                {{ $t('requirementAnalysis.cancelGeneration') }}
              </button>
            </div>
          </div>

          <!-- 面内失败态 -->
          <div v-if="generationError" class="failure-card">
            <el-icon class="failure-icon"><WarningFilled /></el-icon>
            <div class="failure-body">
              <p class="failure-title">{{ $t('requirementAnalysis.failureTitle') }}</p>
              <p class="failure-msg">{{ generationError }}</p>
            </div>
            <el-button type="primary" size="small" @click="retryGeneration">
              <el-icon class="btn-icon"><RefreshRight /></el-icon>{{ $t('requirementAnalysis.failureRetry') }}
            </el-button>
          </div>

          <!-- 区块一：用例草稿（流式实时堆积） -->
          <section v-if="streamedCases.length > 0" class="result-section">
            <div class="result-section-head">
              <span class="result-section-title">
                <span class="pulse-dot" v-if="isGenerating && !showResults"></span>
                {{ $t('requirementAnalysis.realtimeGeneratedContent') }}
              </span>
              <span class="result-section-meta mono">{{ $t('requirementAnalysis.caseCount', { count: streamedCases.length }) }}</span>
            </div>
            <div class="cards-grid">
              <div
                v-for="(tc, idx) in streamedCases"
                :key="'gen-' + idx"
                class="testcase-card"
                :class="{ 'is-incomplete': tc._incomplete, 'is-new': tc._justArrived }"
              >
                <div class="card-header">
                  <span class="case-id mono">{{ tc.caseId || 'TC' + String(idx + 1).padStart(3, '0') }}</span>
                  <span class="priority-badge" :class="(tc.priority || 'P2').toLowerCase()">{{ tc.priority || 'P2' }}</span>
                </div>
                <div class="card-scenario">{{ tc.scenario || $t('requirementAnalysis.parsing') }}</div>
                <div class="card-divider"></div>
                <div class="card-field" v-if="tc.precondition">
                  <span class="field-icon"><el-icon><Tickets /></el-icon></span>
                  <span class="field-label">{{ $t('requirementAnalysis.cardPrecondition') }}</span>
                  <span class="field-value">{{ tc.precondition }}</span>
                </div>
                <template v-if="tc.stepsList && tc.stepsList.length">
                  <div class="card-field">
                    <span class="field-icon"><el-icon><EditPen /></el-icon></span>
                    <span class="field-label">{{ $t('requirementAnalysis.cardSteps') }}</span>
                    <div class="step-list">
                      <div v-for="(step, si) in tc.stepsList" :key="si" class="step-row">
                        <span class="step-order">{{ +si + 1 }}.</span>
                        <span class="step-desc">{{ step.desc || '—' }}</span>
                        <span class="step-expect" v-if="step.expect">
                          <span class="expect-label">{{ $t('requirementAnalysis.cardExpected') }}：</span>{{ step.expect }}
                        </span>
                      </div>
                    </div>
                  </div>
                </template>
                <template v-else>
                  <div class="card-field" v-if="tc.steps">
                    <span class="field-icon"><el-icon><EditPen /></el-icon></span>
                    <span class="field-label">{{ $t('requirementAnalysis.cardSteps') }}</span>
                    <span class="field-value">{{ tc.steps }}</span>
                  </div>
                  <div class="card-field" v-if="tc.expected">
                    <span class="field-icon"><el-icon><CircleCheck /></el-icon></span>
                    <span class="field-label">{{ $t('requirementAnalysis.cardExpected') }}</span>
                    <span class="field-value">{{ tc.expected }}</span>
                  </div>
                </template>
                <div v-if="tc._incomplete && isGenerating && !showResults" class="streaming-shimmer"></div>
              </div>
            </div>
          </section>

          <!-- 区块二：AI 评审意见 -->
          <section v-if="streamedReviewContent" class="result-section">
            <div class="result-section-head">
              <span class="result-section-title">{{ $t('requirementAnalysis.aiReviewComments') }}</span>
              <span class="result-section-actions">
                <span class="result-section-meta mono">{{ $t('requirementAnalysis.characters', { count: streamedReviewContent.length }) }}</span>
                <el-button size="small" text @click="copyContent(streamedReviewContent)">
                  <el-icon class="btn-icon"><CopyDocument /></el-icon>{{ $t('requirementAnalysis.copyBtn') }}
                </el-button>
              </span>
            </div>
            <div class="stream-content" v-html="formatMarkdown(streamedReviewContent)"></div>
          </section>

          <!-- 区块三：最终用例 -->
          <section v-if="parsedFinalCases.length > 0" class="result-section final">
            <div class="result-section-head">
              <span class="result-section-title">
                {{ $t('requirementAnalysis.finalVersionTestCases') }}
                <span v-if="isGenerating && !showResults" class="streaming-indicator">{{ $t('requirementAnalysis.generating') }}</span>
              </span>
              <span class="result-section-actions">
                <span class="result-section-meta mono">{{ $t('requirementAnalysis.caseCount', { count: parsedFinalCases.length }) }}</span>
                <el-button size="small" text @click="copyContent(finalTestCases)">
                  <el-icon class="btn-icon"><CopyDocument /></el-icon>{{ $t('requirementAnalysis.copyBtn') }}
                </el-button>
              </span>
            </div>
            <div class="cards-grid">
              <div
                v-for="(tc, idx) in parsedFinalCases"
                :key="'final-' + idx"
                class="testcase-card final-card"
                :class="{ 'is-new': tc._justArrived }"
              >
                <div class="card-header">
                  <span class="case-id mono">{{ tc.caseId || 'TC' + String(idx + 1).padStart(3, '0') }}</span>
                  <span class="priority-badge" :class="(tc.priority || 'P2').toLowerCase()">{{ tc.priority || 'P2' }}</span>
                </div>
                <div class="card-scenario">{{ tc.scenario || '' }}</div>
                <div class="card-divider"></div>
                <div class="card-field" v-if="tc.precondition">
                  <span class="field-icon"><el-icon><Tickets /></el-icon></span>
                  <span class="field-label">{{ $t('requirementAnalysis.cardPrecondition') }}</span>
                  <span class="field-value">{{ tc.precondition }}</span>
                </div>
                <template v-if="tc.stepsList && tc.stepsList.length">
                  <div class="card-field">
                    <span class="field-icon"><el-icon><EditPen /></el-icon></span>
                    <span class="field-label">{{ $t('requirementAnalysis.cardSteps') }}</span>
                    <div class="step-list">
                      <div v-for="(step, si) in tc.stepsList" :key="si" class="step-row">
                        <span class="step-order">{{ +si + 1 }}.</span>
                        <span class="step-desc">{{ step.desc || '—' }}</span>
                        <span class="step-expect" v-if="step.expect">
                          <span class="expect-label">{{ $t('requirementAnalysis.cardExpected') }}：</span>{{ step.expect }}
                        </span>
                      </div>
                    </div>
                  </div>
                </template>
                <template v-else>
                  <div class="card-field" v-if="tc.steps">
                    <span class="field-icon"><el-icon><EditPen /></el-icon></span>
                    <span class="field-label">{{ $t('requirementAnalysis.cardSteps') }}</span>
                    <span class="field-value">{{ tc.steps }}</span>
                  </div>
                  <div class="card-field" v-if="tc.expected">
                    <span class="field-icon"><el-icon><CircleCheck /></el-icon></span>
                    <span class="field-label">{{ $t('requirementAnalysis.cardExpected') }}</span>
                    <span class="field-value">{{ tc.expected }}</span>
                  </div>
                </template>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>

    <!-- AI 配置引导弹窗（标准 el-dialog） -->
    <el-dialog
      v-model="showConfigGuide"
      :title="$t('configGuide.title')"
      width="560px"
      append-to-body
      class="config-guide-dialog"
    >
      <p class="config-guide-subtitle">{{ $t('configGuide.subtitle') }}</p>
      <div class="config-guide-list">
        <template v-for="(row, idx) in configGuideRows" :key="row.key">
          <div v-if="idx === 0 || row.group !== configGuideRows[idx - 1].group" class="config-guide-group">
            {{ row.groupLabel }}
          </div>
          <div class="config-guide-row">
            <el-tag :type="row.tagType" effect="light" size="small" round>{{ row.statusText }}</el-tag>
            <span class="config-guide-label">{{ row.label }}</span>
            <span class="config-guide-name mono">{{ row.name || '—' }}</span>
          </div>
        </template>
      </div>
      <template #footer>
        <el-button @click="showConfigGuide = false">{{ $t('configGuide.configureLater') }}</el-button>
        <el-button type="primary" @click="goToConfig">{{ $t('configGuide.goToConfig') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import api from '@/utils/api'
import { ElMessage } from 'element-plus'
import * as XLSX from 'xlsx'
import { useUserStore } from '@/stores/user'
import { Upload, Document, CircleClose, Tickets, EditPen, CircleCheck, Download, Search, Lightning, WarningFilled, Close, MagicStick, CopyDocument, Clock, RefreshRight, CircleCheckFilled } from '@element-plus/icons-vue'
import { retrieveKnowledge } from '@/api/requirement'

// localStorage 键：草稿 / 输出模式 / 提醒条关闭状态
const STORAGE_KEYS = {
  draft: 'aitestpl:ra:manual-draft',
  outputMode: 'aitestpl:ra:output-mode',
  bannerDismissed: 'aitestpl:ra:config-banner-dismissed',
  caseType: 'aitestpl:ra:case-type',
  granularity: 'aitestpl:ra:granularity'
}

export default {
  name: 'RequirementAnalysisView',
  data() {
    return {
      // 全局输出模式设置
      globalOutputMode: 'stream',  // 默认使用流式输出

      // 手动输入需求
      manualInput: {
        title: '',
        description: '',
        selectedProject: ''
      },

      // 文件上传
      selectedFile: null,
      documentTitle: '',
      selectedProject: '',
      projects: [],
      isDragOver: false,

      // 生成状态
      isGenerating: false,
      currentTaskId: null,
      progressText: '',
      currentStep: 0,
      pollInterval: null,
      draftTimer: null,  // 草稿保存节流定时器
      eventSource: null,  // SSE连接
      streamedContent: '',  // 流式接收的内容
      streamedReviewContent: '',  // 流式接收的评审内容
      finalTestCases: '',  // 最终版用例
      streamedCases: [],  // 从流式内容解析出的用例卡片
      parsedFinalCases: [],  // 从最终版用例解析出的用例卡片
      hasShownCompletionMessage: false,  // 是否已经显示过完成消息
      showReviewStep: true,  // 是否显示评审步骤（根据生成配置决定）

      // 生成结果
      showResults: false,
      generationResult: null,

      // AI配置状态
      configStatus: {
        overall_status: 'unknown',
        message: '',
        writer_model: {
          configured: false,
          enabled: false,
          name: null,
          provider: null,
          id: null,
          required: true
        },
        writer_prompt: {
          configured: false,
          enabled: false,
          name: null,
          id: null,
          required: true
        },
        reviewer_model: {
          configured: false,
          enabled: false,
          name: null,
          id: null,
          required: true
        },
        reviewer_prompt: {
          configured: false,
          enabled: false,
          name: null,
          id: null,
          required: true
        },
        generation_config: {
          configured: false,
          enabled: false,
          name: null,
          id: null,
          required: true,
          default_output_mode: null
        }
      },
      showConfigGuide: false,
      checkingConfig: true,
      modalKey: 0,  // 用于强制重新渲染弹窗

      // 业务知识检索
      isRetrieving: false,
      knowledgeResults: [],
      selectedKnowledge: [],
      showKnowledgePanel: false,

      // 新交互状态
      activeTab: 'manual',          // 输入页签：manual | upload
      generationError: null,        // 面内失败信息
      savedToRecords: false,        // 是否已保存到用例库
      savedCount: 0,                // 已导入条数
      taskCancelled: false,         // 本次生成是否被取消
      lastRequest: null,            // 最近一次生成请求（供重试）
      pendingDraftRestore: null,    // 重试时保留的流式草稿
      bannerDismissed: false,       // 配置提醒条是否已关闭
      configLoaded: false,          // 配置检查是否成功（失败时静默，不误导用户）
      caseType: '',            // 用例类型补充指令（自由文本）
      granularity: 'medium',   // 颗粒度：coarse | medium | fine
    }
  },

  computed: {
    canGenerateManual() {
      return this.manualInput.title.trim() &&
             this.manualInput.description.trim() &&
             this.manualInput.description.length <= 2000
    },

    // 当前页签下的生成可用性（统一生成按钮）
    canGenerate() {
      if (this.activeTab === 'manual') return this.canGenerateManual
      return !!(this.selectedFile && this.documentTitle)
    },

    // AI 配置是否未就绪（驱动提醒条/空态引导；与后端语义一致：生成行为配置只需 configured）
    configNotReady() {
      return this.configGuideRows.some(r => {
        if (r.key === 'generation_config') {
          return !this.configStatus[r.key] || !this.configStatus[r.key].configured
        }
        return r.status !== 'enabled'
      })
    },

    // 配置引导弹窗的行数据（名称 + 状态）
    configGuideRows() {
      const groupLabels = {
        model: this.$t('configGuide.modelConfig'),
        prompt: this.$t('configGuide.promptConfig'),
        generation: this.$t('configGuide.generationConfig')
      }
      const defs = [
        { key: 'writer_model', label: this.$t('configGuide.caseWriter'), group: 'model' },
        { key: 'reviewer_model', label: this.$t('configGuide.caseReviewer'), group: 'model' },
        { key: 'writer_prompt', label: this.$t('configGuide.caseWriter'), group: 'prompt' },
        { key: 'reviewer_prompt', label: this.$t('configGuide.caseReviewer'), group: 'prompt' },
        { key: 'generation_config', label: this.$t('configGuide.generationSettings'), group: 'generation' }
      ]
      return defs.map(d => {
        const c = this.configStatus[d.key]
        const status = !c ? 'unconfigured' : (c.enabled ? 'enabled' : (c.configured ? 'disabled' : 'unconfigured'))
        return {
          key: d.key,
          group: d.group,
          groupLabel: groupLabels[d.group],
          label: d.label,
          name: c && c.name ? c.name : '',
          status,
          statusText: status === 'enabled'
            ? this.$t('configGuide.enabled')
            : (status === 'disabled' ? this.$t('configGuide.disabled') : this.$t('configGuide.unconfigured')),
          tagType: status === 'enabled' ? 'success' : (status === 'disabled' ? 'warning' : 'danger')
        }
      })
    },

    // 结果头状态文案
    statusChipText() {
      if (this.taskCancelled) return this.$t('requirementAnalysis.generationCancelled')
      if (this.showResults) {
        return this.savedToRecords
          ? this.$t('requirementAnalysis.savedTag')
          : this.$t('requirementAnalysis.statusCompleted')
      }
      if (this.generationError) return this.$t('requirementAnalysis.statusFailed')
      return this.progressText || this.$t('requirementAnalysis.preparing')
    },

    // 结果头状态样式
    statusChipClass() {
      if (this.generationError || this.taskCancelled) return 'err'
      if (this.showResults) return 'ok'
      return 'run'
    }
  },

  watch: {
    finalTestCases(val) {
      if (val) {
        this.parsedFinalCases = this.parseStreamingTestCases(val)
      } else {
        this.parsedFinalCases = []
      }
    },

    'manualInput.title'() {
      this.persistDraft()
    },

    'manualInput.description'() {
      this.persistDraft()
    },

    globalOutputMode(val) {
      try { localStorage.setItem(STORAGE_KEYS.outputMode, val) } catch (e) { /* ignore */ }
    },

    caseType(val) {
      try { localStorage.setItem(STORAGE_KEYS.caseType, val) } catch (e) { /* ignore */ }
    },
    granularity(val) {
      try { localStorage.setItem(STORAGE_KEYS.granularity, val) } catch (e) { /* ignore */ }
    },
  },

  mounted() {
    this.progressText = this.$t('requirementAnalysis.preparing')
    // 恢复本地记忆：输出模式 / 需求草稿 / 提醒条关闭状态
    try {
      const mode = localStorage.getItem(STORAGE_KEYS.outputMode)
      if (mode === 'stream' || mode === 'complete') this.globalOutputMode = mode
      const draftRaw = localStorage.getItem(STORAGE_KEYS.draft)
      if (draftRaw) {
        const draft = JSON.parse(draftRaw)
        if (draft && (draft.title || draft.description)) {
          this.manualInput.title = draft.title || ''
          this.manualInput.description = draft.description || ''
          this.manualInput.selectedProject = draft.selectedProject || ''
        }
      }
      const caseType = localStorage.getItem(STORAGE_KEYS.caseType)
      if (caseType) this.caseType = caseType
      const granularity = localStorage.getItem(STORAGE_KEYS.granularity)
      if (granularity === 'coarse' || granularity === 'medium' || granularity === 'fine') {
        this.granularity = granularity
      }
      this.bannerDismissed = localStorage.getItem(STORAGE_KEYS.bannerDismissed) === '1'
    } catch (e) { /* ignore */ }
    this.loadProjects()
    this.checkConfigStatus()
  },

  activated() {
    // 当从其他页面返回时，重新检查配置状态
    // 立即隐藏弹窗和遮罩层，强制重新渲染
    this.showConfigGuide = false
    this.checkingConfig = true
    this.modalKey += 1  // 改变key值，强制重新渲染弹窗

    // 延迟检查配置，确保页面完全加载后再显示弹窗
    setTimeout(async () => {
      await this.checkConfigStatus()
    }, 200)
  },

  beforeUnmount() {
    if (this.pollInterval) {
      clearInterval(this.pollInterval)
    }
    if (this.draftTimer) {
      clearTimeout(this.draftTimer)
    }
    // 停止token自动刷新定时器
    const userStore = useUserStore()
    userStore.stopAutoRefresh()
  },

  methods: {
    async loadProjects() {
      try {
        const response = await api.get('/projects/')
        this.projects = response.data.results || response.data
      } catch (error) {
        console.error(this.$t('requirementAnalysis.loadProjectsFailed'), error)
      }
    },

    async checkConfigStatus() {
      try {
        this.checkingConfig = true
        const response = await api.get('/requirement-analysis/config/check/')
        this.configStatus = response.data
        this.configLoaded = true

        // 判断逻辑：只有当"用例编写模型"、"用例评审模型"、"用例编写提示词"和"用例评审提示词"都配置且启用时，才不显示弹框
        const writerModelReady = response.data.writer_model &&
                                response.data.writer_model.configured &&
                                response.data.writer_model.enabled

        const reviewerModelReady = response.data.reviewer_model &&
                                  response.data.reviewer_model.configured &&
                                  response.data.reviewer_model.enabled

        const writerPromptReady = response.data.writer_prompt &&
                                 response.data.writer_prompt.configured &&
                                 response.data.writer_prompt.enabled

        const reviewerPromptReady = response.data.reviewer_prompt &&
                                   response.data.reviewer_prompt.configured &&
                                   response.data.reviewer_prompt.enabled

        // 检查生成行为配置
        const generationConfigReady = response.data.generation_config &&
                                      response.data.generation_config.configured

        // 只有五项都准备好时才不显示引导弹框
        if (writerModelReady && reviewerModelReady && writerPromptReady && reviewerPromptReady && generationConfigReady) {
          this.showConfigGuide = false

          // 如果生成配置允许用户修改，则使用配置的默认输出模式
          if (response.data.generation_config && response.data.generation_config.default_output_mode) {
            this.globalOutputMode = response.data.generation_config.default_output_mode
          }

          // 根据生成配置的enable_auto_review决定是否显示评审步骤
          if (response.data.generation_config && response.data.generation_config.enable_auto_review !== null) {
            this.showReviewStep = response.data.generation_config.enable_auto_review
          } else {
            this.showReviewStep = true  // 默认显示
          }
        } else {
          this.showConfigGuide = true
        }
      } catch (error) {
        console.error('Failed to check config status:', error)
        // 如果检查失败，默认不显示引导，避免影响正常使用
        this.configLoaded = false
        this.showConfigGuide = false
        this.checkingConfig = false
      } finally {
        this.checkingConfig = false
      }
    },

    goToConfig() {
      // 智能判断跳转目标：优先跳转到未配置/未启用的页面
      // 优先级：必需配置 > 可选配置，提示词 > 模型

      // 0. 首先检查生成行为配置（generation_config）
      if (!this.configStatus.generation_config || !this.configStatus.generation_config.configured) {
        this.$router.push('/configuration/generation-config')
        return
      }

      // 1. 优先检查必需的提示词配置（writer_prompt）
      if (!this.configStatus.writer_prompt.configured || !this.configStatus.writer_prompt.enabled) {
        this.$router.push('/configuration/prompt-config')
        return
      }

      // 2. 检查必需的模型配置（writer_model）
      if (!this.configStatus.writer_model.configured || !this.configStatus.writer_model.enabled) {
        this.$router.push('/configuration/ai-model')
        return
      }

      // 3. 检查可选的评审提示词（reviewer_prompt）
      if (!this.configStatus.reviewer_prompt.configured || !this.configStatus.reviewer_prompt.enabled) {
        this.$router.push('/configuration/prompt-config')
        return
      }

      // 4. 检查可选的评审模型（reviewer_model）
      if (!this.configStatus.reviewer_model.configured || !this.configStatus.reviewer_model.enabled) {
        this.$router.push('/configuration/ai-model')
        return
      }

      // 默认跳转到生成行为配置
      this.$router.push('/configuration/generation-config')
    },

    goToPromptConfig() {
      this.$router.push('/configuration/prompt-config')
    },

    handleDrop(event) {
      event.preventDefault()
      this.isDragOver = false
      const files = event.dataTransfer.files
      if (files.length > 0) {
        this.handleFileSelect({ target: { files } })
      }
    },

    handleFileSelect(event) {
      const file = event.target.files[0]
      if (file) {
        const allowedTypes = [
          'application/pdf',
          'application/msword',
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
          'text/plain',
          'text/markdown',
          'text/x-markdown'
        ]

        if (allowedTypes.includes(file.type) ||
            file.name.match(/\.(pdf|doc|docx|txt|md)$/i)) {
          this.selectedFile = file
          this.documentTitle = file.name.replace(/\.[^/.]+$/, "")
        } else {
          ElMessage.error(this.$t('requirementAnalysis.invalidFileFormatDetail'))
        }
      }
    },

    removeFile() {
      this.selectedFile = null
      this.documentTitle = ''
      // 清空文件输入框（v-if 使输入框可能在 DOM 之外，需判空），允许重复选择同一文件
      const fileInput = /** @type {HTMLInputElement | undefined} */ (this.$refs.fileInput)
      if (fileInput) fileInput.value = ''
    },

    // 触发隐藏的文件输入框（$refs 在 JS + checkJs 下类型为 unknown，显式收窄）
    triggerFileInput() {
      const fileInput = /** @type {HTMLInputElement | undefined} */ (this.$refs.fileInput)
      if (fileInput) fileInput.click()
    },

    formatFileSize(bytes) {
      if (bytes === 0) return '0 Bytes'
      const k = 1024
      const sizes = ['Bytes', 'KB', 'MB', 'GB']
      const i = Math.floor(Math.log(bytes) / Math.log(k))
      return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
    },

    // 统一生成入口：依据当前页签分发
    async handleGenerate() {
      if (this.activeTab === 'manual') {
        await this.generateFromManualInput()
      } else {
        await this.generateFromDocument()
      }
    },

    // 需求草稿防丢（本地持久化，节流写入）
    persistDraft() {
      clearTimeout(this.draftTimer)
      this.draftTimer = setTimeout(() => {
        try {
          localStorage.setItem(STORAGE_KEYS.draft, JSON.stringify(this.manualInput))
        } catch (e) { /* ignore */ }
      }, 400)
    },

    // 一键复制
    async copyContent(text) {
      if (!text) return
      try {
        await navigator.clipboard.writeText(text)
        ElMessage.success(this.$t('requirementAnalysis.copySuccess'))
      } catch (e) {
        // 兼容非安全上下文的降级方案
        const ta = document.createElement('textarea')
        ta.value = text
        ta.style.position = 'fixed'
        ta.style.opacity = '0'
        document.body.appendChild(ta)
        ta.select()
        try {
          document.execCommand('copy')
          ElMessage.success(this.$t('requirementAnalysis.copySuccess'))
        } catch (err) {
          ElMessage.error(this.$t('requirementAnalysis.copyFailed'))
        }
        document.body.removeChild(ta)
      }
    },

    // 生成历史入口（复用现有列表页）
    openHistory() {
      this.$router.push('/ai-generation/generated-testcases')
    },

    // 面内失败 → 一键重试（保留已流式收到的草稿）
    async retryGeneration() {
      if (!this.lastRequest) return
      const last = this.lastRequest
      this.pendingDraftRestore = this.streamedContent
      this.generationError = null
      this.taskCancelled = false
      this.savedToRecords = false
      this.savedCount = 0
      this.finalTestCases = ''
      this.parsedFinalCases = []
      this.streamedReviewContent = ''
      this.hasShownCompletionMessage = false
      this.showResults = false
      await this.startGeneration(last.title, last.text, last.projectId, last.mode, last.caseType || '', last.granularity || 'medium')
    },

    async generateFromManualInput() {
      if (!this.canGenerateManual) {
        ElMessage.error(this.$t('requirementAnalysis.fillRequiredInfo'))
        return
      }

      const requirementText = `${this.$t('requirementAnalysis.requirementTitle')}: ${this.manualInput.title}\n\n${this.$t('requirementAnalysis.requirementDescription')}:\n${this.manualInput.description}`

      await this.startGeneration(
        this.manualInput.title,
        requirementText,
        this.manualInput.selectedProject,
        this.globalOutputMode,  // 使用全局输出模式
        this.caseType,
        this.granularity
      )
    },

    async generateFromDocument() {
      if (!this.selectedFile || !this.documentTitle) {
        ElMessage.error(this.$t('requirementAnalysis.selectFileAndTitle'))
        return
      }

      try {
        // 首先上传并提取文档内容
        const formData = new FormData()
        formData.append('title', this.documentTitle)
        formData.append('file', this.selectedFile)
        if (this.selectedProject) {
          formData.append('project', this.selectedProject)
        }

        ElMessage.info(this.$t('requirementAnalysis.extractingContent'))
        const uploadResponse = await api.post('/requirement-analysis/documents/', formData, {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        })

        // 提取文档内容
        const extractResponse = await api.get(`/requirement-analysis/documents/${uploadResponse.data.id}/extract_text/`)
        const extractedText = extractResponse.data.extracted_text

        if (!extractedText || extractedText.trim().length === 0) {
          ElMessage.error(this.$t('requirementAnalysis.extractionFailed'))
          return
        }

        const requirementText = `${this.$t('requirementAnalysis.documentTitle')}: ${this.documentTitle}\n\n${this.$t('requirementAnalysis.documentContent')}:\n${extractedText}`

        await this.startGeneration(
          this.documentTitle,
          requirementText,
          this.selectedProject,
          this.globalOutputMode,  // 使用全局输出模式
          this.caseType,
          this.granularity
        )

      } catch (error) {
        console.error(this.$t('requirementAnalysis.documentProcessingFailed'), error)
        ElMessage.error(this.$t('requirementAnalysis.documentProcessingFailed') + ': ' + (error.response?.data?.error || error.message))
      }
    },

    // 业务知识检索
    async doRetrieveKnowledge() {
      const requirementText = this.buildRequirementText()
      if (!requirementText) {
        ElMessage.warning(this.$t('requirementAnalysis.enterRequirementFirst'))
        return
      }
      this.isRetrieving = true
      this.showKnowledgePanel = true
      this.knowledgeResults = []
      try {
        const projectId = this.manualInput.selectedProject || this.selectedProject || null
        const res = await retrieveKnowledge({
          requirement_text: requirementText,
          project_id: projectId,
          top_k: 10
        })
        this.knowledgeResults = res.data.results || []
        // 默认勾选高分结果 (score >= 6)
        this.selectedKnowledge = this.knowledgeResults
          .filter(k => k.score >= 6)
          .map(k => ({ id: k.id, type: k.type, name: k.name, content: k.content }))
      } catch (e) {
        ElMessage.error(this.$t('requirementAnalysis.retrieveFailed') + ': ' + (e.response?.data?.error || e.message))
      } finally {
        this.isRetrieving = false
      }
    },

    toggleKnowledge(knowledge) {
      const idx = this.selectedKnowledge.findIndex(k => k.id === knowledge.id)
      if (idx >= 0) {
        this.selectedKnowledge.splice(idx, 1)
      } else {
        this.selectedKnowledge.push({
          id: knowledge.id,
          type: knowledge.type,
          name: knowledge.name,
          content: knowledge.content
        })
      }
    },

    isKnowledgeSelected(knowledge) {
      return this.selectedKnowledge.some(k => k.id === knowledge.id)
    },

    confirmKnowledgeSelection() {
      this.showKnowledgePanel = false
    },

    buildRequirementText() {
      if (this.manualInput.title && this.manualInput.description) {
        return `${this.$t('requirementAnalysis.requirementTitle')}: ${this.manualInput.title}\n\n${this.$t('requirementAnalysis.requirementDescription')}:\n${this.manualInput.description}`
      }
      if (this.documentTitle && this.selectedFile) {
        return `${this.$t('requirementAnalysis.documentTitle')}: ${this.documentTitle}`
      }
      return ''
    },

    async startGeneration(title, requirementText, projectId, outputMode = 'stream', caseType = '', granularity = 'medium') {
      // 记录本次请求，供失败后一键重试
      this.lastRequest = { title, text: requirementText, projectId, mode: outputMode, caseType, granularity }

      // 在开始生成前，主动刷新token确保生成过程中不会过期
      try {
        const userStore = useUserStore()
        if (userStore.isTokenExpiringSoon && userStore.refreshToken) {
          console.log('Refreshing token before generation...')
          await userStore.refreshAccessToken()
          console.log('Token refreshed successfully, safe to start generation')
        } else if (userStore.accessToken) {
          console.log('Token status is good, no refresh needed')
        }
      } catch (error) {
        console.error('Token refresh failed:', error)
        ElMessage.error(this.$t('requirementAnalysis.tokenRefreshFailed'))
        return
      }

      this.isGenerating = true
      this.taskCancelled = false
      this.generationError = null  // 清空上次失败信息
      this.showResults = false  // 隐藏上一次的结果
      this.currentStep = 1
      this.progressText = this.$t('requirementAnalysis.creatingTask')
      this.streamedContent = ''  // 清空流式内容
      this.finalTestCases = ''  // 清空最终版用例
      this.streamedReviewContent = ''  // 清空评审内容
      this.streamedCases = []  // 清空用例卡片
      this.parsedFinalCases = []  // 清空最终用例卡片
      this.savedToRecords = false
      this.savedCount = 0
      this.hasShownCompletionMessage = false  // 重置完成消息标志位

      try {
        // 调用新的生成API
        const requestData = {
          title: title,
          requirement_text: requirementText,
          use_writer_model: true,
          use_reviewer_model: true,
          output_mode: outputMode  // 添加输出模式参数
        }

        if (caseType) requestData.case_type = caseType
        requestData.granularity = granularity

        // 如果选择了项目，添加到请求中
        if (projectId) {
          requestData.project = projectId
        }

        // 如果有选择的业务知识，添加到请求中
        if (this.selectedKnowledge && this.selectedKnowledge.length > 0) {
          requestData.selected_knowledge = this.selectedKnowledge
        }

        const response = await api.post('/requirement-analysis/testcase-generation/generate/', requestData)

        this.currentTaskId = response.data.task_id
        this.progressText = this.$t('requirementAnalysis.taskCreated')

        ElMessage.success(this.$t('requirementAnalysis.generateSuccess'))

        // 根据输出模式选择不同的进度获取方式
        if (outputMode === 'stream') {
          this.startStreamingProgress()
        } else {
          this.startPolling()
        }

      } catch (error) {
        console.error(this.$t('requirementAnalysis.createTaskFailed'), error)
        ElMessage.error(this.$t('requirementAnalysis.createTaskFailed') + ': ' + (error.response?.data?.error || error.message))
        this.isGenerating = false
        this.generationError = this.$t('requirementAnalysis.createTaskFailed') + ': ' + (error.response?.data?.error || error.message)
      }
    },

    startStreamingProgress() {
      // 使用SSE进行流式进度获取
      // 注意：EventSource不使用axios代理，需要直接指向后端服务器
      // 完整的URL路径: /api/requirement-analysis/testcase-generation/{task_id}/stream_progress/

      // 动态获取后端URL：使用当前页面的协议和主机名
      // 在生产环境中(如Docker部署)，通常通过Nginx反向代理访问，端口应该是80或443(与当前页面一致)
      // 而不是直接访问后端端口8000
      const currentOrigin = window.location.origin
      const apiUrl = `${currentOrigin}/api/requirement-analysis/testcase-generation/${this.currentTaskId}/stream_progress/`

      console.log('SSE连接URL:', apiUrl)

      // 创建EventSource（不支持自定义headers，使用withCredentials发送cookie）
      this.eventSource = new EventSource(apiUrl, { withCredentials: true })

      // 监听连接打开事件
      this.eventSource.onopen = (event) => {
        console.log('✅ SSE连接已打开', event)
      }

      this.eventSource.onmessage = (event) => {
        console.log('📨 收到SSE消息:', event.data)

        try {
          const data = JSON.parse(event.data)
          console.log('📦 解析后的数据:', data)

          if (data.type === 'progress') {
            // Update progress status
            if (data.status === 'generating') {
              this.currentStep = 2
              this.progressText = `${this.$t('requirementAnalysis.statusGenerating')} ${data.progress}%`
            } else if (data.status === 'reviewing') {
              this.currentStep = 3
              this.progressText = `${this.$t('requirementAnalysis.statusReviewing')} ${data.progress}%`
            } else if (data.status === 'revising') {
              this.currentStep = 3
              this.progressText = `${this.$t('requirementAnalysis.statusRevising')} ${data.progress}%`
            }
          } else if (data.type === 'content') {
            // Real-time streaming content (case generation)
            console.log('✍️ Received streaming content:', data.content.length, 'characters')
            // 重试场景：第一批内容到来前先恢复上次已流式的草稿
            if (this.pendingDraftRestore) {
              this.streamedContent = this.pendingDraftRestore + data.content
              this.pendingDraftRestore = null
            } else {
              this.streamedContent += data.content
            }
            this.streamedCases = this.parseStreamingTestCases(this.streamedContent)
            this.currentStep = 2
            this.progressText = this.$t('requirementAnalysis.statusGenerating')
          } else if (data.type === 'review_content') {
            // Real-time review content
            console.log('📝 Received review content:', data.content.length, 'characters', 'Total length:', this.streamedReviewContent.length + data.content.length)
            this.streamedReviewContent += data.content
            this.currentStep = 3
            this.progressText = this.$t('requirementAnalysis.statusReviewing')
          } else if (data.type === 'final_content') {
            // Real-time final test cases content
            console.log('🎯 Received final cases content:', data.content.length, 'characters', 'Total length:', this.finalTestCases.length + data.content.length)
            this.finalTestCases += data.content
            this.currentStep = 3
            this.progressText = this.$t('requirementAnalysis.statusRevising')
          } else if (data.type === 'status') {
            // Final status
            console.log('📊 Received status update:', data.status)
            if (data.status === 'completed') {
              this.progressText = this.$t('requirementAnalysis.statusCompleted')
              // Fetch final result
              this.fetchFinalResult()
            } else if (data.status === 'failed') {
              this.progressText = this.$t('requirementAnalysis.statusFailed')
              this.generationError = data.error_message || data.error || this.$t('requirementAnalysis.generateFailed')
              this.handleGenerationError()
            }
          } else if (data.type === 'done') {
            // 流式结束，立即关闭EventSource，获取最终结果
            console.log('✅ 流式传输完成')
            if (this.eventSource) {
              console.log('🔒 关闭SSE连接')
              this.eventSource.close()
              this.eventSource = null
            }
            this.fetchFinalResult()
          }
        } catch (e) {
          console.error('❌ 解析SSE数据失败:', e, '原始数据:', event.data)
        }
      }

      this.eventSource.onerror = (error) => {
        console.log('⚠️ SSE连接事件:', error)

        // 如果EventSource已经被关闭（在onmessage中关闭的），不做任何处理
        if (!this.eventSource) {
          console.log('ℹ️ EventSource已关闭，忽略错误事件')
          return
        }

        console.log('EventSource状态:', {
          readyState: this.eventSource.readyState,
          url: this.eventSource.url
        })

        // 如果任务已经完成或不在生成中，不要降级
        if (this.showResults || !this.isGenerating) {
          console.log('ℹ️ 任务已完成或不在生成中，不降级到轮询')
          // 清理EventSource
          if (this.eventSource) {
            this.eventSource.close()
            this.eventSource = null
          }
          return
        }

        // readyState=2表示连接已关闭，readyState=0表示连接中断
        // EventSource会自动重连（readyState=0），除非是致命错误（readyState=2）
        if (this.eventSource.readyState === 2) {
          console.error('❌ SSE连接永久关闭，降级到轮询模式')
          this.eventSource.close()
          this.eventSource = null
          ElMessage.warning(this.$t('requirementAnalysis.streamConnectionInterrupted'))
          this.startPolling()
        } else if (this.eventSource.readyState === 0) {
          // EventSource正在重连，等待一段时间后检查
          console.log('🔄 SSE正在重连...')
          setTimeout(() => {
            // 如果5秒后还是断开状态，降级到轮询
            if (this.eventSource && this.eventSource.readyState === 0) {
              console.error('❌ SSE重连失败，降级到轮询模式')
              this.eventSource.close()
              this.eventSource = null
              ElMessage.warning(this.$t('requirementAnalysis.streamConnectionInterrupted'))
              this.startPolling()
            }
          }, 5000)
        }
      }
    },

    async fetchFinalResult() {
      try {
        // 修复URL：去掉多余的/api/前缀（axios baseURL已经包含/api）
        const response = await api.get(`/requirement-analysis/testcase-generation/${this.currentTaskId}/progress/`)
        const task = response.data

        this.generationResult = task
        this.showResults = true
        this.isGenerating = false

        // 设置第4步为完成状态
        this.currentStep = 4

        // 设置最终版用例（如果还没有通过流式接收完整）
        if (task.final_test_cases) {
          console.log('📝 Getting final cases from task object')
          // 无论this.finalTestCases是否已有值，都用最新的final_test_cases覆盖
          // 这样确保完整输出模式下也能正确显示最终版用例
          this.finalTestCases = task.final_test_cases
        }

        // 如果评审内容为空，从task对象中获取
        if (!this.streamedReviewContent && task.review_feedback) {
          console.log('📝 Getting review content from task object')
          this.streamedReviewContent = task.review_feedback
        }

        // 如果生成内容为空，从task对象中获取
        if (!this.streamedContent && task.generated_test_cases) {
          console.log('✍️ Getting generated content from task object')
          this.streamedContent = task.generated_test_cases
          this.streamedCases = this.parseStreamingTestCases(task.generated_test_cases)
        }

        if (this.eventSource) {
          this.eventSource.close()
          this.eventSource = null
        }

        // Only show completion message once
        if (!this.hasShownCompletionMessage) {
          ElMessage.success(this.$t('requirementAnalysis.generateCompleteSuccess'))
          this.hasShownCompletionMessage = true
        }
      } catch (error) {
        console.error('Failed to fetch final result:', error)
        ElMessage.error(this.$t('requirementAnalysis.fetchResultFailed'))
        this.isGenerating = false
        this.generationError = this.$t('requirementAnalysis.fetchResultFailed') + ': ' + (error.message || this.$t('requirementAnalysis.unknownError'))
      }
    },

    handleGenerationError() {
      this.isGenerating = false
      this.showResults = false
      this.pendingDraftRestore = null
      if (this.eventSource) {
        this.eventSource.close()
        this.eventSource = null
      }
      if (this.pollInterval) {
        clearInterval(this.pollInterval)
        this.pollInterval = null
      }
    },

    startPolling() {
      this.pollInterval = setInterval(async () => {
        try {
          // 修复URL：去掉多余的/api/前缀（axios baseURL已经包含/api）
          const response = await api.get(`/requirement-analysis/testcase-generation/${this.currentTaskId}/progress/`)
          const task = response.data

          console.log(`${this.$t('requirementAnalysis.taskStatus')}: ${task.status}, ${this.$t('requirementAnalysis.progress')}: ${task.progress}%`)

          // 更新进度显示
          if (task.status === 'generating') {
            this.currentStep = 2
            this.progressText = this.$t('requirementAnalysis.statusGenerating')
          } else if (task.status === 'reviewing') {
            this.currentStep = 3
            this.progressText = this.$t('requirementAnalysis.statusReviewing')
          } else if (task.status === 'completed') {
            this.currentStep = 4
            this.progressText = this.$t('requirementAnalysis.statusCompleted')

            // 任务完成，显示结果
            this.generationResult = task
            this.showResults = true
            this.isGenerating = false

            // 设置显示内容（完整输出模式下需要）
            if (task.generated_test_cases) {
              console.log('✍️ Polling mode - Setting generated content')
              this.streamedContent = task.generated_test_cases
              this.streamedCases = this.parseStreamingTestCases(task.generated_test_cases)
            }
            if (task.review_feedback) {
              console.log('📝 Polling mode - Setting review content')
              this.streamedReviewContent = task.review_feedback
            }
            if (task.final_test_cases) {
              console.log('🎯 Polling mode - Setting final test cases')
              this.finalTestCases = task.final_test_cases
              this.parsedFinalCases = this.parseStreamingTestCases(task.final_test_cases)
            }

            clearInterval(this.pollInterval)
            this.pollInterval = null

            // 只显示一次完成消息
            if (!this.hasShownCompletionMessage) {
              ElMessage.success(this.$t('requirementAnalysis.generateCompleteSuccess'))
              this.hasShownCompletionMessage = true
            }
            return
          } else if (task.status === 'failed') {
            this.progressText = this.$t('requirementAnalysis.statusFailed')
            this.isGenerating = false

            clearInterval(this.pollInterval)
            this.pollInterval = null

            this.generationError = task.error_message || this.$t('requirementAnalysis.generateFailed')
            ElMessage.error(this.$t('requirementAnalysis.generateFailed') + ': ' + (task.error_message || this.$t('requirementAnalysis.unknownError')))
            return
          }

        } catch (error) {
          console.error(this.$t('requirementAnalysis.checkProgressFailed'), error)
          // 继续轮询，不中断
        }
      }, 3000) // 每3秒检查一次
    },

    cancelGeneration() {
      if (this.pollInterval) {
        clearInterval(this.pollInterval)
        this.pollInterval = null
      }
      if (this.eventSource) {
        this.eventSource.close()
        this.eventSource = null
      }
      this.isGenerating = false
      this.currentTaskId = null
      this.taskCancelled = true
      this.pendingDraftRestore = null
      ElMessage.info(this.$t('requirementAnalysis.generationCancelled'))
    },

    // 下载测试用例为xlsx文件
    async downloadTestCases() {
      try {
        // 解析最终测试用例内容
        const finalTestCases = this.generationResult.final_test_cases;
        const taskId = this.generationResult.task_id;

        // 创建工作簿
        const workbook = XLSX.utils.book_new();

        // 过滤掉总结和建议部分，只保留测试用例内容
        const filteredContent = this.filterTestCasesOnly(finalTestCases);

        // 解析 JSONL 测试用例为数据行（每行一个独立 JSON）
        let dataRows = this.jsonlToExcelRows(filteredContent);

        // 非 JSONL（历史数据）：整段内容放入场景列，避免静默丢数据
        if (dataRows.length === 0 && this.convertBrToNewline(filteredContent).trim()) {
          dataRows = [['', this.convertBrToNewline(filteredContent), '', '', '', '']];
        }

        // 统一表头 + 数据行
        const worksheetData = [
          [
            this.$t('requirementAnalysis.excelTestCaseNumber'),
            this.$t('requirementAnalysis.excelTestScenario'),
            this.$t('requirementAnalysis.excelPrecondition'),
            this.$t('requirementAnalysis.excelTestSteps'),
            this.$t('requirementAnalysis.excelExpectedResult'),
            this.$t('requirementAnalysis.excelPriority')
          ],
          ...dataRows
        ];

        // 创建工作表
        const worksheet = XLSX.utils.aoa_to_sheet(worksheetData);

        // 设置列宽
        const colWidths = [
          { wch: 15 }, // 测试用例编号
          { wch: 30 }, // 测试场景
          { wch: 25 }, // 前置条件
          { wch: 40 }, // 操作步骤
          { wch: 30 }, // 预期结果
          { wch: 10 }  // 优先级
        ];
        worksheet['!cols'] = colWidths;

        // 设置表头样式（加粗）
        if (worksheetData.length > 1) {
          for (let col = 0; col < Math.min(6, worksheetData[0].length); col++) {
            const cellAddress = XLSX.utils.encode_cell({ r: 0, c: col });
            if (!worksheet[cellAddress]) continue;
            worksheet[cellAddress].s = {
              font: { bold: true },
              alignment: { horizontal: 'center', vertical: 'center', wrapText: true }
            };
          }

          // 设置自动换行
          for (let row = 1; row < worksheetData.length; row++) {
            for (let col = 0; col < Math.min(6, worksheetData[row].length); col++) {
              const cellAddress = XLSX.utils.encode_cell({ r: row, c: col });
              if (worksheet[cellAddress]) {
                worksheet[cellAddress].s = {
                  alignment: { vertical: 'top', wrapText: true }
                };
              }
            }
          }
        }

        // 将工作表添加到工作簿
        XLSX.utils.book_append_sheet(workbook, worksheet, this.$t('requirementAnalysis.testCaseSheetName'));

        // 生成文件名（包含任务ID和日期）
        const fileName = this.$t('requirementAnalysis.excelFileName', { taskId: taskId, date: new Date().toISOString().slice(0, 10) });

        // 导出文件
        XLSX.writeFile(workbook, fileName);

        ElMessage.success(this.$t('requirementAnalysis.downloadSuccess'));
      } catch (error) {
        console.error(this.$t('requirementAnalysis.downloadFailed'), error);
        ElMessage.error(this.$t('requirementAnalysis.downloadFailed') + ': ' + (error.message || this.$t('requirementAnalysis.unknownError')));
      }
    },

    // 保存到用例记录
    async saveToTestCaseRecords() {
      try {
        // 调用后端API保存到记录
        const response = await api.post(`/requirement-analysis/testcase-generation/${this.generationResult.task_id}/save_to_records/`)

        if (response.data.already_saved) {
          ElMessage.info(this.$t('requirementAnalysis.alreadySaved'))
        } else {
          const importedCount = response.data.imported_count || 0
          ElMessage.success(this.$t('requirementAnalysis.saveSuccess', { count: importedCount }))
        }

        // 标记为已保存：按钮变「已保存 ✓」并禁用
        this.savedToRecords = true
        this.savedCount = response.data.imported_count || 0

        // 不跳转，留在当前页面
        // this.$router.push('/generated-testcases')
      } catch (error) {
        console.error(this.$t('requirementAnalysis.saveFailed'), error)
        ElMessage.error(this.$t('requirementAnalysis.saveFailed') + ': ' + (error.response?.data?.error || error.message))
      }
    },

    // 解析 JSONL 测试用例为卡片数据（每行一个独立 JSON，与 writer/revise 的 JSONL 输出约定一致）
    // 流式增量下解析失败的残缺行直接跳过，等待补齐后再整体重解析
    parseStreamingTestCases(content) {
      if (!content) return []

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
          // 不完整行跳过，等待下个 chunk 补齐
        }
      }
      return testCases
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

    // 将HTML的<br>标签转换为换行符（用于Excel导出）
    convertBrToNewline(text) {
      if (!text) return '';
      return text.replace(/<br\s*\/?>/gi, '\n');
    },

    // 过滤掉总结和建议部分，只保留测试用例内容
    filterTestCasesOnly(content) {
      if (!content) return '';

      const lines = content.split('\n');
      const filteredLines = [];
      let inTestCaseSection = true;

      for (let line of lines) {
        const trimmedLine = line.trim();

        // 检查是否到了总结或建议部分
        if (trimmedLine.includes('总结') ||
            trimmedLine.includes('建议') ||
            trimmedLine.includes('Summary') ||
            trimmedLine.includes('Recommendation') ||
            trimmedLine.includes('最后') ||
            trimmedLine.includes('补充说明')) {
          inTestCaseSection = false;
          break;
        }

        if (inTestCaseSection) {
          filteredLines.push(line);
        }
      }

      return filteredLines.join('\n');
    },

    // 解析 JSONL 测试用例为 Excel 数据行（不含表头，步骤/预期按行编号显示）
    jsonlToExcelRows(content) {
      if (!content) return []

      const rows = []
      for (const line of content.split('\n')) {
        const trimmed = line.trim()
        if (!trimmed) continue
        let obj = null
        try {
          obj = JSON.parse(trimmed)
        } catch (e) {
          continue
        }
        if (!(obj && typeof obj === 'object') || (obj.case_id === undefined && obj.title === undefined)) continue

        const steps = Array.isArray(obj.steps) ? obj.steps : []
        const descs = []
        const expects = []
        steps.forEach((s, si) => {
          if (!(s && typeof s === 'object')) return
          if (s.desc) descs.push(`${si + 1}. ${this.convertBrToNewline(s.desc)}`)
          if (s.expect) expects.push(`${si + 1}. ${this.convertBrToNewline(s.expect)}`)
        })

        rows.push([
          obj.case_id || '',
          obj.title || '',
          this.convertBrToNewline(obj.precondition || ''),
          descs.join('\n'),
          expects.join('\n'),
          obj.priority || 'P2',
        ])
      }
      return rows
    }

  }
}
</script>

<style scoped>
/* ================================================================
   Design System — AI Test Case Generation
   Palette: Cool slate + electric blue + violet AI accent
   Typography: System font stack, intentional weights & spacing
   Signature: AI pulse gradient border during generation
   ================================================================ */

.requirement-analysis {
  padding: 28px 24px;
  max-width: 1280px;
  margin: 0 auto;
  position: relative;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Inter', Roboto, sans-serif;
}

/* ---------- Page Header ---------- */
.page-header {
  text-align: center;
  margin-bottom: 36px;
  padding-top: 8px;
}

.page-header h1 {
  font-size: 1.75rem;
  font-weight: 700;
  color: var(--aitest-text-1);
  margin: 0 0 6px 0;
  letter-spacing: -0.02em;
}

.page-header p {
  color: var(--aitest-text-2);
  font-size: 0.95rem;
  margin: 0;
  font-weight: 400;
}

/* ---------- Config Banner（AI 配置未就绪 · 可关细提醒条） ---------- */
.config-banner {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  margin-bottom: 20px;
  border-radius: 10px;
  background: var(--aitest-warning-bg);
  border: 1px solid color-mix(in srgb, var(--aitest-warning) 35%, transparent);
  color: var(--aitest-text-2);
  font-size: 0.86rem;
}

.config-banner-icon {
  color: var(--aitest-warning);
  font-size: 1rem;
  flex-shrink: 0;
}

.config-banner-text {
  flex: 1;
}

.config-banner-close {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--aitest-text-3);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 4px;
  border-radius: 6px;
  transition: all 0.15s ease;
}

.config-banner-close:hover {
  color: var(--aitest-text-1);
  background: var(--aitest-surface);
}

/* ---------- Input Card（页签：粘贴/上传） ---------- */
.input-card {
  background: var(--aitest-surface);
  border-radius: 14px;
  border: 1px solid var(--aitest-border);
  box-shadow: var(--aitest-shadow-sm);
  padding: 8px 24px 24px;
}

.input-tabs .el-tabs__header {
  margin-bottom: 14px;
}

.input-tabs .el-tabs__item {
  font-weight: 600;
}

.input-tabs .el-tabs__item.is-active {
  color: var(--aitest-primary);
}

.input-tabs .el-tabs__active-bar {
  background-color: var(--aitest-primary);
}

/* ---------- 统一生成条 ---------- */
.generate-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid var(--aitest-surface-subtle);
}

.output-mode-compact {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}

.output-mode-label {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--aitest-text-3);
}

.segmented {
  display: inline-flex;
  background: var(--aitest-surface-subtle);
  border: 1px solid var(--aitest-border);
  border-radius: 10px;
  padding: 3px;
  gap: 2px;
}

.segmented-option {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  border: none;
  background: transparent;
  color: var(--aitest-text-2);
  font-size: 0.84rem;
  font-weight: 500;
  padding: 7px 14px;
  border-radius: 7px;
  cursor: pointer;
  transition: all 0.18s ease;
}

.segmented-option:hover {
  color: var(--aitest-text-1);
}

.segmented-option.active {
  background: var(--aitest-surface);
  color: var(--aitest-primary-hover);
  box-shadow: var(--aitest-shadow-xs);
}

.segmented-radio {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  border: 1.5px solid var(--aitest-border-strong);
  transition: all 0.18s ease;
}

.segmented-radio.on {
  border-color: var(--aitest-primary);
  background: var(--aitest-primary);
  box-shadow: 0 0 0 2px var(--aitest-primary-subtle);
}

.generate-bar .generate-manual-btn {
  width: auto;
  min-width: 220px;
  margin-top: 0;
}

.case-type-field {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 340px;
}

.case-type-input {
  width: auto;
  flex: 1;
  padding: 10px 14px;
  font-size: 0.9rem;
}

.granularity-field {
  display: flex;
  align-items: center;
  gap: 10px;
}

/* ---------- Main Content Layout ---------- */
.main-content {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* ---------- Form Elements ---------- */
.form-group {
  margin-bottom: 18px;
}

.form-group label {
  display: block;
  margin-bottom: 6px;
  font-weight: 600;
  font-size: 0.85rem;
  color: var(--aitest-text-2);
}

.form-input, .form-select {
  width: 100%;
  padding: 10px 14px;
  border: 1.5px solid var(--aitest-border);
  border-radius: 8px;
  font-size: 0.9rem;
  color: var(--aitest-text-1);
  background: var(--aitest-surface);
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
  box-sizing: border-box;
  font-family: inherit;
}

.form-input:focus, .form-select:focus {
  outline: none;
  border-color: var(--aitest-primary);
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
}

.form-input::placeholder {
  color: var(--aitest-text-3);
}

.form-textarea {
  width: 100%;
  padding: 12px 14px;
  border: 1.5px solid var(--aitest-border);
  border-radius: 8px;
  font-size: 0.9rem;
  color: var(--aitest-text-1);
  background: var(--aitest-surface);
  resize: vertical;
  font-family: inherit;
  line-height: 1.6;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
  box-sizing: border-box;
}

.form-textarea:focus {
  outline: none;
  border-color: var(--aitest-primary);
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
}

.form-textarea::placeholder {
  color: var(--aitest-text-3);
}

.char-count {
  text-align: right;
  font-size: 0.78rem;
  color: var(--aitest-text-3);
  margin-top: 4px;
}

.required {
  color: var(--aitest-danger);
  font-weight: 500;
}

/* ---------- Primary Buttons ---------- */
.generate-manual-btn, .generate-btn {
  background: var(--aitest-primary);
  color: var(--aitest-surface);
  border: none;
  padding: 13px 28px;
  border-radius: 10px;
  cursor: pointer;
  font-size: 0.95rem;
  font-weight: 600;
  width: 100%;
  margin-top: 10px;
  transition: all 0.2s ease;
  letter-spacing: 0.01em;
  position: relative;
  overflow: hidden;
}

.generate-manual-btn::after, .generate-btn::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 10px;
  opacity: 0;
  transition: opacity 0.3s ease;
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.16), rgba(79, 70, 229, 0.12));
}

.generate-manual-btn:hover:not(:disabled)::after, .generate-btn:hover:not(:disabled)::after {
  opacity: 1;
}

.generate-manual-btn:hover:not(:disabled), .generate-btn:hover:not(:disabled) {
  background: var(--aitest-primary-hover);
  transform: translateY(-1px);
  box-shadow: 0 4px 14px rgba(79, 70, 229, 0.3);
}

.generate-manual-btn:disabled, .generate-btn:disabled {
  background: var(--aitest-border-strong);
  color: var(--aitest-text-3);
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

/* ---------- Upload Area ---------- */
.upload-area {
  border: 2px dashed var(--aitest-border-strong);
  border-radius: 10px;
  padding: 36px 24px;
  text-align: center;
  transition: all 0.2s ease;
  margin-bottom: 20px;
  background: var(--aitest-canvas);
}

.upload-area.drag-over {
  border-color: var(--aitest-primary);
  background: var(--aitest-primary-subtle);
  border-style: solid;
}

.upload-placeholder {
  color: var(--aitest-text-2);
}

.upload-icon {
  font-size: 2.5rem;
  margin-bottom: 12px;
  display: block;
  color: var(--aitest-text-3);
}

.upload-placeholder p {
  margin: 0;
  font-size: 0.9rem;
  color: var(--aitest-text-2);
}

.upload-hint {
  color: var(--aitest-text-3) !important;
  font-size: 0.8rem !important;
  margin-top: 4px !important;
}

.select-file-btn {
  background: var(--aitest-surface-subtle);
  color: var(--aitest-text-2);
  border: 1.5px solid var(--aitest-border);
  padding: 9px 20px;
  border-radius: 8px;
  cursor: pointer;
  margin-top: 14px;
  font-size: 0.85rem;
  font-weight: 500;
  transition: all 0.2s ease;
}

.select-file-btn:hover {
  background: var(--aitest-surface-subtle);
  border-color: var(--aitest-border-strong);
}

.file-selected {
  padding: 18px;
  background: var(--aitest-canvas);
  border-radius: 8px;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 14px;
}

.file-icon {
  font-size: 1.75rem;
  color: var(--aitest-text-2);
}

.file-details {
  flex: 1;
}

.file-name {
  font-weight: 600;
  margin: 0;
  color: var(--aitest-text-1);
  font-size: 0.9rem;
}

.file-size {
  color: var(--aitest-text-3);
  font-size: 0.8rem;
  margin: 3px 0 0 0;
}

.remove-file {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1.1rem;
  color: var(--aitest-text-3);
  padding: 4px;
  border-radius: 6px;
  transition: all 0.15s ease;
}

.remove-file:hover {
  color: var(--aitest-danger);
  background: var(--aitest-danger-bg);
}

/* ---------- Results Area（常驻结果区） ---------- */
.results-area {
  min-height: 0;
}

/* AI Pulse — signature element（靛蓝→天蓝，生成时长驻流动） */
.generation-panel {
  background: var(--aitest-surface);
  border-radius: 14px;
  padding: 24px;
  border: 1px solid var(--aitest-border);
  box-shadow: var(--aitest-shadow-sm);
  position: relative;
  overflow: hidden;
}

.generation-panel.is-generating::before {
  content: '';
  position: absolute;
  inset: -2px;
  border-radius: 16px;
  padding: 2px;
  background: linear-gradient(135deg, var(--aitest-primary), var(--aitest-accent), var(--aitest-primary));
  background-size: 200% 200%;
  mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  animation: aiPulse 3s ease-in-out infinite;
  pointer-events: none;
}

@keyframes aiPulse {
  0%, 100% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
}

/* ---------- 结果头 ---------- */
.result-header {
  margin-bottom: 20px;
}

.result-header-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}

.result-kicker {
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--aitest-text-1);
  letter-spacing: -0.01em;
}

.result-task-id {
  font-size: 0.8rem;
  color: var(--aitest-text-3);
  background: var(--aitest-surface-subtle);
  border: 1px solid var(--aitest-border);
  padding: 2px 10px;
  border-radius: 20px;
}

.result-header-spacer {
  flex: 1;
}

.status-chip {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 0.78rem;
  font-weight: 600;
}

.status-chip .status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentColor;
}

.status-chip.run {
  background: var(--aitest-primary-subtle);
  color: var(--aitest-primary);
}

.status-chip.run .status-dot {
  animation: pulse-dot 1.5s ease-in-out infinite;
}

.status-chip.ok {
  background: var(--aitest-success-bg);
  color: var(--aitest-success);
}

.status-chip.err {
  background: var(--aitest-danger-bg);
  color: var(--aitest-danger);
}

/* ---------- 压缩版步骤条 ---------- */
.mini-steps {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.mini-step {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 5px 10px;
  border-radius: 8px;
  background: var(--aitest-surface-subtle);
  color: var(--aitest-text-3);
  font-size: 0.78rem;
  transition: all 0.25s ease;
}

.mini-step-num {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--aitest-surface);
  border: 1px solid var(--aitest-border);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 0.68rem;
  color: var(--aitest-text-3);
}

.mini-step.active {
  background: var(--aitest-primary-subtle);
  color: var(--aitest-primary);
  font-weight: 600;
}

.mini-step.active .mini-step-num {
  background: var(--aitest-primary);
  border-color: var(--aitest-primary);
  color: var(--aitest-surface);
}

/* ---------- 常驻动作条 ---------- */
.action-bar {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
  padding-top: 16px;
  border-top: 1px solid var(--aitest-surface-subtle);
}

.action-bar .el-button {
  margin: 0;
}

.cancel-row-wrap {
  padding-top: 16px;
  border-top: 1px solid var(--aitest-surface-subtle);
}

.cancel-generation-btn {
  background: var(--aitest-danger-bg);
  color: var(--aitest-danger);
  border: 1.5px solid color-mix(in srgb, var(--aitest-danger) 28%, transparent);
  padding: 9px 22px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.9rem;
  font-weight: 500;
  transition: all 0.2s ease;
}

.cancel-generation-btn:hover {
  background: var(--aitest-danger-bg);
  border-color: color-mix(in srgb, var(--aitest-danger) 45%, transparent);
}

/* ---------- 空态 ---------- */
.results-empty {
  text-align: center;
  padding: 56px 24px;
  background: var(--aitest-surface);
  border: 1px dashed var(--aitest-border-strong);
  border-radius: 14px;
}

.results-empty-icon {
  font-size: 2.4rem;
  color: var(--aitest-border-strong);
  margin-bottom: 14px;
}

.results-empty-title {
  font-size: 1rem;
  font-weight: 700;
  color: var(--aitest-text-2);
  margin: 0 0 6px 0;
}

.results-empty-desc {
  font-size: 0.86rem;
  color: var(--aitest-text-3);
  margin: 0 0 16px 0;
  line-height: 1.6;
  max-width: 460px;
  margin-left: auto;
  margin-right: auto;
}

/* ---------- 面内失败态 ---------- */
.failure-card {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 16px 18px;
  margin-bottom: 18px;
  border-radius: 10px;
  background: var(--aitest-danger-bg);
  border: 1px solid color-mix(in srgb, var(--aitest-danger) 30%, transparent);
}

.failure-icon {
  color: var(--aitest-danger);
  font-size: 1.3rem;
  flex-shrink: 0;
  margin-top: 2px;
}

.failure-body {
  flex: 1;
}

.failure-title {
  font-weight: 700;
  color: var(--aitest-danger);
  font-size: 0.9rem;
  margin: 0 0 4px 0;
}

.failure-msg {
  font-size: 0.84rem;
  color: var(--aitest-text-2);
  margin: 0;
  line-height: 1.5;
  word-break: break-word;
}

/* ---------- 结果区块（草稿/评审/最终） ---------- */
.result-section {
  margin-top: 20px;
}

.result-section-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: var(--aitest-canvas);
  border: 1px solid var(--aitest-border);
  border-bottom: none;
  border-radius: 10px 10px 0 0;
}

.result-section-title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  color: var(--aitest-text-2);
  font-size: 0.88rem;
}

.result-section-meta {
  font-size: 0.78rem;
  color: var(--aitest-text-2);
  background: var(--aitest-surface);
  padding: 3px 10px;
  border-radius: 20px;
  border: 1px solid var(--aitest-border);
}

.result-section-actions {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.result-section.final .result-section-head {
  background: var(--aitest-success-bg);
  border-color: color-mix(in srgb, var(--aitest-success) 35%, transparent);
}

.result-section.final .result-section-title {
  color: var(--aitest-success);
}

/* 等宽方言：用例编号 / 任务ID / 步骤号 */
.mono {
  font-family: var(--aitest-font-mono);
  letter-spacing: 0.01em;
}

/* ---------- AI 评审内容 ---------- */
.stream-content {
  max-height: 400px;
  overflow-y: auto;
  padding: 18px;
  text-align: left;
  background: var(--aitest-surface);
  border: 1px solid var(--aitest-border);
  border-top: none;
  border-radius: 0 0 10px 10px;
  font-size: 0.88rem;
  line-height: 1.7;
  color: var(--aitest-text-2);
  white-space: pre-wrap;
  word-wrap: break-word;
}

.stream-content::-webkit-scrollbar {
  width: 6px;
}

.stream-content::-webkit-scrollbar-track {
  background: transparent;
}

.stream-content::-webkit-scrollbar-thumb {
  background: var(--aitest-border-strong);
  border-radius: 3px;
}

.stream-content::-webkit-scrollbar-thumb:hover {
  background: var(--aitest-text-3);
}

.stream-content h1, .stream-content h2, .stream-content h3,
.stream-content h4, .stream-content h5, .stream-content h6 {
  margin-top: 1em;
  margin-bottom: 0.5em;
  color: var(--aitest-text-1);
  font-weight: 600;
}

.stream-content code {
  background: var(--aitest-surface-subtle);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: 'SF Mono', 'Monaco', 'Menlo', 'Consolas', monospace;
  font-size: 0.82em;
}

.stream-content pre {
  background: var(--aitest-surface-subtle);
  padding: 12px;
  border-radius: 6px;
  overflow-x: auto;
  margin: 10px 0;
}

.stream-content pre code {
  background: none;
  padding: 0;
}

/* ---------- 区块动态点（生成中脉冲） ---------- */
.pulse-dot {
  display: inline-block;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--aitest-primary);
  animation: pulse-dot 1.5s ease-in-out infinite;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.3; transform: scale(0.7); }
}

/* Card Grid */
.cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 12px;
  padding: 16px;
  background: var(--aitest-canvas);
  border: 1px solid var(--aitest-border);
  border-top: none;
  border-radius: 0 0 10px 10px;
  max-height: 560px;
  overflow-y: auto;
}

.cards-grid::-webkit-scrollbar {
  width: 5px;
}

.cards-grid::-webkit-scrollbar-track {
  background: transparent;
}

.cards-grid::-webkit-scrollbar-thumb {
  background: var(--aitest-border-strong);
  border-radius: 3px;
}

.cards-grid::-webkit-scrollbar-thumb:hover {
  background: var(--aitest-text-3);
}

/* Single Test Case Card */
.testcase-card {
  background: var(--aitest-surface);
  border-radius: 10px;
  padding: 16px;
  border: 1px solid var(--aitest-border);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
  transition: all 0.25s ease;
  position: relative;
  overflow: hidden;
  animation: cardFadeIn 0.35s ease both;
}

@keyframes cardFadeIn {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.testcase-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
  transform: translateY(-1px);
  border-color: var(--aitest-border-strong);
}

.testcase-card.is-incomplete {
  border-color: var(--el-color-primary-light-7);
  border-style: dashed;
  background: var(--aitest-canvas);
}

.testcase-card.is-new {
  border-color: color-mix(in srgb, var(--aitest-success) 60%, transparent);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--aitest-success) 12%, transparent);
  animation: cardHighlight 1.5s ease forwards;
}

@keyframes cardHighlight {
  0% { box-shadow: 0 0 0 3px color-mix(in srgb, var(--aitest-success) 22%, transparent); }
  100% { box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03); }
}

.testcase-card.final-card {
  border-left: 3px solid var(--aitest-success);
}

/* Streaming shimmer */
.streaming-shimmer {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  height: 2.5px;
  background: linear-gradient(90deg, transparent, var(--aitest-primary), var(--aitest-accent), transparent);
  animation: shimmer 1.8s infinite;
  border-radius: 0 0 10px 10px;
}

@keyframes shimmer {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}

/* Card header */
.testcase-card .card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.testcase-card .case-id {
  font-family: var(--aitest-font-mono);
  font-size: 0.75rem;
  color: var(--aitest-text-2);
  background: var(--aitest-surface-subtle);
  padding: 2px 10px;
  border-radius: 5px;
  letter-spacing: 0.02em;
  font-weight: 500;
}

.testcase-card .priority-badge {
  padding: 3px 10px;
  border-radius: 20px;
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}

.priority-badge.p0 { background: var(--aitest-danger-bg); color: var(--aitest-danger); }
.priority-badge.p1 { background: var(--aitest-warning-bg); color: var(--aitest-warning); }
.priority-badge.p2 { background: var(--aitest-primary-subtle); color: var(--aitest-primary); }
.priority-badge.p3 { background: var(--aitest-success-bg); color: var(--aitest-success); }
.priority-badge.低 { background: var(--aitest-success-bg); color: var(--aitest-success); }
.priority-badge.中 { background: var(--aitest-primary-subtle); color: var(--aitest-primary); }
.priority-badge.高 { background: var(--aitest-warning-bg); color: var(--aitest-warning); }
.priority-badge.紧急 { background: var(--aitest-danger-bg); color: var(--aitest-danger); }
.priority-badge.low { background: var(--aitest-success-bg); color: var(--aitest-success); }
.priority-badge.medium { background: var(--aitest-primary-subtle); color: var(--aitest-primary); }
.priority-badge.high { background: var(--aitest-warning-bg); color: var(--aitest-warning); }
.priority-badge.critical { background: var(--aitest-danger-bg); color: var(--aitest-danger); }

/* Card scenario */
.testcase-card .card-scenario {
  font-weight: 600;
  color: var(--aitest-text-1);
  font-size: 0.88rem;
  margin-bottom: 12px;
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* Card divider */
.testcase-card .card-divider {
  height: 1px;
  background: var(--aitest-surface-subtle);
  margin-bottom: 10px;
}

/* Card field */
.testcase-card .card-field {
  display: flex;
  gap: 6px;
  margin-bottom: 6px;
  font-size: 0.8rem;
  line-height: 1.5;
  align-items: flex-start;
}

.testcase-card .field-icon {
  flex-shrink: 0;
  margin-top: 1px;
  font-size: 0.82rem;
  color: var(--aitest-text-3);
}

.testcase-card .field-label {
  color: var(--aitest-text-3);
  font-weight: 500;
  flex-shrink: 0;
  min-width: 26px;
  font-size: 0.75rem;
}

.testcase-card .field-value {
  color: var(--aitest-text-2);
  word-break: break-word;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* Card steps (结构化步骤逐条展示) */
.testcase-card .step-list {
  display: flex;
  flex-direction: column;
  gap: 3px;
  flex: 1;
  min-width: 0;
}

.testcase-card .step-row {
  display: flex;
  gap: 6px;
  align-items: baseline;
  line-height: 1.5;
}

.testcase-card .step-order {
  flex-shrink: 0;
  font-family: var(--aitest-font-mono);
  font-size: 0.72rem;
  color: var(--aitest-text-3);
}

.testcase-card .step-desc {
  color: var(--aitest-text-2);
  word-break: break-word;
}

.testcase-card .step-expect {
  color: var(--aitest-text-3);
  word-break: break-word;
}

.testcase-card .expect-label {
  color: var(--aitest-text-3);
}

/* Streaming indicator */
.streaming-indicator {
  font-size: 0.85em;
  margin-left: 8px;
  color: var(--aitest-success);
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* 旧的配置引导模态框样式已删除：改为 el-dialog，样式见尾部全局块 */

/* ---------- Knowledge Panel ---------- */
.knowledge-section {
  margin-bottom: 16px;
}

.retrieve-knowledge-btn {
  width: 100%;
  padding: 10px 16px;
  background: var(--aitest-primary);
  color: var(--aitest-surface);
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.9rem;
  font-weight: 500;
  transition: all 0.2s ease;
}

.retrieve-knowledge-btn:hover:not(:disabled) {
  background: color-mix(in srgb, var(--aitest-primary) 88%, #000);
  box-shadow: 0 4px 14px color-mix(in srgb, var(--aitest-primary) 35%, transparent);
  transform: translateY(-1px);
}

.retrieve-knowledge-btn:disabled {
  background: var(--aitest-border-strong);
  color: var(--aitest-text-3);
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

.selected-knowledge-summary {
  margin-top: 8px;
  font-size: 0.82rem;
  color: var(--aitest-text-2);
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.selected-tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.knowledge-tag {
  background: var(--aitest-primary-subtle);
  color: var(--aitest-primary);
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 0.75rem;
  font-weight: 500;
}

.knowledge-panel {
  margin-bottom: 16px;
  border: 1px solid var(--aitest-border);
  border-radius: 10px;
  overflow: hidden;
  background: var(--aitest-surface);
}

.knowledge-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: var(--aitest-canvas);
  font-weight: 600;
  font-size: 0.85rem;
  color: var(--aitest-text-2);
  border-bottom: 1px solid var(--aitest-border);
}

.knowledge-count {
  font-size: 0.78rem;
  color: var(--aitest-text-3);
  background: var(--aitest-surface);
  padding: 2px 10px;
  border-radius: 12px;
  border: 1px solid var(--aitest-border);
}

.knowledge-panel-body {
  max-height: 360px;
  overflow-y: auto;
  padding: 8px;
}

.knowledge-empty {
  text-align: center;
  padding: 28px;
  color: var(--aitest-text-3);
  font-size: 0.85rem;
}

.knowledge-item {
  padding: 12px;
  margin-bottom: 6px;
  border-radius: 8px;
  border: 1px solid var(--aitest-border);
  background: var(--aitest-surface);
  cursor: pointer;
  transition: all 0.15s ease;
}

.knowledge-item:hover {
  border-color: var(--aitest-primary);
  background: var(--aitest-canvas);
}

.knowledge-item.selected {
  border-color: var(--aitest-primary);
  background: var(--aitest-primary-subtle);
}

.knowledge-item-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.knowledge-checkbox input {
  cursor: pointer;
  accent-color: var(--aitest-primary);
}

.knowledge-item-name {
  font-weight: 600;
  font-size: 0.85rem;
  color: var(--aitest-text-2);
  flex: 1;
}

.knowledge-item-type {
  font-size: 0.72rem;
  padding: 2px 8px;
  border-radius: 10px;
  background: var(--aitest-surface-subtle);
  color: var(--aitest-text-2);
}

.knowledge-item-type.chunk {
  background: var(--aitest-primary-subtle);
  color: var(--aitest-primary);
}

.knowledge-item-type.entry {
  background: var(--aitest-success-bg);
  color: var(--aitest-success);
}

.knowledge-item-score {
  font-size: 0.78rem;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 10px;
  background: var(--aitest-warning-bg);
  color: var(--aitest-warning);
}

.knowledge-item-score.high {
  background: var(--aitest-success-bg);
  color: var(--aitest-success);
}

.knowledge-item-score.low {
  background: var(--aitest-danger-bg);
  color: var(--aitest-danger);
}

.knowledge-item-content {
  font-size: 0.8rem;
  color: var(--aitest-text-2);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  padding-left: 24px;
}

.knowledge-panel-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: var(--aitest-canvas);
  border-top: 1px solid var(--aitest-border);
  font-size: 0.82rem;
  color: var(--aitest-text-2);
}

.confirm-knowledge-btn {
  padding: 6px 20px;
  background: var(--aitest-primary);
  color: var(--aitest-surface);
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.82rem;
  font-weight: 500;
  transition: background 0.15s ease;
}

.confirm-knowledge-btn:hover {
  background: var(--aitest-primary-hover);
}

/* ---------- Responsive ---------- */
@media (max-width: 768px) {
  .requirement-analysis {
    padding: 16px;
  }

  .input-card {
    padding: 6px 16px 18px;
  }

  .generate-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .generate-bar .generate-manual-btn {
    width: 100%;
    min-width: 0;
  }

  .output-mode-compact {
    justify-content: space-between;
  }

  .cards-grid {
    grid-template-columns: 1fr;
    max-height: 480px;
  }

  .result-section-head {
    align-items: flex-start;
    flex-direction: column;
  }

  .action-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .action-bar .el-button {
    width: 100%;
  }
}

/* ---------- 动效降级（尊重系统减弱动态偏好） ---------- */
@media (prefers-reduced-motion: reduce) {
  .generation-panel.is-generating::before,
  .streaming-shimmer,
  .pulse-dot,
  .status-chip.run .status-dot,
  .streaming-indicator,
  .testcase-card {
    animation: none !important;
    transition: none !important;
  }
}
</style>

<style>
/* AI 配置引导对话框（append-to-body 后在 scoped 作用域外，需全局样式） */
.config-guide-dialog .config-guide-subtitle {
  color: var(--aitest-text-2);
  font-size: 0.9rem;
  margin: 0 0 18px 0;
}

.config-guide-dialog .config-guide-group {
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--aitest-text-3);
  margin: 18px 0 8px 0;
}

.config-guide-dialog .config-guide-group:first-child {
  margin-top: 0;
}

.config-guide-dialog .config-guide-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border: 1px solid var(--aitest-border);
  border-radius: 10px;
  margin-bottom: 8px;
  background: var(--aitest-surface);
}

.config-guide-dialog .config-guide-row .el-tag {
  flex-shrink: 0;
}

.config-guide-dialog .config-guide-label {
  font-size: 0.9rem;
  font-weight: 600;
  color: var(--aitest-text-2);
  flex-shrink: 0;
}

.config-guide-dialog .config-guide-name {
  flex: 1;
  text-align: right;
  font-size: 0.84rem;
  color: var(--aitest-text-2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>