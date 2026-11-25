import { useEffect, useRef, useState } from 'react'
import { staffSocketUrl, USE_MOCK } from '../../api/client.js'
import { errorText, niceTime, useApi } from '../../hooks.js'
import { t } from '../../i18n.jsx'

const LANG = { 'Arabic-Egyptian': 'Arabic (Egyptian)' }
const langName = (l) => t(LANG[l] || l)

export default function LiveChats() {
  const chats = useApi('/staff/chats')
  const [selected, setSelected] = useState(null)
  const current = selected || chats.data?.[0]?.call_id
  const detail = useApi(current ? `/staff/calls/${current}` : null)
  const [extra, setExtra] = useState([])
  const [text, setText] = useState('')
  const [ended, setEnded] = useState({})
  const socket = useRef(null)

  useEffect(() => {
    if (USE_MOCK) return undefined
    const ws = new WebSocket(staffSocketUrl())
    ws.onmessage = (ev) => {
      const m = JSON.parse(ev.data)
      if (m.type === 'message') setExtra((x) => [...x, m])
      if (m.type === 'ended') setEnded((e) => ({ ...e, [m.call_id]: true }))
      if (m.type === 'handoff') chats.reload()
    }
    socket.current = ws
    return () => ws.close()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => setExtra([]), [current])

  function send(e) {
    e.preventDefault()
    if (!text.trim()) return
    if (USE_MOCK || socket.current?.readyState !== 1) {
      setExtra((x) => [...x, { call_id: current, role: 'staff', content: text.trim(), created_at: new Date().toISOString() }])
    } else {
      socket.current.send(JSON.stringify({ call_id: current, text: text.trim() }))
    }
    setText('')
  }

  function endChat() {
    if (!USE_MOCK && socket.current?.readyState === 1) socket.current.send(JSON.stringify({ call_id: current, type: 'end' }))
    setEnded((x) => ({ ...x, [current]: true }))
  }

  const d = detail.data
  const messages = [...(d?.messages || []), ...extra.filter((m) => m.call_id === current)]
  const label = { guest: t('Guest'), agent: t('Nour'), staff: t('You') }

  return (
    <>
      <header className="page-head"><div><h1 className="title">{t('Live chats')}</h1><div className="eyebrow">{t('Guests Nour handed over to you')}</div></div></header>
      {chats.error && <div className="error-box">{errorText(chats.error)}</div>}
      {chats.data && chats.data.length === 0 && <div className="card pad muted">{t('No live chats right now. When Nour hands a guest to you, the chat opens here.')}</div>}
      {chats.data?.length > 0 && (
        <div className="row" style={{ alignItems: 'flex-start', gap: 18 }}>
          <div className="stack" style={{ flex: '1 1 260px', gap: 10 }}>
            {chats.data.map((c) => (
              <button key={c.call_id} className="card" onClick={() => setSelected(c.call_id)}
                style={{ padding: '14px 16px', textAlign: 'start', color: 'var(--ink)', border: c.call_id === current ? '2px solid var(--teal)' : undefined }}>
                <div className="row between"><b>{c.guest_name || t('Visitor')}</b><span className="small" style={{ fontWeight: 600, color: ended[c.call_id] ? 'var(--muted)' : 'var(--teal)' }}>{t(ended[c.call_id] ? 'Ended' : 'Live')}</span></div>
                <div className="small" style={{ color: 'var(--text-2)', marginTop: 4 }}>{c.escalation_reason}</div>
                <div className="small muted" style={{ marginTop: 4 }}>{c.booking_id || t('No booking')} · {langName(c.language)} · {niceTime(c.started_at)}</div>
              </button>
            ))}
          </div>
          {d && (
            <section className="card" style={{ flex: '3 1 480px', display: 'flex', flexDirection: 'column' }}>
              <div className="row between" style={{ padding: '14px 18px', borderBottom: '1px solid var(--line-2)' }}>
                <div><b>{d.guest_name || t('Visitor')}</b> <span className="small muted">· {d.booking_id || t('no booking')} · {t('{n} turns', { n: d.turns })}</span></div>
                {d.escalation_reason && <div className="warn-box" style={{ fontSize: 12, padding: '6px 10px' }}>{t('Why handed over: {reason}', { reason: d.escalation_reason })}</div>}
              </div>
              <div className="stack" style={{ padding: 18, gap: 10 }}>
                {messages.map((m, i) => (
                  m.role === 'system'
                    ? <div key={i} className="b-system">{m.content} · {niceTime(m.created_at)}</div>
                    : <div key={i} className={`bubble b-${m.role}`} dir="auto"><div className="who-said">{label[m.role]}</div>{m.content}</div>
                ))}
              </div>
              <form className="row" style={{ padding: '14px 18px', borderTop: '1px solid var(--line-2)' }} onSubmit={send}>
                <label style={{ flex: 1 }}>
                  <span style={{ position: 'absolute', left: -9999 }}>{t('Reply to the guest')}</span>
                  <input disabled={ended[current]} value={text} onChange={(e) => setText(e.target.value)} placeholder={t(ended[current] ? 'This chat has ended' : 'Write a reply…')} dir="auto"
                    style={{ width: '100%', minHeight: 44, padding: '0 12px', border: '1px solid #CFC8B8', borderRadius: 10 }} />
                </label>
                <button className="btn primary" disabled={ended[current]}>{t('Send')}</button>
                <button type="button" className="btn" disabled={ended[current]} onClick={endChat} style={{ borderColor: 'var(--teal)', color: 'var(--teal)' }}>{t('End chat')}</button>
              </form>
            </section>
          )}
        </div>
      )}
    </>
  )
}
