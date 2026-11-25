import { useState } from 'react'
import { egp, errorText, millions, useApi, useHotelToday } from '../../hooks.js'
import { Kpis, PeriodHead } from './Overview.jsx'
import { money, t } from '../../i18n.jsx'

const addDays = (iso, n) => new Date(Date.parse(iso) + n * 86400000).toISOString().slice(0, 10)

function Breakdown({ title, rows, total, showAdr, highlight }) {
  const max = Math.max(1, ...rows.map((r) => r.revenue))
  return (
    <section className="card pad stack">
      <h2 className="h2">{t(title)}</h2>
      {rows.map((r) => (
        <div key={r.name} className="stack" style={{ gap: 5 }}>
          <div className="row between" style={{ fontSize: 14 }}>
            <span>{t(r.name)}</span>
            <span><b>{money(millions(r.revenue))}</b> <span className="muted">· {total ? ((r.revenue / total) * 100).toFixed(1) : 0}% · {showAdr ? `${t('ADR')} ${egp(r.revenue / Math.max(r.room_nights, 1), 0)}` : t('{n} nights', { n: r.room_nights.toLocaleString('en-US') })}</span></span>
          </div>
          <div className="bar-track"><div className="bar-fill" style={{ width: `${(r.revenue / max) * 100}%`, background: highlight === r.name ? 'var(--gold)' : showAdr ? 'var(--teal)' : 'var(--ink)' }} /></div>
        </div>
      ))}
    </section>
  )
}

export default function Revenue() {
  const today = useHotelToday()
  const [days, setDays] = useState(30)
  const { data: s, error } = useApi(today ? '/admin/stats' : null, today ? { query: { date_from: addDays(today, -(days - 1)), date_to: today } } : undefined)

  if (error) return <div className="error-box">{errorText(error)}</div>
  if (!s) return <div className="loading">{t('Loading…')}</div>

  const channels = [...s.by_channel]
  if (!channels.find((c) => c.name === 'Voice Agent')) channels.push({ name: 'Voice Agent', room_nights: 0, revenue: 0 })

  return (
    <>
      <PeriodHead title="Revenue analysis" stats={s} />
      <div className="row">
        {[7, 30, 90, 365].map((d) => <button key={d} className={`chip ${days === d ? 'on' : ''}`} onClick={() => setDays(d)}>{d === 365 ? t('12 months') : t('{n} days', { n: d })}</button>)}
      </div>
      <Kpis s={s} />
      <div className="grid" style={{ '--min': '340px' }}>
        <Breakdown title="By booking channel" rows={channels} total={s.revenue} highlight="Voice Agent" />
        <Breakdown title="By room type" rows={s.by_room_type} total={s.revenue} showAdr />
      </div>
      <p className="small muted" style={{ margin: 0 }}>{t('Revenue is counted per night stayed in the period, after discounts. Voice Agent = bookings made by Nour.')}</p>
    </>
  )
}
