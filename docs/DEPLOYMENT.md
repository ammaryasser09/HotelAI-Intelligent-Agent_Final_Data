# رفع الباك إند (Docker)

الملفات: `Dockerfile` (صورة الـ API)، `docker-compose.yml` (الداتابيز + الـ API + Caddy)، `deploy/Caddyfile` (HTTPS).

## يعني إيه Docker؟

- **Image (صورة):** "علبة" فيها بايثون والمكتبات وكود الـ API، جاهزة تشتغل على أي جهاز بنفس الشكل.
- **Container:** العلبة دي وهي شغالة.
- **docker compose:** بيشغّل كذا container مع بعض بأمر واحد: الداتابيز (PostgreSQL) والـ API، وCaddy على السيرفر.

## ١. تجربة على جهازك

محتاجة **Docker Desktop** متسطّب وشغال.

```powershell
docker compose up -d --build
```

- أول مرة بتاخد شوية وقت: بينزّل PostgreSQL، ويبني صورة الـ API، ويحمّل الداتا التجريبية.
- افتحي <http://localhost:8000/docs> و <http://localhost:8000/health>.
- اللوج: `docker compose logs -f api`
- إيقاف: `docker compose down` (الداتا بتفضل). ولو عايزة الداتابيز ترجع من الأول: `docker compose down -v`.

> الداتابيز اللي جوه Docker **غير** الداتابيز اللي على جهازك (pgAdmin). لو PostgreSQL بتاع جهازك شغال على 5432 مش مشكلة: داتابيز Docker مش بتفتح بورت بره.

## ٢. على سيرفر حقيقي (VPS)

1. سيرفر Linux (Ubuntu مثلاً)، وسطّبي عليه Docker.
2. دومين (أو subdomain) يشاور على IP السيرفر، مثلاً `api.nilepearl.example`.
3. على السيرفر:

```bash
git clone https://github.com/ammaryasser09/HotelAI-Intelligent-Agent_Final_Data.git
cd HotelAI-Intelligent-Agent_Final_Data
cp .env.example .env
nano .env
```

4. في `.env` على السيرفر:

| الإعداد | القيمة |
|---|---|
| `JWT_SECRET` | سر جديد طويل: `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `POSTGRES_PASSWORD` | باسورد قوي للداتابيز |
| `DOMAIN` | الدومين، مثلاً `api.nilepearl.example` |
| `PUBLIC_BASE_URL` | `https://` + الدومين (Paymob بيكلّمه، ومش محتاجين ngrok) |
| `PAYMENT_PROVIDER` | `paymob`، ومعاه مفاتيح Paymob |
| `EMAIL_PROVIDER` | `smtp`، ومعاه `SMTP_HOST` و`SMTP_USER` و`SMTP_PASSWORD` |
| `CORS_ORIGINS` | دومين الفرونت إند، مثلاً `["https://nilepearl.example"]` |

5. تشغيل مع HTTPS:

```bash
docker compose --profile https up -d --build
```

Caddy بياخد شهادة HTTPS مجانية للدومين لوحده، وبيوصّل كل حاجة للـ API، الـ WebSocket بتاع الشات اللايف كمان.

## ٣. بعد الرفع

- **تحديث:** `git pull` وبعدين `docker compose --profile https up -d --build`.
- **باك أب للداتابيز:** `docker compose exec db pg_dump -U hotelai hotelai > backup.sql`
- **تشيك سريع:** `python scripts/check_endpoints.py https://api.nilepearl.example`
- **عملية واحدة بس للـ API:** الشات اللايف بيفتكر مين متوصّل في الذاكرة. لو احتجنا كذا نسخة من الـ API، نضيف Redis.
