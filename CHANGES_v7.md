# تحديث v7 — الحاجات اللي كانت ناقصة في الداتا

الملفات اللي في الـ zip ده تتحط مكان القديمة في `HotelAI_Clean` بنفس المسارات. مفيش ولا ملف اتشال.
الداتابيز بقت **25 جدول** (كانت 23). اتجربت على PostgreSQL 16: تحميل من الأول، وتحميل فوق النسخة القديمة، وسكريبت الـ Docker،
و**33 فحص PASS** (كانوا 28) و**11 فحص رفض PASS** (كانوا 7)، و`check_data.py` = 10/10.

## اتعمل إيه

| # | التعديل | فين |
|---|---|---|
| 1 | **نوع طلب `Maintenance`** (تكييف، نور، حنفية...) | `customer_requests.request_type`، `tools.py`، `prompt.py` |
| 2 | **جدول `verification_codes`** لأكواد الإيميل: تأكيد الإيميل وقت التسجيل ونسيان الباسورد. بيتخزن hash الكود بس، والكود بيشتغل مرة واحدة ولمدة 10 دقايق و5 محاولات | `schema.sql`، `queries.sql` رقم 12، `app_settings` (`otp_valid_minutes`، `otp_max_attempts`) |
| 3 | **الخصم على الحجز:** `discount_source` (Long Stay أو Code)، و`discount_code_id`، و`discount_amount`، و`amount_due` = الإجمالي بعد الخصم. خصم واحد بس، والأكبر | `bookings`، `queries.sql` رقم 4 (بيسجل الخصم ويزوّد `usage_count`) |
| 4 | **قرار طلب الخصم:** `decision` (Approved/Rejected)، و`decided_by`، و`decided_at`، و`issued_code_id`. والكود الشخصي: `discount_codes.customer_id`، للضيف ده بس ومرة واحدة | `customer_requests`، `discount_codes`، `queries.sql` رقم 11، `tools.py` (`check_discount_code`) |
| 5 | **جدول `hotel_photos`** بيربط صور الفندق بالأماكن (البيسين، السبا، الجيم، المطعم، اللوبي، الفندق) + tool جديد `hotel_photos` | `schema.sql`، `seed/hotel_photos.csv`، `queries.sql` رقم 13، `tools.py`، `prompt.py` |
| 6 | **`deposit_nights = 1`** في الإعدادات بدل ما العربون يبقى مكتوب جوه الكود | `app_settings.csv`، `queries.sql` رقم 4، `tools.py`، `run_checks.sql` |
| 7 | `queries.sql` رقم 1a بيرجّع صور الأوض (`image_nile`، `image_city`) | `queries.sql` |
| 8 | القاعدة رقم 3 في الـ README اتعدلت للوجين بدل رقم الحجز والاسم | `README.md` |

## الداتا القديمة
مااتغيرتش. الأعمدة الجديدة فاضية أو صفر في الحجوزات والطلبات القديمة، و`hotel_photos` فيه 6 صفوف.

## محتاج يتعمل يدوي
- **`ERD.png`** ماتعملتش من جديد. `ERD.md` (Mermaid) متحدّث وفيه الجدولين الجداد والعلاقات، فممكن تطلعوا منه صورة جديدة (مثلاً من mermaid.live).

## إعادة تحميل الداتابيز
من فولدر `database`:
```
psql -U postgres -d hotelai -v ON_ERROR_STOP=1 -f schema.sql -f load_data.sql
psql -U postgres -d hotelai -P pager=off -f tests/run_checks.sql        # 33 سطر PASS
psql -U postgres -d hotelai -f tests/constraint_checks.sql             # 11 سطر PASS
```
