import { useState } from 'react'
import { api } from '../../api/client.js'
import { errorText, niceDate, useApi } from '../../hooks.js'
import { t } from '../../i18n.jsx'

const TYPES = [
  ['Housekeeping', 'Clean room, towels, amenities'],
  ['Room Service', 'Order food to your room'],
  ['Maintenance', 'Something not working'],
  ['Late Checkout', 'Leave later on your last day'],
  ['Airport Transfer', 'Sedan EGP 2,500 · book 24 h ahead'],
  ['Special Request', 'Celebrations, dietary needs, accessibility'],
  ['Complaint', 'Tell us what went wrong'],
  ['Staff Callback', 'A team member contacts you']
]
const statusBadge = { Open: 'b-amber', 'In Progress': 'b-blue', Resolved: 'b-green', Closed: 'b-grey' }

export default function Requests() {
  const { data, error, reload } = useApi('/me/requests')
  const bookings = useApi('/me/bookings')
  const [type, setType] = useState(null)
  const [text, setText] = useState('')
  const [bookingId, setBookingId] = useState('')
  const [msg, setMsg] = useState(null)
  const [emergency, setEmergency] = useState(false)
  const [eText, setEText] = useState('')

  const active = (bookings.data || []).filter((b) => ['Confirmed', 'Pending'].includes(b.booking_status))

  async function send(e) {
    e.preventDefault()
    try {
      const r = await api('/requests', { method: 'POST', body: { request_type: type, request_text: text, booking_id: bookingId || null } })
      setMsg({ ok: t('Request {id} sent. Our team sees it now.', { id: r.request_id }) })
      setType(null); setText('')
      reload()
    } catch (err) { setMsg({ error: errorText(err) }) }
  }

  async function sendEmergency(e) {
    e.preventDefault()
    try {
      const r = await api('/requests/emergency', { method: 'POST', body: { request_text: eText } })
      setMsg({ ok: t('Emergency reported ({id}). Staff are on their way. Ambulance {a} · Police {p} · Fire {f} · Reception {r}', { id: r.request.request_id, a: r.ambulance, p: r.police, f: r.fire, r: r.reception }) })
      setEmergency(false); setEText('')
      reload()
    } catch (err) { setMsg({ error: errorText(err) }) }
  }

  return (
    <>
      <header><h1 className="title serif">{t('Requests')}</h1><p className="muted" style={{ margin: '6px 0 0' }}>{t('Ask for anything during your stay. Our team sees it right away.')}</p></header>

      <section className="card pad row between" style={{ border: '2px solid var(--red)' }}>
        <div style={{ flex: '1 1 300px' }}>
          <div style={{ fontWeight: 600, color: 'var(--red)', fontSize: 16 }}>{t('Emergency?')}</div>
          <div className="small" style={{ color: 'var(--text-2)', fontSize: 14, marginTop: 4 }}>{t('Ambulance 123 · Police 122 · Fire 180 · Reception 24/7 +20 2 2794 5500')}</div>
        </div>
        <button className="btn danger solid" onClick={() => setEmergency(true)}>{t('Report an emergency')}</button>
      </section>

      {msg?.ok && <div className="ok-box">{msg.ok}</div>}
      {msg?.error && <div className="error-box">{msg.error}</div>}

      <div className="grid" style={{ '--min': '190px', gap: 14 }}>
        {TYPES.map(([name, hint]) => (
          <button key={name} className="card" onClick={() => { setType(name); setMsg(null) }}
            style={{ minHeight: 96, padding: 16, textAlign: 'start', display: 'flex', flexDirection: 'column', gap: 6, color: 'var(--ink)', borderColor: type === name ? 'var(--gold)' : undefined, borderWidth: type === name ? 2 : 1 }}>
            <b style={{ fontSize: 15 }}>{t(name === 'Staff Callback' ? 'Talk to staff' : name)}</b><span className="small muted">{t(hint)}</span>
          </button>
        ))}
      </div>

      {type && (
        <form className="card pad stack" onSubmit={send}>
          <b>{t(type)}</b>
          {active.length > 0 && (
            <label className="field">{t('For booking')}
              <select value={bookingId} onChange={(e) => setBookingId(e.target.value)}>
                <option value="">{t('Not about a booking')}</option>
                {active.map((b) => <option key={b.booking_id} value={b.booking_id}>{b.booking_id} · {t(b.room_type_name)} {b.room_number} · {niceDate(b.check_in)}</option>)}
              </select>
            </label>
          )}
          <label className="field">{t('What do you need?')}<textarea dir="auto" required minLength={3} value={text} onChange={(e) => setText(e.target.value)} /></label>
          <div className="row"><button className="btn primary">{t('Send request')}</button><button type="button" className="btn" onClick={() => setType(null)}>{t('Cancel')}</button></div>
        </form>
      )}

      <section className="stack">
        <h2 className="h2">{t('My requests')}</h2>
        {error && <div className="error-box">{errorText(error)}</div>}
        {(data || []).length === 0 && <div className="card pad muted" style={{ textAlign: 'center', borderStyle: 'dashed' }}>{t('No requests yet. Requests you make here or to Nour show up here with their status.')}</div>}
        {(data || []).map((r) => (
          <div key={r.request_id} className="card pad row between">
            <div style={{ flex: '1 1 300px' }}>
              <b dir="auto">{r.request_text}</b>
              <div className="small muted">{t(r.request_type)} · {r.request_id} · {niceDate(r.created_at)}{r.discount_code ? t(' · your code {code}', { code: r.discount_code }) : ''}</div>
            </div>
            {r.priority !== 'Normal' && <span className={`badge ${r.priority === 'Critical' ? 'b-red' : 'b-amber'}`}>{t(r.priority)}</span>}
            <span className={`badge ${statusBadge[r.request_status] || 'b-grey'}`}>{t(r.request_status)}</span>
          </div>
        ))}
      </section>

      {emergency && (
        <div className="modal-back" role="dialog" aria-label={t('Report an emergency')}>
          <form className="modal" onSubmit={sendEmergency}>
            <h2 style={{ color: 'var(--red)' }}>{t('Report an emergency')}</h2>
            <p className="small" style={{ margin: 0 }}>{t('If someone is in danger, call 123 (ambulance) first. This alerts every member of staff on duty.')}</p>
            <label className="field">{t('What is happening and where?')}<textarea dir="auto" required minLength={3} value={eText} onChange={(e) => setEText(e.target.value)} /></label>
            <div className="row"><button className="btn danger solid">{t('Send emergency alert')}</button><button type="button" className="btn" onClick={() => setEmergency(false)}>{t('Close')}</button></div>
          </form>
        </div>
      )}
    </>
  )
}
