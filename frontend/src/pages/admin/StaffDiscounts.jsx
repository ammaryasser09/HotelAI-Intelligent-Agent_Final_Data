import { useState } from 'react'
import { api } from '../../api/client.js'
import { useAuth } from '../../auth/AuthContext.jsx'
import { errorText, niceDate, useApi } from '../../hooks.js'
import { t } from '../../i18n.jsx'

function DiscountRequest({ r, onDone }) {
  const [value, setValue] = useState(10)
  const [type, setType] = useState('PERCENTAGE')
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  async function decide(action) {
    setError(null)
    try {
      const res = await api(`/admin/discount-requests/${r.request_id}/${action}`, { method: 'POST', body: action === 'approve' ? { discount_type: type, discount_value: Number(value) } : undefined })
      setResult(res)
      setTimeout(onDone, 2500)
    } catch (e) { setError(e) }
  }

  return (
    <section className="card pad stack" style={{ border: '2px solid var(--gold)' }}>
      <div className="row between"><h2 className="h2">{t('Discount request · {id}', { id: r.request_id })}</h2><span className="small muted">{niceDate(r.created_at)} {r.created_at.slice(11, 16)}</span></div>
      <div style={{ fontSize: 15 }}><b>{r.guest_name}</b> — <span dir="auto">{r.request_text}</span>{r.booking_id ? t(' (booking {id})', { id: r.booking_id }) : ''}</div>
      {result ? (
        <div className={result.decision === 'Approved' ? 'ok-box' : 'error-box'}>
          {result.decision === 'Approved' ? t('Approved — {name} gets code {code} by email, valid until {date}.', { name: r.guest_name, code: result.discount_code, date: niceDate(result.valid_to) }) : t('Rejected — {name} gets an email that the request was not approved.', { name: r.guest_name })}
        </div>
      ) : (
        <div className="row" style={{ alignItems: 'flex-end', gap: 12 }}>
          <label className="field">{t('Type')}<select value={type} onChange={(e) => setType(e.target.value)}><option value="PERCENTAGE">{t('Percentage')}</option><option value="FIXED_AMOUNT">{t('Fixed amount (EGP)')}</option></select></label>
          <label className="field">{t('Value')}<input type="number" min="1" value={value} onChange={(e) => setValue(e.target.value)} style={{ width: 110 }} /></label>
          <button className="btn teal" onClick={() => decide('approve')}>{t('Approve and email a code')}</button>
          <button className="btn danger" onClick={() => decide('reject')}>{t('Reject')}</button>
        </div>
      )}
      {error && <div className="error-box">{errorText(error)}</div>}
    </section>
  )
}

export default function StaffDiscounts() {
  const { account } = useAuth()
  const discounts = useApi('/admin/discount-requests')
  const staff = useApi('/admin/staff')
  const [adding, setAdding] = useState(false)
  const [form, setForm] = useState({ full_name: '', email: '', password: '' })
  const [msg, setMsg] = useState(null)

  async function toggle(p) {
    setMsg(null)
    try {
      const updated = await api(`/admin/staff/${p.account_id}/${p.is_active ? 'disable' : 'enable'}`, { method: 'POST' })
      staff.setData((rows) => rows.map((x) => (x.account_id === p.account_id ? updated : x)))
    } catch (e) { setMsg({ error: errorText(e) }) }
  }

  async function resetPassword(p) {
    const pw = window.prompt(t('New password for {name} (8+ characters with a letter and a number)', { name: p.full_name }))
    if (!pw) return
    try { await api(`/admin/staff/${p.account_id}/password`, { method: 'POST', body: { new_password: pw } }); setMsg({ ok: t('Password changed for {name}.', { name: p.full_name }) }) } catch (e) { setMsg({ error: errorText(e) }) }
  }

  async function add(e) {
    e.preventDefault()
    try {
      const s = await api('/admin/staff', { method: 'POST', body: form })
      staff.setData((rows) => [...rows, s])
      setAdding(false); setForm({ full_name: '', email: '', password: '' })
      setMsg({ ok: t('{name} can now sign in.', { name: s.full_name }) })
    } catch (err) { setMsg({ error: errorText(err) }) }
  }

  return (
    <>
      <header className="page-head"><div><h1 className="title">{t('Staff & discount requests')}</h1></div></header>

      {discounts.error && <div className="error-box">{errorText(discounts.error)}</div>}
      {discounts.data?.length === 0 && <div className="card pad muted">{t('No discount requests waiting. When a guest asks Nour for a discount, it shows here.')}</div>}
      {(discounts.data || []).map((r) => <DiscountRequest key={r.request_id} r={r} onDone={discounts.reload} />)}

      {msg?.ok && <div className="ok-box">{msg.ok}</div>}
      {msg?.error && <div className="error-box">{msg.error}</div>}

      <section className="card table-box">
        <div className="row between" style={{ padding: '16px 20px' }}>
          <h2 className="h2">{t('Staff accounts')}</h2>
          <button className="btn sm primary" onClick={() => setAdding(!adding)}>{t('+ Add staff member')}</button>
        </div>
        {adding && (
          <form className="row" style={{ padding: '0 20px 16px', alignItems: 'flex-end', gap: 12 }} onSubmit={add}>
            <label className="field" style={{ flex: '1 1 180px' }}>{t('Full name')}<input required minLength={3} value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></label>
            <label className="field" style={{ flex: '1 1 220px' }}>{t('Email')}<input required type="email" dir="ltr" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></label>
            <label className="field" style={{ flex: '1 1 160px' }}>{t('First password')}<input dir="ltr" required minLength={8} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></label>
            <button className="btn primary">{t('Create account')}</button>
          </form>
        )}
        {(staff.data || []).map((p) => (
          <div key={p.account_id} className="row" style={{ gap: '8px 18px', padding: '12px 20px', borderTop: '1px solid var(--line-2)', fontSize: 14 }}>
            <span style={{ flex: '1 1 170px' }}><b>{p.full_name}</b></span>
            <span className="muted" style={{ flex: '0 0 70px' }}>{t(p.role)}</span>
            <span style={{ flex: '1 1 240px', color: 'var(--text-2)' }} className="ltr">{p.email}</span>
            <span className="small muted" style={{ flex: '0 0 130px' }}>{p.last_login_at ? t('Last in {date}', { date: niceDate(p.last_login_at, false, false) }) : t('Never signed in')}</span>
            <span className={`badge ${p.is_active ? 'b-green' : 'b-grey'}`}>{t(p.is_active ? 'Active' : 'Disabled')}</span>
            <button className="btn sm" onClick={() => resetPassword(p)}>{t('Reset password')}</button>
            {p.account_id !== account.account_id && <button className="btn sm" onClick={() => toggle(p)}>{t(p.is_active ? 'Disable' : 'Enable')}</button>}
          </div>
        ))}
      </section>
    </>
  )
}
