import { useState } from 'react'
import { api } from '../../api/client.js'
import { errorText, niceDate, useApi, useHotelToday } from '../../hooks.js'
import { t, t as tr } from '../../i18n.jsx'

const pBadge = { Critical: 'b-red', Urgent: 'b-red', Normal: 'b-blue' }
const sBadge = { Open: 'b-amber', 'In Progress': 'b-blue', Resolved: 'b-green', Closed: 'b-grey' }

export default function Tickets() {
  const today = useHotelToday()
  const { data, error, reload, setData } = useApi('/staff/requests')
  const [filter, setFilter] = useState('all')
  const [msg, setMsg] = useState(null)

  const list = (data || []).filter((t) => t.request_type !== 'Discount Request')
    .filter((t) => filter === 'all' || (filter === 'urgent' ? t.priority !== 'Normal' : t.request_status === 'Open'))

  async function act(t, action) {
    setMsg(null)
    try {
      const updated = await api(`/staff/requests/${t.request_id}/${action}`, { method: 'POST', body: action === 'close' ? { outcome: 'Resolved' } : undefined })
      setData((rows) => rows.map((r) => (r.request_id === t.request_id ? updated : r)))
      if (action === 'close') setTimeout(reload, 1200)
    } catch (e) { setMsg(errorText(e)) }
  }

  const when = (iso) => (iso.slice(0, 10) === today ? `${t('Today')} ${iso.slice(11, 16)}` : niceDate(iso, false, false))

  return (
    <>
      <header className="page-head"><div><div className="eyebrow">{today ? niceDate(today, true) : ''}</div><h1 className="title">{t('Tickets')}</h1></div></header>
      <div className="row">
        {[['all', 'All'], ['urgent', 'Urgent & critical'], ['open', 'Not taken yet']].map(([id, label]) => (
          <button key={id} className={`chip ${filter === id ? 'on' : ''}`} onClick={() => setFilter(id)}>{t(label)}</button>
        ))}
      </div>
      {(error || msg) && <div className="error-box">{msg || errorText(error)}</div>}
      <div className="stack" style={{ gap: 10 }}>
        {list.map((t) => (
          <article key={t.request_id} className="card row" style={{ padding: '14px 18px', gap: '12px 20px' }}>
            <span className={`badge ${pBadge[t.priority]}`} style={{ borderRadius: 6, minWidth: 64, textAlign: 'center' }}>{tr(t.priority)}</span>
            <div style={{ flex: '1 1 320px', minWidth: 0 }}>
              <div style={{ fontSize: 15, fontWeight: 600 }} dir="auto">{t.request_text}</div>
              <div className="small muted">{tr(t.request_type)} · {t.guest_name || tr('Visitor')} · {t.room_number ? tr('Room {n}', { n: t.room_number }) : tr('No room')} · {t.request_id} · {when(t.created_at)}{t.call_id ? tr(' · from Nour') : ''}</div>
            </div>
            <div className="small" style={{ flex: '0 0 150px', color: 'var(--text-2)' }}>{t.handled_by || tr('Not taken yet')}</div>
            <span className={`badge ${sBadge[t.request_status]}`}>{tr(t.request_status)}</span>
            {t.request_status === 'Open' && <button className="btn sm" onClick={() => act(t, 'take')}>{tr('Take it')}</button>}
            {t.request_status === 'In Progress' && <button className="btn sm teal" onClick={() => act(t, 'close')}>{tr('Mark resolved')}</button>}
          </article>
        ))}
        {data && list.length === 0 && <div className="card pad muted">{t('Nothing in this list.')}</div>}
      </div>
      <p className="small muted" style={{ margin: 0 }}>{t('Emergencies (Critical) always sit on top. Discount requests go to the administrator.')}</p>
    </>
  )
}
