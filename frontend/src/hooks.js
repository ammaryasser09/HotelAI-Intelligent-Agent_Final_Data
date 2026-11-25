import { useCallback, useEffect, useState } from 'react'
import { api } from './api/client.js'
import { days as dayNames, months as monthNames, t } from './i18n.jsx'

export function useApi(path, options) {
  const key = path + JSON.stringify(options || {})
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  const reload = useCallback(() => {
    if (!path) return Promise.resolve()
    setLoading(true)
    return api(path, options)
      .then((d) => { setData(d); setError(null) })
      .catch(setError)
      .finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])

  useEffect(() => { reload() }, [reload])
  return { data, error, loading, reload, setData }
}

let todayPromise = null
export function useHotelToday() {
  const [today, setToday] = useState(null)
  useEffect(() => {
    todayPromise = todayPromise || api('/health').then((h) => h.hotel_today).catch(() => new Date().toISOString().slice(0, 10))
    todayPromise.then(setToday)
  }, [])
  return today
}

export const daysBetween = (a, b) => Math.round((Date.parse(b) - Date.parse(a)) / 86400000)

export const egp =(n, digits = 2) =>
  n === null || n === undefined ? '—' : Number(n).toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits })

export const millions = (n) => (Number(n) / 1e6).toFixed(2) + 'M'


export function niceDate(iso, withDay = false, withYear = true) {
  if (!iso) return '—'
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number)
  const dt = new Date(Date.UTC(y, m - 1, d))
  return `${withDay ? dayNames()[dt.getUTCDay()] + ' ' : ''}${d} ${monthNames()[m - 1]}${withYear ? ' ' + y : ''}`
}

export function niceTime(iso) {
  if (!iso) return ''
  const t = iso.slice(11, 16)
  return t
}

export function stayRange(ci, co) {
  const sameYear = ci.slice(0, 4) === co.slice(0, 4)
  return `${niceDate(ci, false, !sameYear)} – ${niceDate(co)}`
}

export const initials = (name = '') => name.split(' ').filter(Boolean).slice(0, 2).map((w) => w[0]).join('').toUpperCase()

export const errorText = (e) => {
  if (!e) return ''
  const map = {
    INVALID_CREDENTIALS: 'Wrong email or password.',
    ACCOUNT_DISABLED: 'This account is disabled. Contact the hotel administration.',
    CHECK_IN_IN_THE_PAST: 'Check-in can’t be in the past.',
    CAPACITY_EXCEEDED: 'Too many guests for this room type.',
    ROOM_NOT_FREE: 'The room is not free yet: the previous guest has not checked out.',
    BOOKING_NOT_FOUND_OR_NO_MATCH: 'No booking matches that reference and name.',
    NOT_CANCELLABLE: 'This booking can’t be cancelled.',
    'Failed to fetch': 'Can’t reach the server. Is the backend running?',
    WEAK_PASSWORD: 'The password needs at least 8 characters, with a letter and a number.',
    EMAIL_ALREADY_REGISTERED: 'This email already has an account. Sign in, or reset the password.',
    PHONE_ALREADY_REGISTERED: 'This phone number is already registered.',
    ALREADY_REGISTERED: 'This email or phone number is already registered.',
    CODE_EXPIRED: 'The code has expired. Ask for a new one.',
    WRONG_CODE: 'Wrong code. Check the email and try again.',
    TOO_YOUNG: 'Guests must be 18 or older to book.',
    EMAIL_NOT_VERIFIED: 'Confirm your email first (the code is in your inbox).',
    DATE_OF_BIRTH_REQUIRED: 'Add your date of birth to make your first booking.',
    CHANGE_ON_BOOKING_PLATFORM: 'This booking was made on a booking website: change it there.',
    NON_REFUNDABLE_CANNOT_CHANGE: 'A non-refundable booking can’t be changed.',
    NOT_CHANGEABLE: 'This booking can’t be changed.',
    TOO_LATE_TO_CHANGE: 'Changes close 48 hours before arrival. Call reception for help.',
    NO_ROOM_AVAILABLE: 'No room of this type is free for these dates.',
    CHECK_OUT_NOT_AFTER_CHECK_IN: 'Check-out must be after check-in.',
    BOOKING_NOT_FOUND: 'Booking not found.',
    PAYMENT_PROVIDER_ERROR: 'The payment service didn’t answer. Try again in a minute.',
    NOTHING_TO_CHANGE: 'Change the dates, the room type or the guests first.',
    ROOM_JUST_TAKEN: 'Someone took the last room a moment ago. Try other dates or another room type.',
    ALREADY_VERIFIED: 'Your email is already confirmed.',
    STAFF_RESET_BY_ADMIN: 'Hotel staff can’t reset their password here. Ask the hotel administrator to set a new one for you.'
  }
  return t(map[e.message] || e.message || 'Something went wrong.')
}
