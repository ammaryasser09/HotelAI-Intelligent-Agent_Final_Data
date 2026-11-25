import { useState } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext.jsx'
import { USE_MOCK } from '../api/client.js'
import { initials } from '../hooks.js'
import NourPanel from './NourPanel.jsx'
import VerifyEmailBanner from './VerifyEmailBanner.jsx'
import { LangToggle, t } from '../i18n.jsx'

export function Logo({ size = 32 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 34 34" aria-hidden="true">
      <circle cx="17" cy="17" r="15" fill="none" stroke="#C9A45C" strokeWidth="1.5" />
      <circle cx="17" cy="17" r="6" fill="#C9A45C" />
      <path d="M4 22c4-3 8-3 13 0s9 3 13 0" fill="none" stroke="#C9A45C" strokeWidth="1.5" />
    </svg>
  )
}

export function MicIcon({ color = '#C9A45C', size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="1.9" aria-hidden="true">
      <rect x="9" y="3" width="6" height="11" rx="3" />
      <path d="M5 11a7 7 0 0 0 14 0M12 18v3" />
    </svg>
  )
}

const menus = {
  guest: { sub: 'Hotel · Cairo', items: [['/guest', 'Home'], ['/guest/bookings', 'My bookings'], ['/guest/book', 'Book a room'], ['/guest/requests', 'Requests'], ['/guest/rewards', 'Rewards']] },
  staff: { sub: 'Staff', items: [['/staff', 'Front desk'], ['/staff/tickets', 'Tickets'], ['/staff/chats', 'Live chats']] },
  admin: { sub: 'Admin', items: [['/admin', 'Overview'], ['/admin/revenue', 'Revenue'], ['/admin/nour', 'Nour (AI agent)'], ['/admin/staff', 'Staff & discounts'], ['/staff', 'Front desk view']] }
}

export default function Layout({ area }) {
  const { account, logout } = useAuth()
  const navigate = useNavigate()
  const [nourOpen, setNourOpen] = useState(false)
  const menu = menus[area]

  return (
    <div className={area === 'guest' ? 'guest' : ''}>
      <div className="shell">
        <nav className="side" aria-label="Main menu">
          <div className="brand">
            <Logo />
            <div><div className="brand-name">{t('Nile Pearl')}</div><div className="brand-sub">{t(menu.sub)}</div></div>
          </div>
          <div className="nav">
            {menu.items.map(([to, label]) => (
              <NavLink key={to} to={to} end={to.split('/').length === 2}>{t(label)}</NavLink>
            ))}
          </div>
          <div className="side-foot">
            {area === 'guest' && (
              <button className="nour-btn" onClick={() => setNourOpen(true)}><MicIcon /> {t('Talk to Nour')}</button>
            )}
            <div className="who">
              <div className="avatar">{initials(account.full_name)}</div>
              <div><b>{account.full_name}</b><span>{t(account.role)}{USE_MOCK ? ` · ${t('demo data')}` : ''}</span></div>
            </div>
            <button className="link-btn" onClick={() => { logout(); navigate('/login') }}>{t('Sign out')}</button>
            <LangToggle dark />
          </div>
        </nav>
        <main className="main">
          {area === 'guest' && <VerifyEmailBanner />}
          <Outlet context={{ openNour: () => setNourOpen(true) }} />
        </main>
      </div>
      {nourOpen && <NourPanel onClose={() => setNourOpen(false)} />}
    </div>
  )
}
