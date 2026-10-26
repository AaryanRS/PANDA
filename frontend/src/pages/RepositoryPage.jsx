import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, LoaderCircle } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { connectRepository } from '../services/api.js'

function messageFor(error) {
  if (error.code === 'invalid_url') return ['INVALID GITHUB URL', error.message]
  if (error.code === 'repository_not_found') return ['REPOSITORY NOT FOUND', error.message]
  if (error.code === 'github_rate_limit') return ['GITHUB RATE LIMIT', error.message]
  if (error.code === 'github_unavailable') return ['GITHUB SERVICE UNAVAILABLE', error.message]
  return ['COULD NOT CONNECT REPOSITORY', error.message]
}

export function RepositoryPage() {
  const [url, setUrl] = useState('')
  const [state, setState] = useState('idle')
  const [repository, setRepository] = useState(null)
  const [error, setError] = useState(null)

  async function submit(event) {
    event.preventDefault()
    setState('loading')
    setError(null)
    setRepository(null)
    sessionStorage.removeItem('panda.repository')
    try {
      const data = await connectRepository(url.trim())
      setRepository(data)
      try { sessionStorage.setItem('panda.repository', JSON.stringify(data)) } catch { /* Connection remains usable for this view. */ }
      setState('success')
    } catch (requestError) {
      setError(requestError)
      setState('error')
    }
  }

  return <section className="page repository-page">
    <div className="page-kicker"><span>PANDA / REPOSITORY</span><span>01 — CONNECT</span></div>
    <div className="repo-layout"><div><p className="eyebrow">OPEN SOURCE CONTRIBUTION WORKSPACE</p><h1>UNDERSTAND A<br/><span>CODEBASE.</span></h1><p className="lead">Start with the repository. Move toward a contribution with context.</p>
      <form onSubmit={submit} className="repo-form"><label htmlFor="repo-url">GITHUB REPOSITORY URL</label><div><input id="repo-url" type="text" inputMode="url" placeholder="https://github.com/owner/repository" value={url} onChange={event => setUrl(event.target.value)} required/><button type="submit" disabled={state === 'loading'}>{state === 'loading' ? <><LoaderCircle className="spin" size={18}/> CONNECTING</> : <>CONNECT REPOSITORY <ArrowRight size={18}/></>}</button></div></form>
      <AnimatePresence>{state === 'loading' && <motion.div className="investigation" initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ opacity: 0 }}><span>CONNECTING</span><span>REPOSITORY</span><span>LABELS</span><span>OPEN ISSUES</span></motion.div>}</AnimatePresence>
      {state === 'error' && <div className="data-error" role="alert"><strong>{messageFor(error)[0]}</strong><p>{messageFor(error)[1]}</p><button type="button" onClick={submit}>RETRY CONNECTION →</button></div>}
    </div><aside className="repo-side"><div className="side-mark">P<span>.</span></div><span className="mono-label">THE STARTING POINT</span><p>One repository. A focused path from issue to implementation.</p><span className="side-rule"/><span className="eyebrow">GITHUB REST API / PUBLIC REPOSITORIES</span></aside></div>
    {state === 'success' && repository && <div className="repo-summary"><div className="summary-heading"><strong>REPOSITORY CONNECTED</strong><span>LIVE GITHUB DATA</span></div><div className="summary-name">{repository.full_name}</div>{repository.description && <p className="repo-description">{repository.description}</p>}<div className="summary-stats">{[['OPEN ISSUES', repository.open_issues_count.toLocaleString()],['LANGUAGE', repository.language || 'NOT SPECIFIED'],['DEFAULT BRANCH', repository.default_branch],['STARS', repository.stars.toLocaleString()]].map(([label,value])=><div key={label}><span>{label}</span><b>{value}</b></div>)}</div>{repository.issue_search_limit_reached && <p className="limit-note">GitHub search exposes at most 1,000 results. Issue browsing is limited to that search window.</p>}<Link to="/issues" className="button-link">EXPLORE ISSUES <ArrowRight size={17}/></Link></div>}
    <div className="page-footer"><span>01 / REPOSITORY</span>{state === 'success' ? <Link to="/issues">NEXT / ISSUE EXPLORER →</Link> : <span>GITHUB SOURCE / READY TO CONNECT</span>}</div>
  </section>
}
