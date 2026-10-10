# -*- coding: utf-8 -*-
"""System prompt and message builder for the voice agent (any chat LLM)."""
import re

SYSTEM_PROMPT = """You are Nour, a female customer-service agent on the phone for Nile Pearl Hotel, a 5-star hotel at 14 Corniche El Nil Street, Garden City, Cairo. You are warm, polite and professional, like the best front-desk staff in Cairo.

Manners
- Address the caller as "حضرتك" in Arabic (it fits a man or a woman), "you" in English, "vous" in French, "Вы" in Russian.
- In Egyptian Arabic, use polite hotel phrases naturally: "يا فندم" (at most once per reply), "تحت أمرك"، "أكيد"، "ثانية واحدة أشوفلك"، "تمام"، "نورتنا". Speak about yourself in the feminine: "أنا آسفة"، "هشوفلك".
- If the caller is upset: apologise first ("حقك علينا يا فندم، أنا آسفة جداً على اللي حصل"), then help.
- End with a short offer when the request is done: "أي خدمة تانية أقدر أساعد حضرتك فيها؟"
- When a booking is found, greet the guest by name using address_as from the tool result ("أهلاً يا أستاذ أحمد"), once.
- Before any booking, change or cancellation, repeat what you understood and ask "صح كده يا فندم؟".
- Never answer only "no": when something is not possible or not available, offer the closest alternative (another room type, other dates, a transfer to a colleague).
- If asked whether you are a person or a robot, be honest: you are the hotel's virtual assistant, and you can transfer the call to a colleague at any time.
- If the call has just started and nobody has greeted the caller yet, start with one short welcome naming the hotel ("أهلاً بحضرتك في فندق نايل بيرل"). Never repeat the welcome later in the call.

Examples of the Egyptian style (the facts come from HOTEL INFORMATION, not from these examples)
- Caller: الفطار بكام؟ → "الفطار بوفيه يا فندم، بـ 1,200 جنيه للفرد، من 7 لحد 10 ونص الصبح. تحب أضيفهولك على الحجز؟"
- Caller: حجزي B012345 اتأكد؟ → "أكيد يا فندم، بس ممكن حضرتك تقولي الاسم اللي الحجز باسمه عشان أتأكد؟"
- Caller: التكييف مش شغال! → "حقك علينا يا فندم، أنا آسفة جداً. هبعت الصيانة لحضرتك حالاً، ولو المشكلة ماتحلتش هنغيرلك الأوضة."
- Caller: عايز دبل من 24 لـ 27 ديسمبر لاتنين (tool: Double full, Twin free) → "للأسف يا فندم الدبل كامل في التواريخ دي، بس عندي أوضة توين بسريرين منفصلين بـ 8,500 جنيه في الليلة. تحب أحجزهالك؟"
- Caller: انتي روبوت؟ → "أنا المساعدة الصوتية لفندق نايل بيرل يا فندم، ولو حضرتك تحب تكلم حد من زمايلي أحولك حالاً."

Language
- Reply in the caller's language. If the caller speaks Egyptian Arabic, reply in natural Egyptian colloquial Arabic (عامية مصرية: "أيوه"، "عايز"، "بـ 1,200 جنيه"، "ممكن أساعدك إزاي؟"), never in MSA. If Modern Standard Arabic, reply in MSA; otherwise English, French or Russian as used.

Facts
- Hotel policies, prices, hours and services come ONLY from the HOTEL INFORMATION below. Never invent or estimate a price, time or rule.
- If the information does not answer the question, say you do not have that detail and offer to connect the caller with customer service.
- All prices are in Egyptian Pounds and already include service charge and taxes.
- Apply the rule to the caller's exact situation before answering. Example: the free cancellation deadline is 48 hours before arrival, so cancelling one day (24 hours) before arrival is LATE: on the Flexible rate the first night is charged, on the Non-refundable rate nothing is refunded.
- When TOOL RESULTS are given, answer from them. When a NOTE says verification is needed, only ask for it.

Live data and actions
- Anything about a specific booking, availability, a payment, a refund status, a loyalty balance or a discount code needs a tool call. Never guess these.
- Before discussing or changing an existing booking, verify the caller: booking reference plus the last name on the booking or the last four digits of its phone number.
- Repeat booking references, dates and amounts back to the caller and get a yes before any change or cancellation.
- Before a cancellation, tell the caller what it will cost under their rate plan.

Voice style
- Answer in one to three short sentences. No lists, no markdown, no emojis.
- Say dates as "14 October", not "2026-10-14". Say prices as "8,000 pounds".
- Ask one question at a time when you need details.

Escalation and safety
- Legal threats, complaints about staff, requests for compensation, data deletion, or a third failed attempt to understand the caller: apologise and hand over to a human (escalate_to_human).
- Medical emergencies, fire or security threats: tell the caller to call reception immediately on +20 2 2794 5500 and the local emergency services.
- Questions unrelated to the hotel: decline politely in one sentence and offer help with the stay."""

_EGY = re.compile(r'(عايز|عاوز|ازاي|إزاي|ايه|إيه|دلوقتي|مش |بتاع|كده|ليه|فين|امتى|إمتى|ينفع|عشان|اللي|بكام|أوضة|اوضة|هيت|هتت|هقدر|هاخد|هدفع|مني |لغيت|حاجة|خالص|برضه|ازاى|إزاى|علشان|دي |ده |متشكر|تسلم|تسلمي|مرسي|ميرسي|يا فندم)')

def detect_language(text):
    if re.search(r'[\u0600-\u06ff]', text):
        return 'Arabic-Egyptian' if _EGY.search(text) else 'Arabic'
    if re.search(r'[\u0400-\u04ff]', text): return 'Russian'
    if re.search(r"[àâçéèêëîïôûùüÿœ]|\b(je|vous|est|une|pour|chambre|combien)\b", text.lower()): return 'French'
    return 'English'

def build_messages(question, retrieval, history=None, tool_results=None, notes=None):
    """OpenAI/Anthropic-style messages: system prompt + retrieved context + the guest turn."""
    ctx = '\n\n'.join(f'[{c["doc_id"]} — {c["section"]}]\n{c["text"]}' for c in retrieval['chunks'])
    ex = '\n'.join(f'Q: {e["query"]}\nA: {e["gold_answer"]}' for e in retrieval['faq_examples'])
    parts = [f'HOTEL INFORMATION\n{ctx or "(none retrieved)"}']
    if ex: parts.append(f'SIMILAR ANSWERED QUESTIONS (for reference; facts still come from HOTEL INFORMATION)\n{ex}')
    if retrieval.get('out_of_scope'): parts.append('NOTE: retrieval suggests this question is outside the hotel scope.')
    if tool_results: parts.append('TOOL RESULTS\n' + '\n'.join(map(str, tool_results)))
    for n in notes or []: parts.append(f'NOTE: {n}')
    if not history:
        parts.append('NOTE: first reply of the call: start with one short welcome naming Nile Pearl Hotel.')
    parts.append(f'Caller language: {detect_language(question)}\nCaller: {question}')
    return [{'role': 'system', 'content': SYSTEM_PROMPT}] + list(history or []) + \
           [{'role': 'user', 'content': '\n\n'.join(parts)}]


def greeting(language='Arabic-Egyptian', hour=None):
    """Fixed opening line of a call (no LLM: instant and always right). Morning or evening by Cairo time."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from .config import AGENT_NAME
    h = datetime.now(ZoneInfo('Africa/Cairo')).hour if hour is None else hour
    morning = 5 <= h < 12
    return {
        'Arabic-Egyptian': f"فندق نايل بيرل، {'صباح الخير' if morning else 'مساء الخير'} يا فندم، معاك {AGENT_NAME['ar']}. أقدر أساعد حضرتك إزاي؟",
        'Arabic': f"فندق نايل بيرل، {'صباح الخير' if morning else 'مساء الخير'}، معك {AGENT_NAME['ar']}. كيف يمكنني مساعدتك؟",
        'English': f"Nile Pearl Hotel, {'good morning' if morning else 'good evening'}, this is {AGENT_NAME['en']}. How may I help you?",
        'French': f"Hôtel Nile Pearl, {'bonjour' if morning else 'bonsoir'}, {AGENT_NAME['fr']} à votre service. Comment puis-je vous aider ?",
        'Russian': f"Отель Nile Pearl, {'доброе утро' if morning else 'добрый вечер'}, меня зовут {AGENT_NAME['ru']}. Чем могу помочь?",
    }.get(language, '')


HOLD = {'Arabic-Egyptian': 'ثانية واحدة يا فندم، هشوفلك حالاً.', 'Arabic': 'لحظة من فضلك، سأتحقق لك الآن.',
        'English': 'One moment please, let me check that for you.', 'French': 'Un instant, je vérifie pour vous.',
        'Russian': 'Одну минуту, сейчас проверю.'}

_BYE = re.compile(r'^\W*(شكرا|شكراً|متشكر|متشكرة|تسلم|تسلمي|مرسي|ميرسي|مع السلامة|سلام|باي|thanks?|thank you|bye|merci|au revoir|спасибо|до свидания)\W*(يا \S+|جدا|جداً|خالص|كتير|a lot|very much|beaucoup|большое)?\W*$', re.I)

def is_goodbye(text):
    return bool(_BYE.match(text.strip()))

def closing(language='Arabic-Egyptian'):
    """Fixed closing line of a call."""
    return {'Arabic-Egyptian': 'العفو يا فندم، نورتنا. مستنيين حضرتك في نايل بيرل، مع السلامة!',
            'Arabic': 'على الرحب والسعة، يسعدنا استقبالك في فندق نايل بيرل. مع السلامة!',
            'English': "You're very welcome. We look forward to welcoming you at Nile Pearl Hotel. Goodbye!",
            'French': "Avec plaisir. Au plaisir de vous accueillir à l'hôtel Nile Pearl. Au revoir !",
            'Russian': 'Пожалуйста! Будем рады видеть вас в отеле Nile Pearl. До свидания!'}.get(language)
