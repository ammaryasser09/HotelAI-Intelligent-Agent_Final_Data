from google.genai import types
from app.rag.tools import check_availability, hotel_photos, create_request, escalate_to_human, REQUEST_TYPES, CATEGORIES
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
    description="Search the hotel's information: policies, prices, opening hours, services, facilities, rooms and location, including distances to the airport and landmarks and what is near the hotel. Only for questions about Nile Pearl Hotel and a stay there; never search for unrelated topics such as sports, weather or politics, decline those yourself. Write the query yourself in English with the topic in it, never the guest's words as they are. If the guest asks several things, call it once for each question.",    behavior="NON_BLOCKING",
    parameters={
        "type": "OBJECT",
        "properties": {
            "question": {"type": "STRING", "description": "One clear English question with its topic, e.g. 'How to reach Gold level in the loyalty program?'"},
        },
        "required": ["question"],
    },
)

CREATE_REQUEST = types.FunctionDeclaration(
    name="create_request",
    description="Open a ticket for the hotel team: in-stay requests (housekeeping, room service, extra bed...), Maintenance for anything broken, Complaint, Special Request for a coming stay (needs a booking and a category), Discount Request, and Emergency for medical, fire or security (top priority, works without login). In an emergency, call this tool at once in the same turn, before or while you give the emergency numbers; never say the team was alerted unless this tool returned ok.",
    behavior="NON_BLOCKING",
    parameters={
        "type": "OBJECT",
        "properties": {
            "request_type": {"type": "STRING", "enum": list(REQUEST_TYPES)},
            "request_text": {"type": "STRING", "description": "What the guest needs, in one short English sentence."},
            "booking_ref": {"type": "STRING", "description": "B followed by six digits, only if the request is about a booking."},
            "category": {"type": "STRING", "enum": sorted({c for v in CATEGORIES.values() for c in v}), "description": "Only for a Complaint or a Special Request."},
        },
        "required": ["request_type", "request_text"],
    },
)

ESCALATE_TO_HUMAN = types.FunctionDeclaration(
    name="escalate_to_human",
    description="The guest has a problem and asked to talk to a person: hand the chat to a member of staff, or open an urgent callback ticket if no one is free.",
    behavior="NON_BLOCKING",
    parameters={
        "type": "OBJECT",
        "properties": {
            "reason": {"type": "STRING", "description": "The guest's problem in one short English sentence."},
            "booking_ref": {"type": "STRING", "description": "B followed by six digits, only if it is about a booking."},
        },
        "required": ["reason"],
    },
)

DECLARATIONS = [CHECK_AVAILABILITY, HOTEL_PHOTOS, SEARCH_HOTEL_INFO, CREATE_REQUEST, ESCALATE_TO_HUMAN]
FUNCTIONS = {
    "check_availability": check_availability,
    "hotel_photos": hotel_photos,
    "search_hotel_info": search_hotel_info,
    "create_request": create_request,
    "escalate_to_human": escalate_to_human,
}