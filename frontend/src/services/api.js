const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

export class ApiError extends Error {
  constructor(message, status, code) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

async function request(path, options = {}) {
  let response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, options)
  } catch {
    throw new ApiError('Could not reach the PANDA backend. Check that it is running and try again.', 0, 'backend_unavailable')
  }
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = data.detail
    throw new ApiError(typeof detail === 'string' ? detail : detail?.message || 'PANDA could not complete this request.', response.status, detail?.code || 'request_failed')
  }
  return data
}

export function connectRepository(url) {
  return request('/api/repository/connect', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url }) })
}

export function getIssues({ owner, repo, page = 1, category = 'ALL', search = '', difficulty = 'ALL', skill = 'ALL', effort = 'ALL', signal }) {
  const params = new URLSearchParams({ owner, repo, page: String(page), category, search, difficulty, skill, effort })
  return request(`/api/issues?${params}`, { signal })
}

export function getIssue(owner, repo, number, signal) {
  return request(`/api/issues/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/${number}`, { signal })
}

export async function analyzeIssue(owner, repo, number, onStage, signal) {
  let response
  try {
    response = await fetch(`${API_BASE_URL}/api/issues/${encodeURIComponent(owner)}/${encodeURIComponent(repo)}/${number}/analyze`, {
      method: 'POST',
      headers: { Accept: 'application/x-ndjson' },
      signal,
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new ApiError('Could not reach the PANDA backend. Check that it is running and try again.', 0, 'backend_unavailable')
  }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    const detail = data.detail
    throw new ApiError(detail?.message || 'PANDA could not start the analysis.', response.status, detail?.code || 'request_failed')
  }
  if (!response.body) throw new ApiError('PANDA received no analysis response.', 502, 'analysis_failed')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let result = null
  async function handleLine(line) {
    if (!line.trim()) return
    let event
    try { event = JSON.parse(line) } catch { throw new ApiError('PANDA received a malformed analysis event.', 502, 'analysis_failed') }
    if (event.type === 'stage') onStage?.(event.stage)
    if (event.type === 'error') throw new ApiError(event.message, event.status, event.code)
    if (event.type === 'result') result = event.data
  }
  while (true) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''
    for (const line of lines) await handleLine(line)
    if (done) break
  }
  if (buffer.trim()) await handleLine(buffer)
  if (!result) throw new ApiError('PANDA could not validate the Gemma response.', 502, 'gemma_invalid_response')
  return result
}

export async function getHealth() {
  let response
  try {
    response = await fetch(`${API_BASE_URL}/api/health`)
  } catch {
    throw new Error('Could not reach the PANDA backend.')
  }

  if (!response.ok) {
    throw new Error(`Backend returned HTTP ${response.status}.`)
  }

  const data = await response.json()
  if (data.status !== 'ok' || data.service !== 'panda-backend') {
    throw new Error('Backend returned an unexpected health response.')
  }
  return data
}
