import { Link, useOutletContext } from 'react-router-dom'
import { useAuth } from '../../auth/AuthContext.jsx'
import { imageUrl } from '../../api/client.js'
import { daysBetween, egp, niceDate, useApi, useHotelToday } from '../../hooks.js'
import { MicIcon } from '../../components/Layout.jsx'
import { money, t } from '../../i18n.jsx'

export const roomImage = (type, view) => imageUrl(`/static/rooms/${type.toLowerCase()}${view === 'City' && type !== 'Suite' ? '_city' : ''}.webp`)

export function freeCancelUntil(b) {
  if (b.rate_plan !== 'Flexible') return null
  const d = new Date(Date.parse(b.check_in + 'T15:00:00Z') - 48 * 3600000)
  return d.toISOString().slice(0, 10)
}

export const guestsText = (adults, children) =>
  (adults === 1 ? t('1 adult') : t('{n} adults', { n: adults })) + (children ? ` · ${t('{n} child', { n: children })}` : '')

const linkBtn = { display: 'inline-flex', alignItems: 'center', justifyContent: 'center', textDecoration: 'none' }

export default function GuestHome() {
  const { account } = useAuth()
  const { openNour } = useOutletContext()
  const today = useHotelToday()
  const bookings = useApi('/me/bookings')
  const loyalty = useApi('/me/loyalty')

  const upcoming = (bookings.data || [])
    .filter((b) => ['Confirmed', 'Pending'].includes(b.booking_status) && b.check_out > (today || ''))
    .sort((a, b) => a.check_in.localeCompare(b.check_in))
  const next = upcoming[0]
  const firstName = account.full_name.split(' ')[0]
  const days = next && today ? daysBetween(today, next.check_in) : null
  const inStay = next && today && next.check_in <= today
  const cancelUntil = next && freeCancelUntil(next)
  const balance = next ? next.amount_due - (next.amount_paid || 0) : 0
  const l = loyalty.data
  const type = next ? t(next.room_type_name) : ''

  let lead = t('Plan your next stay on the Nile. ')
  if (next && inStay) lead = t('Enjoy your stay in room {room}. ', { room: next.room_number })
  else if (next) lead = days === 0 ? t('Your {type} room is ready for you today. ', { type }) : days === 1 ? t('Your {type} room is ready for you tomorrow. ', { type }) : t('Your {type} room is ready for you in {days} days. ', { type, days })

  return (
    <>
      <section className="hero">
        <div className="small" style={{ letterSpacing: '.12em', textTransform: 'uppercase', color: '#E2C98F' }}>{today ? niceDate(today, true) : ''}</div>
        <h1>{t('Welcome back, {name}', { name: firstName })}</h1>
        <p>{lead}{t('Ask Nour anything — in Arabic, English, French or Russian.')}</p>
        <div className="row" style={{ marginTop: 8 }}>
          <button className="btn gold pill" onClick={openNour}><MicIcon color="#0F2235" size={18} /> {t('Call Nour now')}</button>
          <Link className="btn pill" to="/guest/book" style={{ ...linkBtn, background: 'transparent', color: '#fff', borderColor: 'rgba(255,255,255,.6)' }}>{t('Book another stay')}</Link>
        </div>
      </section>

      <div className="grid" style={{ '--min': '320px' }}>
        {next ? (
          <section className="card booking-card">
            <img src={roomImage(next.room_type_name, next.view)} alt={type} />
            <div className="body">
              <div className="row between">
                <span className="small muted" style={{ letterSpacing: '.1em', textTransform: 'uppercase' }}>{t(inStay ? 'Your stay' : 'Your next stay')}</span>
                <span className={`badge ${next.booking_status === 'Pending' ? 'b-amber' : 'b-green'}`}>{t(next.booking_status)}</span>
              </div>
              <div className="serif-name" style={{ fontSize: 26 }}>{t('{type} Room · {room}', { type, room: next.room_number })}</div>
              <div className="grid" style={{ '--min': '140px', gap: 12, fontSize: 14 }}>
                <div><div className="small muted">{t('Check-in')}</div><b>{niceDate(next.check_in, true, false)} · {t('3:00 PM')}</b></div>
                <div><div className="small muted">{t('Check-out')}</div><b>{niceDate(next.check_out, true, false)} · {t('12:00 PM')}</b></div>
                <div><div className="small muted">{t('Guests')}</div><b>{guestsText(next.adults, next.children)} · {t('{n} nights', { n: next.nights })}</b></div>
                <div><div className="small muted">{t('Reference')}</div><b>{next.booking_id}</b></div>
              </div>
              <div className="note-box" style={{ fontSize: 14 }}>
                <div className="row between"><span>{t(next.rate_plan === 'Flexible' ? 'Deposit paid online' : 'Paid online')}</span><b>{money(egp(next.amount_paid))}</b></div>
                <div className="row between"><span>{t('Balance at the hotel')}</span><b>{money(egp(balance))}</b></div>
              </div>
              {cancelUntil && today && cancelUntil >= today && (
                <div className="warn-box">{cancelUntil === today ? t('Free cancellation ends today at 3:00 PM.') : t('Free cancellation until {date} at 3:00 PM.', { date: niceDate(cancelUntil, true, false) })}</div>
              )}
            </div>
          </section>
        ) : (
          <section className="card pad stack">
            <div className="serif-name">{t('No upcoming stay')}</div>
            <p className="muted" style={{ margin: 0 }}>{t('Book a room and it will show here.')}</p>
            <Link className="btn primary" to="/guest/book" style={linkBtn}>{t('Book a room')}</Link>
          </section>
        )}

        {l?.member && (
          <section className="card pad stack">
            <div className="small muted" style={{ letterSpacing: '.1em', textTransform: 'uppercase' }}>{t('Nile Pearl Rewards')}</div>
            <div className="row" style={{ alignItems: 'baseline' }}><span style={{ fontFamily: 'var(--serif)', fontSize: 40 }}>{l.points_balance.toLocaleString('en-US')}</span><span className="muted">{t('points')}</span></div>
            <div style={{ fontSize: 14 }}>{t('Worth {amount} off your next bill.', { amount: money(egp(l.points_worth_egp, 0)) })}</div>
            <div className="row between small"><b style={{ color: 'var(--gold-text)' }}>{t(l.tier)}</b><span className="muted">{t('{n} stays', { n: l.total_stays })}</span></div>
            {l.late_checkout_until && <div className="small" style={{ color: 'var(--text-2)' }}>{t('Your {tier} perk: late check-out until {time}.', { tier: t(l.tier), time: l.late_checkout_until })}</div>}
            <Link className="btn" to="/guest/rewards" style={{ ...linkBtn, marginTop: 'auto' }}>{t('View rewards')}</Link>
          </section>
        )}
      </div>

      <section className="stack">
        <h2 style={{ fontFamily: 'var(--serif)', fontWeight: 500, fontSize: 24 }}>{t('During your stay')}</h2>
        <div className="grid" style={{ '--min': '220px' }}>
          {[['spa', 'Spa', '60-minute massage · EGP 3,500'], ['pool', 'Swimming Pool', 'Free for hotel guests'], ['restaurant', 'Breakfast buffet', '7:00–10:30 · EGP 1,200 per adult']].map(([img, name, info]) => (
            <div key={img} className="card" style={{ overflow: 'hidden' }}>
              <img src={imageUrl(`/static/hotel/${img}.webp`)} alt={t(name)} style={{ width: '100%', height: 140, objectFit: 'cover', display: 'block' }} />
              <div style={{ padding: '14px 16px', fontSize: 14 }}><b>{t(name)}</b><div className="muted">{t(info)}</div></div>
            </div>
          ))}
        </div>
      </section>
    </>
  )
}
