import { Link } from 'react-router-dom'

export function PageShell({ number, title, description, next }) {
  return (
    <section className="page">
      <p className="eyebrow">PHASE 1 / {number}</p>
      <h1>{title}</h1>
      <p className="page-description">{description}</p>
      <div className="placeholder-panel">
        <span className="panel-mark">P</span>
        <div><p className="eyebrow">FOUNDATION PLACEHOLDER</p><p>This view establishes the route and layout for a later phase.</p></div>
      </div>
      {next && <Link className="text-link" to={next.href}>{next.label} <span aria-hidden="true">→</span></Link>}
    </section>
  )
}
