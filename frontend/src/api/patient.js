import api from './index'

export const patientApi = {
  login: (patientId, cardNumber) => api.post('/patient/auth/login', {
    patient_id: patientId,
    medical_card_number: cardNumber,
  }).then((r) => r.data),

  getMe: () => api.get('/patient/auth/me').then((r) => r.data),

  createTriageSession: () => api.post('/patient/triage/sessions').then((r) => r.data),

  listTriageSessions: () => api.get('/patient/triage/sessions').then((r) => r.data),

  triageChat: (sessionId, message) => api.post('/patient/triage/chat', {
    session_id: sessionId,
    message,
  }).then((r) => r.data),

  adoptTriage: (sessionId, deptName) => api.post(`/patient/triage/sessions/${sessionId}/adopt`, {
    dept_name: deptName,
  }).then((r) => r.data),

  nurseTransfer: (sessionId) => api.post(`/patient/triage/sessions/${sessionId}/nurse`).then((r) => r.data),

  listBookings: () => api.get('/patient/bookings').then((r) => r.data),

  createBooking: (body) => api.post('/patient/bookings', body).then((r) => r.data),

  syncBookingHis: (bookingId) => api.post(`/patient/bookings/${bookingId}/sync-his`).then((r) => r.data),

  getTimeline: () => api.get('/patient/timeline').then((r) => r.data),

  getReports: (patientId) => api.get(`/patient/reports/${patientId}`).then((r) => r.data),

  getNavByDept: (deptName) => api.get(`/patient/navigation/dept/${deptName}`).then((r) => r.data),

  createNurseRequest: (body) => api.post('/patient/nurse/request', body).then((r) => r.data),
}

export default patientApi