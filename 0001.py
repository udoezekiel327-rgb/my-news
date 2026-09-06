import os
import time
import sys
import subprocess
import re
from datetime import datetime

# 1. Verification of Required Core NLP and XML Processing Libraries
try:
    import requests
    import nltk
    from nltk.sentiment.vader import SentimentIntensityAnalyzer
except ImportError:
    print("-> Installing required real-time analysis tools...")
    # FIXED: Split 'requests' and 'nltk' into separate arguments
    subprocess.call([sys.executable, "-m", "pip", "install", "requests", "nltk"])
    import requests
    import nltk
    from nltk.sentiment.vader import SentimentIntensityAnalyzer

# Download internal lexicon rules for immediate sentiment parsing
nltk.download('vader_lexicon', quiet=True)
sia = SentimentIntensityAnalyzer()

# --- LIVE APP CONFIGURATION ---
TOKEN_NUMBER = "8842733470"
TOKEN_SECRET = "AAEjKZi9zHcjwm7v3If8iPNvOmOCMUiHs0I"
CHAT_ID = "6951496380"
# FIXED: Corrected Telegram API URL structure
TELEGRAM_URL = f"https://api.telegram.org/bot{TOKEN_NUMBER}:{TOKEN_SECRET}/sendMessage"

# Global RSS Network Data Streams
RSS_FEEDS = {
    "Reuters Economy": "https://google.com",
    "CNBC Macro Finance": "https://google.com"
}

# Tracking set to remember sent articles so you NEVER get duplicate alert spams
SENT_ARTICLES_CACHE = set()

# Comprehensive text layout filters tracking ALL major currency zones
ZONES = {
    "🇺🇸 USD ZONE": ["fed", "powell", "fomc", "white house", "nfp", "dollar", "us economy", "united states"],
    "🇪🇺 EUR ZONE": ["ecb", "lagarde", "eurozone", "germany", "france", "brussels", "european union"],
    "🇯🇵 JPY ZONE": ["boj", "ueda", "japan", "tokyo", "yen"],
    "🇬🇧 GBP ZONE": ["boe", "bailey", "uk economy", "britain", "london", "pound sterling"],
    "🇨🇭 CHF ZONE": ["snb", "switzerland", "swiss", "zurich", "franc"],
    "🇦🇺 AUD ZONE": ["rba", "bullock", "australia", "sydney", "aussie", "australian dollar"],
    "🇨🇦 CAD ZONE": ["boc", "tiff", "macklem", "canada", "ottawa", "loonie", "canadian dollar"],
    "🇳🇿 NZD ZONE": ["rbnz", "orr", "new zealand", "wellington", "kiwi", "nz dollar"]
}

CATEGORIES = {
    "📈 INTEREST RATES": ["hike", "cut", "hawkish", "dovish", "interest rate", "monetary policy", "tightening", "easing"],
    "📊 GDP AND GROWTH": ["gdp", "recession", "growth", "contraction", "economic output", "unemployment", "labor market"],
    "⚖️ POLITICAL RISK": ["election", "tariff", "sanction", "geopolitical", "trade war", "conflict", "brexit"],
    "💸 INFLATION DATA": ["cpi", "inflation", "consumer prices", "ppi", "core cpi"]
}

def clean_xml_tags(text):
    """Strips out structural HTML/XML tags from raw RSS text blocks."""
    if not text:
        return ""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text)

def analyze_sentiment(text):
    """Evaluates underlying trading sentiment metrics using VADER."""
    scores = sia.polarity_scores(text.lower())
    compound = scores['compound']
    if compound >= 0.05:
        return "🟢 BULLISH (Positive)"
    elif compound <= -0.05:
        return "🔴 BEARISH (Negative)"
    else:
        return "⚪ NEUTRAL"

def send_telegram_alert(message):
    """Pushes formatted UI data feeds directly to your phone."""
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        res = requests.post(TELEGRAM_URL, json=payload, timeout=10)
        return res.json().get("ok", False)
    except Exception as e:
        print("-> Telegram Broadcast Error:", e)
        return False

def process_article(headline, summary):
    """Processes text criteria filters, checks cache, and triggers active mobile alerts."""
    headline = clean_xml_tags(headline)
    summary = clean_xml_tags(summary)
    
    combined = f"{headline} {summary}".lower()
    
    # Run structural criteria scan
    matched_zones = [z for z, keywords in ZONES.items() if any(k in combined for k in keywords)]
    matched_cats = [c for c, keywords in CATEGORIES.items() if any(k in combined for k in keywords)]
    
    # Filter block to eliminate unrelated news noise
    if not matched_zones and not matched_cats:
        return False
        
    sentiment_rating = analyze_sentiment(f"{headline} {summary}")
    current_timestamp = datetime.now().strftime("%d/%m/%Y at %I:%M:%S %p")
    
    # Format into a professional UI layout incorporating the timestamp row
    ui_layout = (
        f"<b>🚨 LIVE MACRO NEWS WIRE BREAKING</b>\n\n"
        f"📅 <b>Released:</b> {current_timestamp}\n"
        f"📰 <b>Headline:</b> {headline}\n\n"
        f"🌍 <b>Zones:</b> {', '.join(matched_zones) if matched_zones else 'Global Context'}\n"
        f"📌 <b>Category:</b> {', '.join(matched_cats) if matched_cats else 'General Macro'}\n"
        f"📊 <b>Sentiment:</b> {sentiment_rating}\n\n"
        f"📝 <i>Summary: {summary[:250]}...</i>"
    )
    
    print(f"\n[LIVE ALERT MATCHED]: {headline[:50]}...")
    return send_telegram_alert(ui_layout)

def run_rss_scraper_cycle():
    """Parses live financial feeds utilizing custom lightweight XML data extractions."""
    print(f"📡 [{datetime.now().strftime('%I:%M:%S %p')}] Scanning live internet financial tickers...")
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    for feed_name, url in RSS_FEEDS.items():
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code != 200:
                continue
                
            # Parse XML objects using basic fast structural text finds
            titles = re.findall(r'<title>(.*?)</title>', response.text)
            descriptions = re.findall(r'<description>(.*?)</description>', response.text)
            
            # Match items and loop through the newest elements
            for i in range(1, min(len(titles), 8)):
                headline = titles[i]
                summary = descriptions[i] if i < len(descriptions) else "Click link for breakdown summaries."
                
                # Deduplication cache lookup
                if headline in SENT_ARTICLES_CACHE:
                    continue
                    
                # Add to cache database matrix
                SENT_ARTICLES_CACHE.add(headline)
                
                # Run through the main macro analyzer engine
                process_article(headline, summary)
                time.sleep(1)
                
        except Exception as e:
            print(f"❌ Network read anomaly on {feed_name}: {e}")

if __name__ == "__main__":
    print("🚀 Real-Time Live Scraper Engine Engaged Successfully.")
    run_rss_scraper_cycle()
    print("✅ Run complete.")