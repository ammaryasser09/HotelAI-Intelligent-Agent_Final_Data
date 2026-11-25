import { Logo } from './Layout.jsx'
import { t } from '../i18n.jsx'

export default function AuthShell({ children, onSubmit }) {
  return (
    <div className="login-page">
      <div className="login-art">
        <div className="row"><Logo size={40} /><span className="brand-sub" style={{ fontSize: 13 }}>{t('Hotel · Cairo')}</span></div>
        <h1>{t('Nile Pearl Hotel')}</h1>
        <p style={{ margin: 0, color: '#E9E4D8', maxWidth: 460, lineHeight: 1.5 }}>{t('Your stay, your bookings and Nour — our AI concierge who answers in Arabic, English, French and Russian.')}</p>
      </div>
      <div className="login-form">
        <form onSubmit={onSubmit}>{children}</form>
      </div>
    </div>
  )
}
