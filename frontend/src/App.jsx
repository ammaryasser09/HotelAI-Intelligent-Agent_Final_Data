import { Navigate, Route, Routes } from 'react-router-dom'
import { homeFor, useAuth } from './auth/AuthContext.jsx'
import Login from './pages/Login.jsx'
import { t } from './i18n.jsx'
import Layout from './components/Layout.jsx'
import GuestHome from './pages/guest/GuestHome.jsx'
import MyBookings from './pages/guest/MyBookings.jsx'
import BookRoom from './pages/guest/BookRoom.jsx'
import Requests from './pages/guest/Requests.jsx'
import Rewards from './pages/guest/Rewards.jsx'
import FrontDesk from './pages/staff/FrontDesk.jsx'
import Tickets from './pages/staff/Tickets.jsx'
import LiveChats from './pages/staff/LiveChats.jsx'
import Overview from './pages/admin/Overview.jsx'
import Revenue from './pages/admin/Revenue.jsx'
import NourStats from './pages/admin/NourStats.jsx'
import StaffDiscounts from './pages/admin/StaffDiscounts.jsx'

function Protected({ roles, children }) {
  const { account, ready } = useAuth()
  if (!ready) return <div className="loading">{t('Loading…')}</div>
  if (!account) return <Navigate to="/login" replace />
  if (!roles.includes(account.role)) return <Navigate to={homeFor(account.role)} replace />
  return children
}

export default function App() {
  const { account, ready } = useAuth()
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/guest" element={<Protected roles={['Guest']}><Layout area="guest" /></Protected>}>
        <Route index element={<GuestHome />} />
        <Route path="bookings" element={<MyBookings />} />
        <Route path="book" element={<BookRoom />} />
        <Route path="requests" element={<Requests />} />
        <Route path="rewards" element={<Rewards />} />
      </Route>
      <Route path="/staff" element={<Protected roles={['Staff', 'Admin']}><Layout area="staff" /></Protected>}>
        <Route index element={<FrontDesk />} />
        <Route path="tickets" element={<Tickets />} />
        <Route path="chats" element={<LiveChats />} />
      </Route>
      <Route path="/admin" element={<Protected roles={['Admin']}><Layout area="admin" /></Protected>}>
        <Route index element={<Overview />} />
        <Route path="revenue" element={<Revenue />} />
        <Route path="nour" element={<NourStats />} />
        <Route path="staff" element={<StaffDiscounts />} />
      </Route>
      <Route path="*" element={!ready ? <div className="loading">{t('Loading…')}</div> : <Navigate to={account ? homeFor(account.role) : '/login'} replace />} />
    </Routes>
  )
}
