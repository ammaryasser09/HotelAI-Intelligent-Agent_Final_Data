import { useState } from 'react'
import { api } from '../api/client.js'
import { useAuth } from '../auth/AuthContext.jsx'
import { errorText } from '../hooks.js'
import { t } from '../i18n.jsx'

export default function VerifyEmailBanner() {
  const { account, startSession } = useAuth()
  const [code, setCode] = useState('')
  const [msg, setMsg] = useState(null)
  const [busy, setBusy] = useState(false)

  if (!account || account.role !== 'Guest' || account.email_verified) return null

  async function verify(e) {
    e.preventDefault()
    setBusy(true)
    setMsg(null)
    try { startSession(await api('/auth/verify-email', { method: 'POST', body: { code: code.trim() } })) } catch (err) { setMsg({ error: errorText(err) }) } finally { setBusy(false) }
  }

  async function resend() {
    setMsg(null)
    try {
      const r = await api('/auth/verify-email/resend', { method: 'POST' })
      setMsg({ ok: t('A new code is on its way. It works for {n} minutes.', { n: r.expires_in_minutes }) })
    } catch (err) { setMsg({ error: errorText(err) }) }
  }

  return (
    <form className="card pad row" onSubmit={verify} style={{ borderColor: 'var(--gold)', borderWidth: 2, background: '#FBF6EA', alignItems: 'flex-end', gap: 12 }}>
      <div style={{ flex: '1 1 280px' }}>
        <b>{t('Confirm your email')}</b>
        <div className="small" style={{ color: 'var(--text-2)', marginTop: 4 }}>{t('We sent a 6-digit code to {email}. Bookings open after you confirm it.', { email: account.email })}</div>
      </div>
      <label className="field" style={{ flex: '0 1 150px' }}>{t('Code')}<input dir="ltr" required inputMode="numeric" pattern="\d{6}" maxLength={6} value={code} onChange={(e) => setCode(e.target.value)} autoComplete="one-time-code" /></label>
      <button className="btn primary" disabled={busy}>{t('Confirm')}</button>
      <button type="button" className="btn" onClick={resend}>{t('Send a new code')}</button>
      {msg?.ok && <div className="ok-box" style={{ flexBasis: '100%' }}>{msg.ok}</div>}
      {msg?.error && <div className="error-box" style={{ flexBasis: '100%' }}>{msg.error}</div>}
    </form>
  )
}
