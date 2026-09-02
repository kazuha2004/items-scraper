import urllib.parse
# pyrefly: ignore [missing-import]
from playwright.sync_api import sync_playwright
from models import Product

def scrape_flipkart(query: str, max_results: int = 5) -> list[Product]:
    results = []
    encoded_query = urllib.parse.quote_plus(query)
    url = f"https://www.flipkart.com/search?q={encoded_query}"

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled",
                "--window-size=1366,768",
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768},
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            extra_http_headers={
                "Accept-Language": "en-IN,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Linux"',
            }
        )
        page = context.new_page()
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-IN', 'en']});
        """)

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)

            # Detect Flipkart bot-block (sometimes shows "Access Denied" or redirects)
            page_title = page.title().lower()
            if "access denied" in page_title or "blocked" in page_title or "403" in page_title:
                print(f"[Flipkart] ⚠️ Access blocked by Flipkart. Server IP may be blacklisted. Title: '{page.title()}'")
                return results

            try:
                page.wait_for_selector('div[data-id]', timeout=10000)
            except Exception:
                print(f"[Flipkart] ⚠️ No product cards found — IP may be blocked or page structure changed. Title: '{page.title()}'")
                page.wait_for_timeout(3000)

            product_cards = page.query_selector_all('div[data-id]')
            print(f"[Flipkart] Found {len(product_cards)} product cards")

            for card in product_cards[:max_results]:
                try:
                    url_elem = card.query_selector('a[href*="/p/"]')
                    if not url_elem:
                        continue

                    product_url_path = url_elem.get_attribute("href")
                    product_url = f"https://www.flipkart.com{product_url_path}"

                    title = page.evaluate("""(card) => {
                        const titleLink = card.querySelector('a[title]');
                        if (titleLink) return titleLink.getAttribute('title');
                        const namedDiv = card.querySelector('div[class*="name"], div[class*="title"]');
                        if (namedDiv && namedDiv.innerText.length > 5) return namedDiv.innerText.trim();
                        let longest = "";
                        const allDivs = card.querySelectorAll('div, a, p, span');
                        for (const el of allDivs) {
                            if (el.children.length === 0) {
                                const text = (el.innerText || '').trim();
                                if (text.length > longest.length && !text.includes('₹') && !/^[0-5](\\.[0-9])?$/.test(text) && !text.toLowerCase().includes('off')) {
                                    longest = text;
                                }
                            }
                        }
                        if (longest.length > 5) return longest;
                        const img = card.querySelector('img');
                        return img ? img.getAttribute('alt') : "";
                    }""", card) or ""

                    img_elem = card.query_selector('img')

                    price = 0.0
                    price_text = page.evaluate("""(card) => {
                        const allDivs = card.querySelectorAll('div');
                        for (const div of allDivs) {
                            const text = div.innerText || '';
                            if (text.startsWith('₹') && text.length < 15 && div.children.length === 0) {
                                return text;
                            }
                        }
                        return null;
                    }""", card)
                    if price_text:
                        try:
                            price = float(price_text.replace("₹", "").replace(",", "").strip())
                        except (ValueError, TypeError) as e:
                            print(f"[Flipkart] Could not parse price: {e}")

                    rating = None
                    rating_text = page.evaluate(r"""(card) => {
                        const spans = card.querySelectorAll('div, span');
                        for (const el of spans) {
                            const t = el.innerText?.trim();
                            if (t && /^[1-5](\.[0-9])?$/.test(t) && el.children.length === 0) {
                                return t;
                            }
                        }
                        return null;
                    }""", card)
                    if rating_text:
                        try:
                            rating = float(rating_text)
                        except (ValueError, TypeError) as e:
                            print(f"[Flipkart] Could not parse rating: {e}")

                    reviews = 0
                    reviews_text = page.evaluate(r"""(card) => {
                        const els = card.querySelectorAll('span');
                        for (const el of els) {
                            const t = el.innerText?.trim() || '';
                            const m = t.match(/^[\(]?([\d,]+)[\)]?\s*(Ratings?|Reviews?|ratings?|reviews?)/i)
                                   || t.match(/^\(([\d,]+)\)$/);
                            if (m) return m[1].replace(/,/g, '');
                        }
                        return null;
                    }""", card)
                    if reviews_text:
                        try:
                            reviews = int(reviews_text)
                        except (ValueError, TypeError) as e:
                            print(f"[Flipkart] Could not parse review count: {e}")

                    image_url = img_elem.get_attribute('src') if img_elem else ""

                    results.append(Product(
                        platform="Flipkart",
                        title=title or "Unknown Product",
                        price=price,
                        rating=rating,
                        review_count=reviews,
                        availability=price > 0,
                        image_url=image_url or "",
                        product_url=product_url
                    ))
                except Exception as e:
                    print(f"[Flipkart] Error parsing product: {e}")

        except Exception as e:
            print(f"[Flipkart] Error scraping: {e}")
        finally:
            browser.close()

    return results
