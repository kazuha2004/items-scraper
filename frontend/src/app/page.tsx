"use client";

import { useState, useMemo, useEffect } from 'react';

interface Product {
  platform: string;
  title: string;
  price: number;
  rating: number | null;
  review_count: number | null;
  availability: boolean;
  image_url: string;
  product_url: string;
  match_type: string;
}

interface PricePoint {
  date: string;
  price: number;
}

interface ProductHistory {
  product_url: string;
  title: string;
  platform: string;
  current_price: number;
  lowest_price: number;
  highest_price: number;
  history: PricePoint[];
}

type SortKey = 'price' | 'rating' | 'platform';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000';

function StarRating({ rating }: { rating: number }) {
  const full = Math.floor(rating);
  const half = rating % 1 >= 0.5;
  return (
    <span className="stars">
      {'★'.repeat(full)}{half ? '½' : ''}{'☆'.repeat(5 - full - (half ? 1 : 0))}
    </span>
  );
}

function SkeletonGrid({ count = 6 }: { count?: number }) {
  return (
    <div className="product-grid">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="skeleton-card">
          <div className="skeleton skel-img" />
          <div style={{ padding: '1rem' }}>
            <div className="skeleton skel-line" style={{ marginBottom: '0.5rem' }} />
            <div className="skeleton skel-line short" />
            <div className="skeleton skel-line price" style={{ marginTop: '0.75rem' }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function PriceHistoryModal({
  product,
  onClose
}: {
  product: Product;
  onClose: () => void;
}) {
  const [historyData, setHistoryData] = useState<ProductHistory | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchHistory() {
      try {
        const url = `${API_BASE}/api/product/history?url=${encodeURIComponent(product.product_url)}&price=${product.price}&title=${encodeURIComponent(product.title)}&platform=${encodeURIComponent(product.platform)}`;
        const res = await fetch(url);
        if (res.ok) {
          const data = await res.json();
          setHistoryData(data);
        }
      } catch (e) {
        console.error("Failed to load history", e);
      } finally {
        setLoading(false);
      }
    }
    fetchHistory();
  }, [product]);

  const points = historyData?.history || [];
  const prices = points.map(p => p.price).filter(p => p > 0);
  const minPrice = prices.length ? Math.min(...prices) : product.price;
  const maxPrice = prices.length ? Math.max(...prices) : product.price;
  const range = maxPrice - minPrice || 1;

  // Generate SVG coordinates
  const svgWidth = 460;
  const svgHeight = 160;
  const padding = 20;

  const polyPoints = points.map((pt, i) => {
    const x = padding + (i / Math.max(points.length - 1, 1)) * (svgWidth - 2 * padding);
    const y = svgHeight - padding - ((pt.price - minPrice) / range) * (svgHeight - 2 * padding);
    return `${x},${y}`;
  }).join(' ');

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">
            <span>📈</span> Price History & Trends
          </div>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        <div className="modal-body">
          <div className="alert-product-preview">
            {product.image_url && <img src={product.image_url} alt="" className="alert-thumb" />}
            <div>
              <div className="alert-prod-title">{product.title}</div>
              <span className={`platform-tag tag-${product.platform.toLowerCase()}`} style={{ position: 'static', display: 'inline-block', marginTop: '4px' }}>
                {product.platform}
              </span>
            </div>
          </div>

          {loading ? (
            <div style={{ textAlign: 'center', padding: '2rem', color: '#6b7280' }}>Loading price tracker history...</div>
          ) : (
            <>
              <div className="price-stats-grid">
                <div className="stat-card">
                  <div className="stat-label">Lowest Price</div>
                  <div className="stat-val lowest">₹{minPrice.toLocaleString('en-IN')}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Highest Price</div>
                  <div className="stat-val highest">₹{maxPrice.toLocaleString('en-IN')}</div>
                </div>
                <div className="stat-card">
                  <div className="stat-label">Current Price</div>
                  <div className="stat-val current">₹{product.price.toLocaleString('en-IN')}</div>
                </div>
              </div>

              <div className="chart-container">
                <svg className="chart-svg" viewBox={`0 0 ${svgWidth} ${svgHeight}`}>
                  {/* Grid lines */}
                  <line x1={padding} y1={padding} x2={svgWidth - padding} y2={padding} stroke="#e5e7eb" strokeDasharray="3,3" />
                  <line x1={padding} y1={svgHeight / 2} x2={svgWidth - padding} y2={svgHeight / 2} stroke="#e5e7eb" strokeDasharray="3,3" />
                  <line x1={padding} y1={svgHeight - padding} x2={svgWidth - padding} y2={svgHeight - padding} stroke="#e5e7eb" strokeDasharray="3,3" />

                  {/* Price Line */}
                  <polyline
                    fill="none"
                    stroke="#2563eb"
                    strokeWidth="3"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    points={polyPoints}
                  />

                  {/* Data Points */}
                  {points.map((pt, i) => {
                    const x = padding + (i / Math.max(points.length - 1, 1)) * (svgWidth - 2 * padding);
                    const y = svgHeight - padding - ((pt.price - minPrice) / range) * (svgHeight - 2 * padding);
                    return (
                      <g key={i}>
                        <circle cx={x} cy={y} r="4.5" fill="#ffffff" stroke="#2563eb" strokeWidth="2.5" />
                        <text x={x} y={y - 8} fontSize="9" fontWeight="700" textAnchor="middle" fill="#374151">
                          ₹{Math.round(pt.price)}
                        </text>
                      </g>
                    );
                  })}
                </svg>

                <div className="chart-dates">
                  {points.map((pt, i) => (
                    <span key={i}>{pt.date}</span>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function PriceAlertModal({
  product,
  onClose,
  onAlertCreated
}: {
  product: Product;
  onClose: () => void;
  onAlertCreated: (msg: string) => void;
}) {
  const [email, setEmail] = useState('');
  const [targetPrice, setTargetPrice] = useState(Math.round(product.price * 0.9));
  const [discountPercent, setDiscountPercent] = useState(10);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  const handlePreset = (pct: number) => {
    setDiscountPercent(pct);
    setTargetPrice(Math.round(product.price * (1 - pct / 100)));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || targetPrice <= 0) return;
    if (targetPrice >= product.price) {
      setErrorMsg('Target price must be lower than the current price.');
      return;
    }
    setLoading(true);
    setErrorMsg('');
    try {
      const res = await fetch(`${API_BASE}/api/alerts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email,
          product_url: product.product_url,
          title: product.title,
          platform: product.platform,
          current_price: product.price,
          target_price: targetPrice
        })
      });
      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Failed to set alert');
      }
      setSuccess(true);
      onAlertCreated(`Alert created for ${email}! We'll notify you when it drops.`);
    } catch (err: any) {
      setErrorMsg(err.message || 'Something went wrong. Try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">
            <span>🔔</span> Set Price Drop Alert
          </div>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        <div className="modal-body">
          <div className="alert-product-preview">
            {product.image_url && <img src={product.image_url} alt="" className="alert-thumb" />}
            <div>
              <div className="alert-prod-title">{product.title}</div>
              <div style={{ fontSize: '0.8rem', color: '#6b7280', marginTop: '2px' }}>
                Current: <strong style={{ color: '#111827' }}>₹{product.price.toLocaleString('en-IN')}</strong> on {product.platform}
              </div>
            </div>
          </div>

          {success ? (
            <div className="alert-success-box">
              <span style={{ fontSize: '2rem' }}>🎉</span>
              <div className="alert-success-title">Price Alert Activated!</div>
              <div className="alert-success-desc">
                We'll monitor <strong>{product.platform}</strong> daily and send an email to <strong>{email}</strong> the second this drops below <strong>₹{targetPrice.toLocaleString('en-IN')}</strong>!
              </div>
              <button className="search-btn" style={{ marginTop: '0.5rem' }} onClick={onClose}>
                Done
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div className="form-group">
                <label className="form-label">When price drops by:</label>
                <div className="target-presets">
                  {[5, 10, 15, 20].map(pct => (
                    <button
                      key={pct}
                      type="button"
                      className={`preset-btn${discountPercent === pct ? ' active' : ''}`}
                      onClick={() => handlePreset(pct)}
                    >
                      -{pct}% (₹{Math.round(product.price * (1 - pct / 100)).toLocaleString('en-IN')})
                    </button>
                  ))}
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Or enter custom target price (₹):</label>
                <input
                  type="number"
                  className="form-input"
                  value={targetPrice}
                  onChange={e => {
                    setTargetPrice(Number(e.target.value));
                    setDiscountPercent(0);
                  }}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Your Email Address (No login needed):</label>
                <input
                  type="email"
                  className="form-input"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="yourname@gmail.com"
                  required
                />
              </div>

              {errorMsg && (
                <div style={{ color: '#dc2626', fontSize: '0.8rem' }}>{errorMsg}</div>
              )}

              <button type="submit" className="submit-alert-btn" disabled={loading}>
                {loading ? 'Activating Alert...' : '🔔 Notify Me on Price Drop'}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}

function ProductCard({
  product,
  idx,
  onOpenHistory,
  onOpenAlert
}: {
  product: Product;
  idx: number;
  onOpenHistory: (p: Product) => void;
  onOpenAlert: (p: Product) => void;
}) {
  const platformClass = product.platform.toLowerCase();
  return (
    <div
      className="product-card"
      style={{ animationDelay: `${idx * 40}ms` }}
      onClick={() => window.open(product.product_url, '_blank')}
    >
      <div className="card-image-wrap">
        <span className={`platform-tag tag-${platformClass}`}>{product.platform}</span>
        {product.image_url ? (
          <img src={product.image_url} alt={product.title} />
        ) : (
          <div style={{ color: '#d1d5db', fontSize: '0.8rem' }}>No image</div>
        )}
      </div>
      <div className="card-body">
        <p className="card-title">{product.title}</p>
        {product.rating && (
          <div className="card-rating">
            <StarRating rating={product.rating} />
            <span style={{ color: '#374151', fontWeight: 600 }}>{product.rating.toFixed(1)}</span>
            {product.review_count ? <span className="rating-count">({product.review_count.toLocaleString()})</span> : null}
          </div>
        )}
        <div className="card-footer">
          <span className="card-price">
            {product.price > 0 ? `₹${product.price.toLocaleString('en-IN')}` : 'N/A'}
          </span>
          <a
            href={product.product_url}
            target="_blank"
            rel="noopener noreferrer"
            className={`buy-btn buy-${platformClass}`}
            onClick={e => e.stopPropagation()}
          >
            Buy Now
          </a>
        </div>

        {/* Feature Action Buttons */}
        <div className="card-actions" onClick={e => e.stopPropagation()}>
          <button className="action-btn" title="View Price Trend" onClick={() => onOpenHistory(product)}>
            📈 History
          </button>
          <button className="action-btn action-btn-alert" title="Set Price Drop Alert" onClick={() => onOpenAlert(product)}>
            🔔 Alert
          </button>
        </div>
      </div>
    </div>
  );
}

function SectionHeader({ title, count }: { title: string; count: number }) {
  return (
    <div className="section-header">
      <div>
        <h2 className="section-title">{title}</h2>
        <span className="section-count">{count} listing{count !== 1 ? 's' : ''}</span>
      </div>
    </div>
  );
}

export default function Home() {
  const [query, setQuery] = useState('');
  const [liveQuery, setLiveQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<Product[]>([]);
  const [hasSearched, setHasSearched] = useState(false);
  const [sortBy, setSortBy] = useState<SortKey>('price');
  const [filterPlatform, setFilterPlatform] = useState('All');

  // Modals state
  const [historyModalProduct, setHistoryModalProduct] = useState<Product | null>(null);
  const [alertModalProduct, setAlertModalProduct] = useState<Product | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setLiveQuery(query);
    setLoading(true);
    setHasSearched(true);
    setResults([]);
    setFilterPlatform('All');
    setSortBy('price');
    try {
      const res = await fetch(`${API_BASE}/api/search?q=${encodeURIComponent(query)}`);
      if (!res.ok) throw new Error('Search failed');
      const data = await res.json();
      setResults(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const sortFn = (a: Product, b: Product) => {
    if (sortBy === 'price') return (a.price || Infinity) - (b.price || Infinity);
    if (sortBy === 'rating') return (b.rating || 0) - (a.rating || 0);
    if (sortBy === 'platform') return a.platform.localeCompare(b.platform);
    return 0;
  };

  const filterFn = (p: Product) => filterPlatform === 'All' || p.platform === filterPlatform;

  const exact = useMemo(() =>
    results
      .filter(p => p.match_type === 'exact')
      .filter(p => filterPlatform === 'All' || p.platform === filterPlatform)
      .sort((a, b) => {
        if (sortBy === 'price') return (a.price || Infinity) - (b.price || Infinity);
        if (sortBy === 'rating') return (b.rating || 0) - (a.rating || 0);
        if (sortBy === 'platform') return a.platform.localeCompare(b.platform);
        return 0;
      }),
    [results, sortBy, filterPlatform]
  );
  const related = useMemo(() =>
    results
      .filter(p => p.match_type === 'related')
      .filter(p => filterPlatform === 'All' || p.platform === filterPlatform)
      .sort((a, b) => {
        if (sortBy === 'price') return (a.price || Infinity) - (b.price || Infinity);
        if (sortBy === 'rating') return (b.rating || 0) - (a.rating || 0);
        if (sortBy === 'platform') return a.platform.localeCompare(b.platform);
        return 0;
      }),
    [results, sortBy, filterPlatform]
  );

  const platforms = ['All', ...Array.from(new Set(results.map(p => p.platform)))];

  return (
    <>
      {/* HEADER */}
      <header className="header">
        <div className="header-inner">
          <div className="logo">DealHunter<span className="logo-dot" /></div>
          <form onSubmit={handleSearch} className="search-form">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#9ca3af" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
            </svg>
            <input
              id="search-input"
              type="text"
              className="search-input"
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Search for iPhone, Smartwatch, Shoes…"
              autoComplete="off"
            />
            <button id="search-btn" type="submit" className="search-btn" disabled={loading}>
              {loading ? 'Searching…' : 'Search'}
            </button>
          </form>
        </div>
      </header>

      <main>
        {/* HERO */}
        {!hasSearched && (
          <section className="hero">
            <h1>Compare prices across<br /><span>all platforms</span></h1>
            <p>Search once. Get results from Amazon, Flipkart, and Meesho — sorted with price history graphs & drop alerts.</p>
            <div className="platform-badges">
              <div className="platform-badge"><div className="dot" style={{ background: '#f59e0b' }} />Amazon</div>
              <div className="platform-badge"><div className="dot" style={{ background: '#2563eb' }} />Flipkart</div>
              <div className="platform-badge"><div className="dot" style={{ background: '#db2777' }} />Meesho</div>
            </div>
            <div className="hero-suggestions">
              <p className="suggestions-label">Try searching for:</p>
              <div className="suggestions-chips">
                {['Samsung Galaxy A35', 'boAt Airdopes 141', 'iPhone 15', 'Noise ColorFit Pro 5', 'Prestige pressure cooker 3L'].map(s => (
                  <button key={s} className="suggestion-chip" onClick={() => setQuery(s)}>{s}</button>
                ))}
              </div>
            </div>
          </section>
        )}

        {/* RESULTS */}
        {hasSearched && (
          <div className="results-container">
            {/* Filter + Sort toolbar */}
            {!loading && results.length > 0 && (
              <div className="toolbar">
                <div className="toolbar-left">
                  <span className="results-meta">Results for <strong>&ldquo;{liveQuery}&rdquo;</strong></span>
                </div>
                <div className="toolbar-right">
                  <div className="filter-group">
                    {platforms.map(pl => (
                      <button key={pl} className={`filter-btn${filterPlatform === pl ? ' active' : ''}`} onClick={() => setFilterPlatform(pl)}>{pl}</button>
                    ))}
                  </div>
                  <div className="sort-group">
                    <span className="sort-label">Sort:</span>
                    {(['price', 'rating', 'platform'] as SortKey[]).map(s => (
                      <button key={s} className={`sort-btn${sortBy === s ? ' active' : ''}`} onClick={() => setSortBy(s)}>
                        {s === 'price' ? '↑ Price' : s === 'rating' ? '★ Rating' : '⊞ Platform'}
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {loading && (
              <div>
                <div className="section-header">
                  <div className="skeleton skel-line" style={{ width: '200px', height: '22px' }} />
                </div>
                <SkeletonGrid count={6} />
              </div>
            )}

            {!loading && results.length === 0 && (
              <div className="empty-state">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
                <p>No results found. Try a different search term.</p>
              </div>
            )}

            {/* ── EXACT MATCHES ── */}
            {!loading && exact.length > 0 && (
              <section className="result-section">
                <SectionHeader title={`Exact Matches — "${liveQuery}"`} count={exact.length} />
                <div className="product-grid">
                  {exact.map((p, i) => (
                    <ProductCard
                      key={p.product_url || `${p.platform}-${p.title}`}
                      product={p}
                      idx={i}
                      onOpenHistory={prod => setHistoryModalProduct(prod)}
                      onOpenAlert={prod => setAlertModalProduct(prod)}
                    />
                  ))}
                </div>
              </section>
            )}

            {/* Divider */}
            {!loading && exact.length > 0 && related.length > 0 && (
              <div className="section-divider" />
            )}

            {/* ── RELATED PRODUCTS ── */}
            {!loading && related.length > 0 && (
              <section className="result-section">
                <SectionHeader title="Related Products" count={related.length} />
                <p className="section-subtitle">Similar products that may also interest you</p>
                <div className="product-grid">
                  {related.map((p, i) => (
                    <ProductCard
                      key={p.product_url || `${p.platform}-${p.title}`}
                      product={p}
                      idx={i}
                      onOpenHistory={prod => setHistoryModalProduct(prod)}
                      onOpenAlert={prod => setAlertModalProduct(prod)}
                    />
                  ))}
                </div>
              </section>
            )}
          </div>
        )}
      </main>

      {/* PRICE HISTORY MODAL */}
      {historyModalProduct && (
        <PriceHistoryModal
          product={historyModalProduct}
          onClose={() => setHistoryModalProduct(null)}
        />
      )}

      {/* PRICE DROP ALERT MODAL */}
      {alertModalProduct && (
        <PriceAlertModal
          product={alertModalProduct}
          onClose={() => setAlertModalProduct(null)}
          onAlertCreated={msg => showToast(msg)}
        />
      )}

      {/* TOAST NOTIFICATION */}
      {toastMessage && (
        <div className="toast-container">
          <div className="toast">
            <span>✨</span> {toastMessage}
          </div>
        </div>
      )}
    </>
  );
}
