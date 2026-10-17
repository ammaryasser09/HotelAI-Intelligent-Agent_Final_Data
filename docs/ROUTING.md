# Routing: who answers what

Anything that can change between two phone calls comes from the **database**. Anything printed
in a brochure comes from the **knowledge base (RAG)**. Never answer availability, a specific
booking, a payment, a points balance or a code check from RAG.

| The guest asks | Route | Source |
|---|---|---|
| What time is check-in? Is there a pool? Pets? Cancellation policy? | **RAG** | `knowledge_base/*.txt` |
| How much is a Deluxe room? What room types are there? | **RAG** or **DB** | `room_types.txt` = `room_types` (same numbers, checked) |
| What's on the menu? How much is a burger? | **RAG** or **DB** | `in_room_dining_menu.txt` = `menu_items` |
| How far is the airport? A pharmacy nearby? | **RAG** | `location_and_surroundings.txt` |
| Is a Double free 12-15 November? | **DB** | `free_rooms()` - query 1 in `database/queries.sql` |
| What will three nights cost? | **DB** | `room_types.base_price` x nights (`pricing_tiers` for special rates) |
| Book it for me | **DB write** | availability again, the guest's "yes", then insert - query 4 |
| My booking B000037, is it confirmed? Did my payment go through? | **DB: a booking in the guest's account** (or linked after the reference check) | `my_bookings` - query 2 |
| What would cancelling cost me now? | **DB** | query 3 (rate plan + 48-hour rule) |
| Cancel it | **DB write** | quote, the guest's "yes", then update - query 3b |
| Can I stay until 5 PM? How many points do I have? | **DB** | `loyalty_members`, `loyalty_tiers`, `fees` - query 5 |
| Is code PEARL100 valid? | **DB** | `discount_codes` - query 6 |
| Order a burger to my room | **DB write** | `menu_items` + delivery charge `services` S002 - query 7 |
| I want to complain / I need a vegetarian breakfast | **DB write** | `create_request`: a ticket in `customer_requests` (`Complaint` / `Special Request` with its category) - query 10 |
| What's the weather? Book me a flight | **REFUSE** | one polite sentence, offer hotel help |
| I'm suing you / your staff was rude / I want compensation / delete my data / repeated misunderstanding | **ESCALATE** | hand to a person; `calls.status = 'escalated'` |
| Fire, someone collapsed, a stranger at the door | **EMERGENCY** | first sentence: call reception +20 2 2794 5500 now |

## Four rules the agent never breaks

1. **The login decides whose bookings.** A logged-in guest sees only the bookings of the account
   (`v_account_bookings`), with no further questions; the account comes from the session, never from
   the conversation. A booking made by phone, agency or a booking platform is added first
   (`link_booking`): the reference must match the last name (English or Arabic) or the last 4 digits
   of the phone on the booking. A visitor gets general answers only and is asked to log in.
2. **Quote before acting.** Before a cancellation or a change, tell the guest what it costs and get a "yes".
3. **Read back numbers.** Repeat the booking reference, dates and amounts before any write.
4. **One "today".** Use `hotel_today()` / `app_settings.system_date`, never the machine clock, while the demo data is in use.

`rag/hotel_faq_gold.csv` marks each question with `requires_tool`: true only when the answer
needs live data or an action (a specific booking, availability, a payment, a balance, a code,
a change). A general policy question is false: its answer is fixed text in the knowledge base.
