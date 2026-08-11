import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  { path: '/', redirect: '/login' },
  { path: '/login', name: 'login', component: () => import('../views/Login.vue') },
  {
    path: '/workstation',
    name: 'workstation',
    component: () => import('../views/Workstation.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/config',
    name: 'config',
    component: () => import('../views/SubAgentConfig.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/admin',
    component: () => import('../views/admin/AdminLayout.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
    children: [
      { path: '', redirect: '/admin/buildings' },
      { path: 'buildings', name: 'adminBuildings', component: () => import('../views/admin/AdminBuildings.vue') },
      { path: 'departments', name: 'adminDepartments', component: () => import('../views/admin/AdminDepartments.vue') },
      { path: 'users', name: 'adminUsers', component: () => import('../views/admin/AdminUsers.vue') },
      { path: 'exam-items', name: 'adminExamItems', component: () => import('../views/admin/AdminExamItems.vue') },
      { path: 'rag', name: 'adminRag', component: () => import('../views/admin/AdminRagDocs.vue') },
      { path: 'kb', name: 'adminKb', component: () => import('../views/admin/AdminKb.vue') },
      { path: 'agents', name: 'adminAgents', component: () => import('../views/admin/AdminAgentConfig.vue') },
      { path: 'permissions', name: 'adminPermissions', component: () => import('../views/admin/AdminPermissions.vue') },
      { path: 'cases', name: 'adminCases', component: () => import('../views/admin/AdminCases.vue') },
      { path: 'audit', name: 'adminAudit', component: () => import('../views/admin/AdminAuditLog.vue') },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth && !auth.token) {
    return '/login'
  }
  // 非 admin 角色禁止进入后台管理路由
  if (to.meta.requiresAdmin && !auth.isAdmin) {
    return '/workstation'
  }
  if (to.path === '/login' && auth.token) {
    return '/workstation'
  }
})

export default router
