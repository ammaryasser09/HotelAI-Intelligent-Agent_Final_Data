// Demo data taken from database/seed (hotel "today" = 2026-09-19). Same shapes as the FastAPI responses.
import { ApiError } from './client.js'
import { callActions, callMessages } from './mockCalls.js'

const TODAY = '2026-09-19'
const PASSWORD = 'NilePearl@2026'

const accounts = [
  { account_id: 44, role: 'Guest', full_name: 'Fatma Hassan', email: 'fatma.hassan55@example.com', customer_id: 'C000055', email_verified: true },
  { account_id: 3, role: 'Staff', full_name: 'Nada Samir', email: 'nada.samir@nilepearlhotel.example', customer_id: null, email_verified: true },
  { account_id: 1, role: 'Admin', full_name: 'Hala Mansour', email: 'admin@nilepearlhotel.example', customer_id: null, email_verified: true }
]

const roomTypes = [
  ['RT001', 'Single', 'Comfortable room suitable for one guest', 1, 6000, 28, 'single'],
  ['RT002', 'Double', 'Comfortable room with one double bed for two guests', 2, 8000, 34, 'double'],
  ['RT003', 'Twin', 'Room with two separate beds', 2, 8500, 34, 'twin'],
  ['RT004', 'Deluxe', 'Spacious room with premium facilities', 3, 12000, 45, 'deluxe'],
  ['RT005', 'Family', 'Large room suitable for families', 4, 14000, 60, 'family'],
  ['RT006', 'Suite', 'Luxury suite with separate living area and Nile view', 4, 20000, 85, 'suite']
].map(([room_type_id, room_type_name, description, capacity, base_price, size_sqm, img]) => ({
  room_type_id, room_type_name, description, capacity, base_price, size_sqm,
  image_nile: `/static/rooms/${img}.webp`, image_city: img === 'suite' ? null : `/static/rooms/${img}_city.webp`
}))
const freeNov12 = { Single: 6, Double: 3, Twin: 4, Deluxe: 0, Family: 0, Suite: 0 }
const freeOther = { Single: 4, Double: 5, Twin: 3, Deluxe: 2, Family: 2, Suite: 1 }

const nightsBetween = (a, b) => Math.round((new Date(b) - new Date(a)) / 86400000)
const r2 = (n) => Math.round(n * 100) / 100

function booking(id, type, room, view, ci, co, adults, children, status, plan, rate, paid) {
  const nights = nightsBetween(ci, co)
  const total = r2(rate * nights)
  return {
    booking_id: id, access: 'own', booking_status: status, rate_plan: plan, check_in: ci, check_out: co, nights, adults, children,
    room_type_name: type, room_number: room, view, price_per_night: rate, total_amount: total, discount_source: null, discount_amount: 0,
    amount_due: total, payment_status: 'Paid', amount_paid: paid ?? total, refund_amount: 0, payment_due_at: null
  }
}

const db = {
  bookings: [
    booking('B003268', 'Twin', 907, 'City', '2026-09-21', '2026-10-02', 1, 0, 'Confirmed', 'Flexible', 8095.46, 8095.46),
    booking('B001453', 'Twin', 706, 'City', '2026-12-28', '2027-01-09', 1, 0, 'Confirmed', 'Flexible', 10515.60, 10515.60),
    booking('B006719', 'Family', 1403, 'Nile', '2026-07-04', '2026-07-13', 3, 0, 'Completed', 'Flexible', 15173.70),
    booking('B019359', 'Deluxe', 1302, 'Nile', '2026-04-14', '2026-04-17', 2, 1, 'Completed', 'Flexible', 13806.54),
    booking('B014019', 'Twin', 801, 'Nile', '2025-08-18', '2025-08-21', 2, 0, 'Completed', 'Non-refundable', 8044.84)
  ],
  channel: { B003268: 'Booking Platform', B001453: 'Website', B006719: 'Website', B019359: 'Mobile App', B014019: 'Website' },
  myRequests: [],
  nextBooking: 20003,
  nextRequest: 15184,
  arrivals: [
    ['B005158', 'Fatma', 'Gamal', 201, 'Single', 10, 1, 0, 77100.00, 7710.00],
    ['B009701', 'William', 'Miller', 206, 'Single', 1, 1, 0, 6633.80, 6633.80],
    ['B012985', 'Yousef', 'Khalil', 208, 'Single', 12, 1, 0, 92649.24, 7720.77],
    ['B010425', 'Hugo', 'Richard', 302, 'Single', 8, 1, 0, 49007.20, 6125.90],
    ['B000170', 'Hassan', 'Hassan', 501, 'Double', 5, 2, 0, 41249.90, 8249.98],
    ['B001552', 'Ahmad', 'Mansour', 506, 'Double', 13, 1, 1, 100647.69, 7742.13],
    ['B004692', 'Ahmed', 'Alenezi', 507, 'Double', 10, 2, 0, 95673.00, 9567.30],
    ['B010383', 'Ahmad', 'Saleh', 709, 'Twin', 11, 1, 0, 101790.04, 101790.04],
    ['B013274', 'Amr', 'Hassan', 805, 'Twin', 10, 1, 0, 93513.90, 9351.39],
    ['B014655', 'Khalid', 'Alzahrani', 806, 'Twin', 6, 1, 0, 58782.60, 58782.60],
    ['B015269', 'James', 'Roberts', 810, 'Twin', 4, 2, 0, 30542.72, 7635.68],
    ['B001503', 'James', 'Roberts', 1006, 'Deluxe', 2, 3, 0, 21897.98, 10948.99],
    ['B002355', 'Nour', 'Fathy', 1009, 'Deluxe', 10, 1, 2, 118241.40, 11824.14],
    ['B006299', 'Mahmoud', 'Ibrahim', 1101, 'Deluxe', 10, 2, 0, 111016.10, 11101.61],
    ['B006778', 'Saeed', 'Alkaabi', 1104, 'Deluxe', 2, 3, 0, 20961.04, 10480.52],
    ['B000819', 'James', 'Brown', 1401, 'Family', 3, 2, 0, 41390.25, 13796.75],
    ['B003480', 'Saeed', 'Alnuaimi', 1405, 'Family', 1, 2, 1, 17549.47, 17549.47],
    ['B004898', 'Sherif', 'Fathy', 1408, 'Family', 10, 2, 2, 171519.10, 17151.91],
    ['B011406', 'Salma', 'Youssef', 1409, 'Family', 5, 1, 0, 64721.70, 12944.34],
    ['B004450', 'Mostafa', 'Hamed', 1506, 'Suite', 4, 1, 0, 102178.72, 25544.68],
    ['B009615', 'Fahad', 'Alotaibi', 1507, 'Suite', 9, 4, 0, 158282.01, 158282.01],
    ['B001788', 'Fatima', 'Alrashid', 1608, 'Suite', 10, 1, 0, 244188.00, 244188.00]
  ].map(([booking_id, first_name, last_name, room_number, room_type_name, nights, adults, children, amount_due, amount_paid]) => ({
    booking_id, first_name, last_name, room_type_name, room_number, check_in: TODAY,
    check_out: new Date(Date.parse(TODAY) + nights * 86400000).toISOString().slice(0, 10), nights, adults, children,
    amount_due, amount_paid, balance_due: r2(amount_due - amount_paid), checked_in_at: null
  })),
  inHouse: [
    ['B002357', 'Arthur', 'Richard', 501, 'Double', '2026-09-15', 4, 39150.56, 9787.64],
    ['B019394', 'Anna', 'Fischer', 507, 'Double', '2026-09-18', 1, 8812.67, 8812.67],
    ['B010390', 'Mariam', 'Hassan', 709, 'Twin', '2026-09-14', 5, 41686.05, 8337.21],
    ['B013412', 'Louis', 'Thomas', 1003, 'Twin', '2026-09-12', 7, 75338.69, 10762.67],
    ['B004104', 'William', 'Smith', 1104, 'Deluxe', '2026-09-15', 4, 61083.80, 15270.95],
    ['B007318', 'Olivia', 'Thomas', 1401, 'Family', '2026-09-12', 7, 96511.24, 96511.24],
    ['B015966', 'Gabriel', 'Martin', 1405, 'Family', '2026-09-18', 1, 13167.96, 13167.96],
    ['B007805', 'Mahmoud', 'Fathy', 1005, 'Twin', '2026-09-11', 14, 133474.32, 9533.88]
  ].map(([booking_id, first_name, last_name, room_number, room_type_name, check_in, nights, amount_due, amount_paid]) => ({
    booking_id, first_name, last_name, room_type_name, room_number, check_in,
    check_out: new Date(Date.parse(check_in) + nights * 86400000).toISOString().slice(0, 10), nights, adults: 1, children: 0,
    amount_due, amount_paid, balance_due: r2(amount_due - amount_paid), checked_in_at: check_in + 'T15:20:00+02:00'
  })),
  tickets: [
    ['REQ015183', 'Urgent', 'Staff Callback', 'Questions about the charges on the bill before check-out', 'James Davies', 1403, 'Open', null, '2026-09-19T11:52:27'],
    ['REQ015014', 'Urgent', 'Complaint', 'Air conditioning not working', 'Lea Richard', null, 'Open', null, '2026-09-14T15:25:58'],
    ['REQ015033', 'Urgent', 'Complaint', 'No hot water in the bathroom', 'Dina Youssef', 1403, 'Open', null, '2026-09-10T15:25:58'],
    ['REQ015046', 'Urgent', 'Complaint', 'Elevator out of service', 'Noura Alzahrani', null, 'In Progress', 'Yasmin Lotfy', '2026-09-08T15:25:58'],
    ['REQ004383', 'Normal', 'Room Service', 'I would like to order room service.', 'Tarek Zaki', 1207, 'In Progress', 'Yasmin Lotfy', '2026-09-19T18:10:30'],
    ['REQ013737', 'Normal', 'Housekeeping', 'My room needs cleaning.', 'James Jones', 1407, 'In Progress', 'Nada Samir', '2026-09-19T16:23:13'],
    ['REQ015181', 'Normal', 'Maintenance', 'The AC in room 1106 is not cooling', 'Nour Fathy', 1106, 'In Progress', 'Omar Hegazy', '2026-09-19T09:12:15'],
    ['REQ015180', 'Normal', 'Maintenance', 'The bedside lamp in room 1504 is not working', 'Omar Hamed', 1504, 'Open', null, '2026-09-19T07:40:00'],
    ['REQ015182', 'Normal', 'Discount Request', 'Honeymoon, 5 nights from 18 December 2026, 2 adults: asks for a discount', 'Hassan Fathy', null, 'Open', null, '2026-09-19T10:06:18'],
    ['REQ015177', 'Normal', 'Special Request', 'Birthday room decoration and a cake', 'Sofia Volkov', 1209, 'Open', null, '2026-09-18T19:45:36'],
    ['REQ004570', 'Normal', 'Housekeeping', 'My room needs cleaning.', 'Hugo Richard', 1302, 'Open', null, '2026-09-17T06:45:23'],
    ['REQ015026', 'Normal', 'Complaint', 'Pool closed without notice', 'Tarek Ibrahim', 803, 'In Progress', 'Nada Samir', '2026-09-16T15:25:58'],
    ['REQ014354', 'Normal', 'Housekeeping', 'My room needs cleaning.', 'Isla Brown', 1402, 'Open', null, '2026-09-13T23:55:55'],
    ['REQ001868', 'Normal', 'Housekeeping', 'Can someone clean my room?', 'Hamdan Alshamsi', 1209, 'Open', null, '2026-09-12T06:21:58'],
    ['REQ015042', 'Normal', 'Complaint', 'Request ignored by reception', 'Mostafa Nasser', 1401, 'In Progress', 'Karim Fathy', '2026-09-12T15:25:58'],
    ['REQ015060', 'Normal', 'Complaint', 'Elevator out of service', 'Hana Fathy', null, 'In Progress', 'Nada Samir', '2026-09-12T15:25:58'],
    ['REQ015034', 'Normal', 'Complaint', 'Request ignored by reception', 'Khaled Ibrahim', 1207, 'In Progress', 'Karim Fathy', '2026-09-05T15:25:58']
  ].map(([request_id, priority, request_type, request_text, guest_name, room_number, request_status, handled_by, created_at]) => ({
    request_id, priority, request_type, category: null, request_status, request_text, customer_id: null, guest_name,
    booking_id: null, room_number, call_id: null, handled_by, decision: null, created_at
  })),
  staff: [
    [1, 'Admin', 'Hala Mansour', 'admin@nilepearlhotel.example'],
    [2, 'Staff', 'Karim Fathy', 'karim.fathy@nilepearlhotel.example'],
    [3, 'Staff', 'Nada Samir', 'nada.samir@nilepearlhotel.example'],
    [4, 'Staff', 'Omar Hegazy', 'omar.hegazy@nilepearlhotel.example'],
    [5, 'Staff', 'Yasmin Lotfy', 'yasmin.lotfy@nilepearlhotel.example']
  ].map(([account_id, role, full_name, email]) => ({ account_id, role, full_name, email, is_active: true, last_login_at: null })),
  discountRequests: [
    { request_id: 'REQ015182', customer_id: 'C000081', guest_name: 'Hassan Fathy', booking_id: null, request_text: 'Honeymoon, 5 nights from 18 December 2026, 2 adults: asks for a discount', created_at: '2026-09-19T10:06:18' }
  ]
}

const call = (call_id, started_at, seconds, language, status, guest_name, booking_id, turns, actions, tickets, avg_latency_ms, extra = {}) => ({
  call_id, started_at, ended_at: new Date(Date.parse(started_at) + seconds * 1000).toISOString(), channel: 'voice', language, status,
  escalation_reason: null, visitor: !guest_name, guest_name, booking_id, assigned_to: null, turns, actions, tickets, avg_latency_ms,
  duration_seconds: seconds, ...extra
})
db.calls = [
  call('81e7f5ea-84ab-5772-a2ec-d3897054c858', '2026-09-19T11:52:18', 40, 'English', 'escalated', 'James Davies', 'B002226', 4, 1, 1, 1180, { escalation_reason: 'Guest wants to talk to someone about the charges on his bill before check-out; no one was free', summary: 'No staff free: urgent Staff Callback ticket opened (bill before check-out)' }),
  call('f5b77b93-118a-58d8-86c8-c847f17b19b9', '2026-09-19T10:30:41', 216, 'Arabic-Egyptian', 'escalated', 'Mahmoud Fathy', 'B007805', 11, 2, 0, 1108, { escalation_reason: 'The agent misunderstood twice; the guest wants the list of charges on room 1005 and asked for a person', assigned_to: 'Nada Samir', summary: 'Handed to Nada Samir (live chat): list of charges on room 1005' }),
  call('2bca871c-5a31-5320-8828-d76e9138d411', '2026-09-19T10:05:50', 40, 'Arabic-Egyptian', 'completed', 'Hassan Fathy', null, 4, 1, 1, 1210, { summary: 'Discount Request for a honeymoon in December (waiting for the administrator)' }),
  call('28ef31b4-d8f9-519e-a21a-27f0ed5c01df', '2026-09-19T09:12:04', 32, 'Arabic-Egyptian', 'completed', 'Nour Fathy', 'B006557', 4, 2, 1, 1240, { summary: 'Maintenance: the AC in room 1106 is not cooling; ticket opened' }),
  call('3165021f-5008-58a0-913b-1877985e2dae', '2026-09-19T08:20:09', 73, 'English', 'completed', 'Ahmed Saber', 'B020001', 6, 2, 0, 1320, { summary: 'New booking B020001: Double, 7-15 December, Flexible, extended-stay discount; payment link sent' }),
  call('54a26e66-6b3e-58d0-a6a6-fd392809702c', '2026-09-18T23:35:08', 28, 'Arabic-Egyptian', 'completed', 'Karim Adel', 'B007628', 4, 1, 1, 1150, { summary: 'Complaint: noise next to room 1201 at night; reception informed' }),
  call('e08ba4e0-559b-546d-9ae6-4715c2a737c5', '2026-09-18T22:41:37', 38, 'English', 'completed', null, null, 4, 1, 1, 1260, { summary: 'Emergency (medical) in room 410 from a caller who is not logged in; numbers given, Critical ticket opened' }),
  call('1dea0079-c847-55ac-86d2-14aa240bb51b', '2026-09-18T19:45:20', 32, 'Russian', 'completed', 'Sofia Volkov', 'B006486', 4, 2, 1, 1190, { summary: 'Special request on B006486: birthday decoration and a cake' }),
  call('3d5f7820-e698-51bb-a99a-78f75b4b9b31', '2026-09-18T16:30:02', 39, 'English', 'completed', 'Emma Fischer', 'B016453', 4, 1, 0, 1170, { summary: 'Booking B016453 (made through a travel agent) added to the account' }),
  call('092d8a57-3f62-5936-a243-41216236ab97', '2026-09-18T14:02:26', 61, 'English', 'completed', 'Michael Davis', 'B020002', 5, 3, 0, 1371, { summary: 'New booking B020002 with personal code PEARL5150: Twin, 23-26 October, Flexible' }),
  call('5c0639b0-c4c2-523d-a354-3e8254cb9218', '2026-09-18T12:15:30', 32, 'Arabic-Egyptian', 'completed', null, null, 5, 0, 0, 1184, { summary: 'Visitor asked about a booking: asked to log in; gym question answered' }),
  call('cf86e48c-cc59-5015-a115-6a1c37338aeb', '2026-09-17T20:10:44', 15, 'French', 'abandoned', null, null, 3, 0, 0, 905, { summary: 'The caller hung up before saying what they needed' }),
  call('ff5f9a87-9c44-5eca-a359-dbedc193b77b', '2026-09-17T17:40:55', 34, 'Arabic', 'completed', 'Salma Nabil', 'B003887', 5, 2, 0, 1391, { summary: 'Payment status of B003887: deposit paid, balance at the hotel' }),
  call('3a3c5573-87ae-574f-b7f8-5701e0af0466', '2026-09-17T06:05:12', 34, 'Arabic', 'completed', 'Yara Mahmoud', 'B010781', 4, 1, 1, 1471, { summary: 'Emergency (smoke) on floor 8; evacuation advice and numbers given, Critical ticket opened' }),
  call('ca7e9112-9797-5250-bb1b-2b278e6167a5', '2026-09-16T13:20:47', 38, 'Arabic', 'completed', 'Reem Alqahtani', null, 5, 1, 1, 812, { summary: 'Discount Request for three rooms in November (rejected on 17 September)' }),
  call('252dec86-4087-5dc8-b676-bb6988424c19', '2026-09-15T21:05:33', 47, 'French', 'completed', 'Manon Robert', null, 5, 1, 1, 1224, { summary: 'Discount Request from a student (approved on 16 September: code PEARL6290)' }),
  call('d19c9b18-425b-558e-8ec2-68bfc47f8833', '2026-09-14T19:30:15', 47, 'English', 'completed', 'Michael Davis', null, 5, 1, 1, 981, { summary: 'Discount Request from a returning guest (approved on 15 September: code PEARL5150)' })
]

const chatMessages = [
  ['guest', 'عايز أعرف الحساب بتاعي لحد النهارده.', null],
  ['agent', 'أستاذ محمود، حجزك B007805 أوضة توين من 11 لـ 25 سبتمبر على السعر المرن: الليلة الأولى مدفوعة أونلاين والباقي بيتدفع في الفندق. تحب أقولك المبلغ الباقي؟', 1155],
  ['guest', 'لا مش ده، أنا قصدي الحاجات اللي طلبتها على الأوضة.', null],
  ['agent', 'تقصد إنك عايز تطلب روم سيرفس؟ أقدر أقولك المنيو.', 1294],
  ['guest', 'لأ يا عم، مش فاهمني. خليني أكلم حد من الفندق.', null],
  ['agent', 'آسف إني مافهمتكش صح. هحوّلك دلوقتي لحد من فريق الفندق في نفس الشات، وهيشوف كلامنا من الأول فمش هتحتاج تعيد.', 876],
  ['system', 'Nada Samir (reception) joined the chat.', null],
  ['staff', 'أهلاً أستاذ محمود، معاك ندى من الاستقبال. حضرتك عايز كشف بالطلبات اللي اتحسبت على أوضة 1005، صح؟', null],
  ['guest', 'أيوه بالظبط.', null]
].map(([role, content, latency_ms], i) => ({ turn_no: i + 1, role, content, latency_ms, created_at: new Date(Date.parse('2026-09-19T10:30:45') + i * 20000).toISOString() }))

const monthly = [['2025-10', 46829147, 4044], ['2025-11', 46720850, 3981], ['2025-12', 48908927, 4194], ['2026-01', 44542950, 3884], ['2026-02', 43776703, 3740], ['2026-03', 44973378, 3979], ['2026-04', 45414026, 4015], ['2026-05', 46803025, 4074], ['2026-06', 45946437, 3898], ['2026-07', 48470255, 4226], ['2026-08', 47338233, 4141], ['2026-09', 44388856, 3944]]

function stats(from, to) {
  const daily = []
  for (let d = new Date(from); d <= new Date(to); d = new Date(d.getTime() + 86400000)) {
    const key = d.toISOString().slice(0, 7)
    const m = monthly.find(([k]) => k === key)
    const days = new Date(d.getUTCFullYear(), d.getUTCMonth() + 1, 0).getDate()
    const sold = m ? Math.round(m[2] / days) : 0
    daily.push({ day: d.toISOString().slice(0, 10), rooms_sold: sold, occupancy: r2(sold / 146 * 100) / 100, revenue: m ? r2(m[1] / days) : 0 })
  }
  return {
    date_from: from, date_to: to, rooms: 146, room_nights_sold: 3904, occupancy: 0.8913, revenue: 45083020.0, adr: 11548.01, revpar: 10292.92,
    bookings_made: 2, cancellation_rate: 0.1809,
    by_channel: [['Website', 1259, 13992156], ['Booking Platform', 954, 10673399], ['Mobile App', 822, 9902195], ['Phone', 525, 6382773], ['Travel Agent', 344, 4132497]].map(([name, room_nights, revenue]) => ({ name, room_nights, revenue })),
    by_room_type: [['Deluxe', 874, 11269113], ['Family', 582, 8695516], ['Suite', 357, 7725501], ['Twin', 806, 7401210], ['Double', 820, 6997889], ['Single', 465, 2993791]].map(([name, room_nights, revenue]) => ({ name, room_nights, revenue })),
    daily, open_tickets: { Normal: 126, Urgent: 4 }, avg_resolution_hours: null
  }
}

const delay = (ms) => new Promise((r) => setTimeout(r, ms))
const fail = (status, reason, extra = {}) => { throw new ApiError(status, { reason, ...extra }) }
const clone = (x) => JSON.parse(JSON.stringify(x))

function whoAmI(token) {
  const acc = accounts.find((a) => `mock-${a.account_id}` === token)
  if (!acc) fail(401, 'NOT_LOGGED_IN')
  return acc
}

function cancellationQuote(b) {
  if (!['Pending', 'Confirmed'].includes(b.booking_status)) fail(409, 'NOT_CANCELLABLE')
  if (b.rate_plan === 'Non-refundable') {
    return { booking_id: b.booking_id, booking_status: b.booking_status, rate_plan: b.rate_plan, check_in: b.check_in, free_cancellation_until: null, is_free: false, amount_paid: b.amount_paid, charge: b.amount_paid, refund: 0 }
  }
  const until = new Date(Date.parse(b.check_in + 'T15:00:00') - 48 * 3600000)
  const isFree = until >= new Date(TODAY + 'T09:00:00')
  return { booking_id: b.booking_id, booking_status: b.booking_status, rate_plan: b.rate_plan, check_in: b.check_in, free_cancellation_until: until.toISOString().slice(0, 16), is_free: isFree, amount_paid: b.amount_paid, charge: isFree ? 0 : b.amount_paid, refund: isFree ? b.amount_paid : 0 }
}

export async function mockRequest(method, fullPath, body, token) {
  await delay(150)
  const [path, qs] = fullPath.split('?')
  const q = Object.fromEntries(new URLSearchParams(qs || ''))
  const route = `${method} ${path}`
  let m

  if (route === 'POST /auth/login') {
    const acc = accounts.find((a) => a.email.toLowerCase() === String(body?.email || '').trim().toLowerCase())
    if (!acc || body?.password !== PASSWORD) fail(401, 'INVALID_CREDENTIALS')
    return { access_token: `mock-${acc.account_id}`, token_type: 'bearer', expires_in: 86400, account: acc }
  }
  if (route === 'POST /auth/signup') {
    if (accounts.find((a) => a.email.toLowerCase() === String(body.email).toLowerCase())) fail(409, 'EMAIL_ALREADY_REGISTERED')
    const acc = { account_id: 9000 + accounts.length, role: 'Guest', full_name: `${body.first_name} ${body.last_name}`, email: body.email, customer_id: null, email_verified: false }
    accounts.push(acc)
    return { access_token: `mock-${acc.account_id}`, token_type: 'bearer', expires_in: 86400, account: acc }
  }
  if (route === 'POST /auth/forgot-password') return { sent: true, expires_in_minutes: 10 }
  if (route === 'POST /auth/reset-password') {
    if (body.code !== '123456') fail(400, 'WRONG_CODE', { attempts_left: 4 })
    const acc = accounts.find((a) => a.email.toLowerCase() === String(body.email).toLowerCase() && a.role === 'Guest') || fail(400, 'CODE_EXPIRED')
    return { access_token: `mock-${acc.account_id}`, token_type: 'bearer', expires_in: 86400, account: acc }
  }
  if (route === 'GET /health') return { status: 'ok', database: 'demo data', hotel_today: TODAY, rooms: 150 }
  if (route === 'GET /room-types') return clone(roomTypes)
  if (route === 'GET /availability') {
    const rt = roomTypes.find((r) => r.room_type_name.toLowerCase() === String(q.room_type).toLowerCase()) || fail(404, 'UNKNOWN_ROOM_TYPE')
    if (q.check_in < TODAY) fail(400, 'CHECK_IN_IN_THE_PAST', { today: TODAY })
    if (Number(q.guests || 1) > rt.capacity) fail(400, 'CAPACITY_EXCEEDED', { capacity: rt.capacity })
    const nights = nightsBetween(q.check_in, q.check_out)
    const total = rt.base_price * nights
    const free = (q.check_in < '2026-11-15' && q.check_out > '2026-11-12' ? freeNov12 : freeOther)[rt.room_type_name]
    return {
      room_type: rt.room_type_name, check_in: q.check_in, check_out: q.check_out, nights, guests: Number(q.guests || 1), rooms_free: free,
      nile_view_free: Math.min(free, 2), free_room_numbers: [], images: { nile: rt.image_nile, city: rt.image_city },
      flexible: { rate_per_night: rt.base_price, total, discount: null, amount_due: total, deposit_now: rt.base_price, pay_at_hotel: total - rt.base_price },
      non_refundable: { total: r2(total * 0.85), pay_now: r2(total * 0.85) }, alternatives: []
    }
  }

  const me = whoAmI(token)
  if (route === 'GET /auth/me') return clone(me)
  if (route === 'POST /auth/verify-email') {
    if (body.code !== '123456') fail(400, 'WRONG_CODE', { attempts_left: 4 })
    me.email_verified = true
    return { access_token: token, token_type: 'bearer', expires_in: 86400, account: clone(me) }
  }
  if (route === 'POST /auth/verify-email/resend') return { sent: true, expires_in_minutes: 10 }
  if (me.role === 'Guest' && !me.email_verified && path.startsWith('/me')) fail(403, 'EMAIL_NOT_VERIFIED')

  if ((m = path.match(/^\/payments\/mock\/(B\d{6})\/pay$/))) {
    const b = db.bookings.find((x) => x.booking_id === m[1]) || fail(404, 'BOOKING_NOT_FOUND')
    const amount = b.rate_plan === 'Flexible' ? b.price_per_night : b.amount_due
    Object.assign(b, { booking_status: 'Confirmed', payment_status: 'Paid', amount_paid: amount, payment_due_at: null })
    return { booking_id: b.booking_id, booking_status: 'Confirmed', payment_status: 'Paid', amount_paid: amount }
  }
  if (path.startsWith('/me') || path === '/requests' || path === '/bookings' || path === '/requests/emergency') {
    if (me.role !== 'Guest') fail(403, 'GUESTS_ONLY')
    if (route === 'GET /me/bookings') return clone(db.bookings)
    if (route === 'GET /me/loyalty') return { member: true, tier: 'Silver', points_balance: 2149, points_worth_egp: 1000, total_stays: 41, late_checkout_until: '13:00', benefits: 'Member rate; late check-out until 1:00 PM' }
    if (route === 'GET /me/requests') return clone(db.myRequests)
    if ((m = path.match(/^\/me\/bookings\/(B\d{6})\/cancellation$/)) && method === 'GET') {
      return cancellationQuote(db.bookings.find((b) => b.booking_id === m[1]) || fail(404, 'BOOKING_NOT_FOUND'))
    }
    if ((m = path.match(/^\/me\/bookings\/(B\d{6})\/cancel$/)) && method === 'POST') {
      const b = db.bookings.find((x) => x.booking_id === m[1]) || fail(404, 'BOOKING_NOT_FOUND')
      const quote = cancellationQuote(b)
      b.booking_status = 'Cancelled'
      b.payment_status = quote.refund ? 'Refunded' : 'Paid'
      b.refund_amount = quote.refund
      return { booking_id: b.booking_id, booking_status: 'Cancelled', payment_status: b.payment_status, charge: quote.charge, refund: quote.refund }
    }
    if ((m = path.match(/^\/me\/bookings\/(B\d{6})\/change$/))) {
      const b = db.bookings.find((x) => x.booking_id === m[1]) || fail(404, 'BOOKING_NOT_FOUND')
      if (db.channel[b.booking_id] === 'Booking Platform') fail(409, 'CHANGE_ON_BOOKING_PLATFORM')
      if (b.rate_plan !== 'Flexible') fail(409, 'NON_REFUNDABLE_CANNOT_CHANGE')
      const c = method === 'GET' ? q : body
      const ci = c.check_in || b.check_in
      const co = c.check_out || b.check_out
      if (co <= ci) fail(400, 'CHECK_OUT_NOT_AFTER_CHECK_IN')
      const type = c.room_type || b.room_type_name
      const rt = roomTypes.find((r) => r.room_type_name === type) || fail(404, 'UNKNOWN_ROOM_TYPE')
      const adults = Number(c.adults ?? b.adults)
      const children = Number(c.children ?? b.children)
      if (adults + children > rt.capacity) fail(400, 'CAPACITY_EXCEEDED', { capacity: rt.capacity })
      const rate = type === b.room_type_name ? b.price_per_night : rt.base_price
      const nights = nightsBetween(ci, co)
      const total = r2(rate * nights)
      const held = b.booking_status === 'Pending' ? 0 : b.amount_paid
      const deposit = rate
      const quote = {
        booking_id: b.booking_id, booking_status: b.booking_status, room_type: type, room_number: type === b.room_type_name ? b.room_number : 1500 + nights,
        view: b.view, check_in: ci, check_out: co, nights, adults, children, price_per_night: rate, total_amount: total, discount: null, amount_due: total,
        amount_paid: Math.min(held, deposit), pay_now: b.booking_status === 'Pending' ? deposit : 0, pay_at_hotel: r2(total - Math.max(Math.min(held, deposit), b.booking_status === 'Pending' ? deposit : 0)),
        refund: r2(Math.max(held - deposit, 0)), payment_url: b.booking_status === 'Pending' ? '#' : null
      }
      if (method === 'POST') Object.assign(b, { check_in: ci, check_out: co, nights, room_type_name: type, room_number: quote.room_number, adults, children, price_per_night: rate, total_amount: total, amount_due: total, amount_paid: quote.amount_paid })
      return quote
    }
    if (route === 'POST /me/bookings/link') fail(404, 'BOOKING_NOT_FOUND_OR_NO_MATCH')
    if (route === 'POST /requests' || route === 'POST /requests/emergency') {
      const emergency = route.endsWith('emergency')
      const r = {
        request_id: 'REQ0' + db.nextRequest++, call_id: null, request_type: emergency ? 'Emergency' : body.request_type, category: body.category || null,
        priority: emergency ? 'Critical' : body.request_type === 'Staff Callback' ? 'Urgent' : 'Normal', request_status: 'Open',
        request_text: body.request_text, booking_id: body.booking_id || null, decision: null, created_at: new Date().toISOString(), resolved_at: null
      }
      db.myRequests.unshift(r)
      return emergency ? { request: r, ambulance: '123', police: '122', fire: '180', reception: '+20 2 2794 5500' } : r
    }
    if (route === 'POST /bookings') {
      const rt = roomTypes.find((r) => r.room_type_name === body.room_type)
      const nights = nightsBetween(body.check_in, body.check_out)
      const rate = body.rate_plan === 'Non-refundable' ? r2(rt.base_price * 0.85) : rt.base_price
      const id = 'B0' + db.nextBooking++
      const b = booking(id, rt.room_type_name, 1500 + db.nextBooking % 7, 'City', body.check_in, body.check_out, body.adults, body.children, 'Pending', body.rate_plan, rate, 0)
      b.payment_status = 'Pending'
      b.payment_due_at = new Date(Date.parse(TODAY + 'T12:00:00') + 24 * 3600000).toISOString()
      db.bookings.unshift(b)
      db.channel[id] = 'Website'
      const payNow = body.rate_plan === 'Non-refundable' ? b.total_amount : rate
      return { booking_id: id, booking_status: 'Pending', room_type: rt.room_type_name, room_number: b.room_number, view: 'City', check_in: b.check_in, check_out: b.check_out, nights, adults: b.adults, children: b.children, rate_plan: b.rate_plan, price_per_night: rate, total_amount: b.total_amount, discount: null, amount_due: b.total_amount, pay_now: payNow, pay_at_hotel: r2(b.total_amount - payNow), payment_due_at: b.payment_due_at, payment_url: '#' }
    }
  }

  if (path.startsWith('/staff')) {
    if (!['Staff', 'Admin'].includes(me.role)) fail(403, 'STAFF_ONLY')
    if (route === 'GET /staff/arrivals') return clone(db.arrivals)
    if (route === 'GET /staff/in-house') return clone(db.inHouse.sort((a, b) => a.check_out.localeCompare(b.check_out) || a.room_number - b.room_number))
    if ((m = path.match(/^\/staff\/bookings\/(B\d{6})\/check-in$/))) {
      const i = db.arrivals.findIndex((b) => b.booking_id === m[1])
      if (i < 0) fail(404, 'BOOKING_NOT_FOUND')
      const blocking = db.inHouse.find((b) => b.room_number === db.arrivals[i].room_number)
      if (blocking) fail(409, 'ROOM_NOT_FREE', { room_number: blocking.room_number, guest: `${blocking.first_name} ${blocking.last_name}` })
      const [b] = db.arrivals.splice(i, 1)
      b.checked_in_at = new Date().toISOString()
      db.inHouse.push(b)
      return { booking_id: b.booking_id, booking_status: 'Confirmed', room_number: b.room_number, balance_paid: 0, points_earned: 0, new_tier: null }
    }
    if ((m = path.match(/^\/staff\/bookings\/(B\d{6})\/check-out$/))) {
      const i = db.inHouse.findIndex((b) => b.booking_id === m[1])
      if (i < 0) fail(404, 'BOOKING_NOT_FOUND')
      const [b] = db.inHouse.splice(i, 1)
      return { booking_id: b.booking_id, booking_status: 'Completed', room_number: b.room_number, balance_paid: b.balance_due, points_earned: 0, new_tier: null }
    }
    if ((m = path.match(/^\/staff\/bookings\/(B\d{6})\/no-show$/))) {
      db.arrivals = db.arrivals.filter((b) => b.booking_id !== m[1])
      return { booking_id: m[1], booking_status: 'No-show', room_number: 0, balance_paid: 0, points_earned: 0, new_tier: null }
    }
    if (route === 'GET /staff/requests') {
      const rank = { Critical: 0, Urgent: 1, Normal: 2 }
      return clone(db.tickets.filter((t) => ['Open', 'In Progress'].includes(t.request_status)).sort((a, b) => rank[a.priority] - rank[b.priority] || a.created_at.localeCompare(b.created_at)))
    }
    if ((m = path.match(/^\/staff\/requests\/(REQ\d{6})\/(take|close)$/))) {
      const t = db.tickets.find((x) => x.request_id === m[1]) || fail(404, 'REQUEST_NOT_FOUND')
      if (m[2] === 'take') { t.request_status = 'In Progress'; t.handled_by = me.full_name } else { t.request_status = body?.outcome || 'Resolved'; t.handled_by = t.handled_by || me.full_name }
      return clone(t)
    }
    if (route === 'GET /staff/chats') return clone(db.calls.filter((c) => c.assigned_to === me.full_name && c.status === 'escalated'))
    if ((m = path.match(/^\/staff\/calls\/(.+)$/))) {
      const c = db.calls.find((x) => x.call_id === m[1]) || fail(404, 'CALL_NOT_FOUND')
      return { ...clone(c), messages: clone(callMessages[c.call_id] || []), call_actions: clone(callActions[c.call_id] || []) }
    }
  }

  if (path.startsWith('/admin')) {
    if (me.role !== 'Admin') fail(403, 'ADMINS_ONLY')
    if (route === 'GET /admin/stats') {
      const to = q.date_to || TODAY
      const from = q.date_from || new Date(Date.parse(to) - 29 * 86400000).toISOString().slice(0, 10)
      return stats(from, to)
    }
    if (route === 'GET /admin/calls') return clone(q.status ? db.calls.filter((c) => c.status === q.status) : db.calls)
    if (route === 'GET /admin/staff') return clone(db.staff)
    if ((m = path.match(/^\/admin\/staff\/(\d+)\/(enable|disable)$/))) {
      const s = db.staff.find((x) => x.account_id === Number(m[1])) || fail(404, 'STAFF_NOT_FOUND')
      if (s.account_id === me.account_id) fail(409, 'CANNOT_DISABLE_YOURSELF')
      s.is_active = m[2] === 'enable'
      return clone(s)
    }
    if ((m = path.match(/^\/admin\/staff\/(\d+)\/password$/))) return clone(db.staff.find((x) => x.account_id === Number(m[1])))
    if (route === 'POST /admin/staff') {
      const s = { account_id: 100 + db.staff.length, role: 'Staff', full_name: body.full_name, email: body.email, is_active: true, last_login_at: null }
      db.staff.push(s)
      return s
    }
    if (route === 'GET /admin/discount-requests') return clone(db.discountRequests)
    if ((m = path.match(/^\/admin\/discount-requests\/(REQ\d{6})\/(approve|reject)$/))) {
      db.discountRequests = db.discountRequests.filter((r) => r.request_id !== m[1])
      const t = db.tickets.find((x) => x.request_id === m[1])
      if (t) t.request_status = m[2] === 'approve' ? 'Resolved' : 'Closed'
      return m[2] === 'approve'
        ? { request_id: m[1], decision: 'Approved', discount_code: 'PEARL' + (7000 + Math.floor(Math.random() * 999)), valid_to: '2026-12-18' }
        : { request_id: m[1], decision: 'Rejected', discount_code: null, valid_to: null }
    }
  }

  if (route === 'POST /calls') return { call_id: crypto.randomUUID ? crypto.randomUUID() : String(Date.now()), status: 'active' }

  fail(404, 'NOT_FOUND_IN_DEMO_DATA', { route })
}

export const demoLogins = accounts.map((a) => ({ role: a.role, name: a.full_name, email: a.email, password: PASSWORD }))
export { db as mockDb, TODAY as MOCK_TODAY }
export const bookingChannel = (id) => db.channel[id]
