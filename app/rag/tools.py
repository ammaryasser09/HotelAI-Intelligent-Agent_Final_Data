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
    """Free rooms of a type for [check_in, check_out): children count toward capacity; only Confirmed/Completed bookings occupy a room."""
    t = _type_id(room_type)
    if not t: return {'ok': False, 'reason': 'UNKNOWN_ROOM_TYPE', 'room_types': [r['room_type_name'] for r in _types().values()]}
    ci, co = _d(check_in), _d(check_out)
    if co <= ci: return {'ok': False, 'reason': 'CHECK_OUT_NOT_AFTER_CHECK_IN'}
    if ci < SYSTEM_DATE: return {'ok': False, 'reason': 'CHECK_IN_IN_THE_PAST', 'today': str(SYSTEM_DATE)}
    rt = _types()[t]
    if int(guests) > int(rt['capacity']):
        fits = [r['room_type_name'] for r in _types().values() if int(r['capacity']) >= int(guests)]
        return {'ok': False, 'reason': 'CAPACITY_EXCEEDED', 'capacity': int(rt['capacity']), 'room_types_that_fit': fits}
    busy = {b['room_number'] for b in _t('bookings') if b['booking_status'] in ('Confirmed', 'Completed')
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
            'non_refundable_total': round(base * n * 0.85, 2),
            'note': 'standard rates; the confirmed rate for the dates is set when booking'}

# ── bookings (identity check first) ─────────────────────────────────────────
def find_booking(booking_ref, last_name=None, phone_last4=None):
    """Booking summary after the reservation_security.txt check: reference + last name or phone digits."""
    b = next((x for x in _t('bookings') if x['booking_id'] == str(booking_ref).strip().upper()), None)
    if not b: return {'ok': False, 'reason': 'BOOKING_NOT_FOUND'}
    c = next(x for x in _t('customers') if x['customer_id'] == b['customer_id'])
    names = {normalize(c['last_name']), normalize(c.get('last_name_ar') or '')} - {''}
    ok = (last_name and normalize(last_name).strip() in names) or \
         (phone_last4 and c['phone'][-4:] == str(phone_last4).strip()[-4:])
    if not ok: return {'ok': False, 'reason': 'IDENTITY_NOT_VERIFIED'}
    p = next(x for x in _t('payments') if x['booking_id'] == b['booking_id'])
    room = next(x for x in _t('rooms') if x['room_number'] == b['room_number'])
    nights = (_d(b['check_out']) - _d(b['check_in'])).days
    return {'ok': True, 'booking_ref': b['booking_id'], 'guest': f"{c['first_name']} {c['last_name']}",
            'guest_ar': f"{c.get('first_name_ar', '')} {c.get('last_name_ar', '')}".strip(),
            'address_as': SALUTE(c),
            'status': b['booking_status'], 'room_type': _types()[b['room_type_id']]['room_type_name'],
            'room_number': room['room_number'] if b['booking_status'] in ('Confirmed', 'Completed') else None,
            'check_in': b['check_in'], 'check_out': b['check_out'], 'nights': nights,
            'adults': int(b['adults']), 'children': int(b['children']), 'rate_plan': b['rate_plan'],
            'total': _money(float(b['price_per_night']) * nights), 'payment_status': p['payment_status'],
            'amount_paid': _money(p['amount_paid']), 'refund_amount': _money(p['refund_amount']),
            'payment_method': p['payment_method']}

def quote_cancellation(booking_ref, last_name=None, phone_last4=None, when=None):
    """What a cancellation costs now, per cancellation_policy.txt. Nothing is changed."""
    b = find_booking(booking_ref, last_name, phone_last4)
    if not b['ok']: return b
    if b['status'] in ('Cancelled', 'Completed', 'No-show'):
        return {'ok': False, 'reason': f'BOOKING_IS_{b["status"].upper().replace("-", "_")}', 'booking': b}
    when = when or datetime.combine(SYSTEM_DATE, datetime.min.time()).replace(hour=12)
    arrival = datetime.combine(_d(b['check_in']), datetime.min.time()).replace(hour=15)
    if _d(b['check_in']) <= SYSTEM_DATE:
        return {'ok': False, 'reason': 'STAY_IN_PROGRESS', 'advice': 'early departure: tell reception; one extra night is charged without notice'}
    night = round(b['total'] / b['nights'], 2)
    if b['rate_plan'] == 'Non-refundable':
        charge, why = b['total'], 'Non-refundable rate: nothing is refunded'
    elif arrival - when >= timedelta(hours=48):
        charge, why = 0.0, 'Flexible rate, 48 hours or more before arrival: free'
    else:
        charge, why = night, 'Flexible rate, less than 48 hours before arrival: the first night is charged'
    paid = b['amount_paid']
    return {'ok': True, 'booking_ref': b['booking_ref'], 'rate_plan': b['rate_plan'], 'charge': charge,
            'refund': round(max(paid - charge, 0), 2), 'amount_paid': paid,
            'charged_to_guarantee_card': round(max(charge - paid, 0), 2), 'rule': why,
            'refund_timing': 'processed within 3 business days; card refunds appear in 7-14 business days'}

def late_checkout_quote(booking_ref, until='16:00', last_name=None, phone_last4=None):
    """Late check-out price per check_in_check_out.txt, including the member benefit."""
    b = find_booking(booking_ref, last_name, phone_last4)
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

def loyalty_status(booking_ref, last_name=None, phone_last4=None):
    b = find_booking(booking_ref, last_name, phone_last4)
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

def escalate_to_human(reason, booking_ref=None):
    return {'ok': True, 'handoff': 'customer service', 'reason': reason, 'booking_ref': booking_ref,
            'say': 'a member of the hotel team will take over now'}

TOOLS = {f.__name__: f for f in (check_availability, find_booking, quote_cancellation, late_checkout_quote,
                                  check_discount_code, loyalty_status, menu, room_service_quote, escalate_to_human)}

def _p(**props): return {'type': 'object', 'properties': props}
S, I = {'type': 'string'}, {'type': 'integer'}
VERIFY = {'booking_ref': {'type': 'string', 'description': 'B followed by six digits, e.g. B013193'},
          'last_name': {'type': 'string', 'description': 'last name on the booking (English or Arabic spelling)'},
          'phone_last4': {'type': 'string', 'description': 'last four digits of the phone on the booking'}}
TOOL_SCHEMAS = [
    {'name': 'check_availability', 'description': 'Free rooms and standard price for a room type and dates.',
     'parameters': {**_p(room_type=S, check_in={'type': 'string', 'format': 'date'}, check_out={'type': 'string', 'format': 'date'}, guests=I),
                    'required': ['room_type', 'check_in', 'check_out', 'guests']}},
    {'name': 'find_booking', 'description': 'Booking and payment details after verifying the caller.',
     'parameters': {**_p(**VERIFY), 'required': ['booking_ref']}},
    {'name': 'quote_cancellation', 'description': 'What cancelling a booking would cost and refund now. Does not cancel.',
     'parameters': {**_p(**VERIFY), 'required': ['booking_ref']}},
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
    {'name': 'escalate_to_human', 'description': 'Hand the call to a person (legal, staff, compensation, data deletion, repeated misunderstanding).',
     'parameters': {**_p(reason=S, booking_ref=S), 'required': ['reason']}},
]
