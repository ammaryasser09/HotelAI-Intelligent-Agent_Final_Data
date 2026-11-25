import { useState } from 'react'
import { api } from '../../api/client.js'
import { egp, errorText, niceDate, useApi, useHotelToday } from '../../hooks.js'
import { money, t } from '../../i18n.jsx'

export function StaffHead({ title, today }) {
  return (
    <header className="page-head">
      <div><div className="eyebrow">{today ? niceDate(today, true) : ''}</div><h1 className="title">{t(title)}</h1></div>
    </header>
  )
}

export default function FrontDesk() {
  const today = useHotelToday()
  const arrivals = useApi('/staff/arrivals')
  const inHouse = useApi('/staff/in-house')
  const tickets = useApi('/staff/requests')
  const [tab, setTab] = useState('arr')
  const [q, setQ] = useState('')
  const [msg, setMsg] = useState(null)
  const [busy, setBusy] = useState('')
  const [checkout, setCheckout] = useState(null)
  const [method, setMethod] = useState('Cash')

  const arr = arrivals.data || []
  const house = inHouse.data || []
  const leaving = house.filter((b) => today && b.check_out <= today)
  const occupiedBy = Object.fromEntries(leaving.map((b) => [b.room_number, `${b.first_name} ${b.last_name}`]))
  const urgent = (tickets.data || []).filter((t) => t.priority !== 'Normal').length
  const match = (b) => !q || `${b.first_name} ${b.last_name} ${b.booking_id} ${b.room_number}`.toLowerCase().includes(q.toLowerCase())

  async function act(path, label, body) {
    setBusy(path)
    setMsg(null)
    try {
      const r = await api(path, { method: 'POST', body })
      setMsg({ ok: t('{label}: {id}, room {room}', { label: t(label), id: r.booking_id, room: r.room_number }) + (r.balance_paid ? t(' · collected {amount}', { amount: money(egp(r.balance_paid)) }) : '') + (r.points_earned ? t(' · {n} points earned', { n: r.points_earned }) : '') + (r.new_tier ? t(' · moved up to {tier}', { tier: t(r.new_tier) }) : '') })
      setCheckout(null)
      arrivals.reload(); inHouse.reload()
    } catch (e) { setMsg({ error: errorText(e) }) } finally { setBusy('') }
  }

  return (
    <>
      <header className="page-head">
        <div><div className="eyebrow">{today ? niceDate(today, true) : ''}</div><h1 className="title">{t('Front desk')}</h1></div>
        <label className="field" style={{ flex: '0 1 300px', color: 'var(--muted)', fontSize: 12 }}>{t('Find a guest or booking')}
          <input placeholder={t('Name, B000000 or room')} value={q} onChange={(e) => setQ(e.target.value)} />
        </label>
      </header>

      <div className="grid" style={{ '--min': '170px', gap: 14 }}>
        <div className="card kpi"><div className="label">{t('Arrivals waiting')}</div><div className="value">{arr.length}</div><div className="note">{t('confirmed, not checked in')}</div></div>
        <div className="card kpi"><div className="label">{t('Leaving today')}</div><div className="value">{leaving.length}</div><div className="note">{t('balance to collect at check-out')}</div></div>
        <div className="card kpi"><div className="label">{t('In house')}</div><div className="value">{house.length}</div><div className="note">{t('checked-in stays')}</div></div>
        <div className="card kpi"><div className="label">{t('Open tickets')}</div><div className="value">{tickets.data ? tickets.data.length : '…'}</div><div className="note" style={{ color: 'var(--red)', fontWeight: 600 }}>{t('{n} urgent or critical', { n: urgent })}</div></div>
      </div>

      <div className="row">
        <button className={`chip ${tab === 'arr' ? 'on' : ''}`} onClick={() => setTab('arr')}>{t('Arrivals ({n})', { n: arr.length })}</button>
        <button className={`chip ${tab === 'house' ? 'on' : ''}`} onClick={() => setTab('house')}>{t('In house ({n})', { n: house.length })}</button>
      </div>
      {msg?.ok && <div className="ok-box">{msg.ok}</div>}
      {msg?.error && <div className="error-box">{msg.error}</div>}
      {(arrivals.error || inHouse.error) && <div className="error-box">{errorText(arrivals.error || inHouse.error)}</div>}

      {tab === 'arr' ? (
        <section className="card table-box">
          <table>
            <thead><tr><th>{t('Guest')}</th><th>{t('Booking')}</th><th>{t('Room')}</th><th>{t('Stay')}</th><th>{t('Guests')}</th><th>{t('Balance at hotel (EGP)')}</th><th>{t('Room')}</th><th></th></tr></thead>
            <tbody>
              {arr.filter(match).map((b) => {
                const waitingFor = occupiedBy[b.room_number]
                return (
                  <tr key={b.booking_id}>
                    <td><b>{b.first_name} {b.last_name}</b>{b.check_in < (today || '') && <div className="small" style={{ color: 'var(--amber)' }}>{t('late: due {date}', { date: niceDate(b.check_in, false, false) })}</div>}</td>
                    <td>{b.booking_id}</td><td>{b.room_number} · {t(b.room_type_name)}</td><td>{t('{n} nights', { n: b.nights })}</td>
                    <td>{b.adults}{b.children ? ` + ${b.children}` : ''}</td><td>{b.balance_due ? egp(b.balance_due) : '—'}</td>
                    <td><span className={`badge ${waitingFor ? 'b-amber' : 'b-blue'}`}>{waitingFor ? t('Waiting: {name} leaving', { name: waitingFor }) : t('Ready')}</span></td>
                    <td className="row" style={{ flexWrap: 'nowrap', gap: 6, borderBottom: 0 }}>
                      <button className="btn sm primary" disabled={!!busy} onClick={() => act(`/staff/bookings/${b.booking_id}/check-in`, 'Checked in')}>{t('Check in')}</button>
                      <button className="btn sm" disabled={!!busy} onClick={() => act(`/staff/bookings/${b.booking_id}/no-show`, 'Marked no-show')}>{t('No-show')}</button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          {arr.length === 0 && !arrivals.loading && <div className="pad muted">{t('No arrivals waiting.')}</div>}
        </section>
      ) : (
        <section className="card table-box">
          <table>
            <thead><tr><th>{t('Guest')}</th><th>{t('Booking')}</th><th>{t('Room')}</th><th>{t('Check-out')}</th><th>{t('Balance to collect (EGP)')}</th><th></th></tr></thead>
            <tbody>
              {house.filter(match).map((b) => (
                <tr key={b.booking_id}>
                  <td><b>{b.first_name} {b.last_name}</b></td><td>{b.booking_id}</td><td>{b.room_number} · {t(b.room_type_name)}</td>
                  <td>{b.check_out <= (today || '') ? <span className="badge b-amber">{t('Today')}</span> : niceDate(b.check_out, true, false)}</td>
                  <td style={{ fontWeight: 600 }}>{b.balance_due ? egp(b.balance_due) : t('Paid')}</td>
                  <td><button className="btn sm primary" disabled={!!busy} onClick={() => setCheckout(b)}>{t('Check out')}</button></td>
                </tr>
              ))}
            </tbody>
          </table>
          {house.length === 0 && !inHouse.loading && <div className="pad muted">{t('Nobody is checked in yet.')}</div>}
        </section>
      )}

      {checkout && (
        <div className="modal-back" role="dialog" aria-label={t('Check out')}>
          <div className="modal">
            <h2 className="h2" style={{ fontSize: 20 }}>{t('Check out {name} · room {room}', { name: `${checkout.first_name} ${checkout.last_name}`, room: checkout.room_number })}</h2>
            <div className="note-box" style={{ fontSize: 15 }}>
              <div className="row between"><span>{t('Stay total')}</span><b>{money(egp(checkout.amount_due))}</b></div>
              <div className="row between"><span>{t('Paid online')}</span><b>{money(egp(checkout.amount_paid))}</b></div>
              <div className="row between"><span>{t('Collect now')}</span><b>{money(egp(checkout.balance_due))}</b></div>
            </div>
            {checkout.balance_due > 0 && (
              <label className="field">{t('Paid by')}
                <select value={method} onChange={(e) => setMethod(e.target.value)}>
                  {['Cash', 'Credit Card', 'Debit Card', 'Digital Wallet', 'Bank Transfer'].map((m) => <option key={m} value={m}>{t(m)}</option>)}
                </select>
              </label>
            )}
            <div className="row">
              <button className="btn primary" disabled={!!busy} onClick={() => act(`/staff/bookings/${checkout.booking_id}/check-out`, 'Checked out', { payment_method: method })}>{t('Confirm check-out')}</button>
              <button className="btn" onClick={() => setCheckout(null)}>{t('Cancel')}</button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
