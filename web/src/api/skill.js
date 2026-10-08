import { get, del, postForm } from './http'

export const listSkills = () => get('/api/skills')
export const getSkill = (id) => get(`/api/skills/${id}`)
export const getSkillVersion = (id, v) => get(`/api/skills/${id}/versions/${v}`)
export const uploadSkill = (formData) => postForm('/api/skills', formData)
export const deleteSkill = (id) => del(`/api/skills/${id}`)
