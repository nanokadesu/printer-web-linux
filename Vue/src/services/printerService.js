import api from './api'

export const getPrinters = () => api.get('/printers')
export const uploadPrintFile = (formData) => api.post('/print/upload', formData)
export const printCalibrationPage = (data) => api.post('/print/calibration', data)
export const getActiveJobs = () => api.get('/print/jobs')
export const continuePrintJob = (jobId) => api.post(`/print/jobs/${jobId}/continue`)
export const cancelPrintJob = (jobId) => api.post(`/print/jobs/${jobId}/cancel`)
export const clearCompletedJobs = () => api.get('/print/jobs/clear_completed')
