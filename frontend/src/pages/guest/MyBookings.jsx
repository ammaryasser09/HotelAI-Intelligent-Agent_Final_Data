import { useState } from 'react'
import { api } from '../../api/client.js'
import ChangeBooking from '../../components/ChangeBooking.jsx'
import PayButton from '../../components/PayButton.jsx'
import { egp, errorText, niceDate, stayRange, useApi, useHotelToday } from '../../hooks.js'
import { money, t } from '../../i18n.jsx'
import { freeCancelUntil, roomImage } from './GuestHome.jsx'

const statusBadge = { Confirmed: 'b-green', Pending: 'b-amber', Completed: 'b-grey', Cancelled: 'b-grey', 'No-show': 'b-grey' }

export default function MyBookings() {
  const today = useHotelToday() || ''
  const { data, error, loading, reload } = useApi('/me/bookings')
  const [tab, setTab] = useState('up')
  const [quote, setQuote] = useState(null)
  const [changing, setChanging] = useState(null)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)
  const [showLink, setShowLink] = useState(false)
  const [link, setLink] = useState({ booking_ref: '', proof: '' })

  const all = data || []
  const isUp = (b) => ['Confirmed', 'Pending'].includes(b.booking_status) && b.check_out > today
  const up = all.filter(isUp).sort((a, b) => a.check_in.localeCompare(b.check_in))
  const past = all.filter((b) => !isUp(b)).sort((a, b) => b.check_in.localeCompare(a.check_in))
  const list = tab === 'up' ? up : past

  async function askCancel(b) {
    setMsg(null)
    try { setQuote(await api(`/me/bookings/${b.booking_id}/cancellation`)) } catch (e) { setMsg({ error: errorText(e) }) }
  }

  async function confirmCancel() {
    setBusy(true)
    try {
      const r = await api(`/me/bookings/${quote.booking_id}/cancel`, { method: 'POST' })
      setMsg({ ok: t('Booking {id} is cancelled.', { id: r.booking_id }) + (r.refund ? t(' {amount} goes back to your card.', { amount: money(egp(r.refund)) }) : '') })
      setQuote(null)
      reload()
    } catch (e) { setMsg({ error: errorText(e) }) } finally { setBusy(false) }
  }

  async function linkBooking(e) {
    e.preventDefault()
    const proof = link.proof.trim()
    const body = { booking_ref: link.booking_ref.trim().toUpperCase(), ...(/^\d{4}$/.test(proof) ? { phone_last4: proof } : { last_name: proof }) }
    try {
      await api('/me/bookings/link', { method: 'POST', body })
      setMsg({ ok: t('Booking {id} was added to your account.', { id: body.booking_ref }) })
      setShowLink(false)
      reload()
    } catch (err) { setMsg({ error: errorText(err) }) }
  }

  function payLine(b) {
    if (b.booking_status === 'Pending') return t('Payment due by {date}', { date: `${niceDate(b.payment_due_at)} ${b.payment_due_at?.slice(11, 16) || ''}` })
    if (b.booking_status === 'Completed') return t('Paid in full')
    if (b.refund_amount) return t('Refunded {amount}', { amount: money(egp(b.refund_amount)) })
    return t('Paid {paid} · {rest} at the hotel', { paid: money(egp(b.amount_paid)), rest: money(egp(b.amount_due - (b.amount_paid || 0))) })
  }

  function policy(b) {
    const until = freeCancelUntil(b)
    const outside = b.access === 'linked' ? t('Made outside our website: changes are made where you booked. ') : ''
    if (!until) return outside + t('Non-refundable rate: it can’t be changed, and nothing is refunded.')
    if (until >= today) return outside + t('Free changes and cancellation until {date}, 3:00 PM.', { date: niceDate(until, true, false) })
    return outside + t('The free-cancellation time has passed: the deposit would be kept.')
  }

  return (
    <>
      <header className="page-head">
        <div><h1 className="title serif">{t('My bookings')}</h1><p className="muted" style={{ margin: '6px 0 0' }}>{t('{up} upcoming · {past} past', { up: up.length, past: past.length })}</p></div>
        <button className="btn" onClick={() => setShowLink(!showLink)}>{t('+ Add a booking made elsewhere')}</button>
      </header>

      {showLink && (
        <form className="card pad row" style={{ alignItems: 'flex-end', gap: 14 }} onSubmit={linkBooking}>
          <label className="field" style={{ flex: '1 1 180px' }}>{t('Booking reference')}<input required dir="ltr" placeholder="B000000" value={link.booking_ref} onChange={(e) => setLink({ ...link, booking_ref: e.target.value })} /></label>
          <label className="field" style={{ flex: '1 1 220px' }}>{t('Last name or last 4 phone digits')}<input required value={link.proof} onChange={(e) => setLink({ ...link, proof: e.target.value })} /></label>
          <button className="btn primary">{t('Link booking')}</button>
          <div className="small muted" style={{ flexBasis: '100%' }}>{t('For bookings made by phone, a travel agent or a booking website.')}</div>
        </form>
      )}
      {msg?.ok && <div className="ok-box">{msg.ok}</div>}
      {msg?.error && <div className="error-box">{msg.error}</div>}

      <div className="row">
        <button className={`chip ${tab === 'up' ? 'on' : ''}`} onClick={() => setTab('up')}>{t('Upcoming ({n})', { n: up.length })}</button>
        <button className={`chip ${tab === 'past' ? 'on' : ''}`} onClick={() => setTab('past')}>{t('Past & cancelled ({n})', { n: past.length })}</button>
      </div>

      {loading && !data && <div className="loading">{t('Loading your bookings…')}</div>}
      {error && <div className="error-box">{errorText(error)}</div>}

      <div className="stack">
        {list.map((b) => (
          <article key={b.booking_id} className="card booking-card">
            <img src={roomImage(b.room_type_name, b.view)} alt={t(b.room_type_name)} />
            <div className="body">
              <div className="row between">
                <div className="serif-name">{t('{type} Room · {room}', { type: t(b.room_type_name), room: b.room_number })}</div>
                <span className={`badge ${statusBadge[b.booking_status] || 'b-grey'}`}>{t(b.booking_status)}</span>
              </div>
              <div className="row" style={{ gap: '8px 22px', fontSize: 14, color: 'var(--text-2)' }}>
                <span>{stayRange(b.check_in, b.check_out)}</span><span>{t('{n} nights', { n: b.nights })}</span><span>{b.booking_id}</span><span>{t(b.rate_plan)}</span><span>{t('{view} view', { view: t(b.view) })}</span>
              </div>
              <div className="row" style={{ gap: '8px 22px', fontSize: 14 }}>
                <span>{t('Total {amount}', { amount: '' })}<b>{money(egp(b.amount_due))}</b></span>
                <span style={{ color: 'var(--text-2)' }}>{payLine(b)}</span>
              </div>
              {isUp(b) && (
                <>
                  <div className="note-box">{policy(b)}</div>
                  <div className="row">
                    {b.booking_status === 'Pending' && <PayButton bookingId={b.booking_id} onPaid={reload} label={b.rate_plan === 'Flexible' ? 'Pay the deposit' : 'Pay now'} />}
                    {b.rate_plan === 'Flexible' && b.access !== 'linked' && freeCancelUntil(b) >= today && <button className="btn" onClick={() => setChanging(b)}>{t('Change dates or room')}</button>}
                    <button className="btn danger" onClick={() => askCancel(b)}>{t('Cancel booking')}</button>
                  </div>
                </>
              )}
            </div>
          </article>
        ))}
        {!loading && list.length === 0 && <div className="card pad muted" style={{ textAlign: 'center' }}>{t('Nothing here yet.')}</div>}
      </div>

      {changing && <ChangeBooking booking={changing} onClose={() => setChanging(null)} onChanged={reload} />}

      {quote && (
        <div className="modal-back" role="dialog" aria-label={t('Cancel booking')}>
          <div className="modal">
            <h2 style={{ fontFamily: 'var(--serif)', fontWeight: 500, fontSize: 22 }}>{t('Cancel {id}?', { id: quote.booking_id })}</h2>
            <p style={{ margin: 0, fontSize: 14, lineHeight: 1.7, color: 'var(--text-2)' }}>
              {quote.is_free
                ? t('You are inside the free-cancellation time, so everything you paid comes back. Refunds take up to 3 business days, then 7–14 business days to show on your card.')
                : quote.rate_plan === 'Non-refundable' ? t('This is a non-refundable booking, so nothing is refunded.') : t('The free-cancellation time has passed, so the hotel keeps the first-night deposit. Nothing more is charged.')}
            </p>
            <div className="note-box" style={{ fontSize: 15 }}>
              <div className="row between"><span>{t('Refund to your card')}</span><b>{money(egp(quote.refund))}</b></div>
              {quote.charge > 0 && <div className="row between"><span>{t('Kept by the hotel')}</span><b>{money(egp(quote.charge))}</b></div>}
            </div>
            <div className="row">
              <button className="btn danger solid" disabled={busy} onClick={confirmCancel}>{t('Yes, cancel it')}</button>
              <button className="btn" onClick={() => setQuote(null)}>{t('Keep my booking')}</button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
