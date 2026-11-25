import { useState } from 'react'
import { api } from '../api/client.js'
import { egp, errorText, niceDate, useHotelToday } from '../hooks.js'
import { money, t } from '../i18n.jsx'
import PayButton from './PayButton.jsx'

const TYPES = ['Single', 'Double', 'Twin', 'Deluxe', 'Family', 'Suite']

export default function ChangeBooking({ booking, onClose, onChanged }) {
  const today = useHotelToday()
  const [f, setF] = useState({
    check_in: booking.check_in, check_out: booking.check_out, room_type: booking.room_type_name,
    adults: booking.adults, children: booking.children
  })
  const [quote, setQuote] = useState(null)
  const [done, setDone] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const set = (k) => (e) => { setF({ ...f, [k]: e.target.value }); setQuote(null) }
  const changes = () => {
    const c = {}
    if (f.check_in !== booking.check_in) c.check_in = f.check_in
    if (f.check_out !== booking.check_out) c.check_out = f.check_out
    if (f.room_type !== booking.room_type_name) c.room_type = f.room_type
    if (Number(f.adults) !== booking.adults) c.adults = Number(f.adults)
    if (Number(f.children) !== booking.children) c.children = Number(f.children)
    return c
  }

  async function preview(e) {
    e.preventDefault()
    const c = changes()
    if (!Object.keys(c).length) { setError(new Error('NOTHING_TO_CHANGE')); return }
    setBusy(true); setError(null)
    try { setQuote(await api(`/me/bookings/${booking.booking_id}/change`, { query: c })) } catch (err) { setError(err) } finally { setBusy(false) }
  }

  async function confirm() {
    setBusy(true); setError(null)
    try { setDone(await api(`/me/bookings/${booking.booking_id}/change`, { method: 'POST', body: changes() })) } catch (err) { setError(err) } finally { setBusy(false) }
  }

  const row = (label, value) => <div className="row between"><span>{label}</span><b>{value}</b></div>

  return (
    <div className="modal-back" role="dialog" aria-label={t('Change booking')}>
      <div className="modal">
        <h2 style={{ fontSize: 22, fontWeight: 600 }}>{t('Change booking {id}', { id: booking.booking_id })}</h2>
        {done ? (
          <>
            <div className="ok-box">{t('Your booking is changed: {type} room {room}, {from} – {to}.', { type: t(done.room_type), room: done.room_number, from: niceDate(done.check_in), to: niceDate(done.check_out) })}</div>
            <div className="note-box" style={{ fontSize: 14 }}>
              {row(t('New total'), money(egp(done.amount_due)))}
              {done.refund > 0 && row(t('Refund to your card'), money(egp(done.refund)))}
              {done.pay_now > 0 && row(t('To pay now'), money(egp(done.pay_now)))}
              {row(t('Balance at the hotel'), money(egp(done.pay_at_hotel)))}
            </div>
            <div className="row">
              {done.pay_now > 0 && <PayButton bookingId={done.booking_id} url={done.payment_url} onPaid={onChanged} label="Pay now" />}
              <button className="btn primary" onClick={() => { onChanged(); onClose() }}>{t('Done')}</button>
            </div>
          </>
        ) : (
          <form className="stack" onSubmit={preview}>
            <div className="row" style={{ gap: 12 }}>
              <label className="field" style={{ flex: '1 1 150px' }}>{t('Check-in')}<input type="date" min={today || undefined} value={f.check_in} onChange={set('check_in')} required /></label>
              <label className="field" style={{ flex: '1 1 150px' }}>{t('Check-out')}<input type="date" min={f.check_in} value={f.check_out} onChange={set('check_out')} required /></label>
            </div>
            <div className="row" style={{ gap: 12 }}>
              <label className="field" style={{ flex: '1 1 150px' }}>{t('Room type')}
                <select value={f.room_type} onChange={set('room_type')}>{TYPES.map((x) => <option key={x} value={x}>{t(x)}</option>)}</select>
              </label>
              <label className="field" style={{ flex: '0 1 90px' }}>{t('Adults')}<input type="number" min="1" max="4" value={f.adults} onChange={set('adults')} /></label>
              <label className="field" style={{ flex: '0 1 90px' }}>{t('Children')}<input type="number" min="0" max="3" value={f.children} onChange={set('children')} /></label>
            </div>
            {quote && (
              <div className="note-box" style={{ fontSize: 14 }}>
                {row(t('New stay'), `${t(quote.room_type)} · ${niceDate(quote.check_in)} – ${niceDate(quote.check_out)} · ${t('{n} nights', { n: quote.nights })}`)}
                {row(t('Before'), money(egp(booking.amount_due)))}
                {row(t('New total'), money(egp(quote.amount_due)))}
                {quote.discount && row(t('Discount'), `− ${money(egp(quote.discount.amount))}`)}
                {quote.refund > 0 && row(t('Refund to your card'), money(egp(quote.refund)))}
                {quote.pay_now > 0 && row(t('To pay now'), money(egp(quote.pay_now)))}
                {row(t('Balance at the hotel'), money(egp(quote.pay_at_hotel)))}
              </div>
            )}
            {error && <div className="error-box">{errorText(error)}</div>}
            <div className="row">
              {quote
                ? <button type="button" className="btn primary" disabled={busy} onClick={confirm}>{t('Confirm the change')}</button>
                : <button className="btn primary" disabled={busy}>{t(busy ? 'Checking…' : 'See the new price')}</button>}
              <button type="button" className="btn" onClick={onClose}>{t('Cancel')}</button>
            </div>
            <div className="small muted">{t('New dates and extra nights keep your agreed nightly rate; a new room type uses its standard rate.')}</div>
          </form>
        )}
      </div>
    </div>
  )
}
