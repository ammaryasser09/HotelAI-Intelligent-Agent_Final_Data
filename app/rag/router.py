# -*- coding: utf-8 -*-
"""
Code-side router: the code decides which tools to run, the LLM only phrases the answer.

Small models (7B and below) often skip tool calls or guess. This router reads the caller's
message with simple rules, runs the needed tools itself, and hands the results to the LLM
as TOOL RESULTS, together with notes such as "not logged in". The LLM can still call
tools on its own; the router only makes the common cases reliable.

Who is calling comes from the login, not from the conversation:
  account_id = the logged-in guest -> the bookings of the account need no further questions;
               a booking that is not in the account is added first (link_booking: reference +
               last name or the last 4 digits of its phone number)
  account_id = None (visitor)      -> general answers and availability only; to book or to manage
               a booking the caller logs in first
"""
import re
from datetime import date
from . import tools as T

MONTHS = {'يناير': 1, 'فبراير': 2, 'مارس': 3, 'أبريل': 4, 'ابريل': 4, 'إبريل': 4, 'مايو': 5, 'يونيو': 6, 'يوليو': 7,
          'أغسطس': 8, 'اغسطس': 8, 'سبتمبر': 9, 'أكتوبر': 10, 'اكتوبر': 10, 'نوفمبر': 11, 'ديسمبر': 12,
          'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6, 'july': 7, 'august': 8,
          'september': 9, 'october': 10, 'november': 11, 'december': 12}
TYPES = [(r'سينجل|سنجل|فردية|single', 'Single'), (r'دبل|دابل|مزدوجة|double', 'Double'), (r'توين|twin', 'Twin'),
         (r'ديلوكس|دي?لوكس|deluxe', 'Deluxe'), (r'فاميلي|عائلية|عائلي|family', 'Family'), (r'سويت|جناح|suite', 'Suite')]
GUESTS = [(r'لوحدي|لفرد|شخص واحد|\bone\b', 1), (r'لاتنين|لاثنين|لإتنين|اتنين|اثنين|لفردين|two|أنا ومراتي|انا ومراتي|أنا وجوزي', 2),
          (r'لتلاتة|تلاتة|ثلاثة|three', 3), (r'لأربعة|لاربعة|أربعة|اربعة|four', 4), (r'لخمسة|خمسة|five', 5), (r'لستة|ستة|six', 6)]
AR_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
# "my booking / my payment / my points": the caller's own data
MINE = re.compile(r'حجزي|حجزنا|الحجز بتاعي|الحجز بتاعنا|حجوزاتي|الريزيرفيشن|دفعت|الدفع بتاعي|فلوسي|فاتورتي|الفاتورة|نقطي|نقاطي|'
                  r'مستوايا|عضويتي|my (?:booking|reservation|payment|points|bill|invoice)', re.I)
# wants to change or cancel a booking, or to book a new one
MANAGE = re.compile(r'ألغي|الغي|إلغاء|الغاء|اكنسل|أكنسل|أغير|اغير|أعدل|اعدل|أأخر|أزود|ازود|أمد|امد|cancel|change my|modify', re.I)
NEW = re.compile(r'أحجز|احجز|احجزلي|\bbook\b', re.I)
CANCEL = re.compile(r'ألغي|الغي|إلغاء|الغاء|لغيت|cancel|أكنسل|اكنسل', re.I)

def _year_for(month, day, today):
    y = today.year
    return y if date(y, month, day) >= today else y + 1

def parse_dates(text, today):
    t = text.translate(AR_DIGITS).lower()
    m = re.search(r'(\d{1,2})\s*(?:لـ|ل|الى|إلى|لحد|to|-|–)\s*(\d{1,2})\s*([^\s\d،,.؟?]+)', t)
    if m and m.group(3).strip() in MONTHS:
        mo = MONTHS[m.group(3).strip()]; d1, d2 = int(m.group(1)), int(m.group(2))
        y = _year_for(mo, d1, today); ci = date(y, mo, d1)
        co = date(y, mo, d2) if d2 > d1 else date(y + (mo == 12), mo % 12 + 1, d2)
        return ci, co
    return None

def _who(t):
    """Last name or last 4 phone digits given in the message (only used to add a booking to the account)."""
    name = re.search(r'(?:باسم|باسمها|باسمه|الاسم|اسمي|اسم العيلة|last name is|name is|under)\s*[:،]?\s*([^\s،,.؟?]+)', t)
    phone = re.search(r'(?:آخر|اخر)\s*(?:أربع|اربع|4)\s*(?:أرقام|ارقام)(?:\s*(?:في|فى)\s*(?:التليفون|الموبايل|الفون))?\s*(\d{4})|'
                      r'last (?:four|4) digits?\s*(\d{4})', t)
    if name: return {'last_name': name.group(1)}
    if phone: return {'phone_last4': phone.group(1) or phone.group(2)}
    return {}

def route(text, today=None, account_id=None):
    today = today or T.SYSTEM_DATE
    t = text.translate(AR_DIGITS)
    results, notes = [], []
    ref = re.search(r'\bB\d{6}\b', t.upper())
    ref = ref.group() if ref else None

    if account_id is None:                                       # visitor
        if ref or MINE.search(t) or MANAGE.search(t) or NEW.search(t):
            notes.append('VISITOR: the caller is not logged in. Answer general questions only. To book, to see or manage a '
                         'booking, or to make a request, ask them to log in on the website first. Say NOTHING about any '
                         'booking, not even whether it exists.')
    elif ref:
        who = _who(t)
        b = T.find_booking(ref, account_id=account_id)
        if b.get('reason') == 'IDENTITY_NOT_VERIFIED':           # a real booking, but not in this account
            if who:
                b = T.link_booking(account_id, ref, **who); results.append(('link_booking', b))
                if b.get('ok'):
                    notes.append(f'{ref} was added to the account (made by phone, agency or a booking platform): '
                                 'tell the caller, then answer.')
                    b = b['booking']
                else:
                    notes.append('The name or digits do not match the booking: say you could not add it and ask again. '
                                 'Reveal nothing about it.')
            else:
                notes.append(f'NOT IN ACCOUNT: {ref} is not in the caller\'s account. Say NOTHING about it (not even that '
                             'it exists). Offer to add it: ask for the last name on the booking or the last 4 digits of its '
                             'phone number (link_booking).')
        else:
            results.append(('find_booking', b))
        if b.get('ok'):
            kw = dict(who, account_id=account_id)
            if CANCEL.search(t):
                results.append(('quote_cancellation', T.quote_cancellation(ref, **kw)))
                notes.append('Tell the caller the charge and refund BEFORE cancelling, and ask them to confirm.')
            hour = re.search(r'(?:الساعة|لحد|until)\s*(\d{1,2})', t)
            if re.search(r'أخرج|اخرج|الخروج|أفضل|افضل|late check', t, re.I) and hour:
                h = int(hour.group(1)); h = h + 12 if h < 9 else h           # "4" means 4 PM
                results.append(('late_checkout_quote', T.late_checkout_quote(ref, f'{h:02d}:00', **kw)))
            if re.search(r'نقط|نقاط|points|مستوى|مستوايا', t, re.I):
                results.append(('loyalty_status', T.loyalty_status(ref, **kw)))
    elif MINE.search(t) or MANAGE.search(t):
        mine = T.my_bookings(account_id); results.append(('my_bookings', mine))
        if mine.get('ok') and not mine['bookings']:
            notes.append('The account has no bookings. If the caller booked by phone, through an agency or a booking '
                         'platform, offer to add it: booking reference + last name or the last 4 digits of its phone.')
        elif mine.get('ok'):
            notes.append('Confirm with the caller which of the account\'s bookings they mean before acting on it.')

    code = re.search(r'\b(PEARL\d+)\b', t.upper())
    if code: results.append(('check_discount_code', T.check_discount_code(code.group(1), account_id=account_id)))
    rt = next((name for pat, name in TYPES if re.search(pat, t, re.I)), None)
    dates = parse_dates(t, today)
    if rt and dates and not ref:
        g = next((n for pat, n in GUESTS if re.search(pat, t, re.I)), None)
        if g is None:
            notes.append(f'Ask how many guests (adults and children) before quoting {rt} for {dates[0]}..{dates[1]}.')
        else:
            results.append(('check_availability', T.check_availability(rt, str(dates[0]), str(dates[1]), g,
                                                                    discount_code=code.group(1) if code else None,
                                                                    account_id=account_id)))
    elif rt and not dates and re.search(r'عايز|عاوز|أحجز|احجز|فاضي|متاح|book|available', t, re.I) and not ref:
        notes.append(f'Ask for the check-in and check-out dates and the number of guests before checking {rt} availability.')
    return results, notes
