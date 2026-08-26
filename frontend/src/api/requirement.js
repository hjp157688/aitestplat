import request from '@/utils/api'

// ==================== 需求管理 ====================

/**
 * 获取需求列表
 */
export function getRequirements(params) {
  return request({
    url: '/requirement-analysis/requirements-manage/',
    method: 'get',
    params
  })
}

/**
 * 获取需求详情
 */
export function getRequirement(id) {
  return request({
    url: `/requirement-analysis/requirements-manage/${id}/`,
    method: 'get'
  })
}

/**
 * 创建需求
 */
export function createRequirement(data) {
  return request({
    url: '/requirement-analysis/requirements-manage/',
    method: 'post',
    data
  })
}

/**
 * 更新需求
 */
export function updateRequirement(id, data) {
  return request({
    url: `/requirement-analysis/requirements-manage/${id}/`,
    method: 'put',
    data
  })
}

/**
 * 删除需求
 */
export function deleteRequirement(id) {
  return request({
    url: `/requirement-analysis/requirements-manage/${id}/`,
    method: 'delete'
  })
}

/**
 * 批量删除需求
 */
export function batchDeleteRequirements(ids) {
  return request({
    url: '/requirement-analysis/requirements-manage/batch_delete/',
    method: 'post',
    data: { ids }
  })
}

/**
 * 为选中的需求批量AI生成测试用例
 * @param {number[]} ids 选中的需求ID列表
 * @param {Object} options 生成选项 { output_mode, case_type, granularity, use_reviewer_model }
 */
export function generateTestCasesForRequirements(ids, options = {}) {
  return request({
    url: '/requirement-analysis/requirements-manage/generate_test_cases/',
    method: 'post',
    data: { ids, ...options }
  })
}

/**
 * AI解析需求文本
 */
export function aiParseRequirements(projectId, content) {
  return request({
    url: '/requirement-analysis/requirements-manage/ai_parse/',
    method: 'post',
    data: { project_id: projectId, content }
  })
}

/**
 * AI解析需求文件
 */
export function aiParseRequirementsFile(projectId, file) {
  const formData = new FormData()
  formData.append('project_id', projectId)
  formData.append('file', file)
  return request({
    url: '/requirement-analysis/requirements-manage/ai_parse_file/',
    method: 'post',
    data: formData,
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

/**
 * 导入AI解析的需求
 */
export function aiImportRequirements(projectId, requirements) {
  return request({
    url: '/requirement-analysis/requirements-manage/ai_import/',
    method: 'post',
    data: { project_id: projectId, requirements }
  })
}

// ==================== 禅道代理 ====================

/**
 * 获取禅道产品列表
 */
export function getZentaoProducts() {
  return request({
    url: '/requirement-analysis/zentao/products/',
    method: 'get'
  })
}

/**
 * 获取禅道项目列表
 */
export function getZentaoProjects() {
  return request({
    url: '/requirement-analysis/zentao/projects/',
    method: 'get'
  })
}

/**
 * 获取禅道产品下的需求列表
 */
export function getZentaoProductStories(productId) {
  return request({
    url: `/requirement-analysis/zentao/products/${productId}/stories/`,
    method: 'get'
  })
}

/**
 * 获取禅道项目下的需求列表
 */
export function getZentaoProjectStories(projectId) {
  return request({
    url: `/requirement-analysis/zentao/projects/${projectId}/stories/`,
    method: 'get'
  })
}

/**
 * 同步禅道需求到本地
 */
export function syncZentaoRequirements(data) {
  return request({
    url: '/requirement-analysis/zentao/sync/',
    method: 'post',
    data
  })
}

/**
 * 获取禅道连接状态
 */
export function getZentaoStatus() {
  return request({
    url: '/requirement-analysis/zentao/status/',
    method: 'get'
  })
}

/**
 * 导出测试用例到禅道（异步：返回 task_id，用 getZentaoTask 轮询进度）
 */
export function exportCasesToZentao(data) {
  return request({
    url: '/testcases/zentao-export/',
    method: 'post',
    data
  })
}

/**
 * 从禅道导入测试用例（异步：返回 task_id，用 getZentaoTask 轮询进度）
 */
export function importCasesFromZentao(data) {
  return request({
    url: '/testcases/zentao-import/',
    method: 'post',
    data
  })
}

/**
 * 查询禅道同步任务进度（导入/导出通用）
 */
export function getZentaoTask(taskId) {
  return request({
    url: `/testcases/zentao-task/${taskId}/`,
    method: 'get'
  })
}

// ==================== 禅道配置 ====================

/**
 * 获取禅道配置列表
 */
export function getZentaoConfigs() {
  return request({
    url: '/requirement-analysis/zentao-config/',
    method: 'get'
  })
}

/**
 * 创建禅道配置
 */
export function createZentaoConfig(data) {
  return request({
    url: '/requirement-analysis/zentao-config/',
    method: 'post',
    data
  })
}

/**
 * 更新禅道配置
 */
export function updateZentaoConfig(id, data) {
  return request({
    url: `/requirement-analysis/zentao-config/${id}/`,
    method: 'put',
    data
  })
}

/**
 * 删除禅道配置
 */
export function deleteZentaoConfig(id) {
  return request({
    url: `/requirement-analysis/zentao-config/${id}/`,
    method: 'delete'
  })
}

/**
 * 测试禅道连接
 */
export function testZentaoConnection(id) {
  return request({
    url: `/requirement-analysis/zentao-config/${id}/test_connection/`,
    method: 'post'
  })
}

/**
 * 启用禅道配置
 */
export function enableZentaoConfig(id) {
  return request({
    url: `/requirement-analysis/zentao-config/${id}/enable/`,
    method: 'post'
  })
}

/**
 * 禁用禅道配置
 */
export function disableZentaoConfig(id) {
  return request({
    url: `/requirement-analysis/zentao-config/${id}/disable/`,
    method: 'post'
  })
}


// ==================== WeKnora 外部知识库 ====================

/**
 * 获取 WeKnora 连接配置（单例行）
 */
export function getWeKnoraConfig() {
  return request({
    url: '/requirement-analysis/weknora-config/',
    method: 'get'
  })
}

/**
 * 保存 WeKnora 连接配置
 */
export function updateWeKnoraConfig(data) {
  return request({
    url: '/requirement-analysis/weknora-config/1/',
    method: 'put',
    data
  })
}

/**
 * 测试 WeKnora 连接
 */
export function testWeKnoraConnection(data) {
  return request({
    url: '/requirement-analysis/weknora-config/test_connection/',
    method: 'post',
    data
  })
}

/**
 * 获取 WeKnora 智能体列表
 */
export function listWeKnoraAgents() {
  return request({
    url: '/requirement-analysis/weknora-config/agents/',
    method: 'get'
  })
}

/**
 * 项目⇄智能体绑定列表
 */
export function listWeKnoraBindings(params) {
  return request({
    url: '/requirement-analysis/weknora-bindings/',
    method: 'get',
    params
  })
}

/**
 * 创建/更新项目⇄智能体绑定(upsert)
 */
export function saveWeKnoraBinding(data) {
  return request({
    url: '/requirement-analysis/weknora-bindings/',
    method: 'post',
    data
  })
}

/**
 * 删除项目绑定
 */
export function deleteWeKnoraBinding(id) {
  return request({
    url: `/requirement-analysis/weknora-bindings/${id}/`,
    method: 'delete'
  })
}
