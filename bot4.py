import os
import time
import sys
import re
import xml.etree.ElementTree as ET
from datetime import datetime
import asyncio

try:
    import requests
    import nltk
    from nltk.sentiment.vader import SentimentIntensityAnalyzer
except ImportError:
    import subprocess
    subprocess.call([sys.executable, "-m", "pip", "install", "requests nltk"])
    import requests
    import nltk
    from nltk.sentiment.vader import SentimentIntensityAnalyzer

nltk.download('vader_lexicon', quiet=True)
sia = SentimentIntensityAnalyzer()

# Adjust VADER scores specifically for financial market terminology
FINANCIAL_LEXICON = {
    "hike": 2.5, "hawkish": 2.5, "surge": 1.5, "growth": 1.5, "robust": 1.5,
    "cut": -2.0, "dovish": -2.5, "recession": -2.5, "collapse": -3.0, "shrink": -2.0,
    "inflation": -0.5, "contraction": -1.5, "unemployment": -1.5, "beat": 2.0, "miss": -2.0
}
sia.lexicon.update(FINANCIAL_LEXICON)

# --- TELEGRAM CONFIGURATION ---
BOT_TOKEN = os.environ.get("BOT_SECRET", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
BASE_TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Optional API key for Economic Calendar Pre-Announcements (Free key available at financialmodelingprep.com)
FMP_API_KEY = "demo" 

APPROVED_USERS_FILE = "approved_users.txt"

# --- RELIABLE LIVE MACRO RSS SOURCES & OFFICIAL FEEDS ---
RSS_FEEDS = {
    # Institutional & Market News Feeds
    "CNBC Economy": "https://www.cnbc.com/id/20910258/device/rss/rss.html",
    "CNBC Market Insider": "https://www.cnbc.com/id/20409666/device/rss/rss.html",
    "Yahoo Macro Finance": "https://finance.yahoo.com/rss/topstories",
    "MarketWatch Headlines": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    "ForexLive Breaking": "https://www.forexlive.com/feed/",
    "DailyFX News": "https://www.dailyfx.com/feeds/market-news",
    
    # Official Government & Central Bank RSS Feeds
    "US BLS (Consumer Price Index)": "https://www.bls.gov/feed/cpi_at.rss",
    "US BLS (Employment / NFP)": "https://www.bls.gov/feed/empsit_at.rss",
    "US BLS (Producer Price Index)": "https://www.bls.gov/feed/ppi_at.rss",
    "US Federal Reserve Press Releases": "https://www.federalreserve.gov/feeds/press_monetary.xml"
}

SENT_ARTICLES_CACHE = set()

# Regex-bounded Zone matching
ZONES = {
    "🇺🇸 USD ZONE": [r"\bfed\b", r"\bwarsh\b", r"\bfomc\b", r"\bdollar\b", r"\bus economy\b", r"\bunited states\b", r"\bnfp\b", r"\bcpi\b", r"\bppi\b"],
    "🇪🇺 EUR ZONE": [r"\becb\b", r"\blagarde\b", r"\beurozone\b", r"\bgermany\b", r"\bfrance\b", r"\beuro\b"],
    "🇯🇵 JPY ZONE": [r"\bboj\b", r"\bueda\b", r"\bjapan\b", r"\btokyo\b", r"\byen\b"],
    "🇬🇧 GBP ZONE": [r"\bboe\b", r"\bbailey\b", r"\buk economy\b", r"\bbritain\b", r"\bpound\b", r"\bsterling\b"],
    "🇨🇭 CHF ZONE": [r"\bsnb\b", r"\bswitzerland\b", r"\bswiss\b", r"\bfranc\b"],
    "🇦🇺 AUD ZONE": [r"\brba\b", r"\bbullock\b", r"\baustralia\b", r"\baussie\b", r"\baustralian dollar\b"],
    "🇨🇦 CAD ZONE": [r"\bboc\b", r"\bmacklem\b", r"\bcanada\b", r"\bloonie\b", r"\bcanadian dollar\b"],
    "🇳🇿 NZD ZONE": [r"\brbnz\b", r"\borr\b", r"\bnew zealand\b", r"\bkiwi\b", r"\bnz dollar\b"]
}

CATEGORIES = {
    "📈 INTEREST RATES / FOMC": [r"\bhike\b", r"\bcut\b", r"\bhawkish\b", r"\bdovish\b", r"\binterest rate\b", r"\bmonetary policy\b", r"\bfomc\b", r"\bwarsh\b"],
    "📊 GDP AND GROWTH": [r"\bgdp\b", r"\brecession\b", r"\bgrowth\b", r"\bcontraction\b", r"\beconomic output\b", r"\bunemployment\b"],
    "⚖️ POLITICAL RISK": [r"\belection\b", r"\btariff\b", r"\bsanction\b", r"\bgeopolitical\b", r"\btrade war\b"],
    "💸 INFLATION (CPI / PPI)": [r"\bcpi\b", r"\binflation\b", r"\bconsumer prices\b", r"\bppi\b", r"\bproducer prices\b"],
    "👷 EMPLOYMENT (NFP)": [r"\bnfp\b", r"\bnonfarm payrolls\b", r"\bpayrolls\b", r"\bjobs report\b", r"\bunemployment rate\b"],
    "🧠 TOP ECONOMIST ANALYSIS": [r"\bhatzius\b", r"\bgapen\b", r"\bzentner\b", r"\bguha\b", r"\bfurman\b", r"\bgoldman sachs\b", r"\bmorgan stanley\b", r"\bjp morgan\b", r"\bubs\b"]
}

# --- HELPER FUNCTIONS ---
def load_approved_users():
    if not os.path.exists(APPROVED_USERS_FILE):
        return [str(CHAT_ID)]
    with open(APPROVED_USERS_FILE, "r") as f:
        ids = [line.strip() for line in f.readlines() if line.strip()]
    if str(CHAT_ID) not in ids:
        ids.append(str(CHAT_ID))
    return ids

def save_approved_user(user_id):
    user_id_str = str(user_id)
    ids = load_approved_users()
    if user_id_str not in ids:
        with open(APPROVED_USERS_FILE, "a") as f:
            f.write(f"{user_id_str}\n")

def clean_html(text):
    if not text:
        return ""
    clean = re.compile('<.*?>')
    return re.sub(clean, '', text).strip()

def analyze_financial_sentiment(text):
    scores = sia.polarity_scores(text.lower())
    compound = scores['compound']
    if compound >= 0.15:
        return "🟢 BULLISH (Positive)"
    elif compound <= -0.15:
        return "🔴 BEARISH (Negative)"
    else:
        return "⚪ NEUTRAL"

def send_telegram_alert(message):
    approved_ids = load_approved_users()
    success = False
    
    for current_recipient in approved_ids:
        payload = {
            "chat_id": current_recipient,
            "text": message,
            "parse_mode": "HTML"
        }
        try:
            res = requests.post(f"{BASE_TELEGRAM_URL}/sendMessage", json=payload, timeout=10)
            if current_recipient == str(CHAT_ID):
                success = res.json().get("ok", False)
        except Exception as e:
            print(f"-> Telegram Broadcast Error for {current_recipient}:", e)
            
    return success

def process_article(headline, summary, source="Live Feed", article_link=None):
    headline = clean_html(headline)
    summary = clean_html(summary)
    combined = f"{headline} {summary}".lower()
    
    matched_zones = [z for z, patterns in ZONES.items() if any(re.search(p, combined) for p in patterns)]
    matched_cats = [c for c, patterns in CATEGORIES.items() if any(re.search(p, combined) for p in patterns)]
    
    if not matched_zones:
        return False
        
    sentiment_rating = analyze_financial_sentiment(f"{headline} {summary}")
    current_timestamp = datetime.now().strftime("%d/%m/%Y at %I:%M:%S %p")
    
    link_html = f"🔗 <a href='{article_link}'>Read Full Article</a>\n" if article_link else ""
    
    ui_layout = (
        f"<b>🚨 LIVE MACRO NEWS WIRE DETECTED</b>\n\n"
        f"📡 <b>Source:</b> {source}\n"
        f"📅 <b>Released:</b> {current_timestamp}\n"
        f"📰 <b>Headline:</b> {headline}\n\n"
        f"🌍 <b>Zones:</b> {', '.join(matched_zones)}\n"
        f"📌 <b>Category:</b> {', '.join(matched_cats) if matched_cats else 'General Macro'}\n"
        f"📊 <b>Sentiment:</b> {sentiment_rating}\n\n"
        f"📝 <i>Summary: {summary[:250]}...</i>\n\n"
        f"{link_html}"
    )
    
    print(f"\n[TARGET MACRO MATCH]: {headline[:50]}...")
    return send_telegram_alert(ui_layout)

def run_live_feed_scraper():
    print(f"📡 [{datetime.now().strftime('%I:%M:%S %p')}] Scanning active market feeds...")
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    for feed_name, url in RSS_FEEDS.items():
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                continue
            
            root = ET.fromstring(response.content)
            
            for item in root.findall('.//item'):
                title_elem = item.find('title')
                desc_elem = item.find('description')
                link_elem = item.find('link')
                
                title = title_elem.text if title_elem is not None else ""
                desc = desc_elem.text if desc_elem is not None else ""
                link = link_elem.text.strip() if link_elem is not None and link_elem.text else ""
                
                if not title or title in SENT_ARTICLES_CACHE:
                    continue
                
                SENT_ARTICLES_CACHE.add(title)
                process_article(title, desc, source=feed_name, article_link=link)
                time.sleep(0.2)
                
        except Exception as e:
            # Prevent XML parsing errors on non-standard RSS formats from crashing thread
            continue

# --- PRE-ANNOUNCEMENT / ECONOMIC CALENDAR WATCHER ---
def fetch_pre_announcements():
    """Polls Economic Calendar for upcoming major releases (NFP, CPI, PPI, FOMC)."""
    try:
        url = f"https://financialmodelingprep.com/api/v3/economic_calendar?apikey={FMP_API_KEY}"
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return
            
        events = resp.json()
        target_events = ["Non Farm Payrolls", "CPI MoM", "PPI MoM", "FOMC Rate Decision"]
        
        for event in events:
            event_name = event.get("event", "")
            if any(target in event_name for target in target_events):
                event_date = event.get("date", "")
                estimate = event.get("estimate", "N/A")
                previous = event.get("previous", "N/A")
                
                cache_key = f"{event_name}_{event_date}"
                if cache_key in SENT_ARTICLES_CACHE:
                    continue
                    
                SENT_ARTICLES_CACHE.add(cache_key)
                
                preview_msg = (
                    f"🗓️ <b>HIGH IMPACT MACRO PREPAREDNESS ALERT</b>\n\n"
                    f"🎯 <b>Event:</b> {event_name}\n"
                    f"⏰ <b>Scheduled Time:</b> {event_date}\n"
                    f"🔮 <b>Analyst Consensus Estimate:</b> {estimate}\n"
                    f"🔙 <b>Previous Release:</b> {previous}\n\n"
                    f"⚡ <i>Stay alerted for immediate volatility upon release!</i>"
                )
                send_telegram_alert(preview_msg)
    except Exception as e:
        print("Calendar fetch note:", e)

# --- TELEGRAM POLLING & AUTHORIZATION LISTENER ---
def check_telegram_updates(offset=0):
    try:
        url = f"{BASE_TELEGRAM_URL}/getUpdates"
        payload = {"offset": offset, "timeout": 5}
        resp = requests.get(url, json=payload, timeout=7).json()
        
        if not resp.get("ok"):
            return offset
            
        for update in resp.get("result", []):
            update_id = update["update_id"]
            offset = update_id + 1
            
            if "message" in update and "text" in update["message"]:
                msg = update["message"]
                text = msg["text"]
                sender_id = str(msg["chat"]["id"])
                first_name = msg["chat"].get("first_name", "Unknown")
                username = msg["chat"].get("username", "NoUsername")
                
                if text.startswith("/start"):
                    approved_list = load_approved_users()
                    if sender_id in approved_list:
                        requests.post(f"{BASE_TELEGRAM_URL}/sendMessage", json={
                            "chat_id": sender_id,
                            "text": " You are already an approved user of the Macro Forex Engine!"
                        })
                    else:
                        requests.post(f"{BASE_TELEGRAM_URL}/sendMessage", json={
                            "chat_id": sender_id,
                            "text": "⏳ Welcome! Your access request has been sent to the Admin. Please wait for authorization."
                        })
                        
                        admin_text = (
                            f"👤 <b>New User Requesting Access:</b>\n\n"
                            f"🏷️ <b>Name:</b> {first_name}\n"
                            f"🌐 <b>Username:</b> @{username}\n"
                            f"🆔 <b>Chat ID:</b> <code>{sender_id}</code>"
                        )
                        keyboard = {
                            "inline_keyboard": [[
                                {"text": "✅ Approve", "callback_data": f"approve_{sender_id}"},
                                {"text": "❌ Reject", "callback_data": f"reject_{sender_id}"}
                            ]]
                        }
                        requests.post(f"{BASE_TELEGRAM_URL}/sendMessage", json={
                            "chat_id": CHAT_ID,
                            "text": admin_text,
                            "parse_mode": "HTML",
                            "reply_markup": keyboard
                        })

            elif "callback_query" in update:
                cb = update["callback_query"]
                cb_id = cb["id"]
                cb_data = cb["data"]
                admin_msg = cb.get("message", {})
                message_id = admin_msg.get("message_id")
                
                requests.post(f"{BASE_TELEGRAM_URL}/answerCallbackQuery", json={"callback_query_id": cb_id})
                
                if cb_data.startswith("approve_"):
                    target_id = cb_data.split("_")[1]
                    save_approved_user(target_id)
                    
                    requests.post(f"{BASE_TELEGRAM_URL}/editMessageText", json={
                        "chat_id": CHAT_ID,
                        "message_id": message_id,
                        "text": f"✅ <b>Approved user with ID:</b> <code>{target_id}</code>",
                        "parse_mode": "HTML"
                    })
                    requests.post(f"{BASE_TELEGRAM_URL}/sendMessage", json={
                        "chat_id": target_id,
                        "text": "🎉 Congratulations! Your request has been approved. You will now receive live Forex macro feeds!"
                    })
                    
                elif cb_data.startswith("reject_"):
                    target_id = cb_data.split("_")[1]
                    requests.post(f"{BASE_TELEGRAM_URL}/editMessageText", json={
                        "chat_id": CHAT_ID,
                        "message_id": message_id,
                        "text": f"❌ <b>Rejected user request for ID:</b> <code>{target_id}</code>",
                        "parse_mode": "HTML"
                    })
                    requests.post(f"{BASE_TELEGRAM_URL}/sendMessage", json={
                        "chat_id": target_id,
                        "text": "❌ Your request to access the bot was declined."
                    })

        return offset
    except Exception as e:
        return offset

# --- CONCURRENT ASYNC LOOPS ---
async def telegram_listener_task():
    offset = 0
    while True:
        offset = await asyncio.to_thread(check_telegram_updates, offset)
        await asyncio.sleep(1)

async def rss_scraper_task():
    while True:
        await asyncio.to_thread(run_live_feed_scraper)
        await asyncio.sleep(30)

async def calendar_announcement_task():
    while True:
        await asyncio.to_thread(fetch_pre_announcements)
        await asyncio.sleep(21600)  # Checks calendar once every 6 hours

async def main():
    print("🚀 Upgraded Financial Macro News Engine Active...")
    print("🤖 Authorization Approval Listener Active...")
    print("-> Continuous multi-feed scanning running. Press 'Ctrl + C' to stop.")
    print("-" * 65)
    
    await asyncio.gather(
        telegram_listener_task(),
        rss_scraper_task(),
        calendar_announcement_task()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bot shutdown requested. Exiting cleanly...")
