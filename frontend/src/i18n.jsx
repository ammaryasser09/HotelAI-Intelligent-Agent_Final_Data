import { createContext, Fragment, useContext, useEffect, useState } from 'react'

const AR = {
  // general
  'Loading…': 'جارٍ التحميل…', 'Sign out': 'تسجيل الخروج', 'demo data': 'بيانات تجريبية', 'Cancel': 'إلغاء', 'Close': 'إغلاق',
  'Something went wrong.': 'حدث خطأ ما.', 'Nothing here yet.': 'لا يوجد شيء هنا بعد.', 'Today': 'اليوم', 'EGP': 'ج.م',
  Guest: 'ضيف', Staff: 'موظف', Admin: 'مدير', Visitor: 'زائر',
  'Hotel · Cairo': 'فندق · القاهرة', 'Nile Pearl': 'نايل بيرل',
  // statuses and values from the API
  Confirmed: 'مؤكد', Pending: 'بانتظار الدفع', Completed: 'منتهٍ', Cancelled: 'ملغى', 'No-show': 'لم يحضر',
  Open: 'مفتوح', 'In Progress': 'قيد التنفيذ', Resolved: 'تم الحل', Closed: 'مغلق',
  Normal: 'عادي', Urgent: 'عاجل', Critical: 'حرج', Flexible: 'مرن', 'Non-refundable': 'غير قابل للاسترداد',
  Nile: 'النيل', City: 'المدينة', Active: 'نشط', Disabled: 'موقوف',
  Single: 'فردية', Double: 'مزدوجة', Twin: 'بسريرين', Deluxe: 'ديلوكس', Family: 'عائلية', Suite: 'جناح',
  Standard: 'عادي', Silver: 'فضي', Gold: 'ذهبي', Platinum: 'بلاتيني',
  Housekeeping: 'تنظيف الغرفة', 'Room Service': 'خدمة الغرف', Maintenance: 'صيانة', 'Late Checkout': 'مغادرة متأخرة',
  'Early Check-in': 'وصول مبكر', 'Airport Transfer': 'توصيل من/إلى المطار', 'Special Request': 'طلب خاص', Complaint: 'شكوى',
  'Staff Callback': 'التواصل مع موظف', 'Discount Request': 'طلب خصم', Emergency: 'طوارئ', 'Extra Bed': 'سرير إضافي',
  'Payment Inquiry': 'استفسار عن الدفع', 'General Inquiry': 'استفسار عام',
  Website: 'الموقع', 'Booking Platform': 'منصة حجز', 'Mobile App': 'تطبيق الجوال', Phone: 'الهاتف', 'Travel Agent': 'شركة سياحة', 'Voice Agent': 'نور (المساعد الصوتي)',
  English: 'الإنجليزية', Arabic: 'العربية', 'Arabic (Egyptian)': 'العربية (المصرية)', French: 'الفرنسية', Russian: 'الروسية',
  // login
  'Nile Pearl Hotel': 'فندق نايل بيرل', 'Sign in': 'تسجيل الدخول', 'Signing in…': 'جارٍ الدخول…', Email: 'البريد الإلكتروني', Password: 'كلمة المرور',
  'Guests, staff and administrators all sign in here.': 'الضيوف والموظفون والإدارة يدخلون من نفس الصفحة.',
  'Staff or admin who forgot the password: contact the hotel administration.': 'الموظف أو المدير الذي نسي كلمة المرور: تواصل مع إدارة الفندق.',
  'Your stay, your bookings and Nour — our AI concierge who answers in Arabic, English, French and Russian.': 'إقامتك وحجوزاتك ونور — مساعدتنا الذكية التي تجيبك بالعربية والإنجليزية والفرنسية والروسية.',
  'Demo accounts (password NilePearl@2026)': 'حسابات تجريبية (كلمة المرور NilePearl@2026)',
  'Wrong email or password.': 'البريد الإلكتروني أو كلمة المرور غير صحيحة.',
  'This account is disabled. Contact the hotel administration.': 'هذا الحساب موقوف. تواصل مع إدارة الفندق.',
  'Check-in can’t be in the past.': 'لا يمكن أن يكون تاريخ الوصول في الماضي.',
  'Too many guests for this room type.': 'عدد الضيوف أكبر من سعة هذه الغرفة.',
  'The room is not free yet: the previous guest has not checked out.': 'الغرفة غير جاهزة بعد: الضيف السابق لم يغادر.',
  'No booking matches that reference and name.': 'لا يوجد حجز بهذا الرقم وهذا الاسم.',
  'This booking can’t be cancelled.': 'لا يمكن إلغاء هذا الحجز.',
  'Can’t reach the server. Is the backend running?': 'تعذّر الاتصال بالخادم. هل الـ backend يعمل؟',
  // sign up, password reset, email check
  'Forgot your password?': 'نسيت كلمة المرور؟', 'New guest?': 'ضيف جديد؟', 'Create an account': 'إنشاء حساب', 'Creating…': 'جارٍ الإنشاء…',
  'We send a code to your email to confirm it. You can ask Nour questions now; bookings open once the email is confirmed.': 'سنرسل كوداً إلى بريدك لتأكيده. يمكنك سؤال نور الآن، والحجز يُفتح بعد تأكيد البريد.',
  'First name': 'الاسم الأول', 'Last name': 'اسم العائلة', 'Nationality (optional)': 'الجنسية (اختياري)',
  'At least 8 characters, with a letter and a number.': '8 أحرف على الأقل، بها حرف ورقم.', 'Already have an account?': 'لديك حساب بالفعل؟',
  'Reset your password': 'استعادة كلمة المرور', 'Write the email of your account and we send you a 6-digit code.': 'اكتب البريد الإلكتروني لحسابك وسنرسل لك كوداً من 6 أرقام.',
  'If {email} has a guest account, a code is on its way. It works for {n} minutes.': 'إذا كان للبريد {email} حساب ضيف، فالكود في الطريق إليه، وهو صالح لمدة {n} دقائق.',
  'Code from the email': 'الكود المرسل إلى بريدك', 'New password': 'كلمة المرور الجديدة', 'Send the code': 'أرسل الكود', 'Save the new password': 'احفظ كلمة المرور الجديدة',
  'Use another email or send the code again': 'استخدم بريداً آخر أو أعد إرسال الكود', 'Back to sign in': 'العودة لتسجيل الدخول',
  'Confirm your email': 'أكّد بريدك الإلكتروني', 'We sent a 6-digit code to {email}. Bookings open after you confirm it.': 'أرسلنا كوداً من 6 أرقام إلى {email}. يُفتح الحجز بعد تأكيده.',
  Code: 'الكود', Confirm: 'تأكيد', 'Send a new code': 'أرسل كوداً جديداً', 'A new code is on its way. It works for {n} minutes.': 'كود جديد في الطريق إليك، صالح لمدة {n} دقائق.',
  'Date of birth': 'تاريخ الميلاد',
  'Hotel staff can’t reset their password here. Ask the hotel administrator to set a new one for you.': 'موظفو الفندق لا يمكنهم تغيير كلمة المرور من هنا. اطلب من مدير الفندق تعيين كلمة مرور جديدة لك.',
  'The password needs at least 8 characters, with a letter and a number.': 'كلمة المرور يجب أن تكون 8 أحرف على الأقل وبها حرف ورقم.',
  'This email already has an account. Sign in, or reset the password.': 'هذا البريد له حساب بالفعل. سجّل الدخول أو استعد كلمة المرور.',
  'This phone number is already registered.': 'رقم الهاتف هذا مسجّل بالفعل.', 'This email or phone number is already registered.': 'البريد أو رقم الهاتف مسجّل بالفعل.',
  'The code has expired. Ask for a new one.': 'انتهت صلاحية الكود. اطلب كوداً جديداً.', 'Wrong code. Check the email and try again.': 'الكود غير صحيح. راجع البريد وحاول مرة أخرى.',
  'Guests must be 18 or older to book.': 'يجب أن يكون عمر الضيف 18 عاماً أو أكثر للحجز.', 'Confirm your email first (the code is in your inbox).': 'أكّد بريدك الإلكتروني أولاً (الكود في بريدك).',
  'Add your date of birth to make your first booking.': 'أضف تاريخ ميلادك لإتمام أول حجز.', 'Your email is already confirmed.': 'بريدك الإلكتروني مؤكد بالفعل.',
  "This booking was made on a booking website: change it there.": "تم هذا الحجز عبر موقع حجز: عدّله من هناك.",
  "A non-refundable booking can’t be changed.": "الحجز غير القابل للاسترداد لا يمكن تعديله.",
  "This booking can’t be changed.": "لا يمكن تعديل هذا الحجز.",
  "Changes close 48 hours before arrival. Call reception for help.": "التعديل يُغلق قبل الوصول بـ 48 ساعة. اتصل بالاستقبال للمساعدة.",
  "No room of this type is free for these dates.": "لا توجد غرفة متاحة من هذا النوع في هذه التواريخ.",
  "Check-out must be after check-in.": "يجب أن يكون تاريخ المغادرة بعد تاريخ الوصول.",
  "Booking not found.": "الحجز غير موجود.",
  "The payment service didn’t answer. Try again in a minute.": "خدمة الدفع لم تستجب. حاول مرة أخرى بعد دقيقة.",
  "Change the dates, the room type or the guests first.": "غيّر التواريخ أو نوع الغرفة أو عدد الضيوف أولاً.",
  "Someone took the last room a moment ago. Try other dates or another room type.": "حجز شخص آخر آخر غرفة قبل لحظات. جرّب تواريخ أخرى أو نوع غرفة آخر.",
  "Waiting for the payment…": "بانتظار الدفع…",
  "Change booking": "تعديل الحجز",
  "Change booking {id}": "تعديل الحجز {id}",
  "Your booking is changed: {type} room {room}, {from} – {to}.": "تم تعديل حجزك: غرفة {type} رقم {room}، {from} – {to}.",
  "New total": "الإجمالي الجديد",
  "To pay now": "المطلوب دفعه الآن",
  "Done": "تم",
  "Room type": "نوع الغرفة",
  "New stay": "الإقامة الجديدة",
  "Before": "قبل",
  "Discount": "الخصم",
  "Confirm the change": "تأكيد التعديل",
  "See the new price": "اعرض السعر الجديد",
  "New dates and extra nights keep your agreed nightly rate; a new room type uses its standard rate.": "التواريخ الجديدة والليالي الإضافية بنفس سعر الليلة المتفق عليه، وتغيير نوع الغرفة يكون بسعرها الأساسي.",
  "Change dates or room": "تغيير التواريخ أو الغرفة",
  "Paid — your booking is confirmed": "تم الدفع — حجزك مؤكد",
  "Conversation": "المحادثة", "View": "عرض",
  "No messages were saved for this call.": "لم تُحفظ رسائل لهذه المكالمة.",
  "What Nour did": "ما قامت به نور",
  "No actions.": "لا توجد إجراءات.",
  "Click a conversation to read it and see what Nour did.": "اضغط على أي محادثة لقراءتها ومعرفة ما قامت به نور.",
  "Checked availability": "تحققت من التوفر",
  "Made a booking": "أنشأت حجزاً",
  "Looked up the guest’s bookings": "اطلعت على حجوزات الضيف",
  "Opened a booking": "فتحت حجزاً",
  "Opened a ticket": "فتحت تذكرة",
  "Checked a discount code": "تحققت من كود خصم",
  "Linked a booking": "أضافت حجزاً للحساب",
  "Quoted a cancellation": "حسبت تكلفة الإلغاء",
  "Cancelled a booking": "ألغت حجزاً",
  "Quoted a change": "حسبت تكلفة التعديل",
  "Changed a booking": "عدّلت حجزاً",
  "Searched hotel information": "بحثت في معلومات الفندق",
  // guest menu
  Home: 'الرئيسية', 'My bookings': 'حجوزاتي', 'Book a room': 'احجز غرفة', Requests: 'الطلبات', Rewards: 'المكافآت', 'Talk to Nour': 'تحدّث مع نور',
  // guest home
  'Welcome back, {name}': 'أهلاً بعودتك يا {name}', 'Call Nour now': 'اتصل بنور الآن', 'Book another stay': 'احجز إقامة أخرى',
  'Enjoy your stay in room {room}. ': 'نتمنى لك إقامة سعيدة في الغرفة {room}. ',
  'Your {type} room is ready for you today. ': 'غرفتك ({type}) جاهزة لك اليوم. ',
  'Your {type} room is ready for you tomorrow. ': 'غرفتك ({type}) جاهزة لك غداً. ',
  'Your {type} room is ready for you in {days} days. ': 'غرفتك ({type}) جاهزة لك بعد {days} أيام. ',
  'Plan your next stay on the Nile. ': 'خطّط لإقامتك القادمة على النيل. ',
  'Ask Nour anything — in Arabic, English, French or Russian.': 'اسأل نور عن أي شيء — بالعربية أو الإنجليزية أو الفرنسية أو الروسية.',
  'Your stay': 'إقامتك', 'Your next stay': 'إقامتك القادمة', '{type} Room · {room}': 'غرفة {type} · {room}',
  'Check-in': 'الوصول', 'Check-out': 'المغادرة', Guests: 'الضيوف', Reference: 'رقم الحجز', '3:00 PM': '3:00 م', '12:00 PM': '12:00 م',
  '{n} adults': '{n} بالغين', '1 adult': 'بالغ واحد', '{n} child': '{n} طفل', '{n} nights': '{n} ليلة',
  'Deposit paid online': 'العربون المدفوع أونلاين', 'Paid online': 'المدفوع أونلاين', 'Balance at the hotel': 'المتبقي يُدفع في الفندق',
  'Free cancellation ends today at 3:00 PM.': 'الإلغاء المجاني ينتهي اليوم الساعة 3:00 م.',
  'Free cancellation until {date} at 3:00 PM.': 'الإلغاء المجاني حتى {date} الساعة 3:00 م.',
  'No upcoming stay': 'لا توجد إقامة قادمة', 'Book a room and it will show here.': 'احجز غرفة وستظهر هنا.',
  'Nile Pearl Rewards': 'مكافآت نايل بيرل', points: 'نقطة', 'Worth {amount} off your next bill.': 'تساوي خصم {amount} من فاتورتك القادمة.',
  '{n} stays': '{n} إقامة', 'Your {tier} perk: late check-out until {time}.': 'ميزة مستواك ({tier}): مغادرة متأخرة حتى {time}.',
  'View rewards': 'عرض المكافآت', 'During your stay': 'أثناء إقامتك', Spa: 'السبا', 'Swimming Pool': 'حمام السباحة', 'Breakfast buffet': 'بوفيه الإفطار',
  '60-minute massage · EGP 3,500': 'مساج 60 دقيقة · 3,500 ج.م', 'Free for hotel guests': 'مجاني لنزلاء الفندق', '7:00–10:30 · EGP 1,200 per adult': '7:00–10:30 · 1,200 ج.م للفرد',
  // my bookings
  '{up} upcoming · {past} past': '{up} قادمة · {past} سابقة', '+ Add a booking made elsewhere': '+ أضف حجزاً تم من مكان آخر',
  'Booking reference': 'رقم الحجز', 'Last name or last 4 phone digits': 'اسم العائلة أو آخر 4 أرقام من الهاتف', 'Link booking': 'إضافة الحجز',
  'For bookings made by phone, a travel agent or a booking website.': 'للحجوزات التي تمت بالهاتف أو عن طريق شركة سياحة أو موقع حجز.',
  'Booking {id} was added to your account.': 'تمت إضافة الحجز {id} إلى حسابك.',
  'Upcoming ({n})': 'القادمة ({n})', 'Past & cancelled ({n})': 'السابقة والملغاة ({n})', 'Loading your bookings…': 'جارٍ تحميل حجوزاتك…',
  '{view} view': 'إطلالة {view}', 'Total {amount}': 'الإجمالي {amount}', 'Payment due by {date}': 'يجب الدفع قبل {date}', 'Paid in full': 'مدفوع بالكامل',
  'Refunded {amount}': 'تم استرداد {amount}', 'Paid {paid} · {rest} at the hotel': 'المدفوع {paid} · {rest} في الفندق',
  'Made outside our website: changes are made where you booked. ': 'تم الحجز خارج موقعنا: التعديل يتم من حيث حجزت. ',
  'Free changes and cancellation until {date}, 3:00 PM.': 'التعديل والإلغاء مجاناً حتى {date} الساعة 3:00 م.',
  'The free-cancellation time has passed: the deposit would be kept.': 'انتهت مدة الإلغاء المجاني: سيحتفظ الفندق بالعربون.',
  'Non-refundable rate: it can’t be changed, and nothing is refunded.': 'سعر غير قابل للاسترداد: لا يمكن تعديله ولا يُسترد منه شيء.',
  'Pay the deposit': 'ادفع العربون', 'Cancel booking': 'إلغاء الحجز', 'Cancel {id}?': 'إلغاء الحجز {id}؟',
  'You are inside the free-cancellation time, so everything you paid comes back. Refunds take up to 3 business days, then 7–14 business days to show on your card.': 'أنت داخل مدة الإلغاء المجاني، لذلك يُسترد كل ما دفعته. يستغرق الاسترداد حتى 3 أيام عمل، ثم 7–14 يوم عمل حتى يظهر على بطاقتك.',
  'This is a non-refundable booking, so nothing is refunded.': 'هذا حجز غير قابل للاسترداد، لذلك لا يُسترد شيء.',
  'The free-cancellation time has passed, so the hotel keeps the first-night deposit. Nothing more is charged.': 'انتهت مدة الإلغاء المجاني، لذلك يحتفظ الفندق بعربون الليلة الأولى فقط، ولا يُخصم أي مبلغ آخر.',
  'Refund to your card': 'المبلغ المسترد إلى بطاقتك', 'Kept by the hotel': 'يحتفظ به الفندق', 'Yes, cancel it': 'نعم، ألغِ الحجز', 'Keep my booking': 'احتفظ بحجزي',
  'Booking {id} is cancelled.': 'تم إلغاء الحجز {id}.', ' {amount} goes back to your card.': ' سيعود {amount} إلى بطاقتك.',
  // book a room
  'Prices in EGP, taxes included, room only.': 'الأسعار بالجنيه المصري، شاملة الضرائب، للغرفة فقط.', Adults: 'البالغون', Children: 'الأطفال',
  'Discount code': 'كود الخصم', Optional: 'اختياري', 'Check availability': 'تحقق من التوفر', 'Checking…': 'جارٍ التحقق…',
  '{n} nights · ': '{n} ليالٍ · ', '{n} rooms free': '{n} غرفة متاحة', ' for these dates': ' في هذه التواريخ',
  '{n} guests · {size} m²': '{n} ضيوف · {size} م²', '1 guest · {size} m²': 'ضيف واحد · {size} م²',
  'deposit {amount}': 'العربون {amount}', '15% lower · pay now': 'أقل 15% · الدفع الآن',
  '{n} rooms left': 'متبقٍ {n} غرف', '1 room left': 'متبقٍ غرفة واحدة', ' · {n} with Nile view': ' · {n} بإطلالة على النيل', ' · tap a price to book': ' · اضغط على السعر للحجز',
  'Sold out for these dates': 'محجوزة بالكامل في هذه التواريخ', 'Fits up to {n} guests': 'تتسع حتى {n} ضيوف', 'Fits up to 1 guest': 'تتسع لضيف واحد',
  'Booking {id} is held for you': 'الحجز {id} محجوز لك', 'Pay now': 'ادفع الآن', 'See my bookings': 'عرض حجوزاتي',
  'Pay {now} now': 'ادفع {now} الآن', ' and {rest} at the hotel': ' و{rest} في الفندق', 'The room is held until {date}.': 'الغرفة محجوزة لك حتى {date}.',
  'Comfortable room suitable for one guest': 'غرفة مريحة مناسبة لضيف واحد', 'Comfortable room with one double bed for two guests': 'غرفة مريحة بسرير مزدوج لضيفين',
  'Room with two separate beds': 'غرفة بسريرين منفصلين', 'Spacious room with premium facilities': 'غرفة واسعة بتجهيزات فاخرة',
  'Large room suitable for families': 'غرفة كبيرة مناسبة للعائلات', 'Luxury suite with separate living area and Nile view': 'جناح فاخر بصالة منفصلة وإطلالة على النيل',
  // requests
  'Ask for anything during your stay. Our team sees it right away.': 'اطلب أي شيء أثناء إقامتك، وسيراه فريقنا فوراً.', 'Emergency?': 'حالة طوارئ؟',
  'Ambulance 123 · Police 122 · Fire 180 · Reception 24/7 +20 2 2794 5500': 'الإسعاف 123 · الشرطة 122 · المطافئ 180 · الاستقبال على مدار الساعة ‎+20 2 2794 5500',
  'Report an emergency': 'الإبلاغ عن حالة طوارئ', 'Clean room, towels, amenities': 'تنظيف الغرفة، مناشف، مستلزمات', 'Order food to your room': 'اطلب الطعام إلى غرفتك',
  'Something not working': 'شيء لا يعمل', 'Leave later on your last day': 'غادر متأخراً في آخر يوم', 'Sedan EGP 2,500 · book 24 h ahead': 'سيارة 2,500 ج.م · احجز قبلها بـ 24 ساعة',
  'Celebrations, dietary needs, accessibility': 'احتفالات، احتياجات غذائية، سهولة الوصول', 'Tell us what went wrong': 'أخبرنا بما حدث', 'A team member contacts you': 'سيتواصل معك أحد أفراد الفريق',
  'Talk to staff': 'تحدّث مع موظف', 'For booking': 'للحجز', 'Not about a booking': 'ليس متعلقاً بحجز', 'What do you need?': 'ماذا تحتاج؟', 'Send request': 'إرسال الطلب',
  'My requests': 'طلباتي', 'No requests yet. Requests you make here or to Nour show up here with their status.': 'لا توجد طلبات بعد. الطلبات التي ترسلها هنا أو لنور تظهر هنا مع حالتها.',
  'Request {id} sent. Our team sees it now.': 'تم إرسال الطلب {id}، وفريقنا يراه الآن.', ' · your code {code}': ' · الكود الخاص بك {code}',
  'If someone is in danger, call 123 (ambulance) first. This alerts every member of staff on duty.': 'إذا كان أحد في خطر، اتصل بالإسعاف 123 أولاً. هذا التنبيه يصل لكل الموظفين المناوبين.',
  'What is happening and where?': 'ماذا يحدث وأين؟', 'Send emergency alert': 'إرسال تنبيه الطوارئ',
  'Emergency reported ({id}). Staff are on their way. Ambulance {a} · Police {p} · Fire {f} · Reception {r}': 'تم الإبلاغ عن الطوارئ ({id}). الموظفون في الطريق إليك. الإسعاف {a} · الشرطة {p} · المطافئ {f} · الاستقبال {r}',
  // rewards
  '{tier} member · {n} stays': 'عضو {tier} · {n} إقامة', 'Join at the front desk or ask Nour.': 'انضم من الاستقبال أو اطلب من نور.', Points: 'النقاط', 'Can redeem': 'يمكنك استبدال',
  'Late check-out': 'مغادرة متأخرة', 'YOUR TIER': 'مستواك', 'From 0 nights a year': 'من 0 ليلة في السنة', '10 nights a year': '10 ليالٍ في السنة', '25 nights a year': '25 ليلة في السنة', '50 nights a year': '50 ليلة في السنة',
  'Member rate 15% off the Flexible rate': 'سعر الأعضاء أقل 15% من السعر المرن',
  'Member rate · late check-out until 1:00 PM · 20% bonus points': 'سعر الأعضاء · مغادرة متأخرة حتى 1:00 م · نقاط إضافية 20%',
  'Late check-out until 2:00 PM · room upgrade on arrival · 10% off spa · 50% bonus points': 'مغادرة متأخرة حتى 2:00 م · ترقية الغرفة عند الوصول · خصم 10% على السبا · نقاط إضافية 50%',
  'Late check-out until 4:00 PM · free breakfast for two · Suite upgrades · 15% off spa · double points': 'مغادرة متأخرة حتى 4:00 م · إفطار مجاني لشخصين · ترقية إلى جناح · خصم 15% على السبا · نقاط مضاعفة',
  '1 point for every EGP 10 spent on rooms and hotel services · 1,000 points = EGP 500 off · points expire after 24 months without activity.': 'نقطة لكل 10 ج.م تنفقها على الغرف وخدمات الفندق · 1,000 نقطة = خصم 500 ج.م · تنتهي النقاط بعد 24 شهراً بدون نشاط.',
  // nour call
  'Hello, this is Nour from Nile Pearl Hotel. How can I help you today?': 'أهلاً بك، معك نور من فندق نايل بيرل. كيف أقدر أساعدك اليوم؟',
  Listening: 'تستمع', Connecting: 'جارٍ الاتصال', 'End call': 'إنهاء المكالمة', 'Type instead of talking…': 'اكتب بدلاً من التحدث…', Send: 'إرسال', 'Type a message': 'اكتب رسالة', Nour: 'نور',
  // staff
  'Front desk': 'الاستقبال', Tickets: 'التذاكر', 'Live chats': 'المحادثات المباشرة', 'Front desk view': 'شاشة الاستقبال',
  'Find a guest or booking': 'ابحث عن ضيف أو حجز', 'Name, B000000 or room': 'الاسم أو B000000 أو رقم الغرفة',
  'Arrivals waiting': 'وصول منتظر', 'confirmed, not checked in': 'مؤكدة ولم يتم تسجيل وصولها', 'Leaving today': 'مغادرة اليوم', 'balance to collect at check-out': 'مبالغ تُحصّل عند المغادرة',
  'In house': 'داخل الفندق', 'checked-in stays': 'إقامات مسجّل وصولها', 'Open tickets': 'التذاكر المفتوحة', '{n} urgent or critical': '{n} عاجلة أو حرجة',
  'Arrivals ({n})': 'الوصول ({n})', 'In house ({n})': 'داخل الفندق ({n})', Booking: 'الحجز', Room: 'الغرفة', Stay: 'الإقامة', 'Balance at hotel (EGP)': 'المتبقي في الفندق (ج.م)',
  'late: due {date}': 'متأخر: كان موعده {date}', 'Waiting: {name} leaving': 'بانتظار مغادرة {name}', Ready: 'جاهزة', 'Check in': 'تسجيل الوصول',
  'No arrivals waiting.': 'لا يوجد وصول منتظر.', 'Balance to collect (EGP)': 'المبلغ المطلوب تحصيله (ج.م)', Paid: 'مدفوع', 'Check out': 'تسجيل المغادرة',
  'Nobody is checked in yet.': 'لم يُسجَّل وصول أحد بعد.', 'Check out {name} · room {room}': 'تسجيل مغادرة {name} · الغرفة {room}', 'Stay total': 'إجمالي الإقامة', 'Collect now': 'المطلوب الآن',
  'Paid by': 'طريقة الدفع', 'Confirm check-out': 'تأكيد المغادرة', Cash: 'نقداً', 'Credit Card': 'بطاقة ائتمان', 'Debit Card': 'بطاقة خصم', 'Digital Wallet': 'محفظة إلكترونية', 'Bank Transfer': 'تحويل بنكي',
  'Checked in': 'تم تسجيل الوصول', 'Checked out': 'تم تسجيل المغادرة', 'Marked no-show': 'تم تسجيله كعدم حضور',
  '{label}: {id}, room {room}': '{label}: {id}، الغرفة {room}', ' · collected {amount}': ' · تم تحصيل {amount}', ' · {n} points earned': ' · حصل على {n} نقطة', ' · moved up to {tier}': ' · ترقّى إلى {tier}',
  All: 'الكل', 'Urgent & critical': 'العاجلة والحرجة', 'Not taken yet': 'لم يستلمها أحد', 'No room': 'بدون غرفة', 'Room {n}': 'الغرفة {n}', ' · from Nour': ' · من نور',
  'Take it': 'استلمها', 'Mark resolved': 'تم الحل', 'Nothing in this list.': 'لا يوجد شيء في هذه القائمة.',
  'Emergencies (Critical) always sit on top. Discount requests go to the administrator.': 'حالات الطوارئ (الحرجة) تظهر دائماً في الأعلى. طلبات الخصم تذهب إلى المدير.',
  'Guests Nour handed over to you': 'ضيوف حوّلتهم نور إليك', 'No live chats right now. When Nour hands a guest to you, the chat opens here.': 'لا توجد محادثات مباشرة الآن. عندما تحوّل نور ضيفاً إليك ستفتح المحادثة هنا.',
  Live: 'مباشر', Ended: 'انتهت', 'No booking': 'بدون حجز', 'no booking': 'بدون حجز', '{n} turns': '{n} رسالة', 'Why handed over: {reason}': 'سبب التحويل: {reason}',
  You: 'أنت', 'This chat has ended': 'انتهت هذه المحادثة', 'Write a reply…': 'اكتب رداً…', 'Reply to the guest': 'الرد على الضيف', 'End chat': 'إنهاء المحادثة',
  // admin
  Overview: 'نظرة عامة', Revenue: 'الإيرادات', 'Nour (AI agent)': 'نور (المساعد الذكي)', 'Staff & discounts': 'الموظفون والخصومات',
  '{from} – {to} · {n} rooms in service': '{from} – {to} · {n} غرفة في الخدمة', 'Room revenue': 'إيرادات الغرف', '{n} room nights sold': '{n} ليلة مباعة',
  Occupancy: 'نسبة الإشغال', 'of available room nights': 'من الليالي المتاحة', ADR: 'متوسط سعر الليلة', 'average rate per sold night': 'متوسط سعر الليلة المباعة',
  RevPAR: 'الإيراد لكل غرفة', 'revenue per available room': 'الإيراد لكل غرفة متاحة', 'Cancellation rate': 'نسبة الإلغاء', 'of stays arriving in the period': 'من الإقامات الواصلة في الفترة',
  'Room revenue by month': 'إيرادات الغرف حسب الشهر', 'EGP millions · occupancy under each bar · the current month includes nights already booked': 'بالمليون ج.م · نسبة الإشغال تحت كل عمود · الشهر الحالي يشمل الليالي المحجوزة مسبقاً',
  'Loading 12 months…': 'جارٍ تحميل 12 شهراً…', 'Needs your attention': 'يحتاج انتباهك', '{n} discount requests waiting': '{n} طلبات خصم بانتظارك', '1 discount request waiting': 'طلب خصم واحد بانتظارك',
  'Nothing waiting': 'لا شيء بانتظارك', '{n} urgent or critical tickets open': '{n} تذاكر عاجلة أو حرجة مفتوحة', '{n} open in total': '{n} مفتوحة إجمالاً',
  '{n} bookings made by Nour': '{n} حجوزات قامت بها نور', 'See every conversation of the AI agent': 'شاهد كل محادثات المساعد الذكي',
  'Bookings in the period': 'الحجوزات في الفترة', 'Made in the period': 'تمت في الفترة', 'Top channel': 'أعلى قناة حجز', 'Top room type': 'أعلى نوع غرفة', 'Revenue analysis': 'تحليل الإيرادات',
  '{n} days': '{n} يوماً', '12 months': '12 شهراً', 'By booking channel': 'حسب قناة الحجز', 'By room type': 'حسب نوع الغرفة',
  'Revenue is counted per night stayed in the period, after discounts. Voice Agent = bookings made by Nour.': 'الإيراد محسوب لكل ليلة إقامة داخل الفترة بعد الخصومات. نور (المساعد الصوتي) = الحجوزات التي قامت بها نور.',
  'Nour — AI voice agent': 'نور — المساعد الصوتي الذكي', 'Since {date}': 'منذ {date}', Conversations: 'المحادثات', '{n} from visitors not logged in': '{n} من زوار غير مسجلين',
  'Solved by Nour alone': 'حلّتها نور وحدها', '{a} of {b} · {c} handed to staff': '{a} من {b} · {c} حُوّلت لموظف', 'Reply time': 'سرعة الرد', 'average to first audio': 'متوسط الوقت حتى أول رد صوتي',
  'Average call': 'متوسط المكالمة', '{a} tool actions · {b} tickets opened': '{a} إجراء · {b} تذكرة فُتحت', Languages: 'اللغات', 'How calls ended': 'كيف انتهت المكالمات',
  Solved: 'تم الحل', 'Handed to staff': 'حُوّلت لموظف', 'Hung up': 'أُغلق الخط', 'Live now': 'مباشر الآن', Unknown: 'غير معروف',
  'Staff & discount requests': 'الموظفون وطلبات الخصم', 'Discount request · {id}': 'طلب خصم · {id}', ' (booking {id})': ' (الحجز {id})',
  'Approved — {name} gets code {code} by email, valid until {date}.': 'تمت الموافقة — سيصل إلى {name} الكود {code} بالبريد، صالح حتى {date}.',
  'Rejected — {name} gets an email that the request was not approved.': 'تم الرفض — سيصل إلى {name} بريد بأن الطلب لم تتم الموافقة عليه.',
  Type: 'النوع', Percentage: 'نسبة مئوية', 'Fixed amount (EGP)': 'مبلغ ثابت (ج.م)', Value: 'القيمة', 'Approve and email a code': 'وافق وأرسل كوداً بالبريد', Reject: 'رفض',
  'No discount requests waiting. When a guest asks Nour for a discount, it shows here.': 'لا توجد طلبات خصم. عندما يطلب ضيف خصماً من نور سيظهر هنا.',
  'Staff accounts': 'حسابات الموظفين', '+ Add staff member': '+ إضافة موظف', 'Full name': 'الاسم بالكامل', 'First password': 'كلمة المرور الأولى', 'Create account': 'إنشاء الحساب',
  'Last in {date}': 'آخر دخول {date}', 'Never signed in': 'لم يدخل بعد', 'Reset password': 'تغيير كلمة المرور', Disable: 'إيقاف', Enable: 'تفعيل',
  '{name} can now sign in.': 'يمكن لـ {name} الدخول الآن.', 'Password changed for {name}.': 'تم تغيير كلمة مرور {name}.',
  'New password for {name} (8+ characters with a letter and a number)': 'كلمة مرور جديدة لـ {name} (8 أحرف على الأقل بها حرف ورقم)'
}

const MONTHS_EN = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const MONTHS_AR = ['يناير', 'فبراير', 'مارس', 'أبريل', 'مايو', 'يونيو', 'يوليو', 'أغسطس', 'سبتمبر', 'أكتوبر', 'نوفمبر', 'ديسمبر']
const DAYS_EN = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const DAYS_AR = ['الأحد', 'الإثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة', 'السبت']

let current = 'en'
try { current = localStorage.getItem('np_lang') === 'ar' ? 'ar' : 'en' } catch { /* private mode */ }

export const lang = () => current
export const months = () => (current === 'ar' ? MONTHS_AR : MONTHS_EN)
export const days = () => (current === 'ar' ? DAYS_AR : DAYS_EN)

export function t(text, vars) {
  let out = current === 'ar' && AR[text] !== undefined ? AR[text] : text
  if (vars) for (const [k, v] of Object.entries(vars)) out = out.split(`{${k}}`).join(v)
  return out
}

export const money = (amount) => (current === 'ar' ? `${amount} ج.م` : `EGP ${amount}`)

function apply(l) {
  document.documentElement.lang = l
  document.documentElement.dir = l === 'ar' ? 'rtl' : 'ltr'
}
apply(current)

const LangContext = createContext({ lang: 'en', setLang: () => {} })

export function LangProvider({ children }) {
  const [l, setL] = useState(current)
  useEffect(() => apply(l), [l])
  function setLang(next) {
    current = next
    try { localStorage.setItem('np_lang', next) } catch { /* private mode */ }
    setL(next)
  }
  return <LangContext.Provider value={{ lang: l, setLang }}><Fragment key={l}>{children}</Fragment></LangContext.Provider>
}

export const useLang = () => useContext(LangContext)

export function LangToggle({ dark = false }) {
  const { lang: l, setLang } = useLang()
  return (
    <button type="button" onClick={() => setLang(l === 'ar' ? 'en' : 'ar')} className="lang-toggle"
      style={{ color: dark ? '#E9E4D8' : 'var(--ink)', borderColor: dark ? 'rgba(233,228,216,.4)' : '#CFC8B8' }}
      aria-label={l === 'ar' ? 'Switch to English' : 'التبديل إلى العربية'}>
      {l === 'ar' ? 'English' : 'العربية'}
    </button>
  )
}
