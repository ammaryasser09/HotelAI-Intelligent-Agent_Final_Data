# -*- coding: utf-8 -*-
"""
Code-side router: the code decides which tools to run, the LLM only phrases the answer.

Small models (7B and below) often skip tool calls or guess. This router reads the caller's
message with simple rules, runs the needed tools itself, and hands the results to the LLM
as TOOL RESULTS, together with notes such as "verification needed". The LLM can still call
tools on its own; the router only makes the common cases reliable.
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

def route(text, today=None):
    today = today or T.SYSTEM_DATE
    t = text.translate(AR_DIGITS)
    results, notes = [], []
    ref = re.search(r'\bB\d{6}\b', t.upper())
    if ref:
        name = re.search(r'(?:باسم|الاسم|اسمي|اسم العيلة|last name is|name is)\s*[:،]?\s*([^\s،,.؟?]+)', t)
        phone = re.search(r'(?:آخر|اخر)\s*(?:أربع|اربع|4)\s*(?:أرقام|ارقام)\s*(\d{4})|last (?:four|4) digits?\s*(\d{4})', t)
        who = {'last_name': name.group(1)} if name else ({'phone_last4': phone.group(1) or phone.group(2)} if phone else None)
        if not who:
            notes.append(f'VERIFICATION NEEDED for {ref.group()}: ask for the last name on the booking or the last 4 digits '
                         'of its phone number. Say NOTHING about the booking (not even that it exists) until then.')
        else:
            b = T.find_booking(ref.group(), **who); results.append(('find_booking', b))
            if b.get('ok'):
                if re.search(r'ألغي|الغي|إلغاء|الغاء|لغيت|cancel|أكنسل|اكنسل', t, re.I):
                    results.append(('quote_cancellation', T.quote_cancellation(ref.group(), **who)))
                    notes.append('Tell the caller the charge and refund BEFORE cancelling, and ask them to confirm.')
                hour = re.search(r'(?:الساعة|لحد|until)\s*(\d{1,2})', t)
                if re.search(r'أخرج|اخرج|الخروج|أفضل|افضل|late check', t, re.I) and hour:
                    h = int(hour.group(1)); h = h + 12 if h < 9 else h           # "4" means 4 PM
                    results.append(('late_checkout_quote', T.late_checkout_quote(ref.group(), f'{h:02d}:00', **who)))
                if re.search(r'نقط|نقاط|points|مستوى|مستوايا', t, re.I):
                    results.append(('loyalty_status', T.loyalty_status(ref.group(), **who)))
            elif b.get('reason') == 'IDENTITY_NOT_VERIFIED':
                notes.append('The name or digits do not match: say you could not verify, ask again. Reveal nothing.')
    code = re.search(r'\b(PEARL\d+)\b', t.upper())
    if code: results.append(('check_discount_code', T.check_discount_code(code.group(1))))
    rt = next((name for pat, name in TYPES if re.search(pat, t, re.I)), None)
    dates = parse_dates(t, today)
    if rt and dates and not ref:
        g = next((n for pat, n in GUESTS if re.search(pat, t, re.I)), None)
        if g is None:
            notes.append(f'Ask how many guests (adults and children) before quoting {rt} for {dates[0]}..{dates[1]}.')
        else:
            results.append(('check_availability', T.check_availability(rt, str(dates[0]), str(dates[1]), g)))
    elif rt and not dates and re.search(r'عايز|عاوز|أحجز|احجز|فاضي|متاح|book|available', t, re.I) and not ref:
        notes.append(f'Ask for the check-in and check-out dates and the number of guests before checking {rt} availability.')
    return results, notes
