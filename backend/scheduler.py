import os
import asyncio
from datetime import datetime, timezone
# pyrefly: ignore [missing-import]
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from functools import partial

from database import get_tracked_queries, upsert_products, evaluate_pending_alerts, is_connected
from scrapers.meesho import scrape_meesho
from scrapers.amazon import scrape_amazon
from scrapers.flipkart import scrape_flipkart

scheduler = AsyncIOScheduler()

async def run_price_tracking_cycle(executor):
    """
    Periodic background job:
    1. Fetches top tracked queries from MongoDB.
    2. Runs scrapers to get latest prices.
    3. Upserts products and logs daily price history.
    4. Evaluates active user price drop alerts and triggers notifications.
    """
    print(f"⏰ [{datetime.now(timezone.utc).strftime('%H:%M:%S')}] Starting background price tracking cycle...")
    
    tracked_queries = await get_tracked_queries(limit=10)
    # Default popular items if no queries have been searched yet
    if not tracked_queries:
        tracked_queries = ["iphone 15", "boat airdopes 141", "samsung galaxy watch 6", "prestige pressure cooker 3l"]

    loop = asyncio.get_event_loop()

    for query in tracked_queries:
        try:
            print(f"🔄 [Background Track] Scraping '{query}' for price updates...")
            results = await asyncio.gather(
                loop.run_in_executor(executor, partial(scrape_meesho, query, 5)),
                loop.run_in_executor(executor, partial(scrape_amazon, query, 5)),
                loop.run_in_executor(executor, partial(scrape_flipkart, query, 5)),
                return_exceptions=True
            )
            scraped_products = []
            for platform_results in results:
                if not isinstance(platform_results, Exception):
                    scraped_products.extend(platform_results)
            
            if scraped_products:
                await upsert_products(scraped_products)
                print(f"💾 Updated {len(scraped_products)} products & price histories for '{query}' in MongoDB Atlas")
        except Exception as e:
            print(f"Error in background tracking for '{query}': {e}")
        
        # Small delay between query scrapes to avoid rate limiting
        await asyncio.sleep(5)

    # Check and trigger price alerts
    triggered = await evaluate_pending_alerts()
    if triggered:
        print(f"🎉 [PRICE DROP ALERT TRIGGERED] {len(triggered)} alerts matched target prices:")
        for alert in triggered:
            print(f"📧 Notification for {alert['email']}: '{alert['title']}' dropped to ₹{alert['current_price']} on {alert['platform']} (Target: ₹{alert['target_price']})")
    else:
        print("✅ Background price tracking cycle finished. No target price breaches found.")

def start_scheduler(executor):
    """Start APScheduler cron job."""
    interval_minutes = int(os.getenv("SCRAPER_CRON_INTERVAL_MINUTES", "360"))
    scheduler.add_job(
        run_price_tracking_cycle,
        'interval',
        minutes=interval_minutes,
        args=[executor],
        id='price_tracker_job',
        replace_existing=True
    )
    scheduler.start()
    print(f"🕒 Background Price Tracker Scheduler started (Interval: every {interval_minutes} minutes)")

def stop_scheduler():
    """Stop APScheduler."""
    if scheduler.running:
        scheduler.shutdown()
        print("🛑 Background Scheduler stopped.")
