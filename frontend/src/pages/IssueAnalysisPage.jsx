import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ArrowUpRight, LoaderCircle } from 'lucide-react'
import { analyzeIssue } from '../services/api.js'

const stages = ['READING ISSUE', 'FINDING RELEVANT FILES', 'READING SOURCE AND TESTS', 'ASKING GEMMA', 'BUILDING RECOMMENDATION']
function formatDate(value) {
  if (!value) return '—'
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(new Date(value))
}
function failureHeading(code) {
  if (code === 'ollama_unavailable') return 'PANDA AI ENGINE UNAVAILABLE'
  if (code === 'gemma_model_unavailable') return 'GEMMA 4 MODEL NOT AVAILABLE'
  if (code === 'ollama_timeout') return 'ANALYSIS TIMED OUT'
  if (code === 'gemma_invalid_response') return 'PANDA COULD NOT VALIDATE THE GEMMA RESPONSE'
  return 'ISSUE ANALYSIS FAILED'
}

export function IssueAnalysisPage() {
  const [params] = useSearchParams()
  const owner = params.get('owner')
  const repo = params.get('repo')
  const number = Number(params.get('issue'))
  const [result, setResult] = useState(null)
  const [state, setState] = useState(owner && repo && number > 0 ? 'loading' : 'idle')
  const [stage, setStage] = useState(stages[0])
  const [error, setError] = useState(null)
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    if (!owner || !repo || !Number.isInteger(number) || number < 1) { setState('idle'); return undefined }
    const controller = new AbortController()
    setState('loading')
    setStage(stages[0])
    setError(null)
    analyzeIssue(owner, repo, number, setStage, controller.signal)
      .then(data => { setResult(data); setState('success') })
      .catch(requestError => { if (requestError.name !== 'AbortError') { setError(requestError); setState('error') } })
    return () => controller.abort()
  }, [owner, repo, number, retry])

  if (state === 'idle') return <section className="page analysis-page"><div className="page-kicker"><span>PANDA / ISSUE ANALYSIS</span><span>03 — SELECT AN ISSUE</span></div><h1>SELECT AN ISSUE<br/>TO CONTINUE.</h1><Link to="/issues" className="button-link">OPEN ISSUE EXPLORER →</Link></section>

  const issue = result?.issue
  const analysis = result?.analysis
  const evidence = result?.evidence
  const currentStage = Math.max(0, stages.indexOf(stage))
  return <section className="page analysis-page"><div className="page-kicker"><span>PANDA / ISSUE ANALYSIS</span><span>03 — EVIDENCE → REASONING</span></div>
    {state === 'loading' && <div className="analysis-loading"><div className="analysis-loading-head"><LoaderCircle className="spin" size={18}/><span>{stage}</span><span>ISSUE #{number}</span></div><div className="analysis-stage-list">{stages.map((item,index)=><div key={item} className={index < currentStage ? 'complete' : index === currentStage ? 'active' : ''}><span>{index < currentStage ? '✓' : `0${index+1}`}</span>{item}</div>)}</div><p>Reading the selected issue and repository evidence. No source files are modified.</p></div>}
    {state === 'error' && <div className="data-error analysis-error" role="alert"><strong>{failureHeading(error?.code)}</strong><p>{error?.message}</p>{error?.code === 'ollama_unavailable' && <p>Make sure Ollama is running locally.</p>}{error?.code === 'gemma_model_unavailable' && <p>Check that gemma4:12b is installed in Ollama.</p>}<button onClick={()=>setRetry(value=>value+1)}>RETRY ANALYSIS →</button><Link to="/issues">BACK TO ISSUE EXPLORER →</Link></div>}
    {state === 'success' && issue && analysis && <><div className="analysis-title"><span className="issue-number">#{issue.number}</span><h1>{issue.title}</h1><span className="preview-tag">REAL GITHUB ISSUE / {result.model}</span></div><div className="analysis-grid"><section className="evidence-panel"><div className="section-head"><h2>REPOSITORY EVIDENCE</h2><span>{result.repository.full_name}</span></div><div className="evidence-item"><span>FILE</span>{evidence.files.length ? evidence.files.map(file=><div className="retrieved-evidence" key={file.path}><code>{file.path}</code>{file.symbols.length>0&&<small>SYMBOLS / {file.symbols.join(', ')}</small>}</div>) : <code>No relevant source file was confidently identified.</code>}</div><div className="evidence-item"><span>TEST</span>{evidence.tests.length ? evidence.tests.map(file=><div className="retrieved-evidence" key={file.path}><code>{file.path}</code>{file.symbols.length>0&&<small>SYMBOLS / {file.symbols.join(', ')}</small>}</div>) : <code>No relevant existing test was confidently identified.</code>}</div>{evidence.documentation.length>0&&<div className="evidence-item"><span>DOCUMENTATION</span>{evidence.documentation.map(path=><code key={path}>{path}</code>)}</div>}<div className="evidence-item"><span>ISSUE</span><code>{issue.labels.length ? issue.labels.join(' / ') : 'UNLABELLED'} · @{issue.author || 'UNKNOWN'} · {formatDate(issue.updated_at)}</code></div><a className="github-issue-link" href={issue.html_url} target="_blank" rel="noreferrer">OPEN ISSUE ON GITHUB <ArrowUpRight size={15}/></a>{evidence.tree_truncated&&<div className="evidence-note">GitHub returned a truncated repository tree; recommendations use only retrieved paths.</div>}</section><section className="reasoning-panel"><div className="section-head"><h2>ENGINEERING RECOMMENDATION</h2><span>GEMMA 4 / {result.cached ? 'CACHED' : 'LOCAL'}</span></div><div className="plan-section"><h3>FILE TO CHANGE</h3><p className="recommendation-file">{analysis.file_to_change}</p></div><div className="plan-section"><h3>WHY THIS FILE</h3><p>{analysis.why_this_file}</p></div><div className="plan-section"><h3>WHAT NEEDS TO CHANGE</h3><p>{analysis.what_to_change}</p></div><div className="patch-area"><div className="patch-header"><span>PROPOSED FIX</span><span>RECOMMENDATION / NO FILES MODIFIED</span></div><pre className="recommendation-fix">{analysis.proposed_fix}</pre></div><div className="plan-section test-section"><h3>TEST TO RUN / ADD</h3><p>{analysis.test_to_run_or_add}</p></div></section></div><div className="analysis-result-footer"><span>{result.repository.default_branch} / {result.repository.language || 'LANGUAGE NOT SPECIFIED'} / {result.latency_ms < 1000 ? `${result.latency_ms} MS` : `${(result.latency_ms/1000).toFixed(1)} SEC`}</span><span>RECOMMENDATION ONLY / SOURCE UNCHANGED</span></div><div className="page-footer"><Link to={`/issues?owner=${encodeURIComponent(owner)}&repo=${encodeURIComponent(repo)}`}>← ISSUE EXPLORER</Link><a href={issue.html_url} target="_blank" rel="noreferrer">VIEW ISSUE ON GITHUB ↗</a></div></>}
  </section>
}
