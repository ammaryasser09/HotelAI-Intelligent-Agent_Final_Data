from google.genai import types
from app.rag.tools import check_availability, hotel_photos
from app.llm.knowledge import search_hotel_info

CHECK_AVAILABILITY = types.FunctionDeclaration(
    name="check_availability",
    description="Free rooms and prices for a room type and dates.",
    behavior="NON_BLOCKING",
    parameters={
        "type": "OBJECT",
        "properties": {
            "room_type": {"type": "STRING", "description": "Single, Double, Twin, Deluxe, Family or Suite"},
            "check_in": {"type": "STRING", "description": "YYYY-MM-DD"},
            "check_out": {"type": "STRING", "description": "YYYY-MM-DD"},
            "guests": {"type": "INTEGER", "description": "number of guests"},
        },
        "required": ["room_type", "check_in", "check_out", "guests"],
    },
)

HOTEL_PHOTOS = types.FunctionDeclaration(
    name="hotel_photos",
    description="Photos of the hotel areas to show on the call screen.",
    behavior="NON_BLOCKING",
    parameters={
        "type": "OBJECT",
        "properties": {
            "area": {"type": "STRING", "description": "pool, spa, gym, restaurant, lobby or hotel"},
        },
    },
)

SEARCH_HOTEL_INFO = types.FunctionDeclaration(
    name="search_hotel_info",
    description="Search the hotel's information: policies, prices, opening hours, services, facilities, rooms and location. Write the query yourself in English with the topic in it, never the guest's words as they are. If the guest asks several things, call it once for each question.",
    behavior="NON_BLOCKING",
    parameters={
        "type": "OBJECT",
        "properties": {
            "question": {"type": "STRING", "description": "One clear English question with its topic, e.g. 'How to reach Gold level in the loyalty program?'"},
        },
        "required": ["question"],
    },
)

DECLARATIONS = [CHECK_AVAILABILITY, HOTEL_PHOTOS, SEARCH_HOTEL_INFO]
FUNCTIONS = {
    "check_availability": check_availability,
    "hotel_photos": hotel_photos,
    "search_hotel_info": search_hotel_info,
}