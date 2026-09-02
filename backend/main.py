import os
import asyncio
import sys
from functools import partial
from contextlib import asynccontextmanager

# Fix for Playwright subprocess on Windows Python 3.14+
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# pyrefly: ignore [missing-import]
from fastapi import FastAPI, Query, HTTPException
# pyrefly: ignore [missing-import]
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from cachetools import TTLCache
from concurrent.futures import ThreadPoolExecutor

from models import Product, ProductHistoryResponse, PriceAlertCreate, PriceAlertResponse
from scrapers.meesho import scrape_meesho
from scrapers.amazon import scrape_amazon
from scrapers.flipkart import scrape_flipkart
from database import (
    connect_db,
    close_db,
    upsert_products,
    save_tracked_query,
    get_product_history,
    create_price_alert,
    search_db_products
)
from scheduler import start_scheduler, stop_scheduler, run_price_tracking_cycle

# Thread pool: 3 workers run scrapers in parallel
executor = ThreadPoolExecutor(max_workers=3)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: connect to MongoDB Atlas and start background tracking scheduler
    await connect_db()
    start_scheduler(executor)
    yield
    # Shutdown: stop scheduler and close DB client
    stop_scheduler()
    await close_db()

app = FastAPI(title="Product Comparison API", lifespan=lifespan)

# Allow requests from the Next.js frontend (local and deployed on Vercel)
frontend_url = os.getenv("FRONTEND_URL", "").strip()
allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
if frontend_url:
    allowed_origins.append(frontend_url)

# NOTE: allow_credentials=True is incompatible with allow_origins=["*"] per CORS spec.
# We always use an explicit origins list instead.
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory cache: max 100 queries, TTL of 3 hours (10800 seconds)
search_cache = TTLCache(maxsize=100, ttl=10800)

@app.get("/")
def read_root():
    return {
        "message": "Welcome to the DealHunter Product Comparison API with MongoDB Atlas Price Tracking",
        "endpoints": ["/api/search", "/api/product/history", "/api/alerts"]
    }

@app.get("/health")
def health_check():
    """Render health check endpoint."""
    return {"status": "ok"}

@app.get("/api/test-scrape")
async def test_scrape(site: str = "amazon", q: str = "paint color"):
    import traceback
    fn = scrape_amazon if site == "amazon" else (scrape_flipkart if site == "flipkart" else scrape_meesho)
    try:
        loop = asyncio.get_running_loop()
        res = await loop.run_in_executor(executor, partial(fn, q, 3))
        return {"site": site, "count": len(res), "items": [p.model_dump() for p in res]}
    except Exception as e:
        return {"site": site, "error": str(e), "traceback": traceback.format_exc()}

@app.get("/api/search", response_model=List[Product])
async def search_products(q: str):
    q_lower = q.lower().strip()

    # Track search query in MongoDB Atlas for scheduled background refresh
    asyncio.create_task(save_tracked_query(q_lower))

    # 1. Return from in-memory cache if available (instant: 0.05s)
    if q_lower in search_cache:
        print(f"Returning cached results for: {q_lower}")
        return search_cache[q_lower]

    # 2. Check MongoDB Atlas for instant database results (< 0.3s)
    db_products = await search_db_products(q_lower)
    if db_products and len(db_products) >= 2:
        print(f"Returning {len(db_products)} instant DB results for: {q_lower}")
        search_cache[q_lower] = db_products
        # Trigger background live scrape to refresh DB silently
        async def _background_refresh():
            loop = asyncio.get_running_loop()
            res = await asyncio.gather(
                loop.run_in_executor(executor, partial(scrape_amazon, q_lower, 5)),
                loop.run_in_executor(executor, partial(scrape_flipkart, q_lower, 5)),
                loop.run_in_executor(executor, partial(scrape_meesho, q_lower, 5)),
                return_exceptions=True
            )
            fresh = []
            for r in res:
                if isinstance(r, list): fresh.extend(r)
            if fresh:
                await upsert_products(fresh)
        asyncio.create_task(_background_refresh())
        return db_products

    # 3. If new query not in DB, run fast parallel live scrapers (2-4s)
    print(f"Scraping new results for: {q_lower}")
    loop = asyncio.get_running_loop()

    results = await asyncio.gather(
        loop.run_in_executor(executor, partial(scrape_amazon, q_lower, 5)),
        loop.run_in_executor(executor, partial(scrape_flipkart, q_lower, 5)),
        loop.run_in_executor(executor, partial(scrape_meesho, q_lower, 5)),
        return_exceptions=True
    )

    all_products = []
    for platform_results in results:
        if isinstance(platform_results, Exception):
            print(f"Scraper error: {platform_results}")
        elif platform_results:
            all_products.extend(platform_results)

    # Remove junk titles
    all_products = [
        p for p in all_products
        if p.title.lower() not in ("unknown product", "sponsored", "")
        and len(p.title) > 3
    ]

    # Save fresh products into MongoDB Atlas in background
    if all_products:
        asyncio.create_task(upsert_products(all_products))
        search_cache[q_lower] = all_products
    else:
        # Fallback to DB
        all_products = db_products

    # Categorize: "exact" vs "related" (demoting accessories)
    query_words = [w for w in q_lower.split() if len(w) > 2]
    
    accessory_keywords = [
        "cover", "case", "guard", "glass", "strap", "protector", "cable", 
        "charger", "skin", "sleeve", "adapter", "battery", "tempered"
    ]

    query_is_accessory = any(acc in q_lower for acc in accessory_keywords)

    def categorize(product: Product) -> str:
        title = product.title.lower()
        if not query_words:
            return "exact"
        
        matched = [w for w in query_words if w in title]
        is_accessory = False
        if not query_is_accessory:
            is_accessory = any(acc in title for acc in accessory_keywords)

        if len(matched) == len(query_words):
            if is_accessory:
                return "related"
            return "exact"
        # Put partial matches or general search results into related instead of discarding them
        return "related"

    categorized = []
    for p in all_products:
        p.match_type = categorize(p)
        categorized.append(p)

    # Sort each group by price (put ₹0 at end)
    categorized.sort(key=lambda p: (p.match_type == "related", p.price == 0, p.price))

    search_cache[q_lower] = categorized
    return categorized

@app.get("/api/product/history", response_model=ProductHistoryResponse)
async def get_history(
    url: str = Query(..., description="Product URL"),
    price: float = Query(0.0, description="Current price fallback"),
    title: str = Query("", description="Product title fallback"),
    platform: str = Query("", description="Platform fallback")
):
    """Retrieve historical price records for graph rendering."""
    return await get_product_history(url, price, title, platform)

@app.post("/api/alerts", response_model=PriceAlertResponse)
async def set_price_alert(alert_in: PriceAlertCreate):
    """Register a frictionless price drop alert."""
    if alert_in.target_price >= alert_in.current_price:
        raise HTTPException(status_code=400, detail="Target price should be lower than current price.")

    res = await create_price_alert(
        email=alert_in.email,
        product_url=alert_in.product_url,
        title=alert_in.title,
        platform=alert_in.platform,
        current_price=alert_in.current_price,
        target_price=alert_in.target_price
    )

    return PriceAlertResponse(
        id=res.get("id", "alert-1"),
        email=alert_in.email,
        product_url=alert_in.product_url,
        title=alert_in.title,
        platform=alert_in.platform,
        target_price=alert_in.target_price,
        current_price=alert_in.current_price,
        active=True,
        created_at=res.get("created_at", ""),
        message=f"Alert activated! We will notify {alert_in.email} when the price drops below ₹{alert_in.target_price:,.0f} on {alert_in.platform}."
    )

@app.post("/api/scheduler/trigger")
async def trigger_scheduler_manually():
    """Manual trigger to test the background price tracker & alert evaluation."""
    asyncio.create_task(run_price_tracking_cycle(executor))
    return {"message": "Background price tracking cycle triggered successfully."}
