import { useApi, errorText, niceDate } from '../hooks.js'
import { t } from '../i18n.jsx'

const TOOL = {
  check_availability: 'Checked availability', create_booking: 'Made a booking', my_bookings: 'Looked up the guest’s bookings',
  find_booking: 'Opened a booking', create_request: 'Opened a ticket', escalate_to_human: 'Handed to staff',
  check_discount_code: 'Checked a discount code', link_booking: 'Linked a booking', quote_cancellation: 'Quoted a cancellation',
  cancel_booking: 'Cancelled a booking', quote_modification: 'Quoted a change', modify_booking: 'Changed a booking', search_hotel_info: 'Searched hotel information'
}
const LANG = { 'Arabic-Egyptian': 'Arabic (Egyptian)' }

export default function CallDetail({ callId, onClose }) {
  const { data: d, error } = useApi(`/staff/calls/${callId}`)
  const label = { guest: t('Guest'), agent: t('Nour'), staff: t('Staff') }

  return (
    <div className="modal-back" role="dialog" aria-label={t('Conversation')} onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ width: 'min(820px, 100%)' }}>
        <div className="row between">
          <h2 style={{ fontSize: 20, fontWeight: 600 }}>{t('Conversation')}{d ? ` · ${d.guest_name || t('Visitor')}` : ''}</h2>
          <button className="btn sm" onClick={onClose}>{t('Close')}</button>
        </div>
        {error && <div className="error-box">{errorText(error)}</div>}
        {!d && !error && <div className="loading">{t('Loading…')}</div>}
        {d && (
          <>
            <div className="row small muted" style={{ gap: '6px 18px' }}>
              <span>{niceDate(d.started_at)} {d.started_at.slice(11, 16)}</span>
              <span>{t(LANG[d.language] || d.language || 'Unknown')}</span>
              <span>{d.booking_id || t('No booking')}</span>
              {d.duration_seconds !== null && <span className="ltr">{d.duration_seconds} s</span>}
              {d.avg_latency_ms !== null && <span>{t('Reply time')}: <span className="ltr">{(d.avg_latency_ms / 1000).toFixed(2)} s</span></span>}
            </div>
            {d.summary && <div className="note-box" dir="auto">{d.summary}</div>}
            {d.escalation_reason && <div className="warn-box" dir="auto">{t('Why handed over: {reason}', { reason: d.escalation_reason })}</div>}
            <div className="row" style={{ alignItems: 'flex-start', gap: 18 }}>
              <div className="stack" style={{ flex: '2 1 360px', gap: 10 }}>
                {d.messages.length === 0 && <div className="muted small">{t('No messages were saved for this call.')}</div>}
                {d.messages.map((m) => (
                  m.role === 'system'
                    ? <div key={m.turn_no} className="b-system">{m.content}</div>
                    : <div key={m.turn_no} className={`bubble b-${m.role}`} dir="auto">
                        <div className="who-said">{label[m.role]}{m.latency_ms ? <span className="ltr"> · {(m.latency_ms / 1000).toFixed(1)} s</span> : ''}</div>{m.content}
                      </div>
                ))}
              </div>
              <div className="stack" style={{ flex: '1 1 220px', gap: 8 }}>
                <b className="small">{t('What Nour did')}</b>
                {d.call_actions.length === 0 && <div className="small muted">{t('No actions.')}</div>}
                {d.call_actions.map((a, i) => (
                  <div key={i} className="card" style={{ padding: '10px 12px', fontSize: 13 }}>
                    <div className="row between"><b>{t(TOOL[a.tool_name] || a.tool_name)}</b><span className={`badge ${a.success ? 'b-green' : 'b-red'}`}>{a.success ? '✓' : '✕'}</span></div>
                    <div className="muted ltr" style={{ fontSize: 12, marginTop: 4, wordBreak: 'break-word' }}>{a.tool_name}{a.booking_id ? ` · ${a.booking_id}` : ''}</div>
                    {Object.keys(a.arguments || {}).length > 0 && <div className="ltr" style={{ fontSize: 12, marginTop: 4, color: 'var(--text-2)', wordBreak: 'break-word' }}>{Object.entries(a.arguments).map(([k, v]) => `${k}: ${typeof v === 'object' ? JSON.stringify(v) : v}`).join(' · ')}</div>}
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
