import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { usePatientStore } from '../stores/patient'

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
  // —— 患者端 H5 ——
  {
    path: '/patient/login',
    name: 'patientLogin',
    component: () => import('../views/patient/PatientLogin.vue'),
  },
  {
    path: '/patient',
    component: () => import('../views/patient/PatientLayout.vue'),
    meta: { requiresPatientAuth: true },
    children: [
      { path: '', redirect: '/patient/home' },
      { path: 'home', name: 'patientHome', component: () => import('../views/patient/PatientHome.vue') },
      { path: 'triage', name: 'patientTriage', component: () => import('../views/patient/PatientTriage.vue') },
      { path: 'booking', name: 'patientBooking', component: () => import('../views/patient/PatientBooking.vue') },
      { path: 'timeline', name: 'patientTimeline', component: () => import('../views/patient/PatientTimeline.vue') },
      { path: 'reports', name: 'patientReports', component: () => import('../views/patient/PatientReports.vue') },
      { path: 'navigation', name: 'patientNavigation', component: () => import('../views/patient/PatientNavigation.vue') },
      { path: 'profile', name: 'patientProfile', component: () => import('../views/patient/PatientProfile.vue') },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  const patientStore = usePatientStore()

  // 患者端路由守卫
  if (to.meta.requiresPatientAuth && !patientStore.isLoggedIn) {
    return '/patient/login'
  }
  if (to.path === '/patient/login' && patientStore.isLoggedIn) {
    return '/patient/home'
  }

  // 医生端路由守卫
  if (to.meta.requiresAuth && !auth.token) {
    return '/login'
  }
  if (to.meta.requiresAdmin && !auth.isAdmin) {
    return '/workstation'
  }
  if (to.path === '/login' && auth.token) {
    return '/workstation'
  }
})

export default router
