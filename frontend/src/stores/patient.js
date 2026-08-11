import { defineStore } from 'pinia'
import api from '../api'

export const usePatientStore = defineStore('patient', {
  state: () => ({
    token: localStorage.getItem('patient_token') || '',
    patient: JSON.parse(localStorage.getItem('patient_user') || 'null'),
    fontScale: parseInt(localStorage.getItem('patient_font_scale') || '1'),
  }),
  getters: {
    isLoggedIn: (s) => !!s.token && !!s.patient,
    fontClass: (s) => s.fontScale === 2 ? 'text-lg' : s.fontScale === 1 ? 'text-base' : 'text-sm',
  },
  actions: {
    async login(patientId, cardNumber) {
      const { data } = await api.post('/patient/auth/login', {
        patient_id: patientId,
        medical_card_number: cardNumber,
      })
      this.token = data.token
      this.patient = data.patient
      localStorage.setItem('patient_token', data.token)
      localStorage.setItem('patient_user', JSON.stringify(data.patient))
      // Switch token context for patient API calls
      localStorage.setItem('token', data.token)
      localStorage.setItem('user', JSON.stringify({ ...data.patient, role: 'patient' }))
    },
    async fetchProfile() {
      const { data } = await api.get('/patient/auth/me')
      this.patient = data
      localStorage.setItem('patient_user', JSON.stringify(data))
    },
    setFontScale(scale) {
      this.fontScale = scale
      localStorage.setItem('patient_font_scale', String(scale))
    },
    logout() {
      this.token = ''
      this.patient = null
      localStorage.removeItem('patient_token')
      localStorage.removeItem('patient_user')
      // Restore doctor token if exists
      const docToken = localStorage.getItem('doctor_token')
      if (docToken) {
        localStorage.setItem('token', docToken)
      } else {
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        localStorage.removeItem('permissions')
      }
    },
  },
})