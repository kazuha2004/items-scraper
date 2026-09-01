# pyrefly: ignore [missing-import]
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

class Product(BaseModel):
    platform: str
    title: str
    price: float
    rating: Optional[float] = None
    review_count: Optional[int] = None
    availability: bool
    image_url: str
    product_url: str
    match_type: str = "exact"  # "exact" or "related"

class PricePoint(BaseModel):
    date: str
    price: float
    timestamp: Optional[datetime] = None

class ProductHistoryResponse(BaseModel):
    product_url: str
    title: str
    platform: str
    current_price: float
    lowest_price: float
    highest_price: float
    history: List[PricePoint]

class PriceAlertCreate(BaseModel):
    email: EmailStr
    product_url: str
    title: str
    platform: str
    current_price: float
    target_price: float

class PriceAlertResponse(BaseModel):
    id: str
    email: str
    product_url: str
    title: str
    platform: str
    target_price: float
    current_price: float
    active: bool
    created_at: str
    message: str
