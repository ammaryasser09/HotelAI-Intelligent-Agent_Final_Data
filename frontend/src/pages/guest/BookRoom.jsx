import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, imageUrl } from '../../api/client.js'
import PayButton from '../../components/PayButton.jsx'
import { egp, errorText, niceDate, useApi, useHotelToday } from '../../hooks.js'
import { money, t } from '../../i18n.jsx'

const addDays = (iso, n) => new Date(Date.parse(iso) + n * 86400000).toISOString().slice(0, 10)

export default function BookRoom() {
  const today = useHotelToday()
  const types = useApi('/room-types')
  const [form, setForm] = useState({ check_in: '', check_out: '', adults: 1, children: 0, discount_code: '', date_of_birth: '' })
  const [needDob, setNeedDob] = useState(false)
  const [results, setResults] = useState(null)
  const [searching, setSearching] = useState(false)
  const [error, setError] = useState(null)
  const [booked, setBooked] = useState(null)
  const [busy, setBusy] = useState('')

  useEffect(() => {
    if (today && !form.check_in) setForm((f) => ({ ...f, check_in: '2026-11-12' >= today ? '2026-11-12' : addDays(today, 7), check_out: '2026-11-12' >= today ? '2026-11-15' : addDays(today, 10) }))
  }, [today]) // eslint-disable-line react-hooks/exhaustive-deps

  async function search(e) {
    e?.preventDefault()
    if (!types.data) return
    setSearching(true)
    setError(null)
    setBooked(null)
    const guests = Number(form.adults) + Number(form.children)
    const rows = await Promise.all(types.data.map(async (t) => {
      try {
        const a = await api('/availability', { query: { room_type: t.room_type_name, check_in: form.check_in, check_out: form.check_out, guests, discount_code: form.discount_code || undefined } })
        return { type: t, a }
      } catch (err) {
        return { type: t, err }
      }
    }))
    const blocking = rows.find((r) => r.err && r.err.message === 'CHECK_IN_IN_THE_PAST')
    if (blocking) setError(blocking.err)
    setResults(rows)
    setSearching(false)
  }

  useEffect(() => { if (types.data && form.check_in) search() }, [types.data, form.check_in === '']) // eslint-disable-line react-hooks/exhaustive-deps

  async function book(roomType, ratePlan) {
    setBusy(roomType + ratePlan)
    setError(null)
    try {
      const r = await api('/bookings', { method: 'POST', body: { room_type: roomType, check_in: form.check_in, check_out: form.check_out, adults: Number(form.adults), children: Number(form.children), rate_plan: ratePlan, discount_code: form.discount_code || null, date_of_birth: form.date_of_birth || null } })
      setBooked(r)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } catch (e) { if (e.message === 'DATE_OF_BIRTH_REQUIRED') setNeedDob(true); setError(e) } finally { setBusy('') }
  }

  const free = results ? results.reduce((n, r) => n + (r.a?.rooms_free || 0), 0) : 0
  const nights = form.check_in && form.check_out ? Math.round((Date.parse(form.check_out) - Date.parse(form.check_in)) / 86400000) : 0
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  return (
    <>
      <header><h1 className="title serif">{t('Book a room')}</h1><p className="muted" style={{ margin: '6px 0 0' }}>{t('Prices in EGP, taxes included, room only.')}</p></header>

      {booked && (
        <section className="card pad stack" style={{ borderColor: 'var(--teal)', borderWidth: 2 }}>
          <div className="row between"><b style={{ fontSize: 17 }}>{t('Booking {id} is held for you', { id: booked.booking_id })}</b><span className={`badge ${booked.booking_status === 'Pending' ? 'b-amber' : 'b-green'}`}>{t(booked.booking_status)}</span></div>
          <div className="small" style={{ color: 'var(--text-2)', fontSize: 14 }}>
            {t('{type} Room · {room}', { type: t(booked.room_type), room: booked.room_number })} · {niceDate(booked.check_in)} – {niceDate(booked.check_out)} · {t(booked.rate_plan)}.{' '}
            {t('Pay {now} now', { now: money(egp(booked.pay_now)) })}{booked.pay_at_hotel ? t(' and {rest} at the hotel', { rest: money(egp(booked.pay_at_hotel)) }) : ''}.{' '}
            {t('The room is held until {date}.', { date: `${niceDate(booked.payment_due_at)} ${booked.payment_due_at?.slice(11, 16) || ''}` })}
          </div>
          <div className="row">
            {booked.booking_status === 'Pending'
              ? <PayButton bookingId={booked.booking_id} url={booked.payment_url} label="Pay now" onPaid={() => api('/me/bookings').then((all) => { const b = all.find((x) => x.booking_id === booked.booking_id); if (b) setBooked({ ...booked, booking_status: b.booking_status }) })} />
              : <span className="badge b-green">{t('Paid — your booking is confirmed')}</span>}
            <Link className="btn" to="/guest/bookings" style={{ display: 'inline-flex', alignItems: 'center', textDecoration: 'none' }}>{t('See my bookings')}</Link>
          </div>
        </section>
      )}

      <form className="card pad row" style={{ alignItems: 'flex-end', gap: 14 }} onSubmit={search}>
        <label className="field" style={{ flex: '1 1 160px' }}>{t('Check-in')}<input type="date" min={today || undefined} value={form.check_in} onChange={set('check_in')} required /></label>
        <label className="field" style={{ flex: '1 1 160px' }}>{t('Check-out')}<input type="date" min={form.check_in || undefined} value={form.check_out} onChange={set('check_out')} required /></label>
        <label className="field" style={{ flex: '0 1 100px' }}>{t('Adults')}<input type="number" min="1" max="4" value={form.adults} onChange={set('adults')} /></label>
        <label className="field" style={{ flex: '0 1 100px' }}>{t('Children')}<input type="number" min="0" max="3" value={form.children} onChange={set('children')} /></label>
        <label className="field" style={{ flex: '1 1 140px' }}>{t('Discount code')}<input dir="ltr" placeholder={t('Optional')} value={form.discount_code} onChange={set('discount_code')} /></label>
        {needDob && <label className="field" style={{ flex: '1 1 170px' }}>{t('Date of birth')}<input type="date" required value={form.date_of_birth} onChange={set('date_of_birth')} /></label>}
        <button className="btn primary" disabled={searching}>{t(searching ? 'Checking…' : 'Check availability')}</button>
      </form>

      {error && <div className="error-box">{errorText(error)}</div>}
      {results && !error && <div style={{ fontSize: 14, color: 'var(--text-2)' }}>{t('{n} nights · ', { n: nights })}<b>{t('{n} rooms free', { n: free })}</b>{t(' for these dates')}</div>}

      <div className="grid" style={{ '--min': '280px' }}>
        {(results || []).map(({ type, a, err }) => {
          const ok = a && a.rooms_free > 0
          return (
            <article key={type.room_type_id} className="card room-card" style={{ opacity: ok ? 1 : 0.6 }}>
              <img src={imageUrl(type.image_nile)} alt={t(type.room_type_name)} />
              <div className="stack" style={{ padding: 18, gap: 10, flex: 1 }}>
                <div className="row between" style={{ alignItems: 'baseline' }}>
                  <span style={{ fontFamily: 'var(--serif)', fontSize: 21 }}>{t(type.room_type_name)}</span>
                  <span className="small muted">{type.capacity === 1 ? t('1 guest · {size} m²', { size: type.size_sqm }) : t('{n} guests · {size} m²', { n: type.capacity, size: type.size_sqm })}</span>
                </div>
                <div className="small" style={{ color: 'var(--text-2)' }}>{t(type.description)}</div>
                {ok ? (
                  <>
                    <div className="grid small" style={{ '--min': '120px', gap: 8 }}>
                      <button type="button" className="card" disabled={!!busy} onClick={() => book(type.room_type_name, 'Flexible')} style={{ padding: 10, textAlign: 'start', borderColor: '#CFC8B8' }}>
                        <div className="muted">{t('Flexible')}</div><b style={{ fontSize: 15 }}>{money(egp(a.flexible.amount_due, 0))}</b>
                        <div className="muted">{t('deposit {amount}', { amount: egp(a.flexible.deposit_now, 0) })}</div>
                        {a.flexible.discount && <div style={{ color: 'var(--teal)' }}>−{egp(a.flexible.discount.amount, 0)} {a.flexible.discount.source}</div>}
                      </button>
                      <button type="button" className="card" disabled={!!busy} onClick={() => book(type.room_type_name, 'Non-refundable')} style={{ padding: 10, textAlign: 'start', borderColor: '#CFC8B8' }}>
                        <div className="muted">{t('Non-refundable')}</div><b style={{ fontSize: 15 }}>{money(egp(a.non_refundable.total, 0))}</b>
                        <div className="muted">{t('15% lower · pay now')}</div>
                      </button>
                    </div>
                    <div className="small" style={{ color: 'var(--teal)', fontWeight: 600, marginTop: 'auto' }}>{a.rooms_free === 1 ? t('1 room left') : t('{n} rooms left', { n: a.rooms_free })}{a.nile_view_free ? t(' · {n} with Nile view', { n: a.nile_view_free }) : ''}{t(' · tap a price to book')}</div>
                  </>
                ) : (
                  <div className="muted" style={{ marginTop: 'auto', fontWeight: 600, fontSize: 14 }}>{err ? (err.message === 'CAPACITY_EXCEEDED' ? (type.capacity === 1 ? t('Fits up to 1 guest') : t('Fits up to {n} guests', { n: type.capacity })) : errorText(err)) : t('Sold out for these dates')}</div>
                )}
              </div>
            </article>
          )
        })}
      </div>
    </>
  )
}
