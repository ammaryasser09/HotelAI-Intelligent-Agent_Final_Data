from google.genai import types                                  # أنواع جاهزة من مكتبة Gemini
from app.rag.tools import check_availability, hotel_photos      # الدالتين الجاهزين من فريق الـ RAG

CHECK_AVAILABILITY = types.FunctionDeclaration(                 # كارت تعريف الـ tool الأولى
    name="check_availability",                                  # الاسم اللي نور هتناديها بيه
    description="Free rooms and prices for a room type and dates.",  # نور بتقرا ده عشان تعرف إمتى تستخدمها
    behavior="NON_BLOCKING",                                    # تشتغل في الخلفية ونور بتتكلم
    parameters={                                                # البيانات اللي نور لازم تبعتها
        "type": "OBJECT",                                       # مجموعة بيانات
        "properties": {                                         # كل معلومة لوحدها:
            "room_type": {"type": "STRING", "description": "Single, Double, Twin, Deluxe, Family or Suite"},  # نوع الأوضة
            "check_in": {"type": "STRING", "description": "YYYY-MM-DD"},   # يوم الوصول
            "check_out": {"type": "STRING", "description": "YYYY-MM-DD"},  # يوم المغادرة
            "guests": {"type": "INTEGER", "description": "number of guests"},  # عدد الأفراد
        },
        "required": ["room_type", "check_in", "check_out", "guests"],  # الأربعة إجباريين
    },
)

HOTEL_PHOTOS = types.FunctionDeclaration(                       # كارت تعريف الـ tool التانية
    name="hotel_photos",                                        # الاسم اللي نور هتناديها بيه
    description="Photos of the hotel areas to show on the call screen.",  # إمتى تستخدمها
    behavior="NON_BLOCKING",                                    # تشتغل في الخلفية زي الأولى
    parameters={                                                # البيانات اللي نور ممكن تبعتها
        "type": "OBJECT",                                       # مجموعة بيانات
        "properties": {                                         # معلومة واحدة بس:
            "area": {"type": "STRING", "description": "pool, spa, gym, restaurant, lobby or hotel"},  # المكان (اختياري)
        },
    },
)

DECLARATIONS = [CHECK_AVAILABILITY, HOTEL_PHOTOS]               # الكارتين اللي هنديهم لنور
FUNCTIONS = {                                                   # الاسم ← الدالة اللي هتتنفذ فعلاً
    "check_availability": check_availability,                   # الأولى
    "hotel_photos": hotel_photos,                               # التانية
}