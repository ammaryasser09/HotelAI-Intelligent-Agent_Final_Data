import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { homeFor, useAuth } from '../auth/AuthContext.jsx'
import { USE_MOCK } from '../api/client.js'
import { demoLogins } from '../api/mock.js'
import { errorText } from '../hooks.js'
import { Logo } from '../components/Layout.jsx'
import { LangToggle, t } from '../i18n.jsx'

export default function Login() {
  const { account, login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  if (account) return <Navigate to={homeFor(account.role)} replace />

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const acc = await login(email, password)
      navigate(homeFor(acc.role))
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-page">
      <div className="login-art">
        <div className="row"><Logo size={40} /><span className="brand-sub" style={{ fontSize: 13 }}>{t('Hotel · Cairo')}</span></div>
        <h1>{t('Nile Pearl Hotel')}</h1>
        <p style={{ margin: 0, color: '#E9E4D8', maxWidth: 460, lineHeight: 1.5 }}>{t('Your stay, your bookings and Nour — our AI concierge who answers in Arabic, English, French and Russian.')}</p>
      </div>
      <div className="login-form">
        <form onSubmit={submit}>
          <div className="row between"><h2 style={{ fontFamily: 'var(--serif)', fontWeight: 500, fontSize: 30 }}>{t('Sign in')}</h2><LangToggle /></div>
          <p className="muted" style={{ margin: 0 }}>{t('Guests, staff and administrators all sign in here.')}</p>
          <label className="field">{t('Email')}<input type="email" dir="ltr" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="username" /></label>
          <label className="field">{t('Password')}<input type="password" dir="ltr" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" /></label>
          <Link to="/forgot-password" className="small" style={{ alignSelf: 'flex-end', marginTop: -6 }}>{t('Forgot your password?')}</Link>
          {error && <div className="error-box">{errorText(error)}</div>}
          <button className="btn primary" disabled={busy}>{t(busy ? 'Signing in…' : 'Sign in')}</button>
          <p style={{ margin: 0, fontSize: 14 }}>{t('New guest?')} <Link to="/signup" style={{ fontWeight: 600 }}>{t('Create an account')}</Link></p>
          <p className="small muted" style={{ margin: 0 }}>{t('Staff or admin who forgot the password: contact the hotel administration.')}</p>
          {USE_MOCK && (
            <div className="demo-box">
              <b>{t('Demo accounts (password NilePearl@2026)')}</b>
              {demoLogins.map((d) => (
                <button type="button" key={d.email} onClick={() => { setEmail(d.email); setPassword(d.password) }}>
                  {t(d.role)}: {d.name} — <span className="ltr">{d.email}</span>
                </button>
              ))}
            </div>
          )}
        </form>
      </div>
    </div>
  )
}
