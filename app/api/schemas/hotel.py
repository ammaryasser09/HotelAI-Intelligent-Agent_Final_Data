from pydantic import BaseModel


class RoomType(BaseModel):
    room_type_id: str
    room_type_name: str
    description: str
    capacity: int
    base_price: float
    size_sqm: int
    image_nile: str
    image_city: str | None


class HotelPhoto(BaseModel):
    photo_key: str
    title_en: str
    title_ar: str
    image_path: str


class MenuItem(BaseModel):
    item_id: str
    name_en: str
    name_ar: str
    category: str
    price: float
    dietary: str | None


class Menu(BaseModel):
    items: list[MenuItem]
    delivery_charge: float
