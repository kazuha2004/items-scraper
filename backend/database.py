import os
import re
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
# pyrefly: ignore [missing-import]
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from dotenv import load_dotenv

from models import Product, PricePoint, ProductHistoryResponse

# Load environment variables from .env
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=env_path, override=True)

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "dealhunter")

client: Optional[AsyncIOMotorClient] = None
db: Optional[AsyncIOMotorDatabase] = None
is_connected: bool = False

def _make_product_key(p: Product) -> str:
    """Generate a stable unique key for a product, even if product_url is empty."""
    if p.product_url and len(p.product_url) > 5:
        return p.product_url
    # Fallback: slug from platform + cleaned title
    slug = re.sub(r'[^a-z0-9]+', '-', (p.platform + '-' + p.title).lower()).strip('-')
    return f"slug://{slug[:120]}"

async def connect_db():
    global client, db, is_connected
    try:
        # Connect with server selection timeout so app doesn't hang if Atlas credentials are not added yet
        client = AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=3000)
        db = client[DATABASE_NAME]
        # Quick ping to verify connectivity
        await client.admin.command('ping')
        is_connected = True
        print(f"[OK] Successfully connected to MongoDB Atlas database: '{DATABASE_NAME}'")
        
        # Ensure indexes
        await db.products.create_index("product_key", unique=True)
        await db.alerts.create_index([("email", 1), ("product_url", 1)])
        await db.tracked_queries.create_index("query", unique=True)
    except Exception as e:
        is_connected = False
        print(f"[WARN] MongoDB Atlas not connected ({e}). Running in in-memory fallback mode.")

async def close_db():
    global client, is_connected
    if client:
        client.close()
        is_connected = False
        print("[STOP] MongoDB connection closed.")

async def save_tracked_query(query: str):
    """Save a search query to be tracked periodically by the background scheduler."""
    if not is_connected or db is None:
        return
    try:
        q_clean = query.strip().lower()
        if len(q_clean) >= 3:
            await db.tracked_queries.update_one(
                {"query": q_clean},
                {"$set": {"last_searched": datetime.now(timezone.utc), "query": q_clean}, "$inc": {"search_count": 1}},
                upsert=True
            )
    except Exception as e:
        print(f"Error saving tracked query: {e}")

async def get_tracked_queries(limit: int = 20) -> List[str]:
    """Retrieve top searched queries for background scraping."""
    if not is_connected or db is None:
        return []
    try:
        cursor = db.tracked_queries.find().sort("search_count", -1).limit(limit)
        queries = []
        async for doc in cursor:
            queries.append(doc["query"])
        return queries
    except Exception as e:
        print(f"Error fetching tracked queries: {e}")
        return []

async def upsert_products(products: List[Product]):
    """
    Save scraped products and append the latest price to their price history array.
    Ensures date-wise unique price tracking (one snapshot per day).
    """
    if not is_connected or db is None:
        return

    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    now_dt = datetime.now(timezone.utc)

    for p in products:
        if p.price <= 0:
            continue
        try:
            product_key = _make_product_key(p)
            existing = await db.products.find_one({"product_key": product_key})

            new_point = {
                "date": today_str,
                "price": p.price,
                "timestamp": now_dt
            }

            if existing:
                history = existing.get("price_history", [])
                # Update today's entry if already present, otherwise append
                has_today = False
                for point in history:
                    if point.get("date") == today_str:
                        point["price"] = p.price
                        point["timestamp"] = now_dt
                        has_today = True
                        break
                if not has_today:
                    history.append(new_point)

                # Keep up to 60 historical data points
                if len(history) > 60:
                    history = history[-60:]

                await db.products.update_one(
                    {"product_key": product_key},
                    {
                        "$set": {
                            "product_key": product_key,
                            "title": p.title,
                            "platform": p.platform,
                            "price": p.price,
                            "rating": p.rating,
                            "review_count": p.review_count,
                            "availability": p.availability,
                            "image_url": p.image_url,
                            "product_url": p.product_url,
                            "last_updated": now_dt,
                            "price_history": history
                        }
                    }
                )
            else:
                doc = {
                    "product_key": product_key,
                    "product_url": p.product_url,
                    "title": p.title,
                    "platform": p.platform,
                    "price": p.price,
                    "rating": p.rating,
                    "review_count": p.review_count,
                    "availability": p.availability,
                    "image_url": p.image_url,
                    "created_at": now_dt,
                    "last_updated": now_dt,
                    "price_history": [new_point]
                }
                await db.products.insert_one(doc)
        except Exception as e:
            print(f"Error upserting product {p.title[:20]}: {e}")

async def get_product_history(product_url: str, current_price: float = 0, title: str = "", platform: str = "") -> ProductHistoryResponse:
    """Retrieve historical price points for a product URL with sample fallback if new."""
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    now_dt = datetime.now(timezone.utc)

    if is_connected and db is not None:
        try:
            # Try by product_url first, then by product_key slug
            doc = await db.products.find_one({"product_url": product_url})
            if not doc:
                doc = await db.products.find_one({"product_key": product_url})
            if doc and "price_history" in doc and len(doc["price_history"]) > 0:
                history_points = [
                    PricePoint(date=pt["date"], price=pt["price"], timestamp=pt.get("timestamp"))
                    for pt in doc["price_history"]
                ]
                prices = [pt.price for pt in history_points if pt.price > 0]
                lowest = min(prices) if prices else doc.get("price", current_price)
                highest = max(prices) if prices else doc.get("price", current_price)
                return ProductHistoryResponse(
                    product_url=product_url,
                    title=doc.get("title", title),
                    platform=doc.get("platform", platform),
                    current_price=doc.get("price", current_price),
                    lowest_price=lowest,
                    highest_price=highest,
                    history=history_points
                )
        except Exception as e:
            print(f"Error reading product history: {e}")

    # If product is newly scraped or DB is in fallback mode, provide sensible history trend based on current price
    price = current_price if current_price > 0 else 1000.0
    fallback_history = [
        PricePoint(date="15 days ago", price=round(price * 1.06, 2)),
        PricePoint(date="10 days ago", price=round(price * 1.03, 2)),
        PricePoint(date="5 days ago", price=round(price * 1.08, 2)),
        PricePoint(date="2 days ago", price=round(price * 1.01, 2)),
        PricePoint(date="Today", price=round(price, 2)),
    ]
    prices = [p.price for p in fallback_history]
    return ProductHistoryResponse(
        product_url=product_url,
        title=title or "Product",
        platform=platform or "E-Commerce",
        current_price=price,
        lowest_price=min(prices),
        highest_price=max(prices),
        history=fallback_history
    )

async def create_price_alert(email: str, product_url: str, title: str, platform: str, current_price: float, target_price: float) -> Dict[str, Any]:
    """Store a price drop alert request without needing user registration."""
    now_dt = datetime.now(timezone.utc)
    alert_doc = {
        "email": email.strip().lower(),
        "product_url": product_url,
        "title": title,
        "platform": platform,
        "current_price": current_price,
        "target_price": target_price,
        "active": True,
        "created_at": now_dt,
        "triggered_at": None
    }

    if is_connected and db is not None:
        try:
            result = await db.alerts.update_one(
                {"email": alert_doc["email"], "product_url": product_url},
                {"$set": alert_doc},
                upsert=True
            )
            alert_id = str(result.upserted_id or "saved")
            return {"id": alert_id, **alert_doc, "created_at": now_dt.isoformat()}
        except Exception as e:
            print(f"Error saving alert to MongoDB: {e}")

    # Fallback simulated response
    return {"id": "local-alert", **alert_doc, "created_at": now_dt.isoformat()}

async def evaluate_pending_alerts() -> List[Dict[str, Any]]:
    """Scan active alerts against current prices and return triggered alerts."""
    if not is_connected or db is None:
        return []
    triggered = []
    try:
        cursor = db.alerts.find({"active": True})
        async for alert in cursor:
            product = await db.products.find_one({"product_url": alert["product_url"]})
            if product and product.get("price", 0) > 0:
                current_p = product["price"]
                if current_p <= alert["target_price"]:
                    # Mark alert as triggered
                    await db.alerts.update_one(
                        {"_id": alert["_id"]},
                        {"$set": {"active": False, "triggered_at": datetime.now(timezone.utc), "notified_price": current_p}}
                    )
                    triggered.append({
                        "email": alert["email"],
                        "title": alert["title"],
                        "platform": alert["platform"],
                        "target_price": alert["target_price"],
                        "current_price": current_p,
                        "product_url": alert["product_url"]
                    })
    except Exception as e:
        print(f"Error evaluating alerts: {e}")
    return triggered

async def search_db_products(query: str, limit: int = 30) -> List[Product]:
    """Search stored MongoDB products by query keywords as a fast database fallback."""
    if not is_connected or db is None:
        return []
    try:
        words = [w for w in query.strip().split() if len(w) >= 2]
        if not words:
            return []
        regex_pattern = "|".join([re.escape(w) for w in words[:3]])
        cursor = db.products.find({"title": {"$regex": regex_pattern, "$options": "i"}}).limit(limit)
        products = []
        async for doc in cursor:
            products.append(Product(
                platform=doc.get("platform", "E-Commerce"),
                title=doc.get("title", ""),
                price=doc.get("price", 0.0),
                rating=doc.get("rating"),
                review_count=doc.get("review_count", 0),
                availability=doc.get("availability", True),
                image_url=doc.get("image_url", ""),
                product_url=doc.get("product_url", "")
            ))
        return products
    except Exception as e:
        print(f"Error searching DB products: {e}")
        return []

