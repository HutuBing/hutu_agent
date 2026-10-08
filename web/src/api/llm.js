import { get, post, put, del } from './http'

export const listLlms = () => get('/api/llm-configs')
export const createLlm = (data) => post('/api/llm-configs', data)
export const updateLlm = (id, data) => put(`/api/llm-configs/${id}`, data)
export const deleteLlm = (id) => del(`/api/llm-configs/${id}`)
