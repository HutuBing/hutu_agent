/** fetch 封装：JSON 请求、非 2xx 抛错并统一提示。 */
import { ElMessage } from 'element-plus'

export async function http(method, url, body = undefined, isForm = false) {
  const opts = { method, headers: {} }
  if (body !== undefined) {
    if (isForm) {
      opts.body = body // FormData
    } else {
      opts.headers['Content-Type'] = 'application/json'
      opts.body = JSON.stringify(body)
    }
  }
  const resp = await fetch(url, opts)
  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`
    try {
      const j = await resp.json()
      detail = j.detail || JSON.stringify(j)
    } catch { /* 保持默认 */ }
    ElMessage.error(detail)
    throw new Error(detail)
  }
  return resp.json()
}

export const get = (url) => http('GET', url)
export const post = (url, body) => http('POST', url, body)
export const put = (url, body) => http('PUT', url, body)
export const del = (url) => http('DELETE', url)
export const postForm = (url, formData) => http('POST', url, formData, true)
