import { egp, errorText, useApi } from '../../hooks.js'
import { money, t } from '../../i18n.jsx'

const TIERS = [
  ['Standard', 'From 0 nights a year', 'Member rate 15% off the Flexible rate'],
  ['Silver', '10 nights a year', 'Member rate · late check-out until 1:00 PM · 20% bonus points'],
  ['Gold', '25 nights a year', 'Late check-out until 2:00 PM · room upgrade on arrival · 10% off spa · 50% bonus points'],
  ['Platinum', '50 nights a year', 'Late check-out until 4:00 PM · free breakfast for two · Suite upgrades · 15% off spa · double points']
]

export default function Rewards() {
  const { data: l, error, loading } = useApi('/me/loyalty')
  if (loading && !l) return <div className="loading">{t('Loading…')}</div>
  if (error) return <div className="error-box">{errorText(error)}</div>

  return (
    <>
      <header><h1 className="title serif">{t('Nile Pearl Rewards')}</h1>
        <p className="muted" style={{ margin: '6px 0 0' }}>{l.member ? t('{tier} member · {n} stays', { tier: t(l.tier), n: l.total_stays }) : t('Join at the front desk or ask Nour.')}</p></header>
      {l.member && (
        <div className="grid" style={{ '--min': '200px' }}>
          <div className="card kpi dark"><div className="label">{t('Points')}</div><div className="value" style={{ fontFamily: 'var(--serif)', fontWeight: 500, fontSize: 36 }}>{l.points_balance.toLocaleString('en-US')}</div></div>
          <div className="card kpi"><div className="label">{t('Can redeem')}</div><div className="value" style={{ fontFamily: 'var(--serif)', fontWeight: 500, fontSize: 36 }}>{money(egp(l.points_worth_egp, 0))}</div></div>
          <div className="card kpi"><div className="label">{t('Late check-out')}</div><div className="value" style={{ fontFamily: 'var(--serif)', fontWeight: 500, fontSize: 36 }}>{l.late_checkout_until || '12:00'}</div></div>
        </div>
      )}
      <div className="grid" style={{ '--min': '220px' }}>
        {TIERS.map(([name, need, perks]) => (
          <div key={name} className="card stack" style={{ padding: 20, gap: 8, border: l.tier === name ? '2px solid var(--gold)' : undefined }}>
            <div className="row between"><b style={{ fontSize: 17 }}>{t(name)}</b>{l.tier === name && <span className="small" style={{ fontWeight: 600, color: 'var(--gold-text)' }}>{t('YOUR TIER')}</span>}</div>
            <div className="small muted">{t(need)}</div>
            <div style={{ fontSize: 14, color: 'var(--text-2)', lineHeight: 1.5 }}>{t(perks)}</div>
          </div>
        ))}
      </div>
      <div className="small muted">{t('1 point for every EGP 10 spent on rooms and hotel services · 1,000 points = EGP 500 off · points expire after 24 months without activity.')}</div>
    </>
  )
}
