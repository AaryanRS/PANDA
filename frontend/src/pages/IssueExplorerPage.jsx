import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowLeft, ArrowRight, ArrowUpRight, Search } from 'lucide-react'
import { getIssues } from '../services/api.js'

const filters = ['ALL', 'BUG FIX', 'NEW FEATURE', 'REFACTOR', 'TESTING', 'DOCUMENTATION', 'PERFORMANCE']
const skills = ['Python', 'Testing', 'Documentation', 'Performance', 'Backend', 'Frontend', 'Data / ML', 'DevOps / CI', 'Architecture', 'Other']

function readRepository() {
  try { return JSON.parse(sessionStorage.getItem('panda.repository') || 'null') } catch { return null }
}

function dateLabel(value) {
  if (!value) return 'DATE UNAVAILABLE'
  return new Intl.DateTimeFormat(undefined, { year: 'numeric', month: 'short', day: 'numeric' }).format(new Date(value))
}

export function IssueExplorerPage() {
  const repository = useMemo(readRepository, [])
  const [filter, setFilter] = useState('ALL')
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [page, setPage] = useState(1)
  const [data, setData] = useState(null)
  const [state, setState] = useState(repository ? 'loading' : 'idle')
  const [error, setError] = useState('')
  const [retry, setRetry] = useState(0)
  const [difficulty, setDifficulty] = useState('ALL')
  const [skill, setSkill] = useState('ALL')
  const [effort, setEffort] = useState('ALL')

  useEffect(() => {
    const timeout = window.setTimeout(() => setDebouncedSearch(search.trim()), 350)
    return () => window.clearTimeout(timeout)
  }, [search])

  useEffect(() => {
    if (!repository) return undefined
    const controller = new AbortController()
    setState('loading')
    setError('')
    getIssues({ owner: repository.owner, repo: repository.name, page, category: filter, search: debouncedSearch, difficulty, skill, effort, signal: controller.signal })
      .then(result => { setData(result); setState(result.category_available ? (result.issues.length ? 'success' : 'empty') : 'unavailable') })
      .catch(requestError => { if (requestError.name !== 'AbortError') { setError(requestError.message); setState('error') } })
    return () => controller.abort()
  }, [repository, page, filter, debouncedSearch, difficulty, skill, effort, retry])

  function changeFilter(value) { setFilter(value); setPage(1) }
  function changeSearch(value) { setSearch(value); setPage(1) }
  function changePandaFilter(setter, value) { setter(value); setPage(1) }

  if (!repository) return <section className="page issue-page"><div className="page-kicker"><span>PANDA / ISSUE EXPLORER</span><span>02 - FILTER</span></div><div className="issue-heading"><div><p className="eyebrow">CONNECT A REPOSITORY TO BEGIN</p><h1>ISSUE<br/><span>EXPLORER.</span></h1></div></div><p className="data-state">No repository is connected in this browser session.</p><Link to="/repository" className="button-link">CONNECT REPOSITORY <ArrowRight size={17}/></Link></section>

  const total = data?.total_count ?? 0
  const perPage = data?.per_page ?? 10
  const first = total ? (page - 1) * perPage + 1 : 0
  const last = Math.min(page * perPage, total)
  const totalPages = data?.total_pages ?? 0
  const firstButton = Math.max(1, Math.min(page - 2, totalPages - 4))
  const pageButtons = Array.from({ length: Math.max(0, Math.min(5, totalPages - firstButton + 1)) }, (_, i) => firstButton + i)
  const visibleIssues = data?.issues ?? []
  const pandaFiltersActive = difficulty !== 'ALL' || skill !== 'ALL' || effort !== 'ALL'

  return <section className="page issue-page"><div className="page-kicker"><span>PANDA / ISSUE EXPLORER</span><span>02 - FILTER</span></div><div className="issue-heading"><div><p className="eyebrow">REPOSITORY / {repository.full_name} <span className="preview-tag">LIVE GITHUB DATA</span></p><h1>ISSUE<br/><span>EXPLORER.</span></h1></div><div className="issue-count"><b>{data ? total.toLocaleString() : '-'}</b><span>OPEN ISSUES<br/>{pandaFiltersActive ? 'MATCHING PANDA FILTERS' : 'MATCHING SEARCH'}</span></div></div>
    <div className="filter-bar"><div className="filter-chips">{filters.map(item=><button key={item} className={filter===item?'selected':''} aria-pressed={filter===item} onClick={()=>changeFilter(item)}>{item}</button>)}</div><label className="search-box"><Search size={16}/><input value={search} onChange={event=>changeSearch(event.target.value)} placeholder="SEARCH OPEN ISSUES" aria-label="Search open issues"/></label></div>
    <div className="advanced-filters"><span>PANDA ESTIMATES</span><select aria-label="Difficulty" value={difficulty} onChange={event=>changePandaFilter(setDifficulty,event.target.value)}><option value="ALL">ALL DIFFICULTIES</option><option>Beginner</option><option>Intermediate</option><option>Advanced</option></select><select aria-label="Skill" value={skill} onChange={event=>changePandaFilter(setSkill,event.target.value)}><option value="ALL">ALL SKILLS</option>{skills.map(item=><option key={item}>{item}</option>)}</select><select aria-label="Effort" value={effort} onChange={event=>changePandaFilter(setEffort,event.target.value)}><option value="ALL">ALL EFFORTS</option><option>Small</option><option>Medium</option><option>Large</option></select>{pandaFiltersActive && <button className="filter-reset" onClick={()=>{setDifficulty('ALL');setSkill('ALL');setEffort('ALL');setPage(1)}}>CLEAR PANDA FILTERS</button>}</div>
    {data?.search_limit_reached && <div className="limit-note">PANDA checked the first {data.candidate_count?.toLocaleString() || '1,000'} of GitHub Search's 1,000-issue window. Matching counts and pagination apply to that bounded candidate set.</div>}
    {state === 'loading' && <div className="data-state">LOADING ISSUES <span className="loading-tick"/></div>}
    {state === 'error' && <div className="data-error" role="alert"><strong>ISSUE REQUEST FAILED</strong><p>{error}</p><button onClick={()=>setRetry(current=>current+1)}>RETRY REQUEST -&gt;</button></div>}
    {state === 'unavailable' && <div className="data-state"><strong>{filter} CATEGORY UNAVAILABLE</strong><p>No matching repository labels were found. No issues were hidden or classified.</p></div>}
    {state === 'empty' && <div className="data-state"><strong>NO RESULTS</strong><p>No open issues matched this category and search.</p></div>}
    {state === 'success' && visibleIssues.length === 0 && <div className="data-state"><strong>NO ISSUES ON THIS PAGE MATCH THESE PANDA ESTIMATES</strong><p>Try another page or clear one or more PANDA filters.</p></div>}
    <div className="issue-list">{state === 'success' && visibleIssues.map(issue=><Link to={`/analysis?owner=${encodeURIComponent(repository.owner)}&repo=${encodeURIComponent(repository.name)}&issue=${issue.number}`} state={{ issue }} className="issue-row" key={issue.number}><div className="row-top"><span>#{issue.number}</span><span className="issue-type">{issue.labels.length ? issue.labels.join(' / ') : 'UNLABELLED'}</span></div><div className="row-main"><h2>{issue.title}</h2><ArrowUpRight className="row-arrow" size={23}/></div>{issue.body_excerpt && <p className="issue-excerpt">{issue.body_excerpt}</p>}<div className="row-meta"><span>@{issue.author || 'UNKNOWN'}</span><i>·</i><span>{dateLabel(issue.created_at)}</span><i>·</i><span>{issue.comments_count} COMMENTS</span><span className="row-path">{issue.state?.toUpperCase()}</span></div><div className="panda-classification"><span>PANDA ESTIMATE</span><b>{issue.panda?.difficulty || 'Intermediate'}</b><b>{issue.panda?.skill || 'Other'}</b><b>{issue.panda?.effort || 'Medium'}</b></div><small className="row-action">ANALYZE ↗</small></Link>)}</div>
    {state === 'success' && <div className="pagination"><span>SHOWING {first}-{last} OF {total.toLocaleString()} <b>10 PER PAGE</b></span><div><button aria-label="Previous page" disabled={!data.has_previous || state==='loading'} onClick={()=>setPage(page-1)}><ArrowLeft size={17}/></button>{pageButtons.map(number=><button className={page===number?'current':''} aria-current={page===number?'page':undefined} key={number} onClick={()=>setPage(number)}>{number}</button>)}<button aria-label="Next page" disabled={!data.has_next || state==='loading'} onClick={()=>setPage(page+1)}><ArrowRight size={17}/></button></div></div>}
    <div className="page-footer"><Link to="/repository">← REPOSITORY</Link><Link to="/analysis">ISSUE ANALYSIS →</Link></div></section>
}
