import { useState } from 'react'
import { errorText, niceDate, useApi, useHotelToday } from '../../hooks.js'
import { t } from '../../i18n.jsx'
import CallDetail from '../../components/CallDetail.jsx'

const LANG = { 'Arabic-Egyptian': 'Arabic (Egyptian)' }
const STATUS = { completed: ['Solved', 'b-green'], escalated: ['Handed to staff', 'b-amber'], abandoned: ['Hung up', 'b-grey'], active: ['Live now', 'b-blue'] }

function Bars({ rows, color }) {
  const max = Math.max(1, ...rows.map(([, n]) => n))
  return rows.map(([name, n]) => (
    <div key={name} className="row" style={{ fontSize: 14, flexWrap: 'nowrap' }}>
      <span style={{ flex: '0 0 150px' }}>{t(name)}</span>
      <div className="bar-track" style={{ flex: 1 }}><div className="bar-fill" style={{ width: `${(n / max) * 100}%`, background: color }} /></div>
      <b style={{ flex: '0 0 28px', textAlign: 'right' }}>{n}</b>
    </div>
  ))
}

export default function NourStats() {
  const today = useHotelToday()
  const [status, setStatus] = useState('')
  const [open, setOpen] = useState(null)
  const { data, error } = useApi('/admin/calls')
  if (error) return <div className="error-box">{errorText(error)}</div>
  if (!data) return <div className="loading">{t('Loading…')}</div>

  const n = data.length
  const solved = data.filter((c) => c.status === 'completed').length
  const escalated = data.filter((c) => c.status === 'escalated').length
  const lat = data.filter((c) => c.avg_latency_ms)
  const avgLatency = lat.length ? lat.reduce((a, c) => a + c.avg_latency_ms, 0) / lat.length : 0
  const dur = data.filter((c) => c.duration_seconds)
  const avgDur = dur.length ? dur.reduce((a, c) => a + c.duration_seconds, 0) / dur.length : 0
  const actions = data.reduce((a, c) => a + c.actions, 0)
  const tickets = data.reduce((a, c) => a + c.tickets, 0)
  const langs = Object.entries(data.reduce((m, c) => ({ ...m, [LANG[c.language] || c.language || 'Unknown']: (m[LANG[c.language] || c.language || 'Unknown'] || 0) + 1 }), {})).sort((a, b) => b[1] - a[1])
  const first = data.map((c) => c.started_at).sort()[0]
  const when = (iso) => (iso.slice(0, 10) === today ? `${t('Today')} ${iso.slice(11, 16)}` : `${niceDate(iso, false, false)} ${iso.slice(11, 16)}`)

  return (
    <>
      <header className="page-head"><div><div className="eyebrow">{first ? t('Since {date}', { date: niceDate(first) }) : ''}</div><h1 className="title">{t('Nour — AI voice agent')}</h1></div></header>
      <div className="grid" style={{ '--min': '170px', gap: 14 }}>
        <div className="card kpi dark"><div className="label">{t('Conversations')}</div><div className="value">{n}</div><div className="note">{t('{n} from visitors not logged in', { n: data.filter((c) => c.visitor).length })}</div></div>
        <div className="card kpi"><div className="label">{t('Solved by Nour alone')}</div><div className="value">{n ? Math.round((solved / n) * 100) : 0}%</div><div className="note">{t('{a} of {b} · {c} handed to staff', { a: solved, b: n, c: escalated })}</div></div>
        <div className="card kpi"><div className="label">{t('Reply time')}</div><div className="value"><span className="ltr">{(avgLatency / 1000).toFixed(2)} s</span></div><div className="note">{t('average to first audio')}</div></div>
        <div className="card kpi"><div className="label">{t('Average call')}</div><div className="value"><span className="ltr">{Math.round(avgDur)} s</span></div><div className="note">{t('{a} tool actions · {b} tickets opened', { a: actions, b: tickets })}</div></div>
      </div>
      <div className="grid" style={{ '--min': '300px' }}>
        <section className="card pad stack" style={{ gap: 12 }}><h2 className="h2">{t('Languages')}</h2><Bars rows={langs} color="var(--gold)" /></section>
        <section className="card pad stack" style={{ gap: 12 }}><h2 className="h2">{t('How calls ended')}</h2>
          <Bars rows={[['Solved', solved], ['Handed to staff', escalated], ['Hung up', data.filter((c) => c.status === 'abandoned').length]]} color="var(--teal)" />
        </section>
      </div>
      <section className="card table-box">
        <div className="row between" style={{ padding: '16px 20px 8px' }}>
          <div><h2 className="h2">{t('Conversations')}</h2><div className="small muted">{t('Click a conversation to read it and see what Nour did.')}</div></div>
          <div className="row">
            {[['', 'All'], ['escalated', 'Handed to staff'], ['abandoned', 'Hung up']].map(([id, label]) => <button key={id} className={`chip ${status === id ? 'on' : ''}`} onClick={() => setStatus(id)}>{t(label)}</button>)}
          </div>
        </div>
        {data.filter((c) => !status || c.status === status).map((c) => (
          <button key={c.call_id} className="row" onClick={() => setOpen(c.call_id)} style={{ width: '100%', gap: '6px 16px', padding: '12px 20px', border: 0, borderTop: '1px solid var(--line-2)', background: 'transparent', color: 'var(--ink)', fontSize: 14, textAlign: 'start' }}>
            <span className="muted" style={{ flex: '0 0 120px' }}>{when(c.started_at)}</span>
            <span style={{ flex: '0 0 130px' }}>{t(LANG[c.language] || c.language || 'Unknown')}</span>
            <span style={{ flex: '0 0 140px' }}>{c.guest_name || t('Visitor')}</span>
            <span style={{ flex: '1 1 300px' }} dir="ltr" className="ltr">{c.summary || c.escalation_reason || t('{n} turns', { n: c.turns })}</span>
            <span className={`badge ${STATUS[c.status]?.[1] || 'b-grey'}`}>{t(STATUS[c.status]?.[0] || c.status)}</span>
            <span className="small" style={{ color: 'var(--teal)', fontWeight: 600 }}>{t('View')} ›</span>
          </button>
        ))}
      </section>
      {open && <CallDetail callId={open} onClose={() => setOpen(null)} />}
    </>
  )
}
