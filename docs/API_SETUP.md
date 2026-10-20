# تشغيل الـ API على جهازك (Backend - FastAPI)

الحاجات دي **مش على GitHub قصداً**، وكل واحد بيعملها على جهازه مرة واحدة:

| الحاجة | ليه مش على GitHub |
|---|---|
| `.venv` | فولدر المكتبات، كبير وبيتعمل من `requirements-api.txt` |
| `.env` | فيه باسورد الداتابيز بتاعتك والمفتاح السري للتوكن |
| `logs/` | الـ logs بتاعة جهازك |

## أول مرة (مرة واحدة بس)

المطلوب: Python 3.12 و PostgreSQL 16، والداتابيز `hotelai` متحمّلة (شوف `database/README.md`).

```powershell
# 1. المكتبات
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-api.txt

# 2. الإعدادات: انسخ الملف وعدّل فيه باسورد PostgreSQL بتاعك
Copy-Item .env.example .env
code .env

# 3. اعمل مفتاحك السري وحطه مكان CHANGE_ME في .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## كل مرة

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.api.main:app --reload
```

- التوثيق والتجربة: http://127.0.0.1:8000/docs
- حالة السيرفر والداتابيز: http://127.0.0.1:8000/health

## بعد كل `git pull`

```powershell
pip install -r requirements-api.txt   # لو اتضافت مكتبات جديدة
pytest                                 # كل الاختبارات لازم تعدّي
```

## الدخول للتجربة

باسورد الديمو لكل الحسابات: `NilePearl@2026`

| الدور | الإيميل |
|---|---|
| ضيف (عنده حجوزات وحجز مربوط) | `paul.fischer500@example.com` |
| موظف | `karim.fathy@nilepearlhotel.example` |
| أدمن | `admin@nilepearlhotel.example` |

في `/docs`: اعمل `POST /auth/login`، وانسخ `access_token`، ودوس **Authorize** 🔒 فوق، والصقه.
