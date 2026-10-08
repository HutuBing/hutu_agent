import { get, post, put, del } from './http'

export const listAgents = () => get('/api/agents')
export const createAgent = (data) => post('/api/agents', data)
export const updateAgent = (id, data) => put(`/api/agents/${id}`, data)
export const deleteAgent = (id) => del(`/api/agents/${id}`)
