import re
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
                "--no-sandbox", "--disable-setuid-sandbox",
                "--disable-dev-shm-usage", "--disable-gpu",
                "--disable-extensions", "--disable-background-networking",
                "--disable-sync", "--no-first-run", "--mute-audio",
                "--disable-default-apps"
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
            java_script_enabled=True,
        )
        page = context.new_page()
        page.set_default_timeout(15000)

        # Block heavy images and web fonts only (keep CSS so layout selectors work)
        page.route("**/*.{png,jpg,jpeg,webp,gif,svg,woff,woff2,ttf,otf}", lambda route: route.abort())

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            try:
                page.wait_for_selector('div[data-id]', timeout=8000)
            except:
                pass

            product_cards = page.query_selector_all('div[data-id]')

            for card in product_cards[:max_results]:
                try:
                    url_elem = card.query_selector('a[href*="/p/"]')
                    if not url_elem:
                        continue

                    product_url_path = url_elem.get_attribute("href")
                    product_url = f"https://www.flipkart.com{product_url_path}"

                    # Title: Check a[title], img[alt], or the longest text div
                    title = page.evaluate("""(card) => {
                        // 1. Check if there's a link with a title attribute
                        const titleLink = card.querySelector('a[title]');
                        if (titleLink) return titleLink.getAttribute('title');
                        
                        // 2. Check for a div with class containing 'name' or 'title'
                        const namedDiv = card.querySelector('div[class*="name"], div[class*="title"]');
                        if (namedDiv && namedDiv.innerText.length > 5) return namedDiv.innerText.trim();

                        // 3. Find the longest text node that isn't a price or rating
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

                        // 4. Fallback to image alt
                        const img = card.querySelector('img');
                        return img ? img.getAttribute('alt') : "";
                    }""", card) or ""
                    
                    img_elem = card.query_selector('img')

                    # Use JS to find the price — look for any text containing ₹
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
                        except:
                            pass

                    # Rating — look for a short decimal number in a small element
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
                        except:
                            pass

                    # Reviews
                    reviews = 0
                    reviews_elem = card.query_selector('span[class*="_2_R_DZ"]')
                    if not reviews_elem:
                        reviews_elem = card.query_selector('span[class*="Wphh3N"]')
                    if reviews_elem:
                        match = re.search(r'([\d,]+)', reviews_elem.inner_text())
                        if match:
                            try:
                                reviews = int(match.group(1).replace(",", ""))
                            except:
                                pass

                    image_url = img_elem.get_attribute('src') if img_elem else ""

                    product = Product(
                        platform="Flipkart",
                        title=title or "Unknown Product",
                        price=price,
                        rating=rating,
                        review_count=reviews,
                        availability=price > 0,
                        image_url=image_url or "",
                        product_url=product_url
                    )
                    results.append(product)
                except Exception as e:
                    print(f"[Flipkart] Error parsing product: {e}")

        except Exception as e:
            print(f"[Flipkart] Error scraping: {e}")
        finally:
            browser.close()

    return results
