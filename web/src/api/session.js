import { get, post, del, postForm } from './http'

export const listSessions = () => get('/api/sessions')
export const createSession = (data) => post('/api/sessions', data)
export const listMessages = (sid) => get(`/api/sessions/${sid}/messages`)

/** 发起对话并解析 SSE 帧，逐事件回调 onEvent。返回 resp 供调用方 abort。 */
export async function chatStream(sid, content, onEvent, signal) {
  const resp = await fetch(`/api/sessions/${sid}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
    signal,
  })
  if (!resp.ok || !resp.body) throw new Error(`HTTP ${resp.status}`)
  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const frames = buf.split('\n\n')
    buf = frames.pop()
    for (const f of frames) {
      if (!f.startsWith('data: ')) continue
      onEvent(JSON.parse(f.slice(6)))
    }
  }
}
