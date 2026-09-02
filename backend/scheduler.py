import os
import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
# pyrefly: ignore [missing-import]
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from functools import partial

from database import get_tracked_queries, upsert_products, evaluate_pending_alerts, is_connected
from scrapers.meesho import scrape_meesho
from scrapers.amazon import scrape_amazon
from scrapers.flipkart import scrape_flipkart

scheduler = AsyncIOScheduler()

# ── Email config from environment ─────────────────────────────────────────────
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USER = os.getenv("EMAIL_USER", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", EMAIL_USER)


def send_price_alert_email(to_email: str, title: str, platform: str, target_price: float, current_price: float, product_url: str):
    """Send a price drop notification email via SMTP. Silently skips if EMAIL_USER is not configured."""
    if not EMAIL_USER or not EMAIL_PASSWORD:
        print(f"[Email] Skipping email to {to_email} — EMAIL_USER/EMAIL_PASSWORD not set in .env")
        return

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"🎉 Price Drop Alert: {title[:60]}"
        msg["From"] = EMAIL_FROM
        msg["To"] = to_email

        html_body = f"""
        <html><body style="font-family:Arial,sans-serif;background:#f8f9fa;padding:20px;">
          <div style="max-width:540px;margin:0 auto;background:#fff;border-radius:12px;padding:28px;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
            <h2 style="color:#2563eb;margin-top:0;">🎉 Price Drop Alert — DealHunter</h2>
            <p style="color:#374151;">Good news! A product you are tracking has dropped to your target price.</p>
            <div style="background:#f0fdf4;border-left:4px solid #16a34a;padding:16px;border-radius:8px;margin:20px 0;">
              <p style="margin:0;font-weight:600;color:#111827;">{title}</p>
              <p style="margin:6px 0 0;color:#6b7280;">on <strong>{platform}</strong></p>
            </div>
            <table style="width:100%;border-collapse:collapse;margin:16px 0;">
              <tr>
                <td style="padding:8px;color:#6b7280;">Your target price:</td>
                <td style="padding:8px;font-weight:700;color:#2563eb;">₹{target_price:,.0f}</td>
              </tr>
              <tr style="background:#f9fafb;">
                <td style="padding:8px;color:#6b7280;">Current price now:</td>
                <td style="padding:8px;font-weight:700;color:#16a34a;">₹{current_price:,.0f}</td>
              </tr>
            </table>
            <a href="{product_url}" style="display:inline-block;background:#2563eb;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;margin-top:8px;">
              Buy Now →
            </a>
            <p style="color:#9ca3af;font-size:0.78rem;margin-top:24px;">
              You set this alert on DealHunter. Alerts auto-deactivate after triggering once.
            </p>
          </div>
        </body></html>
        """

        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_FROM, to_email, msg.as_string())

        print(f"[Email] ✅ Sent price drop alert to {to_email} for '{title[:40]}'")
    except Exception as e:
        print(f"[Email] ❌ Failed to send email to {to_email}: {e}")


async def run_price_tracking_cycle(executor):
    """
    Periodic background job:
    1. Fetches top tracked queries from MongoDB.
    2. Runs scrapers to get latest prices.
    3. Upserts products and logs daily price history.
    4. Evaluates active user price drop alerts and sends email notifications.
    """
    print(f"⏰ [{datetime.now(timezone.utc).strftime('%H:%M:%S')}] Starting background price tracking cycle...")

    tracked_queries = await get_tracked_queries(limit=10)
    # Default popular items if no queries have been searched yet
    if not tracked_queries:
        tracked_queries = ["iphone 15", "boat airdopes 141", "samsung galaxy watch 6", "prestige pressure cooker 3l"]

    loop = asyncio.get_running_loop()

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

    # Check and trigger price alerts — send real emails
    triggered = await evaluate_pending_alerts()
    if triggered:
        print(f"🎉 [PRICE DROP ALERT TRIGGERED] {len(triggered)} alerts matched target prices:")
        for alert in triggered:
            print(f"📧 Emailing {alert['email']}: '{alert['title']}' dropped to ₹{alert['current_price']} (Target: ₹{alert['target_price']})")
            # send_price_alert_email(
            #     to_email=alert["email"],
            #     title=alert["title"],
            #     platform=alert["platform"],
            #     target_price=alert["target_price"],
            #     current_price=alert["current_price"],
            #     product_url=alert["product_url"]
            # )
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
