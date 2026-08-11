import api from './index'

/** 后台管理 API 封装（仅 admin 角色可调用，后端 require_admin 校验） */
export const adminApi = {
  // ----- 用户 -----
  listUsers: () => api.get('/admin/users').then((r) => r.data),
  createUser: (body) => api.post('/admin/users', body).then((r) => r.data),
  updateUser: (id, body) => api.put(`/admin/users/${id}`, body).then((r) => r.data),
  deleteUser: (id) => api.delete(`/admin/users/${id}`).then((r) => r.data),
  // ----- 科室 -----
  listDepartments: () => api.get('/admin/departments').then((r) => r.data),
  createDepartment: (name) => api.post('/admin/departments', { name }).then((r) => r.data),
  updateDepartment: (id, name) => api.put(`/admin/departments/${id}`, { name }).then((r) => r.data),
  deleteDepartment: (id) => api.delete(`/admin/departments/${id}`).then((r) => r.data),
  // ----- 权限矩阵 -----
  getPermissions: () => api.get('/admin/permissions').then((r) => r.data),
  updatePermissions: (matrix) => api.put('/admin/permissions', { matrix }).then((r) => r.data),
  // ----- 知识库 -----
  listKb: (category) => api.get('/admin/kb', { params: category ? { category } : {} }).then((r) => r.data),
  createKb: (body) => api.post('/admin/kb', body).then((r) => r.data),
  updateKb: (id, body) => api.put(`/admin/kb/${id}`, body).then((r) => r.data),
  deleteKb: (id) => api.delete(`/admin/kb/${id}`).then((r) => r.data),
  listKbCategories: () => api.get('/admin/kb/categories').then((r) => r.data),
  // ----- 楼宇/楼层/房间 -----
  listBuildings: () => api.get('/admin/buildings').then((r) => r.data),
  createBuilding: (name) => api.post('/admin/buildings', { name }).then((r) => r.data),
  updateBuilding: (id, name) => api.put(`/admin/buildings/${id}`, { name }).then((r) => r.data),
  deleteBuilding: (id) => api.delete(`/admin/buildings/${id}`).then((r) => r.data),
  addFloor: (bid, name) => api.post(`/admin/buildings/${bid}/floors`, { name }).then((r) => r.data),
  deleteFloor: (bid, fid) => api.delete(`/admin/buildings/${bid}/floors/${fid}`).then((r) => r.data),
  bindRoom: (bid, fid, body) => api.post(`/admin/buildings/${bid}/floors/${fid}/rooms`, body).then((r) => r.data),
  deleteRoom: (bid, fid, rid) => api.delete(`/admin/buildings/${bid}/floors/${fid}/rooms/${rid}`).then((r) => r.data),
  // ----- 检验项目字典 -----
  listExamItems: (category) => api.get('/admin/exam-items', { params: category ? { category } : {} }).then((r) => r.data),
  createExamItem: (body) => api.post('/admin/exam-items', body).then((r) => r.data),
  updateExamItem: (id, body) => api.put(`/admin/exam-items/${id}`, body).then((r) => r.data),
  deleteExamItem: (id) => api.delete(`/admin/exam-items/${id}`).then((r) => r.data),
  // ----- RAG 文档库 -----
  listRagDocs: (category) => api.get('/admin/rag/docs', { params: category ? { category } : {} }).then((r) => r.data),
  getRagDoc: (id) => api.get(`/admin/rag/docs/${id}`).then((r) => r.data),
  createRagDoc: (body) => api.post('/admin/rag/docs', body).then((r) => r.data),
  updateRagDoc: (id, body) => api.put(`/admin/rag/docs/${id}`, body).then((r) => r.data),
  setRagDocStatus: (id, status) => api.put(`/admin/rag/docs/${id}/status`, { status }).then((r) => r.data),
  deleteRagDoc: (id) => api.delete(`/admin/rag/docs/${id}`).then((r) => r.data),
  ragRecall: (query, topK = 3) => api.post('/admin/rag/recall', { query, top_k: topK }).then((r) => r.data),
  // ----- Agent 能力配置 -----
  getAgentConfig: () => api.get('/admin/agents/config').then((r) => r.data),
  toggleAgent: (body) => api.put('/admin/agents/toggle', body).then((r) => r.data),
  // ----- 归档病案 -----
  listCases: (params) => api.get('/admin/cases', { params }).then((r) => r.data),
  getCaseDetail: (pid) => api.get(`/admin/cases/${pid}`).then((r) => r.data),
  // ----- 系统审计日志 -----
  listAudit: (params) => api.get('/admin/audit', { params }).then((r) => r.data),
}

export default adminApi
