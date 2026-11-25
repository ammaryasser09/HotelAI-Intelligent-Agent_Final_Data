import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client.js'
import { MicIcon } from './Layout.jsx'
import { t } from '../i18n.jsx'

// The call screen. It opens a call record (POST /calls) so the call shows on the dashboards.
// The voice itself (Gemini Live) is the LLM team's part: plug it into connectVoice() below.
export async function connectVoice(/* callId, onMessage */) {
  return null
}

export default function NourPanel({ onClose }) {
  const [callId, setCallId] = useState(null)
  const [seconds, setSeconds] = useState(0)
  const [text, setText] = useState('')
  const [messages, setMessages] = useState([
    { role: 'agent', content: t('Hello, this is Nour from Nile Pearl Hotel. How can I help you today?') }
  ])
  const timer = useRef(null)

  useEffect(() => {
    api('/calls', { method: 'POST', body: { channel: 'voice' } })
      .then((c) => { setCallId(c.call_id); connectVoice(c.call_id, (m) => setMessages((x) => [...x, m])) })
      .catch(() => setCallId(null))
    timer.current = setInterval(() => setSeconds((s) => s + 1), 1000)
    return () => clearInterval(timer.current)
  }, [])

  function send(e) {
    e.preventDefault()
    if (!text.trim()) return
    setMessages((x) => [...x, { role: 'guest', content: text.trim() }])
    setText('')
  }

  const mm = String(Math.floor(seconds / 60)).padStart(2, '0')
  const ss = String(seconds % 60).padStart(2, '0')

  return (
    <div className="modal-back" role="dialog" aria-label="Call with Nour">
      <div className="modal" style={{ background: 'var(--ink)', color: '#fff' }}>
        <div className="row between">
          <div className="row" style={{ gap: 14 }}>
            <div style={{ width: 56, height: 56, borderRadius: '50%', background: 'var(--gold)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <MicIcon color="#0F2235" size={26} />
            </div>
            <div>
              <div style={{ fontFamily: 'var(--serif)', fontSize: 22 }}>{t('Nour')}</div>
              <div className="small" style={{ color: '#B9B3A5' }}>{t(callId ? 'Listening' : 'Connecting')} · <span className="ltr">{mm}:{ss}</span></div>
            </div>
          </div>
          <button className="btn danger solid pill" onClick={onClose}>{t('End call')}</button>
        </div>
        <div className="stack" style={{ gap: 10 }}>
          {messages.map((m, i) => (
            <div key={i} className="bubble" style={m.role === 'guest'
              ? { alignSelf: 'flex-end', background: 'var(--ink-2)', color: '#fff' }
              : { alignSelf: 'flex-start', background: '#fff', color: 'var(--ink)' }} dir="auto">{m.content}</div>
          ))}
        </div>
        <form className="row" onSubmit={send}>
          <label style={{ flex: 1 }}>
            <span style={{ position: 'absolute', left: -9999 }}>{t('Type a message')}</span>
            <input value={text} onChange={(e) => setText(e.target.value)} placeholder={t('Type instead of talking…')} dir="auto"
              style={{ width: '100%', minHeight: 46, padding: '0 14px', border: 0, borderRadius: 12 }} />
          </label>
          <button className="btn gold">{t('Send')}</button>
        </form>
      </div>
    </div>
  )
}
