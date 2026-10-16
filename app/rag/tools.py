# -*- coding: utf-8 -*-
"""
Reference tools for the agent, reading the operational CSVs.

They let the RAG/agent team run the whole voice flow before the FastAPI backend exists,
and they define the behaviour the backend must reproduce. Every function is read-only:
actions (cancel, order) return a quote and what would happen; the backend performs them.
"Today" is app_settings.system_date (SYSTEM_DATE in config.py), never the machine clock.
The same logic in SQL: database/queries.sql.

TOOL_SCHEMAS holds the function-calling definitions (JSON schema) for the LLM.
"""
import csv, os, sys
from datetime import date, datetime, timedelta
from functools import lru_cache
from .config import OPS, ROOT, SYSTEM_DATE
from .text import normalize


def _d(s): return date.fromisoformat(str(s)[:10])
def _money(x): return round(float(x), 2)

@lru_cache(maxsize=None)
def _t(name):
    with open(os.path.join(OPS, f'{name}.csv'), encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def _types():
    return {r['room_type_id']: r for r in _t('room_types')}

def _type_id(room_type):
    k = normalize(room_type).replace(' room', '').strip()
    for r in _types().values():
        if k in (normalize(r['room_type_name']), r['room_type_id'].lower()): return r['room_type_id']
    return None

# Title for addressing the guest by name ("أستاذ أحمد" / "مدام منة"); unisex or unknown names get none.
_MALE = {'Abdullah', 'Ahmad', 'Ahmed', 'Amr', 'Fahad', 'Hamdan', 'Hassan', 'Hossam', 'Karim', 'Khaled', 'Khalid', 'Khalifa',
         'Laith', 'Mahmoud', 'Michael', 'Mina', 'Mohamed', 'Mohammed', 'Mostafa', 'Omar', 'Saeed', 'Salem', 'Saud',
         'Sherif', 'Tarek', 'Yousef', 'Youssef'}
_FEMALE = {'Aisha', 'Aya', 'Dana', 'Dina', 'Fatima', 'Fatma', 'Hana', 'Hessa', 'Huda', 'Layan', 'Lina', 'Mariam', 'Menna',
           'Noora', 'Noura', 'Rana', 'Reem', 'Salma', 'Sara'}
def SALUTE(c):
    fa = c.get('first_name_ar') or ''
    if c['first_name'] in _MALE and fa: return f'أستاذ {fa}'
    if c['first_name'] in _FEMALE and fa: return f'مدام {fa}'
    return ''

# ── availability ────────────────────────────────────────────────────────────
def check_availability(room_type, check_in, check_out, guests):
    """Free rooms of a type for [check_in, check_out): children count toward capacity; only Pending/Confirmed/Completed bookings occupy a room."""
    t = _type_id(room_type)
    if not t: return {'ok': False, 'reason': 'UNKNOWN_ROOM_TYPE', 'room_types': [r['room_type_name'] for r in _types().values()]}
    ci, co = _d(check_in), _d(check_out)
    if co <= ci: return {'ok': False, 'reason': 'CHECK_OUT_NOT_AFTER_CHECK_IN'}
    if ci < SYSTEM_DATE: return {'ok': False, 'reason': 'CHECK_IN_IN_THE_PAST', 'today': str(SYSTEM_DATE)}
    rt = _types()[t]
    if int(guests) > int(rt['capacity']):
        fits = [r['room_type_name'] for r in _types().values() if int(r['capacity']) >= int(guests)]
        return {'ok': False, 'reason': 'CAPACITY_EXCEEDED', 'capacity': int(rt['capacity']), 'room_types_that_fit': fits}
    busy = {b['room_number'] for b in _t('bookings') if b['booking_status'] in ('Pending', 'Confirmed', 'Completed')
            and _d(b['check_in']) < co and ci < _d(b['check_out'])}
    free = [r for r in _t('rooms') if r['room_type_id'] == t and r['room_number'] not in busy and r['status'] != 'Maintenance']
    n = (co - ci).days; base = float(rt['base_price'])
    alternatives = []
    if not free:                                   # offer every other type that fits and is free
        for ot, orow in _types().items():
            if ot == t or int(orow['capacity']) < int(guests): continue
            ofree = [r for r in _t('rooms') if r['room_type_id'] == ot and r['room_number'] not in busy and r['status'] != 'Maintenance']
            if ofree: alternatives.append({'room_type': orow['room_type_name'], 'rooms_free': len(ofree),
                                           'flexible_rate_per_night': float(orow['base_price'])})
    return {'alternatives': alternatives,'ok': True, 'room_type': rt['room_type_name'], 'check_in': str(ci), 'check_out': str(co), 'nights': n,
            'rooms_free': len(free), 'nile_view_free': sum(r['view'] == 'Nile' for r in free),
            'flexible_rate_per_night': base, 'flexible_total': base * n,
            'flexible_deposit_now': base, 'flexible_pay_at_hotel': base * (n - 1),
            'non_refundable_total': round(base * n * 0.85, 2),
            'images': {'nile': rt.get('image_nile') or None, 'city': rt.get('image_city') or None},
            'note': 'standard rates; the confirmed rate for the dates is set when booking'}

# ── accounts and bookings ───────────────────────────────────────────────────
# A logged-in guest (account_id) sees the bookings of the account: those under its customer plus the ones
# linked to it (booking_links). Any other booking needs the reservation_security.txt check:
# reference + last name or the last 4 phone digits (used to link a booking made elsewhere).
def _account(account_id):
    return next((a for a in _t('user_accounts') if a['account_id'] == str(account_id)), None)

def _visible(account_id):
    a = _account(account_id)
    if not a or a['role'] != 'Guest': return set()
    own = {b['booking_id'] for b in _t('bookings') if b['customer_id'] == a['customer_id']}
    return own | {l['booking_id'] for l in _t('booking_links') if l['account_id'] == str(account_id)}

def my_bookings(account_id):
    """Bookings of a logged-in guest, newest first. No further questions are needed for these."""
    if not _account(account_id): return {'ok': False, 'reason': 'NOT_LOGGED_IN'}
    rows = [find_booking(b, account_id=account_id) for b in _visible(account_id)]
    return {'ok': True, 'bookings': sorted(rows, key=lambda r: r['check_in'], reverse=True)}

def link_booking(account_id, booking_ref, last_name=None, phone_last4=None):
    """Add a booking made by phone, agency or a booking platform to the account (reference check first)."""
    if not _account(account_id): return {'ok': False, 'reason': 'NOT_LOGGED_IN'}
    if str(booking_ref).strip().upper() in _visible(account_id): return {'ok': True, 'already_in_account': True}
    b = find_booking(booking_ref, last_name, phone_last4, account_id)
    if not b['ok']: return b
    return {'ok': True, 'linked': b['booking_ref'], 'booking': b, 'note': 'the backend inserts the row in booking_links'}

def find_booking(booking_ref, last_name=None, phone_last4=None, account_id=None):
    """Booking summary: free for a booking in the logged-in account, otherwise after the reference check."""
    b = next((x for x in _t('bookings') if x['booking_id'] == str(booking_ref).strip().upper()), None)
    if not b: return {'ok': False, 'reason': 'BOOKING_NOT_FOUND'}
    c = next(x for x in _t('customers') if x['customer_id'] == b['customer_id'])
    names = {normalize(c['last_name']), normalize(c.get('last_name_ar') or '')} - {''}
    ok = (account_id is not None and b['booking_id'] in _visible(account_id)) or \
         (last_name and normalize(last_name).strip() in names) or \
         (phone_last4 and c['phone'][-4:] == str(phone_last4).strip()[-4:])
    if not ok: return {'ok': False, 'reason': 'IDENTITY_NOT_VERIFIED'}
    p = next(x for x in _t('payments') if x['booking_id'] == b['booking_id'])
    room = next(x for x in _t('rooms') if x['room_number'] == b['room_number'])
    nights = (_d(b['check_out']) - _d(b['check_in'])).days
    return {'ok': True, 'booking_ref': b['booking_id'], 'guest': f"{c['first_name']} {c['last_name']}",
            'guest_ar': f"{c.get('first_name_ar', '')} {c.get('last_name_ar', '')}".strip(),
            'address_as': SALUTE(c),
            'status': b['booking_status'], 'room_type': _types()[b['room_type_id']]['room_type_name'],
            'room_number': room['room_number'] if b['booking_status'] in ('Pending', 'Confirmed', 'Completed') else None,
            'check_in': b['check_in'], 'check_out': b['check_out'], 'nights': nights,
            'adults': int(b['adults']), 'children': int(b['children']), 'rate_plan': b['rate_plan'],
            'total': _money(float(b['price_per_night']) * nights), 'payment_status': p['payment_status'],
            'amount_paid': _money(p['amount_paid']), 'refund_amount': _money(p['refund_amount']),
            'payment_method': p['payment_method'], 'payment_due_at': p.get('payment_due_at') or None}

def quote_cancellation(booking_ref, last_name=None, phone_last4=None, when=None, account_id=None):
    """What a cancellation costs now, per cancellation_policy.txt. Nothing is changed."""
    b = find_booking(booking_ref, last_name, phone_last4, account_id)
    if not b['ok']: return b
    if b['status'] in ('Cancelled', 'Completed', 'No-show'):
        return {'ok': False, 'reason': f'BOOKING_IS_{b["status"].upper().replace("-", "_")}', 'booking': b}
    when = when or datetime.combine(SYSTEM_DATE, datetime.min.time()).replace(hour=12)
    arrival = datetime.combine(_d(b['check_in']), datetime.min.time()).replace(hour=15)
    if _d(b['check_in']) <= SYSTEM_DATE:
        return {'ok': False, 'reason': 'STAY_IN_PROGRESS', 'advice': 'early departure: tell reception; one extra night is charged without notice'}
    night = round(b['total'] / b['nights'], 2)
    if b['status'] == 'Pending':                   # nothing paid yet: cancelling just releases the room
        return {'ok': True, 'booking_ref': b['booking_ref'], 'rate_plan': b['rate_plan'], 'charge': 0.0, 'refund': 0.0,
                'amount_paid': 0.0, 'still_due': 0.0, 'rule': 'Pending booking: the payment link was not paid yet, so cancelling is free',
                'payment_due_at': b['payment_due_at']}
    if b['rate_plan'] == 'Non-refundable':
        charge, why = b['total'], 'Non-refundable rate: nothing is refunded'
    elif arrival - when >= timedelta(hours=48):
        charge, why = 0.0, 'Flexible rate, 48 hours or more before arrival: free, the first-night deposit is refunded'
    else:
        charge, why = night, 'Flexible rate, less than 48 hours before arrival: the first night is charged (the deposit is kept)'
    paid = b['amount_paid']
    return {'ok': True, 'booking_ref': b['booking_ref'], 'rate_plan': b['rate_plan'], 'charge': charge,
            'refund': round(max(paid - charge, 0), 2), 'amount_paid': paid,
            'still_due': round(max(charge - paid, 0), 2), 'rule': why,
            'refund_timing': 'processed within 3 business days; card refunds appear in 7-14 business days'}

def quote_modification(booking_ref, new_check_in=None, new_check_out=None, new_room_type=None, adults=None, children=None,
                       last_name=None, phone_last4=None, account_id=None, when=None):
    """What a change would look like, per booking_modification.txt: availability, room, new total. Changes nothing;
    after the guest says yes the backend runs query 9 in queries.sql."""
    b = find_booking(booking_ref, last_name, phone_last4, account_id)
    if not b['ok']: return b
    raw = next(x for x in _t('bookings') if x['booking_id'] == b['booking_ref'])
    if b['status'] not in ('Pending', 'Confirmed'):
        return {'ok': False, 'reason': f'BOOKING_IS_{b["status"].upper().replace("-", "_")}'}
    if raw['booking_channel'] == 'Booking Platform':
        return {'ok': False, 'reason': 'CHANGE_THROUGH_PLATFORM', 'advice': 'booked on a booking platform: change it there, under its terms'}
    if b['rate_plan'] == 'Non-refundable':
        return {'ok': False, 'reason': 'NON_REFUNDABLE_CANNOT_CHANGE'}
    ci0, co0 = _d(b['check_in']), _d(b['check_out'])
    if ci0 <= SYSTEM_DATE:
        return {'ok': False, 'reason': 'STAY_IN_PROGRESS', 'advice': 'changes during the stay are made at reception'}
    when = when or datetime.combine(SYSTEM_DATE, datetime.min.time()).replace(hour=12)
    if datetime.combine(ci0, datetime.min.time()).replace(hour=15) - when < timedelta(hours=48):
        return {'ok': False, 'reason': 'LESS_THAN_48_HOURS', 'advice': 'a change now counts as a late cancellation of the original dates'}
    ci, co = _d(new_check_in or ci0), _d(new_check_out or co0)
    if co <= ci: return {'ok': False, 'reason': 'CHECK_OUT_NOT_AFTER_CHECK_IN'}
    if ci < SYSTEM_DATE: return {'ok': False, 'reason': 'CHECK_IN_IN_THE_PAST'}
    t0 = raw['room_type_id']; t1 = _type_id(new_room_type) if new_room_type else t0
    if not t1: return {'ok': False, 'reason': 'UNKNOWN_ROOM_TYPE'}
    rt = _types()[t1]
    guests = int(adults if adults is not None else raw['adults']) + int(children if children is not None else raw['children'])
    if guests > int(rt['capacity']):
        fits = [r['room_type_name'] for r in _types().values() if int(r['capacity']) >= guests]
        return {'ok': False, 'reason': 'CAPACITY_EXCEEDED', 'capacity': int(rt['capacity']), 'room_types_that_fit': fits}
    def free(room):
        return not any(x['room_number'] == room and x['booking_id'] != raw['booking_id']
                       and x['booking_status'] in ('Pending', 'Confirmed', 'Completed')
                       and _d(x['check_in']) < co and ci < _d(x['check_out']) for x in _t('bookings'))
    extension_only = t1 == t0 and ci == ci0 and co > co0
    if extension_only or (t1 == t0 and ci >= ci0 and co <= co0):      # same room: extra nights or a shorter stay
        room = raw['room_number'] if free(raw['room_number']) else None
    else:                                                               # new dates or new type: any free room, same room first
        rooms = [r for r in _t('rooms') if r['room_type_id'] == t1 and r['status'] != 'Maintenance' and free(r['room_number'])]
        rooms.sort(key=lambda r: (r['room_number'] != raw['room_number'], r['view'] != 'Nile', int(r['room_number'])))
        room = rooms[0]['room_number'] if rooms else None
    if not room:
        return {'ok': False, 'reason': 'NOT_AVAILABLE', 'advice': 'the booking stays unchanged; offer other dates or another room type'}
    ppn = float(raw['price_per_night']) if t1 == t0 else float(rt['base_price'])
    n = (co - ci).days; total = round(ppn * n, 2); paid = b['amount_paid']
    return {'ok': True, 'booking_ref': b['booking_ref'], 'room_type': rt['room_type_name'], 'room_number': room,
            'check_in': str(ci), 'check_out': str(co), 'nights': n, 'guests': guests, 'price_per_night': ppn,
            'old_total': b['total'], 'new_total': total, 'difference': round(total - b['total'], 2),
            'deposit_paid': paid, 'balance_at_hotel': round(total - paid, 2),
            'rule': 'free on the Flexible rate until 48 hours before arrival; new dates keep the agreed rate, a new room type uses its standard rate'}

def late_checkout_quote(booking_ref, until='16:00', last_name=None, phone_last4=None, account_id=None):
    """Late check-out price per check_in_check_out.txt, including the member benefit."""
    b = find_booking(booking_ref, last_name, phone_last4, account_id)
    if not b['ok']: return b
    night = round(b['total'] / b['nights'], 2)
    cid = next(x['customer_id'] for x in _t('bookings') if x['booking_id'] == b['booking_ref'])
    m = next((x for x in _t('loyalty_members') if x['customer_id'] == cid and x['status'] == 'Active'), None)
    free_until = next((t['late_checkout_until'] for t in _t('loyalty_tiers') if m and t['tier'] == m['tier']), '') or ''
    h = until.zfill(5)
    if free_until and h <= free_until: price, why = 0.0, f'{m["tier"]} member benefit until {free_until}'
    elif h <= '16:00': price, why = 1500.0, 'until 4:00 PM'
    elif h <= '18:00': price, why = round(night * 0.5, 2), 'until 6:00 PM: 50% of the nightly rate'
    else: price, why = night, 'after 6:00 PM: a full night'
    return {'ok': True, 'until': h, 'price': price, 'rule': why, 'subject_to': 'availability'}

# ── codes, loyalty, menu ────────────────────────────────────────────────────
def check_discount_code(code):
    c = next((x for x in _t('discount_codes') if x['discount_code'] == str(code).strip().upper()), None)
    if not c: return {'ok': False, 'reason': 'CODE_NOT_FOUND'}
    val = f"{c['discount_value']}%" if c['discount_type'] == 'PERCENTAGE' else f"{int(float(c['discount_value'])):,} EGP"
    return {'ok': c['status'] == 'Active', 'code': c['discount_code'], 'status': c['status'], 'discount': val,
            'valid_from': c['start_date'], 'valid_to': c['end_date'],
            'uses_left': None if not c['max_usage'] else int(c['max_usage']) - int(c['usage_count']),
            'rule': 'one code or discount per booking'}

def loyalty_status(booking_ref, last_name=None, phone_last4=None, account_id=None):
    b = find_booking(booking_ref, last_name, phone_last4, account_id)
    if not b['ok']: return b
    cid = next(x['customer_id'] for x in _t('bookings') if x['booking_id'] == b['booking_ref'])
    m = next((x for x in _t('loyalty_members') if x['customer_id'] == cid), None)
    if not m: return {'ok': True, 'member': False, 'how_to_join': 'free, when booking, at check-in or on the website'}
    rules = {r['rule']: float(r['value']) for r in _t('loyalty_rules')}
    pts = int(m['points_balance'])
    return {'ok': True, 'member': True, 'tier': m['tier'], 'points': pts, 'status': m['status'],
            'points_worth_egp': int(pts // rules['redeem_points'] * rules['redeem_value'])}

def menu(night=False, category=None):
    items = [m for m in _t('menu_items') if (not night or m['night_menu'] == 'true') and (not category or m['category'] == category)]
    return [{'item': m['name_en'], 'item_ar': m['name_ar'], 'price': int(float(m['price'])), 'dietary': m['dietary']} for m in items]

def room_service_quote(items):
    """items: list of {'item': name (English or Arabic), 'qty': n}. Adds the 300 EGP delivery charge."""
    by = {normalize(m['name_en']): m for m in _t('menu_items')} | {normalize(m['name_ar']): m for m in _t('menu_items')}
    lines, missing = [], []
    for it in items:
        m = by.get(normalize(it['item']))
        if not m: missing.append(it['item']); continue
        q = int(it.get('qty', 1)); lines.append({'item': m['name_en'], 'qty': q, 'price': int(float(m['price'])) * q})
    fee = next(int(float(s['price'])) for s in _t('services') if s['service_id'] == 'S002')
    return {'ok': not missing, 'lines': lines, 'not_on_menu': missing, 'delivery': fee,
            'total': sum(l['price'] for l in lines) + fee, 'eta_minutes': '30-45'}

def escalate_to_human(reason, booking_ref=None, staff_available=True):
    """The guest asked for a person: live chat with a free staff member, otherwise an urgent Staff Callback ticket."""
    if staff_available:
        return {'ok': True, 'handoff': 'live chat with a member of staff', 'reason': reason, 'booking_ref': booking_ref,
                'say': 'a member of the hotel team will continue this chat with you now'}
    t = create_request('Staff Callback', reason, booking_ref)
    return {'ok': True, 'handoff': 'urgent ticket', 'ticket': t, 'reason': reason, 'booking_ref': booking_ref,
            'say': 'no one is free this minute; a member of staff will contact you soon in the chat or by email'}

REQUEST_TYPES = ('Room Service', 'Booking Inquiry', 'Housekeeping', 'Late Checkout', 'Modification Request', 'Airport Transfer',
                 'General Inquiry', 'Cancellation Request', 'Complaint', 'Extra Bed', 'Early Check-in', 'Payment Inquiry',
                 'Discount Request', 'Staff Callback', 'Emergency')
def create_request(request_type, request_text, booking_ref=None):
    """A ticket for the hotel team (query 10). Emergency = Critical, Staff Callback = Urgent. The backend inserts it."""
    if request_type not in REQUEST_TYPES: return {'ok': False, 'reason': 'UNKNOWN_REQUEST_TYPE', 'types': list(REQUEST_TYPES)}
    priority = {'Emergency': 'Critical', 'Staff Callback': 'Urgent'}.get(request_type, 'Normal')
    return {'ok': True, 'request_type': request_type, 'priority': priority, 'booking_ref': booking_ref,
            'status': 'Open', 'note': 'the backend inserts it into customer_requests; Critical tickets alert the staff at once'}

TOOLS = {f.__name__: f for f in (check_availability, my_bookings, link_booking, find_booking, quote_cancellation, quote_modification, late_checkout_quote,
                                  check_discount_code, loyalty_status, menu, room_service_quote, create_request, escalate_to_human)}

def _p(**props): return {'type': 'object', 'properties': props}
S, I = {'type': 'string'}, {'type': 'integer'}
VERIFY = {'booking_ref': {'type': 'string', 'description': 'B followed by six digits, e.g. B013193'},
          'last_name': {'type': 'string', 'description': 'last name on the booking (English or Arabic spelling)'},
          'phone_last4': {'type': 'string', 'description': 'last four digits of the phone on the booking'},
          'account_id': {'type': 'integer', 'description': 'logged-in guest account (filled by the backend); bookings in the account need no name check'}}
TOOL_SCHEMAS = [
    {'name': 'check_availability', 'description': 'Free rooms and standard price for a room type and dates.',
     'parameters': {**_p(room_type=S, check_in={'type': 'string', 'format': 'date'}, check_out={'type': 'string', 'format': 'date'}, guests=I),
                    'required': ['room_type', 'check_in', 'check_out', 'guests']}},
    {'name': 'my_bookings', 'description': 'The bookings of the logged-in guest (own and linked). No further questions needed.',
     'parameters': {**_p(account_id=I), 'required': ['account_id']}},
    {'name': 'link_booking', 'description': 'Add a booking made by phone, agency or a booking platform to the account: reference + last name or last 4 phone digits.',
     'parameters': {**_p(**VERIFY), 'required': ['account_id', 'booking_ref']}},
    {'name': 'find_booking', 'description': 'Booking and payment details: a booking in the account, or after the reference check.',
     'parameters': {**_p(**VERIFY), 'required': ['booking_ref']}},
    {'name': 'quote_cancellation', 'description': 'What cancelling a booking would cost and refund now. Does not cancel.',
     'parameters': {**_p(**VERIFY), 'required': ['booking_ref']}},
    {'name': 'quote_modification', 'description': 'New dates, room type or guests for a booking: availability, room and new total. Does not change it.',
     'parameters': {**_p(new_check_in={'type': 'string', 'format': 'date'}, new_check_out={'type': 'string', 'format': 'date'},
                         new_room_type=S, adults=I, children=I, **VERIFY), 'required': ['booking_ref']}},
    {'name': 'late_checkout_quote', 'description': 'Price of a late check-out until a given time (HH:MM).',
     'parameters': {**_p(until=S, **VERIFY), 'required': ['booking_ref', 'until']}},
    {'name': 'check_discount_code', 'description': 'Whether a discount code is valid today.',
     'parameters': {**_p(code=S), 'required': ['code']}},
    {'name': 'loyalty_status', 'description': 'Nile Pearl Rewards tier and points of the booking guest.',
     'parameters': {**_p(**VERIFY), 'required': ['booking_ref']}},
    {'name': 'menu', 'description': 'Room-service menu; night=true for the 11 PM - 6 AM menu.',
     'parameters': _p(night={'type': 'boolean'}, category=S)},
    {'name': 'room_service_quote', 'description': 'Total of a room-service order including the delivery charge.',
     'parameters': {**_p(items={'type': 'array', 'items': _p(item=S, qty=I)}), 'required': ['items']}},
    {'name': 'create_request', 'description': 'Open a ticket for the hotel team: in-stay requests, complaints, Discount Request, Emergency (Critical).',
     'parameters': {**_p(request_type={'type': 'string', 'enum': list(REQUEST_TYPES)}, request_text=S, booking_ref=S), 'required': ['request_type', 'request_text']}},
    {'name': 'escalate_to_human', 'description': 'The guest has a problem and asked for a person: live chat with staff, or an urgent ticket if no one is free.',
     'parameters': {**_p(reason=S, booking_ref=S), 'required': ['reason']}},
]
