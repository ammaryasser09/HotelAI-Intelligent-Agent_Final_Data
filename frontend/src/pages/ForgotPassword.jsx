import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client.js'
import { homeFor, useAuth } from '../auth/AuthContext.jsx'
import { errorText } from '../hooks.js'
import { LangToggle, t } from '../i18n.jsx'
import AuthShell from '../components/AuthShell.jsx'
import { strongPassword } from './Signup.jsx'

export default function ForgotPassword() {
  const { startSession } = useAuth()
  const navigate = useNavigate()
  const [step, setStep] = useState(1)
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [password, setPassword] = useState('')
  const [minutes, setMinutes] = useState(10)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setError(null)
    if (step === 1 && /@nilepearlhotel\.example$/i.test(email.trim())) { setError(new Error('STAFF_RESET_BY_ADMIN')); return }
    if (step === 2 && !strongPassword(password)) { setError(new Error('WEAK_PASSWORD')); return }
    setBusy(true)
    try {
      if (step === 1) {
        const r = await api('/auth/forgot-password', { method: 'POST', body: { email: email.trim() } })
        setMinutes(r.expires_in_minutes)
        setStep(2)
      } else {
        const res = await api('/auth/reset-password', { method: 'POST', body: { email: email.trim(), code: code.trim(), new_password: password } })
        navigate(homeFor(startSession(res).role))
      }
    } catch (err) { setError(err) } finally { setBusy(false) }
  }

  return (
    <AuthShell onSubmit={submit}>
      <div className="row between"><h2 style={{ fontFamily: 'var(--serif)', fontWeight: 500, fontSize: 30 }}>{t('Reset your password')}</h2><LangToggle /></div>
      {step === 1 ? (
        <>
          <p className="muted" style={{ margin: 0 }}>{t('Write the email of your account and we send you a 6-digit code.')}</p>
          <label className="field">{t('Email')}<input type="email" dir="ltr" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" /></label>
        </>
      ) : (
        <>
          <div className="ok-box">{t('If {email} has a guest account, a code is on its way. It works for {n} minutes.', { email, n: minutes })}</div>
          <label className="field">{t('Code from the email')}<input dir="ltr" required inputMode="numeric" pattern="\d{6}" maxLength={6} value={code} onChange={(e) => setCode(e.target.value)} autoComplete="one-time-code" /></label>
          <label className="field">{t('New password')}<input type="password" dir="ltr" required value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" /></label>
          <div className="small muted" style={{ marginTop: -8 }}>{t('At least 8 characters, with a letter and a number.')}</div>
        </>
      )}
      {error && <div className="error-box">{errorText(error)}</div>}
      <button className="btn primary" disabled={busy}>{t(step === 1 ? 'Send the code' : 'Save the new password')}</button>
      {step === 2 && <button type="button" className="link-btn" style={{ color: 'var(--teal)', padding: 0 }} onClick={() => setStep(1)}>{t('Use another email or send the code again')}</button>}
      <p className="small muted" style={{ margin: 0 }}>{t('Staff or admin who forgot the password: contact the hotel administration.')}</p>
      <Link to="/login" style={{ fontSize: 14, fontWeight: 600 }}>{t('Back to sign in')}</Link>
    </AuthShell>
  )
}
