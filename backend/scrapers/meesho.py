import urllib.parse
# pyrefly: ignore [missing-import]
from playwright.sync_api import sync_playwright
from models import Product

def scrape_meesho(query: str, max_results: int = 5) -> list[Product]:
    results = []
    encoded_query = urllib.parse.quote_plus(query)
    url = f"https://www.meesho.com/search?q={encoded_query}"

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox", "--disable-setuid-sandbox",
                "--disable-dev-shm-usage", "--disable-gpu",
                "--disable-extensions", "--disable-background-networking",
                "--disable-sync", "--no-first-run", "--mute-audio",
                "--disable-default-apps", "--single-process"
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()
        page.set_default_timeout(25000)

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            # Give the SPA time to render the product grid
            page.wait_for_timeout(4000)

            # Use JS to extract all product cards generically —
            # find anchor tags that look like product links (contain /p/ or go to a product page)
            # and extract title, price and image from the surrounding DOM
            products_data = page.evaluate(f"""() => {{
                const results = [];
                // Meesho renders product cards as <a> tags linking to /s/p/... or /product/...
                const links = Array.from(document.querySelectorAll('a[href]')).filter(a => {{
                    const href = a.getAttribute('href') || '';
                    return href.includes('/s/p/') || href.includes('/product/');
                }});

                for (const a of links.slice(0, {max_results})) {{
                    try {{
                        const href = a.getAttribute('href');
                        const productUrl = href.startsWith('http') ? href : 'https://www.meesho.com' + href;

                        // Title: look for <p> or <h3> inside the card
                        const titleEl = a.querySelector('p, h3, [class*="title"], [class*="Title"], [class*="name"]');
                        const title = titleEl ? titleEl.innerText.trim() : '';

                        // Price: look for text containing ₹ inside the card
                        const allText = Array.from(a.querySelectorAll('*')).find(el => {{
                            const t = el.childNodes.length === 1 && el.childNodes[0].nodeType === 3
                                ? el.childNodes[0].textContent.trim()
                                : '';
                            return t.startsWith('₹') && t.length < 15;
                        }});
                        const priceText = allText ? allText.innerText.replace('₹','').replace(/,/g,'').trim() : '0';

                        // Image
                        const img = a.querySelector('img');
                        const imageUrl = img ? (img.getAttribute('src') || img.getAttribute('data-src') || '') : '';

                        // Rating
                        const ratingEl = Array.from(a.querySelectorAll('span, div')).find(el => {{
                            const t = (el.childNodes.length === 1 && el.childNodes[0].nodeType === 3)
                                ? el.childNodes[0].textContent.trim() : '';
                            return /^[1-5](\.[0-9])?$/.test(t);
                        }});
                        const rating = ratingEl ? parseFloat(ratingEl.innerText) : null;

                        if (title && title.length > 3) {{
                            results.push({{ title, price: parseFloat(priceText) || 0, imageUrl, productUrl, rating }});
                        }}
                    }} catch(e) {{}}
                }}
                return results;
            }}""")

            for item in products_data:
                results.append(Product(
                    platform="Meesho",
                    title=item["title"],
                    price=item["price"],
                    rating=item.get("rating"),
                    review_count=None,
                    availability=True,
                    image_url=item["imageUrl"] or "",
                    product_url=item["productUrl"],
                ))

        except Exception as e:
            print(f"[Meesho] Error scraping: {e}")
        finally:
            browser.close()

    return results
