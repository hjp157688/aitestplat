<template>
  <div v-if="hasTrace" class="weknora-trace">
    <!-- 头部：整卡折叠 -->
    <div class="wt-header" @click="cardOpen = !cardOpen">
      <span class="wt-robot">🤖</span>
      <span class="wt-title">{{ $t('weknoraTrace.title') }}</span>
      <span v-if="bindingName" class="wt-sub">{{ bindingName }}</span>
      <span class="wt-spacer"></span>
      <span class="wt-meta mono">{{ refsCount }} {{ $t('weknoraTrace.refsSuffix') }}</span>
      <el-icon class="wt-caret"><ArrowDown v-if="cardOpen" /><ArrowRight v-else /></el-icon>
    </div>

    <div v-show="cardOpen" class="wt-body">
      <!-- 结果：默认主显（高亮） -->
      <div v-if="answer" class="wt-sec wt-result">
        <div class="wt-sec-head"><span class="wt-sec-label">{{ $t('weknoraTrace.resultLabel') }}</span></div>
        <div class="wt-answer">{{ answer }}</div>
      </div>

      <!-- 思考过程：默认折叠成一行，点开看工具调用时间线 -->
      <div v-if="steps && steps.length" class="wt-process">
        <div class="wt-process-toggle" @click="procOpen = !procOpen">
          <span class="wt-process-label">{{ $t('weknoraTrace.processLabel') }}</span>
          <span class="wt-process-hint">{{ steps.length }} {{ $t('weknoraTrace.processUnit') }}</span>
          <span class="wt-spacer"></span>
          <el-icon><ArrowDown v-if="procOpen" /><ArrowRight v-else /></el-icon>
        </div>

        <div v-show="procOpen" class="wt-steps">
          <div v-for="(s, i) in steps" :key="i" class="wt-step" :class="'wt-step--' + s.type">
            <span class="wt-step-tag" :class="'wt-step-tag--' + s.type">{{ stepTag(s) }}</span>
            <div class="wt-step-body">
              <template v-if="s.type === 'thinking'">
                <span class="wt-thinking">{{ s.content }}</span>
              </template>
              <template v-else-if="s.type === 'tool_call'">
                <span class="wt-tool-name">{{ s.name }}</span>
                <span v-if="s.arguments" class="wt-tool-args mono">{{ fmtArgs(s.arguments) }}</span>
              </template>
              <template v-else-if="s.type === 'tool_result'">
                <span class="wt-tool-result">{{ s.content }}</span>
              </template>
              <template v-else>
                <span class="wt-error">{{ s.content }}</span>
              </template>
            </div>
          </div>
        </div>
      </div>

      <!-- 引用来源 -->
      <div v-if="references && references.length" class="wt-sec wt-refs">
        <div class="wt-sec-head"><span class="wt-sec-label">{{ $t('weknoraTrace.refsLabel') }}</span></div>
        <div v-for="(r, i) in references" :key="i" class="wt-ref">
          <span class="wt-ref-doc">{{ r.filename || r.title || r.id }}</span>
          <span v-if="r.title && r.title !== r.filename" class="wt-ref-title">{{ r.title }}</span>
          <span v-if="r.chunk_index != null" class="wt-ref-chunk">#{{ r.chunk_index }}</span>
          <span v-if="r.score != null" class="wt-ref-score mono">{{ Number(r.score).toFixed(2) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ArrowDown, ArrowRight } from '@element-plus/icons-vue'

export default {
  name: 'WeKnoraAgentTrace',
  components: { ArrowDown, ArrowRight },
  props: {
    answer: { type: String, default: '' },
    references: { type: Array, default: () => [] },
    steps: { type: Array, default: () => [] },
    bindingName: { type: String, default: '' }
  },
  data() {
    return {
      cardOpen: true,   // 整卡默认展开
      procOpen: false   // 思考过程默认折叠（只看结果）
    }
  },
  computed: {
    hasTrace() {
      return !!(this.answer || (this.steps && this.steps.length)
        || (this.references && this.references.length))
    },
    refsCount() {
      return (this.references || []).length
    }
  },
  methods: {
    stepTag(s) {
      return ({ thinking: this.$t('weknoraTrace.stepThinking'),
                 tool_call: this.$t('weknoraTrace.stepTool'),
                 tool_result: this.$t('weknoraTrace.stepToolResult'),
                 error: this.$t('weknoraTrace.stepError') })[s.type] || (s.type || '·')
    },
    fmtArgs(args) {
      if (typeof args === 'string') return args
      try { return JSON.stringify(args) } catch (e) { return String(args) }
    }
  }
}
</script>

<style scoped>
.weknora-trace {
  border: 1px solid var(--aitest-border);
  border-radius: 10px;
  background: var(--aitest-surface);
  overflow: hidden;
}
.wt-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  cursor: pointer;
  user-select: none;
  background: linear-gradient(90deg, rgba(79,70,229,0.06), transparent 55%);
}
.wt-robot { font-size: 1.05rem; }
.wt-title { font-weight: 600; color: var(--aitest-text-1); }
.wt-sub { color: var(--aitest-text-3); font-size: 0.85rem; max-width: 40%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.wt-spacer { flex: 1; }
.wt-meta { color: var(--aitest-text-3); font-size: 0.8rem; }
.wt-caret { color: var(--aitest-text-3); }

.wt-body { padding: 12px 14px 14px; }
.wt-sec { margin-top: 4px; }
.wt-sec-head { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.wt-sec-label { font-size: 0.8rem; font-weight: 600; letter-spacing: .04em; color: var(--aitest-text-2); text-transform: uppercase; }

/* 结果：主显、高亮 */
.wt-result .wt-answer {
  background: var(--aitest-surface-subtle);
  border: 1px solid var(--aitest-border);
  border-left: 3px solid var(--aitest-primary, #4f46e5);
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 0.92rem;
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 360px;
  overflow: auto;
}

/* 思考过程：折叠成一行小节 */
.wt-process {
  margin-top: 12px;
}
.wt-process-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  border: 1px dashed var(--aitest-border);
  border-radius: 8px;
  cursor: pointer;
  user-select: none;
  color: var(--aitest-text-3);
  transition: border-color .15s, background .15s;
}
.wt-process-toggle:hover { border-color: var(--aitest-primary, #4f46e5); background: rgba(79,70,229,0.03); }
.wt-process-label { font-size: 0.85rem; font-weight: 500; color: var(--aitest-text-2); }
.wt-process-hint { font-size: 0.78rem; color: var(--aitest-text-3); }
.wt-steps {
  margin-top: 10px;
  border-left: 2px solid var(--aitest-border);
  margin-left: 4px;
  padding-left: 12px;
  display: flex; flex-direction: column; gap: 8px;
}
.wt-step { display: flex; gap: 8px; align-items: flex-start; }
.wt-step-tag {
  flex-shrink: 0;
  font-size: 0.72rem;
  line-height: 1.6;
  padding: 0 7px;
  border-radius: 20px;
  font-weight: 600;
}
.wt-step-tag--thinking { background: var(--aitest-surface-subtle); color: var(--aitest-text-3); }
.wt-step-tag--tool_call { background: rgba(79,70,229,0.12); color: var(--aitest-primary, #4f46e5); }
.wt-step-tag--tool_result { background: rgba(5,150,105,0.12); color: #059669; }
.wt-step-tag--error { background: rgba(220,38,38,0.12); color: #dc2626; }
.wt-step-body { font-size: 0.88rem; line-height: 1.6; color: var(--aitest-text-2); min-width: 0; }
.wt-thinking { color: var(--aitest-text-3); font-style: italic; }
.wt-tool-name { font-weight: 600; color: var(--aitest-primary, #4f46e5); }
.wt-tool-args { display: block; margin-top: 2px; color: var(--aitest-text-3); font-size: 0.78rem; word-break: break-all; }
.wt-tool-result { color: var(--aitest-text-2); white-space: pre-wrap; }
.wt-error { color: #dc2626; }

/* 引用来源 */
.wt-refs { margin-top: 12px; }
.wt-ref { display: flex; align-items: center; gap: 8px; padding: 5px 2px; border-bottom: 1px dashed var(--aitest-border); font-size: 0.88rem; }
.wt-ref:last-child { border-bottom: none; }
.wt-ref-doc { font-weight: 600; color: var(--aitest-text-1); }
.wt-ref-title { color: var(--aitest-text-2); }
.wt-ref-chunk { color: var(--aitest-text-3); font-size: 0.78rem; }
.wt-ref-score { margin-left: auto; color: var(--aitest-primary, #4f46e5); font-variant-numeric: tabular-nums; }
</style>
