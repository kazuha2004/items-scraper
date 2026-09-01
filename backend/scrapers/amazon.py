import urllib.parse
# pyrefly: ignore [missing-import]
from playwright.sync_api import sync_playwright
from models import Product

def scrape_amazon(query: str, max_results: int = 5) -> list[Product]:
    results = []
    encoded_query = urllib.parse.quote_plus(query)
    url = f"https://www.amazon.in/s?k={encoded_query}"

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
        page.set_default_timeout(10000)

        # Block images, fonts, media, and stylesheets to make page load ultra fast (2s)
        page.route("**/*.{png,jpg,jpeg,webp,gif,svg,css,woff,woff2,ttf,otf}", lambda route: route.abort())

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=12000)
            page.wait_for_selector('div[data-component-type="s-search-result"]', timeout=6000)

            product_cards = page.query_selector_all('div[data-component-type="s-search-result"]')

            for card in product_cards[:max_results]:
                try:
                    # Title: use JS to find the longest text inside an h2 tag
                    title = page.evaluate("""(card) => {
                        const h2s = card.querySelectorAll('h2');
                        let longest = "";
                        for (const h2 of h2s) {
                            const text = h2.innerText.trim();
                            if (text.length > longest.length && !text.toLowerCase().includes('sponsored')) {
                                longest = text;
                            }
                        }
                        if (longest.length > 5) return longest;
                        
                        // Fallback: any span with a lot of text that isn't a price
                        const spans = card.querySelectorAll('span');
                        for (const span of spans) {
                            if (span.children.length === 0) {
                                const text = span.innerText.trim();
                                if (text.length > 20 && !text.includes('₹')) return text;
                            }
                        }
                        return "";
                    }""", card) or ""

                    # Fallback: get title from img alt tag
                    if not title:
                        img_fallback = card.query_selector('img.s-image')
                        if img_fallback:
                            title = img_fallback.get_attribute('alt') or ""

                    # Product URL
                    url_elem = card.query_selector('h2 a')
                    if not url_elem:
                        url_elem = card.query_selector('a[class*="a-link-normal"][href*="/dp/"]')
                    product_url_path = url_elem.get_attribute("href") if url_elem else ""
                    product_url = f"https://www.amazon.in{product_url_path}" if product_url_path and not product_url_path.startswith('http') else product_url_path

                    # Price — look for the whole price number
                    price = 0.0
                    price_elem = card.query_selector('span.a-price-whole')
                    if price_elem:
                        try:
                            price = float(price_elem.inner_text().replace(",", "").strip().rstrip('.'))
                        except:
                            pass

                    # Rating
                    rating = None
                    rating_elem = card.query_selector('i[class*="a-icon-star-small"] span.a-icon-alt')
                    if not rating_elem:
                        rating_elem = card.query_selector('i[class*="a-icon-star"] span.a-icon-alt')
                    if rating_elem:
                        try:
                            rating = float(rating_elem.inner_text().split(" out")[0])
                        except:
                            pass

                    # Reviews count
                    reviews = 0
                    reviews_elem = card.query_selector('span[aria-label*="ratings"]')
                    if not reviews_elem:
                        reviews_elem = card.query_selector('span.a-size-base.s-underline-text')
                    if reviews_elem:
                        try:
                            label = reviews_elem.get_attribute('aria-label') or reviews_elem.inner_text()
                            reviews = int(label.replace(",", "").split(" ")[0].strip())
                        except:
                            pass

                    img_elem = card.query_selector('img.s-image')
                    image_url = img_elem.get_attribute('src') if img_elem else ""

                    product = Product(
                        platform="Amazon",
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
                    print(f"[Amazon] Error parsing product: {e}")

        except Exception as e:
            print(f"[Amazon] Error scraping: {e}")
        finally:
            browser.close()

    return results
