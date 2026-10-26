import { useEffect, useState } from 'react'
import { Link, NavLink, Route, Routes } from 'react-router-dom'
import { Activity, AlertCircle, ArrowUpRight, LoaderCircle } from 'lucide-react'
import { getHealth } from './services/api.js'
import { LandingPage } from './pages/LandingPage.jsx'
import { RepositoryPage } from './pages/RepositoryPage.jsx'
import { IssueExplorerPage } from './pages/IssueExplorerPage.jsx'
import { IssueAnalysisPage } from './pages/IssueAnalysisPage.jsx'
import { ImplementationPage } from './pages/ImplementationPage.jsx'

const links = [['/', 'WORKFLOW'], ['/repository', 'REPOSITORY'], ['/issues', 'ISSUES']]
function BackendStatus() {
  const [state, setState] = useState('loading')
  useEffect(() => { let live = true; getHealth().then(() => live && setState('ok')).catch(() => live && setState('error')); return () => { live = false } }, [])
  return <span className={`backend-status backend-status--${state}`}>{state === 'loading' ? <LoaderCircle size={13} className="spin" /> : state === 'ok' ? <Activity size={13} /> : <AlertCircle size={13} />}{state === 'ok' ? 'API CONNECTED' : state === 'error' ? 'API OFFLINE' : 'CHECKING API'}</span>
}

export default function App() {
  return <div className="app-frame"><header className="floating-nav"><Link to="/" className="brand"><img src="/panda-logo.png" alt="PANDA" /></Link><nav aria-label="Main navigation">{links.map(([to, label]) => <NavLink key={to} to={to} end={to === '/'}>{label}</NavLink>)}</nav><div className="nav-right"><BackendStatus /><a href="https://github.com/AaryanRS/PANDA" target="_blank" rel="noreferrer" className="github-link">GITHUB <ArrowUpRight size={15} /></a></div></header><main><Routes><Route path="/" element={<LandingPage />} /><Route path="/repository" element={<RepositoryPage />} /><Route path="/issues" element={<IssueExplorerPage />} /><Route path="/analysis" element={<IssueAnalysisPage />} /><Route path="/implementation" element={<ImplementationPage />} /><Route path="*" element={<section className="page"><p className="eyebrow">404 / NOT FOUND</p><h1>ROUTE NOT FOUND.</h1><Link to="/" className="button-link">RETURN HOME →</Link></section>} /></Routes></main></div>
}
