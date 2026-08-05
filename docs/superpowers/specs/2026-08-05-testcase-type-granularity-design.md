# AITestPlat 用例生成「用例类型 + 颗粒度」Design Spec

> **Goal:** 在 `/ai-generation/requirement-analysis` 首页的用例生成流程中，让用户可**自由补充用例类型指令**（自由文本）并选择**用例颗粒度**（粗/中/细）。前端控件收集两个参数 → 后端持久化到任务记录 → 注入写/改两处提示词 → 历史与详情可回看。旧任务与旧客户端零兼容风险。

**Status:** 已与用户确认（2026-08-05，brainstorming 两段设计逐段获批）

**需求决策记录（用户拍板）：**
- 「用例类型」＝ **自由文本补充指令**（非固定多选；用户自行描述，如"以功能+接口为主 / 仅 P0/P1 / 补充XX场景"）。
- 「颗粒度」＝ **三级选择**：`fine`（细，逐验证点拆分，当前行为）/ `medium`（中，默认）/ `coarse`（粗，场景级合并）。
- 两个参数**持久化到任务记录**，历史/详情可回看本次用的选项。

---

## 1. 前端交互与数据流（`RequirementAnalysisView.vue`）

### 1.1 控件落点：输入卡底部「统一生成条」扩行

现有生成条为 `[输出模式分段控件] [⚡ 生成测试用例]`（出自上一轮完成的单页控制台重构 `RequirementAnalysisView.vue`）。本轮改为一行三个控件 + 按钮，窄屏自动换行：

```
[输出模式 ●流式|完整]  [用例类型 ____________]  [颗粒度 粗 | ●中 | 细]  [⚡ 生成测试用例]
```

- **用例类型**：`<input class="form-input case-type-input">`，`maxlength=120`，弹性宽度（`flex:1; min-width:200px`），placeholder 引导示例（来自 i18n）。内容原样作为补充指令发送。
- **颗粒度**：与输出模式同款 `.segmented` 分段控件，三档，默认 `medium`。

### 1.2 状态与记忆

- `data` 新增：`caseType: ''`、`granularity: 'medium'`。
- localStorage（沿用既有 `STORAGE_KEYS` 模式）新增键：
  - `aitestpl:ra:case-type`
  - `aitestpl:ra:granularity`
- `mounted` 恢复；watch 写入（与 `globalOutputMode` 一致，节流不强制）。
- `startGeneration` 的 `this.lastRequest` 增加 `caseType`/`granularity`，`retryGeneration` 重跑沿用同一组选项。

### 1.3 发送

`POST /requirement-analysis/testcase-generation/generate/` body 增加：

```jsonc
{
  "title": "...",
  "requirement_text": "...",
  "use_writer_model": true,
  "use_reviewer_model": true,
  "output_mode": "stream",
  "case_type": "以功能+接口为主",        // 可空字符串
  "granularity": "medium"              // coarse | medium | fine
}
```

### 1.4 i18n 增量键（zh-cn / en 各一套）

| 键 | zh-cn |
|---|---|
| `caseTypeLabel` | 用例类型 |
| `caseTypePlaceholder` | 以功能、接口为主 / 仅 P0、P1 / 补充XX场景… |
| `granularityLabel` | 颗粒度 |
| `granularityCoarse` / `granularityMedium` / `granularityFine` | 粗 / 中 / 细 |
| `granularityCoarseHint` / `granularityMediumHint` / `granularityFineHint` | 场景级合并 / 正常+异常+边界兼顾 / 逐验证点拆分 |
| `granularityChip`（回显前缀） | 颗粒度 |
| `caseTypeChip`（回显前缀） | 用例类型 |

## 2. 后端

### 2.1 模型 `TestCaseGenerationTask`（定义于 `models.py`）

新增字段：

```python
GRANULARITY_CHOICES = [
    ('coarse', '粗粒度'),
    ('medium', '中粒度'),
    ('fine', '细粒度'),
]

case_type = models.TextField(blank=True, default='', verbose_name='用例类型补充指令')
granularity = models.CharField(
    max_length=10, choices=GRANULARITY_CHOICES, default='medium', verbose_name='颗粒度'
)
```

执行 `makemigrations requirement_analysis` + `migrate`。旧任务回填默认值（`''` / `'medium'`）。

### 2.2 序列化器（`serializers.py`）

- `TestCaseGenerationRequestSerializer`（输入）：新增
  ```python
  case_type = serializers.CharField(max_length=200, required=False, allow_blank=True, default='', help_text='用例类型补充指令（自由文本）')
  granularity = serializers.ChoiceField(choices=['coarse', 'medium', 'fine'], required=False, default='medium', help_text='颗粒度')
  ```
- `TestCaseGenerationTaskSerializer`（输出）：fields 新增 `case_type`、`granularity`、`granularity_display`（`source='get_granularity_display'`，只读）。

### 2.3 视图 `TestCaseGenerationTaskViewSet.generate`（`views.py:1457`）

在 `task_data` 构建处追加（与 `output_mode` 同级）：

```python
task_data['case_type'] = validated_data.get('case_type', '')
task_data['granularity'] = validated_data.get('granularity', 'medium')
```

### 2.4 提示词注入（`models.py` 内承载 `generate_test_cases_stream` / `revise_test_cases_based_on_review` 的那个 `AIModelService`）

新增**纯函数**（无副作用、可单测）：

```python
@staticmethod
def _build_preferences_block(case_type: str, granularity: str) -> str:
    """按颗粒度与用户补充指令生成【生成偏好】指令块"""
    lines = []
    g = granularity or 'medium'
    if g == 'coarse':
        lines.append("【颗粒度：粗】场景级拆分：优先关键功能与主路径，同类验证点可合并为一条用例，数量精简。")
    elif g == 'fine':
        lines.append("【颗粒度：细】逐验证点拆分：禁止将多个验证点合并进一条用例，每条只验证一个点，应写尽写。")
    else:  # medium（默认）
        lines.append("【颗粒度：中】正常+异常+边界场景兼顾，同类验证点可适度合并。")
    if case_type and case_type.strip():
        lines.append(f"【用户补充要求】{case_type.strip()}")
    return "\n".join(lines)
```

**注入点 1 —— 生成（`generate_test_cases_stream`，`models.py:1099`）**：
当前硬编码的"`1. 数量原则 / 2. 深度遍历 / 3. 拒绝合并 / 4. 场景扩展库`"指令块（`:125-:134`）替换为 `prefs = self._build_preferences_block(task.case_type, task.granularity)` 生成的块；`5`（输出顺序）与 `6`（特殊字符）指令保持不变，拼接到其后。

**注入点 2 —— 定稿（`revise_test_cases_based_on_review`）**：
在评审改进提示词中追加 `prefs`（保证最终版同样尊重颗粒度与用户补充）。

> 说明：`models.py:619` 与 `ai_models.py:140` 各有一个 `AIModelService`，本功能只改**承载 `generate_test_cases_stream` / `revise_test_cases_based_on_review` 的那个**（`models.py`），不动另外一个。

## 3. 回显

- **任务详情页**（`TaskDetail.vue`）：在状态/输出模式附近加两个只读 chip：`颗粒度 [粗|中|细]`、`用例类型 {case_type}`（为空则不显示后者）。
- **已生成用例列表**（`GeneratedTestCaseList.vue`）：加一列「生成选项」，显示颗粒度 tag + 用例类型省略显示（`.mono` 弱化）；空则不显示该格内容。只读，无编辑入口。

## 4. 错误处理

- 非法 `granularity` / 超长 `case_type`：请求序列化器返回 400。
- 老任务（无新字段值）/ 老客户端（不传新参数）：后端默认 `''` / `'medium'`，行为与现状完全一致。
- 前端：`granularity` 恒有效，无额外校验；`case_type` 非必填。

## 5. 测试

- 单测 `apps/requirement_analysis/tests/` 新增 `test_generation_preferences.py`：
  - `_build_preferences_block` 的 coarse / medium / fine 三种颗粒度关键词断言；
  - 用户补充指令的拼装与 trim；
  - 空 `case_type`/空 `granularity` 的默认回退；
  - 请求序列化器：合法值通过、非法 granularity 拒绝、case_type 上限。
- 前端：`npx eslint`（三个改动文件）+ `npm run build`。
- 运行时冒烟：起栈后走一遍「选类型/颗粒度 → 生成 → 历史/详情回显」。

## 6. 不做（Out of scope）

- 不做固定式「用例类型」多选（用户已选自由文本）。
- 不改颗粒度与需求分析、知识检索链路（仅生成/定稿提示词）。
- 不动 `output_mode` 的处理方式（保持 `request.data.get`，不并入新逻辑）。
- 不给生成选项加编辑/修改能力（回显只读）。
- 不新增「目标条数」控件（颗粒度不落到 N 条兜底）。

## 7. 验证标准

- `python manage.py makemigrations requirement_analysis` + `migrate` 成功；`python manage.py test apps.requirement_analysis` 通过。
- 前端 `npm run lint` 通过；`npm run build` 无报错。
- 浏览器冒烟：三种颗粒度生成的用例数量/拆分深度肉眼可辨差异；补充指令在用例内容中体现；历史/详情回显正确。

## 8. 提交约定

遵循项目 CLAUDE.md：相关修改合并为一个 commit（后端模型/迁移/序列化器/视图/提示词/前端/ i18n / 测试）；`<type>: <简短描述>`；提交前跑 lint 与测试。
