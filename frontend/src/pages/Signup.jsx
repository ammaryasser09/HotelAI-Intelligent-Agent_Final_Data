import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { api } from '../api/client.js'
import { homeFor, useAuth } from '../auth/AuthContext.jsx'
import { errorText } from '../hooks.js'
import { LangToggle, t } from '../i18n.jsx'
import AuthShell from '../components/AuthShell.jsx'

export const strongPassword = (p) => p.length >= 8 && /[A-Za-z]/.test(p) && /\d/.test(p)

export default function Signup() {
  const { account, startSession } = useAuth()
  const navigate = useNavigate()
  const [f, setF] = useState({ first_name: '', last_name: '', email: '', phone: '', password: '', nationality: '' })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  if (account) return <Navigate to={homeFor(account.role)} replace />
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })

  async function submit(e) {
    e.preventDefault()
    if (!strongPassword(f.password)) { setError(new Error('WEAK_PASSWORD')); return }
    setBusy(true)
    setError(null)
    try {
      const res = await api('/auth/signup', { method: 'POST', body: { ...f, nationality: f.nationality || null } })
      startSession(res)
      navigate('/guest')
    } catch (err) { setError(err) } finally { setBusy(false) }
  }

  return (
    <AuthShell onSubmit={submit}>
      <div className="row between"><h2 style={{ fontFamily: 'var(--serif)', fontWeight: 500, fontSize: 30 }}>{t('Create an account')}</h2><LangToggle /></div>
      <p className="muted" style={{ margin: 0 }}>{t('We send a code to your email to confirm it. You can ask Nour questions now; bookings open once the email is confirmed.')}</p>
      <div className="row" style={{ gap: 12 }}>
        <label className="field" style={{ flex: '1 1 150px' }}>{t('First name')}<input required minLength={2} value={f.first_name} onChange={set('first_name')} autoComplete="given-name" /></label>
        <label className="field" style={{ flex: '1 1 150px' }}>{t('Last name')}<input required minLength={2} value={f.last_name} onChange={set('last_name')} autoComplete="family-name" /></label>
      </div>
      <label className="field">{t('Email')}<input type="email" dir="ltr" required value={f.email} onChange={set('email')} autoComplete="email" /></label>
      <label className="field">{t('Phone')}<input type="tel" dir="ltr" required pattern="\+?[0-9 \-]{8,20}" placeholder="+201001234567" value={f.phone} onChange={set('phone')} autoComplete="tel" /></label>
      <label className="field">{t('Nationality (optional)')}<input value={f.nationality} onChange={set('nationality')} /></label>
      <label className="field">{t('Password')}<input type="password" dir="ltr" required value={f.password} onChange={set('password')} autoComplete="new-password" /></label>
      <div className="small muted" style={{ marginTop: -8 }}>{t('At least 8 characters, with a letter and a number.')}</div>
      {error && <div className="error-box">{errorText(error)}</div>}
      <button className="btn primary" disabled={busy}>{t(busy ? 'Creating…' : 'Create an account')}</button>
      <p style={{ margin: 0, fontSize: 14 }}>{t('Already have an account?')} <Link to="/login" style={{ fontWeight: 600 }}>{t('Sign in')}</Link></p>
    </AuthShell>
  )
}
