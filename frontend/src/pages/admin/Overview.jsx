import { Link } from 'react-router-dom'
import { egp, errorText, millions, niceDate, useApi, useHotelToday } from '../../hooks.js'
import { money, months as monthNames, t } from '../../i18n.jsx'


export function PeriodHead({ title, stats }) {
  return (
    <header className="page-head">
      <div>
        <div className="eyebrow">{stats ? t('{from} – {to} · {n} rooms in service', { from: niceDate(stats.date_from, false, false), to: niceDate(stats.date_to), n: stats.rooms }) : t('Loading…')}</div>
        <h1 className="title">{t(title)}</h1>
      </div>
    </header>
  )
}

export function Kpis({ s }) {
  return (
    <div className="grid" style={{ '--min': '170px', gap: 14 }}>
      <div className="card kpi dark"><div className="label">{t('Room revenue')}</div><div className="value">{money(millions(s.revenue))}</div><div className="note">{t('{n} room nights sold', { n: s.room_nights_sold.toLocaleString('en-US') })}</div></div>
      <div className="card kpi"><div className="label">{t('Occupancy')}</div><div className="value">{(s.occupancy * 100).toFixed(1)}%</div><div className="note">{t('of available room nights')}</div></div>
      <div className="card kpi"><div className="label">{t('ADR')}</div><div className="value">{money(egp(s.adr, 0))}</div><div className="note">{t('average rate per sold night')}</div></div>
      <div className="card kpi"><div className="label">{t('RevPAR')}</div><div className="value">{money(egp(s.revpar, 0))}</div><div className="note">{t('revenue per available room')}</div></div>
      <div className="card kpi"><div className="label">{t('Cancellation rate')}</div><div className="value">{(s.cancellation_rate * 100).toFixed(1)}%</div><div className="note">{t('of stays arriving in the period')}</div></div>
    </div>
  )
}

export default function Overview() {
  const today = useHotelToday()
  const month = useApi('/admin/stats')
  const year = useApi(today ? '/admin/stats' : null, today ? { query: { date_from: monthStartYearAgo(today), date_to: monthEnd(today) } } : undefined)
  const discounts = useApi('/admin/discount-requests')
  const calls = useApi('/admin/calls')
  const s = month.data

  const months = []
  for (const d of year.data?.daily || []) {
    const key = d.day.slice(0, 7)
    let m = months.find((x) => x.key === key)
    if (!m) months.push((m = { key, revenue: 0, sold: 0, days: 0 }))
    m.revenue += d.revenue; m.sold += d.rooms_sold; m.days += 1
  }
  const max = Math.max(1, ...months.map((m) => m.revenue))
  const rooms = year.data?.rooms || 1
  const waitingPay = (calls.data || []).filter((c) => /New booking/.test(c.summary || '')).length
  const urgent = s ? Object.entries(s.open_tickets).filter(([p]) => p !== 'Normal').reduce((n, [, v]) => n + v, 0) : 0
  const openAll = s ? Object.values(s.open_tickets).reduce((a, b) => a + b, 0) : 0

  if (month.error) return <div className="error-box">{errorText(month.error)}</div>
  if (!s) return <div className="loading">{t('Loading…')}</div>

  return (
    <>
      <PeriodHead title="Overview" stats={s} />
      <Kpis s={s} />

      <section className="card pad stack">
        <div className="row between"><h2 className="h2">{t('Room revenue by month')}</h2><span className="small muted">{t('EGP millions · occupancy under each bar · the current month includes nights already booked')}</span></div>
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 10, height: 250, overflowX: 'auto', paddingTop: 10 }}>
          {months.map((m) => {
            const [y, mo] = m.key.split('-').map(Number)
            const current = today && m.key === today.slice(0, 7)
            return (
              <div key={m.key} style={{ flex: '1 0 44px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-end', gap: 6, height: '100%' }}>
                <span className="small" style={{ fontWeight: 600 }}>{(m.revenue / 1e6).toFixed(1)}</span>
                <div title={`${monthNames()[mo - 1]} ${y}: ${money(egp(m.revenue, 0))}`} style={{ width: '100%', maxWidth: 46, height: Math.round((m.revenue / max) * 170), borderRadius: '6px 6px 0 0', background: current ? 'var(--gold)' : 'var(--teal)' }} />
                <span className="small" style={{ color: 'var(--text-2)' }}>{monthNames()[mo - 1]}</span>
                <span style={{ fontSize: 11 }} className="muted">{Math.round((m.sold / (rooms * m.days)) * 100)}%</span>
              </div>
            )
          })}
          {year.loading && <div className="muted">{t('Loading 12 months…')}</div>}
        </div>
      </section>

      <div className="grid" style={{ '--min': '320px' }}>
        <section className="card pad stack">
          <h2 className="h2">{t('Needs your attention')}</h2>
          <Link to="/admin/staff" className="card" style={{ padding: '10px 14px', borderColor: 'var(--gold)', background: '#FBF6EA', color: 'var(--ink)', textDecoration: 'none' }}>
            <b>{discounts.data?.length === 1 ? t('1 discount request waiting') : t('{n} discount requests waiting', { n: discounts.data ? discounts.data.length : '…' })}</b>
            <div className="small muted">{discounts.data?.[0] ? `${discounts.data[0].guest_name} · ${discounts.data[0].request_text}` : t('Nothing waiting')}</div>
          </Link>
          <Link to="/staff/tickets" className="card" style={{ padding: '10px 14px', borderColor: '#E8C4BC', background: '#FBEEEB', color: 'var(--ink)', textDecoration: 'none' }}>
            <b style={{ color: 'var(--red)' }}>{t('{n} urgent or critical tickets open', { n: urgent })}</b>
            <div className="small muted">{t('{n} open in total', { n: openAll })}</div>
          </Link>
          <Link to="/admin/nour" className="card" style={{ padding: '10px 14px', color: 'var(--ink)', textDecoration: 'none' }}>
            <b>{t('{n} bookings made by Nour', { n: waitingPay })}</b>
            <div className="small muted">{t('See every conversation of the AI agent')}</div>
          </Link>
        </section>
        <section className="card pad stack">
          <h2 className="h2">{t('Bookings in the period')}</h2>
          <div className="row between" style={{ fontSize: 14 }}><span>{t('Made in the period')}</span><b>{s.bookings_made}</b></div>
          <div className="row between" style={{ fontSize: 14 }}><span>{t('Cancellation rate')}</span><b>{(s.cancellation_rate * 100).toFixed(1)}%</b></div>
          <div className="row between" style={{ fontSize: 14 }}><span>{t('Top channel')}</span><b>{t(s.by_channel[0]?.name || '—')}</b></div>
          <div className="row between" style={{ fontSize: 14 }}><span>{t('Top room type')}</span><b>{t(s.by_room_type[0]?.name || '—')}</b></div>
          <Link to="/admin/revenue" className="btn" style={{ marginTop: 'auto', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', textDecoration: 'none' }}>{t('Revenue analysis')}</Link>
        </section>
      </div>
    </>
  )
}

function monthStartYearAgo(today) {
  const [y, m] = today.split('-').map(Number)
  const d = new Date(Date.UTC(y, m - 12, 1))
  return d.toISOString().slice(0, 10)
}

function monthEnd(today) {
  const [y, m] = today.split('-').map(Number)
  const end = new Date(Date.UTC(y, m, 0)).toISOString().slice(0, 10)
  const start = monthStartYearAgo(today)
  return (Date.parse(end) - Date.parse(start)) / 86400000 + 1 > 366 ? new Date(Date.parse(start) + 365 * 86400000).toISOString().slice(0, 10) : end
}
