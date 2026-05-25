"""
rss_sources.py
--------------
Curated RSS / Atom feed catalogue for broad financial market coverage.
Organised by category so the ingestor can fetch selectively or all at once.

All feeds are free / public.  No API key required.
"""

# Each entry: (label, feed_url)
# label is used as the 'source' tag in chunk metadata.

RSS_FEEDS: dict[str, list[tuple[str, str]]] = {

    # ── US Macro & Fed ────────────────────────────────────────────────────────
    "us_macro": [
        ("Bloomberg Economics",     "https://feeds.bloomberg.com/economics/news.rss"),
        ("Reuters Business",        "https://feeds.reuters.com/reuters/businessNews"),
        ("Reuters Markets",         "https://feeds.reuters.com/reuters/UKBusiness"),
        ("CNBC Economy",            "https://www.cnbc.com/id/20910258/device/rss/rss.html"),
        ("WSJ Economy",             "https://feeds.content.dowjones.io/public/rss/mw_realestate"),
        ("MarketWatch Economy",     "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
        ("FT Markets",              "https://www.ft.com/rss/markets"),
        ("FT Economics",            "https://www.ft.com/rss/economics"),
        ("Calculated Risk",         "https://www.calculatedriskblog.com/feeds/posts/default"),
        ("Fed Reserve Atlanta",     "https://www.frbatlanta.org/rss/news"),
        ("Fed Reserve NY",          "https://feeds.newyorkfed.org/medialibrary/media/research/staff_reports/sr.xml"),
    ],

    # ── Global Central Banks ──────────────────────────────────────────────────
    "central_banks": [
        ("BIS Press",               "https://www.bis.org/press.rss"),
        ("IMF News",                "https://www.imf.org/en/News/RSS"),
        ("World Bank News",         "https://feeds.worldbank.org/worldbank/news"),
        ("ECB Press",               "https://www.ecb.europa.eu/rss/press.html"),
        ("Bank of England",         "https://www.bankofengland.co.uk/rss/speeches"),
        ("RBI Notifications",       "https://www.rbi.org.in/rss/NotificationsView.aspx"),
        ("OECD Latest",             "https://www.oecd.org/newsroom/rss.xml"),
        ("Bank of Japan",           "https://www.boj.or.jp/en/rss/whatsnew.xml"),
        ("PBoC News",               "http://www.pbc.gov.cn/english/rss/130719enrss.xml"),
        ("Bank of Canada",          "https://www.bankofcanada.ca/feed/"),
        ("RBA Media",               "https://www.rba.gov.au/rss/rss-media-releases.xml"),
        ("Swiss National Bank",     "https://www.snb.ch/en/rss/mmr"),
        ("Banco Central Brazil",    "https://www.bcb.gov.br/api/feed/sitebcb/sitefeeds/noticias"),
    ],

    # ── Europe Markets ────────────────────────────────────────────────────────
    "europe": [
        ("FT Markets",              "https://www.ft.com/rss/markets"),
        ("FT Europe",               "https://www.ft.com/rss/world/europe"),
        ("Reuters Europe Business", "https://feeds.reuters.com/reuters/UKBusiness"),
        ("London Stock Exchange",   "https://www.londonstockexchange.com/exchange/prices-and-markets/rss/rss.xml"),
        ("Handelsblatt (DE)",       "https://www.handelsblatt.com/contentexport/feed/schlagzeilen"),
        ("Les Echos (FR)",          "https://www.lesechos.fr/rss/rss_economie.xml"),
        ("Corriere Economia (IT)",  "https://xml2.corriereobjects.it/rss/economia.xml"),
        ("EuroNews Business",       "https://www.euronews.com/rss?level=theme&name=business"),
        ("ECB Blog",                "https://www.ecb.europa.eu/rss/blog.html"),
    ],

    # ── Asia-Pacific Markets ──────────────────────────────────────────────────
    "asia_pacific": [
        ("Nikkei Asia",             "https://asia.nikkei.com/rss"),
        ("South China Morning Post","https://www.scmp.com/rss/91/feed"),
        ("SCMP Business",           "https://www.scmp.com/rss/5/feed"),
        ("Channel News Asia",       "https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml&category=6511"),
        ("Straits Times Business",  "https://www.straitstimes.com/news/business/rss.xml"),
        ("Japan Times Business",    "https://www.japantimes.co.jp/feed/business/"),
        ("Sydney Morning Herald",   "https://www.smh.com.au/rss/business.xml"),
        ("Korea Herald Business",   "http://www.koreaherald.com/common/rss_xml.php?ct=102"),
        ("Taipei Times Business",   "https://www.taipeitimes.com/xml/business.rss"),
        ("Jakarta Post Business",   "https://www.thejakartapost.com/bisnistech/feed"),
        ("Bangkok Post Business",   "https://www.bangkokpost.com/rss/data/business.xml"),
    ],

    # ── LatAm & MENA Markets ─────────────────────────────────────────────────
    "latam_mena": [
        ("Reuters LatAm",          "https://feeds.reuters.com/reuters/Latinamerica"),
        ("Bloomberg LatAm",        "https://feeds.bloomberg.com/latam/news.rss"),
        ("Valor Economico (BR)",   "https://pox.globo.com/rss/valor/"),
        ("El Financiero (MX)",     "https://www.elfinanciero.com.mx/rss/"),
        ("Arab News Business",     "https://www.arabnews.com/rss/business"),
        ("Gulf News Business",     "https://gulfnews.com/business/rss"),
        ("Daily Sabah Economy",    "https://www.dailysabah.com/rssFeed/economy"),
        ("Africa Business",        "https://africa.businessinsider.com/rss"),
    ],

    # ── Equities & Earnings ───────────────────────────────────────────────────
    "equities": [
        ("CNBC Markets",            "https://www.cnbc.com/id/15839069/device/rss/rss.html"),
        ("Bloomberg Markets",       "https://feeds.bloomberg.com/markets/news.rss"),
        ("Seeking Alpha Markets",   "https://seekingalpha.com/feed.xml"),
        ("BusinessInsider Markets", "https://markets.businessinsider.com/rss/news"),
        ("Reuters Stocks",          "https://feeds.reuters.com/reuters/companyNews"),
        ("Yahoo Finance",           "https://finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US"),
        ("Investopedia",            "https://www.investopedia.com/feeds/news.xml"),
        ("Barron's",                "https://www.barrons.com/xml/rss/3_7514.xml"),
        ("Motley Fool",             "https://www.fool.com/feeds/index.aspx"),
    ],

    # ── Fixed Income & Credit ─────────────────────────────────────────────────
    "fixed_income": [
        ("Bond Buyer",              "https://www.bondbuyer.com/feed"),
        ("Bloomberg Rates",         "https://feeds.bloomberg.com/rates-bonds/news.rss"),
        ("Credit Suisse Research",  "https://www.credit-suisse.com/rss/researchPublications.xml"),
    ],

    # ── Commodities & Energy ──────────────────────────────────────────────────
    "commodities": [
        ("Reuters Commodities",     "https://feeds.reuters.com/reuters/commoditiesNews"),
        ("Platts Energy",           "https://www.spglobal.com/platts/en/rss-feed/oil"),
        ("OilPrice.com",            "https://oilprice.com/rss/main"),
        ("Gold Price",              "https://goldprice.org/rss/gold-news.xml"),
        ("CNBC Commodities",        "https://www.cnbc.com/id/15839064/device/rss/rss.html"),
        ("Bloomberg Energy",        "https://feeds.bloomberg.com/energy-and-oil/news.rss"),
        ("Natural Gas Intel",       "https://www.naturalgasintel.com/feed/"),
        ("Mining.com",              "https://www.mining.com/feed/"),
        ("BarChart Commodities",    "https://www.barchart.com/rss/news/commodities"),
    ],

    # ── India Markets ─────────────────────────────────────────────────────────
    "india": [
        # ── Top-tier Market News ──
        ("Economic Times Markets",  "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"),
        ("Economic Times Economy",  "https://economictimes.indiatimes.com/news/economy/rssfeeds/1386920271.cms"),
        ("Economic Times Stocks",   "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms"),
        ("Economic Times MF",       "https://economictimes.indiatimes.com/mf/rssfeeds/15993498.cms"),
        ("Economic Times IPO",      "https://economictimes.indiatimes.com/markets/ipos/rssfeeds/2165229.cms"),
        ("Livemint Markets",        "https://www.livemint.com/rss/markets"),
        ("Livemint Economy",        "https://www.livemint.com/rss/economy"),
        ("Livemint Money",          "https://www.livemint.com/rss/money"),
        ("Business Standard",       "https://www.business-standard.com/rss/markets-106.rss"),
        ("BS Economy",              "https://www.business-standard.com/rss/economy-policy-102.rss"),
        ("BS Companies",            "https://www.business-standard.com/rss/companies-101.rss"),
        ("Hindu Business",          "https://www.thehindu.com/business/Economy/?service=rss"),
        ("MoneyControl News",       "https://www.moneycontrol.com/rss/marketsnews.xml"),
        ("MoneyControl Economy",    "https://www.moneycontrol.com/rss/economy.xml"),
        ("MoneyControl MF",         "https://www.moneycontrol.com/rss/mf.xml"),
        ("MoneyControl IPO",        "https://www.moneycontrol.com/rss/ipo.xml"),
        ("MoneyControl Results",    "https://www.moneycontrol.com/rss/results.xml"),
        ("MoneyControl Commodities","https://www.moneycontrol.com/rss/commodities.xml"),
        ("NDTV Business",           "https://feeds.feedburner.com/NdtvProfitLatestUpdates"),
        ("Financial Express",       "https://www.financialexpress.com/feed/"),
        # ── Regulatory ──
        ("RBI Monetary",            "https://www.rbi.org.in/rss/MonetaryPolicyView.aspx"),
        ("RBI Notifications",       "https://www.rbi.org.in/rss/NotificationsView.aspx"),
        ("RBI Press Releases",      "https://www.rbi.org.in/rss/PressReleaseView.aspx"),
        ("SEBI Updates",            "https://www.sebi.gov.in/rss/sebiNewsUpdates.xml"),
        # ── India-specific Analysis ──
        ("Mint Lounge Business",    "https://www.livemint.com/rss/opinion"),
        ("FirstPost Business",      "https://www.firstpost.com/rss/business.xml"),
        ("Outlook Business",        "https://www.outlookbusiness.com/rss"),
    ],

    # ── Geopolitics & Trade ───────────────────────────────────────────────────
    "geopolitics": [
        ("Reuters World",           "https://feeds.reuters.com/Reuters/worldNews"),
        ("Bloomberg Politics",      "https://feeds.bloomberg.com/politics/news.rss"),
        ("FT World",                "https://www.ft.com/rss/world"),
        ("Stratfor",                "https://worldview.stratfor.com/rss.xml"),
        ("Foreign Affairs",         "https://www.foreignaffairs.com/rss.xml"),
        ("VOA Economy",             "https://www.voanews.com/podcast/3160.xml"),
        ("Al Jazeera Economy",      "https://www.aljazeera.com/xml/rss/all.xml"),
        ("South China Morning Post","https://www.scmp.com/rss/91/feed"),
    ],

    # ── Tech & AI (market-moving) ─────────────────────────────────────────────
    "tech_ai": [
        ("TechCrunch",              "https://techcrunch.com/feed/"),
        ("The Verge Tech",          "https://www.theverge.com/rss/index.xml"),
        ("Bloomberg Tech",          "https://feeds.bloomberg.com/technology/news.rss"),
        ("MIT Technology Review",   "https://www.technologyreview.com/feed/"),
        ("Wired Business",          "https://www.wired.com/feed/business/rss"),
        ("Ars Technica",            "https://feeds.arstechnica.com/arstechnica/index"),
        ("CNBC Tech",               "https://www.cnbc.com/id/19854910/device/rss/rss.html"),
    ],

    # ── Alternative / Macro Research ─────────────────────────────────────────
    "macro_research": [
        ("Project Syndicate",       "https://www.project-syndicate.org/rss"),
        ("Harvard Business Review", "https://hbr.org/feed"),
        ("VoxEU",                   "https://voxeu.org/rss.xml"),
        ("Brookings",               "https://www.brookings.edu/feed/"),
        ("Peterson Institute",      "https://www.piie.com/rss.xml"),
        ("NBER Working Papers",     "https://www.nber.org/rss/new_working_papers.xml"),
        ("Econbrowser",             "https://econbrowser.com/feed"),
        ("Macro Musings",           "https://www.cato.org/multimedia/macro-musings/rss"),
    ],

    # ── Crypto & Digital Assets ───────────────────────────────────────────────
    "crypto": [
        ("CoinDesk",                "https://www.coindesk.com/arc/outboundfeeds/rss/"),
        ("CoinTelegraph",           "https://cointelegraph.com/rss"),
        ("Decrypt",                 "https://decrypt.co/feed"),
        ("The Block",               "https://www.theblock.co/rss.xml"),
        ("Blockworks",              "https://blockworks.co/feed"),
        ("Bitcoin Magazine",        "https://bitcoinmagazine.com/.rss/full/"),
    ],

    # ── Policy & Regulation ───────────────────────────────────────────────────
    "policy_regulation": [
        ("Politico Economy",        "https://www.politico.com/rss/economy.xml"),
        ("The Hill Business",       "https://thehill.com/business-lobbying/feed/"),
        ("FCA News",                "https://www.fca.org.uk/news/rss.xml"),
        ("SEC Press Releases",      "https://www.sec.gov/news/pressreleases.rss"),
    ],

    # ── SEC & Regulatory Filings (Quantum Pulse) ────────────────────────────────
    "sec_filings": [
        ("SEC Press Releases",      "https://www.sec.gov/news/pressreleases.rss"),
        ("SEC Speeches",            "https://www.sec.gov/news/speeches.rss"),
        ("SEC Litigation",          "https://www.sec.gov/litigation/litreleases.rss"),
        ("SEC Trading Suspensions", "https://www.sec.gov/litigation/suspensions.rss"),
        ("SEC Staff Guidance",      "https://www.sec.gov/news/studies.rss"),
    ],

    # ── Breaking News Wires (Quantum Pulse) ───────────────────────────────────
    "breaking_news": [
        ("GlobeNewswire",           "https://www.globenewswire.com/RssFeed/subjectcode/01-Debt%20Financing/feedTitle/GlobeNewswire%20-%20Debt%20Financing"),
        ("PR Newswire Finance",     "https://www.prnewswire.com/rss/financial-services-latest-news/financial-services-latest-news-list.rss"),
        ("BusinessWire",            "https://feed.businesswire.com/rss/home/?rss=G1QFDERJXkJeEFpRWQ=="),
        ("AP Business",             "https://rsshub.app/apnews/topics/business"),
    ],
}

# Flattened list of all feeds (for full ingestion runs)
ALL_FEEDS: list[tuple[str, str, str]] = [
    (category, label, url)
    for category, feeds in RSS_FEEDS.items()
    for label, url in feeds
]

# High-priority feeds for quick refresh (most market-moving)
PRIORITY_FEEDS: list[tuple[str, str, str]] = [
    (cat, lbl, url)
    for cat, feeds in RSS_FEEDS.items()
    if cat in ("us_macro", "equities", "india", "commodities", "central_banks")
    for lbl, url in feeds
]

# ── Quantum Pulse: Ultra-high-frequency feeds (polled every 60s) ─────────────
PULSE_FEEDS: list[tuple[str, str, str]] = [
    (cat, lbl, url)
    for cat, feeds in RSS_FEEDS.items()
    if cat in ("sec_filings", "breaking_news")
    for lbl, url in feeds
]
