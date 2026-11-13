"""Reads the public Telegram channel and updates products.json + img/ for the site."""
import html
import json
import os
import re

import requests

CHANNEL = "Hahotfim"
PAGES = 4            # כמה עמודים אחורה לקרוא בערוץ (בערך 20 הודעות לעמוד)
MAX_ITEMS = 80       # כמה מוצרים לשמור באתר
OUT = "products.json"
IMG_DIR = "img"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; hahotfim-site/1.0)"}

# קטגוריה לפי מילות מפתח בשם המוצר (הראשונה שמתאימה מנצחת)
CATS = [
    ("car", ["רכב", "טסלה", "tesla", "dash cam", "dvr", "carplay", "מתנע", "jump starter", "צמיג", "tire"]),
    ("creator", ["מיקרופון", "microphone", "סלפי", "selfie", "חצובה", "tripod", "gimbal", "מייצב", "lavalier"]),
    ("gaming", ["gamepad", "בקר", "ram", "ddr", "keyboard", "מקלדת", "mouse", "עכבר", "gaming", "ssd", "מחשב"]),
    ("audio", ["אוזני", "earbuds", "headphone", "anc", "שעון", "watch", "טבעת", "ring", "רמקול", "speaker", "mp3", "נגן"]),
    ("tools", ["מברג", "מקדח", "drill", "מפוח", "מסור", "saw", "laser", "פלס", "worx", "כלי עבודה"]),
    ("beauty", ["פנים", "עיסוי", "massage", "שיער", "hair", "טיפוח", "שיניים", "toothbrush", "יופי", "beauty"]),
]


def category(title):
    low = title.lower()
    for cat, words in CATS:
        if any(w in low for w in words):
            return cat
    return "home"


def num(s):
    return float(s.replace(",", ""))


def text_of(fragment):
    s = re.sub(r"<br\s*/?>", "\n", fragment)
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(s)


def parse(page):
    items = []
    for part in page.split("tgme_widget_message_wrap")[1:]:
        img = re.search(r"tgme_widget_message_photo_wrap[^>]*background-image:url\('([^']+)'\)", part)
        body = re.search(r"tgme_widget_message_text[^>]*>(.*?)</div>", part, re.S)
        when = re.search(r'<time datetime="([^"]+)"', part)
        if not (img and body):
            continue
        t = text_of(body.group(1))
        price = re.search(r"רק ₪([\d.,]+) במקום ₪([\d.,]+)", t)
        link = re.search(r"https://s\.click\.aliexpress\.com/e/_([A-Za-z0-9]+)", t)
        if not (price and link):
            continue
        lines = [l.strip() for l in t.split("\n") if l.strip()]
        title = next((l for l in lines if "₪" not in l and not l.startswith(("🔥", "🖤"))), "")
        if not title:
            continue
        rating = re.search(r"דירוג ([\d.]+)", t)
        sold = re.search(r"📦 ([\d,]+)\+", t)
        items.append({
            "id": link.group(1),
            "t": title[:110],
            "c": category(title),
            "p": num(price.group(1)),
            "o": num(price.group(2)),
            "r": float(rating.group(1)) if rating else None,
            "s": int(sold.group(1).replace(",", "")) if sold else None,
            "img": f"{IMG_DIR}/{link.group(1)}.jpg",
            "time": when.group(1) if when else "",
            "_src": img.group(1),
        })
    return items


def main():
    os.makedirs(IMG_DIR, exist_ok=True)
    try:
        with open(OUT, encoding="utf-8") as f:
            old = {x["id"]: x for x in json.load(f)}
    except (FileNotFoundError, json.JSONDecodeError):
        old = {}

    found, before = [], None
    for _ in range(PAGES):
        url = f"https://t.me/s/{CHANNEL}" + (f"?before={before}" if before else "")
        page = requests.get(url, headers=HEADERS, timeout=30).text
        found += parse(page)
        ids = [int(x) for x in re.findall(rf'data-post="{CHANNEL}/(\d+)"', page)]
        if not ids:
            break
        before = min(ids)
    print(f"found {len(found)} deals in the channel")

    merged = dict(old)
    for x in found:
        path = x["img"]
        if not os.path.exists(path):
            try:
                r = requests.get(x.pop("_src"), headers=HEADERS, timeout=30)
                r.raise_for_status()
                with open(path, "wb") as f:
                    f.write(r.content)
            except Exception as e:
                print("image failed:", x["id"], str(e)[:100])
                continue
        x.pop("_src", None)
        merged[x["id"]] = x

    items = sorted(merged.values(), key=lambda x: x.get("time", ""), reverse=True)[:MAX_ITEMS]
    keep = {os.path.basename(x["img"]) for x in items}
    for name in os.listdir(IMG_DIR):
        if name not in keep:
            os.remove(os.path.join(IMG_DIR, name))

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=1)
    print(f"products.json: {len(items)} products")


if __name__ == "__main__":
    main()
