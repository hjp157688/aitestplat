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

// ==================== 业务知识库 ====================

/**
 * 获取知识文档列表
 */
export function getKnowledgeDocuments(params) {
  return request({
    url: '/requirement-analysis/knowledge-documents/',
    method: 'get',
    params
  })
}

/**
 * 获取知识库概览统计
 */
export function getKnowledgeStats() {
  return request({
    url: '/requirement-analysis/knowledge-documents/stats/',
    method: 'get'
  })
}

/**
 * 检查知识库分词/向量化模型配置状态
 */
export function getKnowledgeConfigStatus() {
  return request({
    url: '/requirement-analysis/knowledge-documents/config_status/',
    method: 'get'
  })
}

/**
 * 上传知识文档
 */
export function uploadKnowledgeDocument(data) {
  return request({
    url: '/requirement-analysis/knowledge-documents/',
    method: 'post',
    data,
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

/**
 * 批量删除知识文档
 */
export function batchDeleteKnowledgeDocuments(ids) {
  return request({
    url: '/requirement-analysis/knowledge-documents/batch_delete/',
    method: 'post',
    data: { ids }
  })
}

/**
 * 删除知识文档
 */
export function deleteKnowledgeDocument(id) {
  return request({
    url: `/requirement-analysis/knowledge-documents/${id}/`,
    method: 'delete'
  })
}

/**
 * 处理文档（分块+向量化）
 */
export function processKnowledgeDocument(id) {
  return request({
    url: `/requirement-analysis/knowledge-documents/${id}/process/`,
    method: 'post'
  })
}

/**
 * 获取文档分块（预览）
 */
export function getKnowledgeDocumentChunks(id) {
  return request({
    url: `/requirement-analysis/knowledge-documents/${id}/chunks/`,
    method: 'get'
  })
}

/**
 * 编辑单个分块（重新向量化）
 */
export function updateKnowledgeDocumentChunk(id, data) {
  return request({
    url: `/requirement-analysis/knowledge-documents/${id}/update-chunk/`,
    method: 'post',
    data
  })
}

/**
 * LLM 提取知识条目
 */
export function extractKnowledgeEntries(id) {
  return request({
    url: `/requirement-analysis/knowledge-documents/${id}/extract/`,
    method: 'post'
  })
}

/**
 * 获取知识条目列表
 */
export function getKnowledgeEntries(params) {
  return request({
    url: '/requirement-analysis/knowledge-entries/',
    method: 'get',
    params
  })
}

/**
 * 创建知识条目
 */
export function createKnowledgeEntry(data) {
  return request({
    url: '/requirement-analysis/knowledge-entries/',
    method: 'post',
    data
  })
}

/**
 * 更新知识条目
 */
export function updateKnowledgeEntry(id, data) {
  return request({
    url: `/requirement-analysis/knowledge-entries/${id}/`,
    method: 'put',
    data
  })
}

/**
 * 批量删除知识条目
 */
export function batchDeleteKnowledgeEntries(ids) {
  return request({
    url: '/requirement-analysis/knowledge-entries/batch_delete/',
    method: 'post',
    data: { ids }
  })
}

/**
 * 删除知识条目
 */
export function deleteKnowledgeEntry(id) {
  return request({
    url: `/requirement-analysis/knowledge-entries/${id}/`,
    method: 'delete'
  })
}

/**
 * 检索业务知识
 */
export function retrieveKnowledge(data) {
  return request({
    url: '/requirement-analysis/knowledge/search/',
    method: 'post',
    data
  })
}