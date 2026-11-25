import { useEffect, useState } from 'react'
import { api, API_URL, USE_MOCK } from '../api/client.js'
import { errorText } from '../hooks.js'
import { t } from '../i18n.jsx'

// Opens the payment page (the fake Paymob of the API, or Paymob itself) in a new tab.
// When the guest comes back to this tab, onPaid() reloads the booking so it shows Confirmed.
export default function PayButton({ bookingId, url, onPaid, label = 'Pay the deposit' }) {
  const [waiting, setWaiting] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!waiting) return undefined
    const back = () => { setWaiting(false); onPaid?.() }
    window.addEventListener('focus', back)
    return () => window.removeEventListener('focus', back)
  }, [waiting, onPaid])

  async function pay() {
    setError(null)
    if (USE_MOCK) {
      try { await api(`/payments/mock/${bookingId}/pay`, { method: 'POST' }); onPaid?.() } catch (e) { setError(e) }
      return
    }
    window.open(url || `${API_URL}/payments/mock/${bookingId}`, '_blank', 'noopener')
    setWaiting(true)
  }

  return (
    <>
      <button type="button" className="btn gold" onClick={pay}>{waiting ? t('Waiting for the payment…') : t(label)}</button>
      {error && <span className="small" style={{ color: 'var(--red)' }}>{errorText(error)}</span>}
    </>
  )
}
