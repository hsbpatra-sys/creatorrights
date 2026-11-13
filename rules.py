"""CreatorRights: asset register, rules engine and contract reader (no UI code)."""
import sqlite3, json, re, os
from datetime import date, datetime, timedelta

DB = os.getenv("CR_DB", os.path.join(os.path.dirname(os.path.abspath(__file__)), "creatorrights.db"))
WARN_DAYS = 30
PLATFORMS = ["Instagram", "YouTube", "Facebook", "Website", "TV"]
REGIONS = {"IN": "India", "UAE": "UAE", "UK": "United Kingdom", "US": "United States"}
COLS = ["asset_id", "name", "asset_type", "supplier", "licence_type", "platforms", "regions",
        "start_date", "end_date", "commercial_ok", "modification_ok", "ai_generated",
        "evidence_url", "evidence_hash", "verified", "parent_id"]


def connect():
    c = sqlite3.connect(DB, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.executescript("""
    CREATE TABLE IF NOT EXISTS assets(
      asset_id TEXT PRIMARY KEY, name TEXT, asset_type TEXT, supplier TEXT, licence_type TEXT,
      platforms TEXT, regions TEXT, start_date TEXT, end_date TEXT, commercial_ok INT,
      modification_ok INT, ai_generated INT, evidence_url TEXT, evidence_hash TEXT,
      verified INT, parent_id TEXT);
    CREATE TABLE IF NOT EXISTS usage_log(
      id INTEGER PRIMARY KEY AUTOINCREMENT, checked_at TEXT, asset_id TEXT, platform TEXT,
      region TEXT, use_date TEXT, commercial INT, status TEXT, reasons TEXT);""")
    if c.execute("SELECT COUNT(*) FROM assets").fetchone()[0] == 0:
        seed(c)
    return c


def seed(c):
    d = lambda n: (date.today() + timedelta(n)).isoformat()
    ev = lambda x: f"contracts/{x}.pdf"
    rows = [  # synthetic data; dates are relative to today so the demo always works
        ("A001", "Festive hero photo", "Photo", "StockCo", "Paid, limited", "Instagram,Website", "IN,UAE", d(-200), d(150), 1, 1, 0, ev("A001"), "", 1, None),
        ("A002", "Diwali background track", "Music", "BeatLib", "Paid, limited", "Instagram,YouTube", "IN", d(-150), d(12), 1, 0, 0, ev("A002"), "", 1, None),
        ("A003", "Brand display font (trial)", "Font", "TypeFoundry", "Non-commercial trial", "ALL", "GLOBAL", d(-30), d(300), 0, 1, 0, ev("A003"), "", 1, None),
        ("A004", "Creator reel clip", "Video", "Riya (creator)", "Creator release", "Instagram", "IN", d(-300), d(-20), 1, 1, 0, ev("A004"), "", 1, None),
        ("A005", "AI-generated festive illustration", "AI image", "GenTool", "Tool terms", "ALL", "GLOBAL", d(-60), d(365), 1, 1, 1, ev("A005"), "", 1, None),
        ("A006", "Festive hero photo (cropped)", "Photo", "In-house edit", "Derivative of A001", "Instagram,Website", "IN,UAE", d(-20), d(150), 1, 1, 0, "", "", 1, "A001"),
        ("A007", "Illustration pack", "Illustration", "Studio Mehta", "Unknown", "Website", "GLOBAL", d(-90), d(200), 1, 1, 0, "", "", 0, None),
        ("A008", "Track remix for reel", "Music", "In-house edit", "Derivative of A002", "Instagram,YouTube", "IN", d(-10), d(12), 1, 1, 0, "", "", 1, "A002"),
        ("A009", "UK stock b-roll", "Video", "FootageHub", "Paid, territory-limited", "YouTube", "UK", d(-100), d(200), 1, 1, 0, ev("A009"), "", 1, None),
        ("A010", "Own product photoshoot", "Photo", "In-house", "Owned", "ALL", "GLOBAL", d(-400), "2099-12-31", 1, 1, 0, ev("A010"), "", 1, None),
    ]
    c.executemany(f"INSERT INTO assets VALUES({','.join('?' * 16)})", rows)
    c.commit()


def _set(s):
    return {x.strip().upper() for x in (s or "").split(",") if x.strip()}


def _issues(a, platform, region, use_date, commercial, tag=""):
    red, amber = [], []
    if use_date < a["start_date"]:
        red.append(f"{tag}Licence has not started yet (starts {a['start_date']})")
    if use_date > a["end_date"]:
        red.append(f"{tag}Licence expired on {a['end_date']}")
    else:
        left = (date.fromisoformat(a["end_date"]) - date.fromisoformat(use_date)).days
        if left <= WARN_DAYS:
            amber.append(f"{tag}Licence ends in {left} days ({a['end_date']})")
    p, r = _set(a["platforms"]), _set(a["regions"])
    if "ALL" not in p and platform.upper() not in p:
        red.append(f"{tag}{platform} is not an allowed platform (allowed: {a['platforms']})")
    if "GLOBAL" not in r and region.upper() not in r:
        red.append(f"{tag}{region} is not an allowed region (allowed: {a['regions']})")
    if commercial and not a["commercial_ok"]:
        red.append(f"{tag}Licence does not cover commercial use")
    return red, amber


def check_use(c, asset_id, platform, region, use_date, commercial, log=True):
    """Return (status, reasons). Status: RED > UNVERIFIED > AMBER > GREEN."""
    a = dict(c.execute("SELECT * FROM assets WHERE asset_id=?", (asset_id,)).fetchone())
    red, amber = _issues(a, platform, region, use_date, commercial)
    if a["parent_id"]:  # derivatives inherit the parent's restrictions
        p = dict(c.execute("SELECT * FROM assets WHERE asset_id=?", (a["parent_id"],)).fetchone())
        if not p["modification_ok"]:
            red.append(f"Parent {p['asset_id']} licence does not allow edits or remixes")
        pr, pa = _issues(p, platform, region, use_date, commercial, tag=f"Parent {p['asset_id']}: ")
        red += pr
        amber += pa
    if a["ai_generated"]:
        amber.append("AI-generated: ownership and training-data rights are unclear")
    if not a["evidence_url"]:
        amber.append("No approval evidence attached")
    if red:
        status, reasons = "RED", red
    elif not a["verified"]:
        status, reasons = "UNVERIFIED", ["Terms not yet confirmed by a person"] + amber
    elif amber:
        status, reasons = "AMBER", amber
    else:
        status, reasons = "GREEN", ["Covered for this platform, region, date and use"]
    if log:
        c.execute("INSERT INTO usage_log(checked_at,asset_id,platform,region,use_date,commercial,status,reasons)"
                  " VALUES(?,?,?,?,?,?,?,?)", (datetime.now().isoformat(timespec="seconds"), asset_id,
                  platform, region, use_date, int(commercial), status, " | ".join(reasons)))
        c.commit()
    return status, reasons


def add_asset(c, d):
    n = c.execute("SELECT COALESCE(MAX(CAST(SUBSTR(asset_id,2) AS INT)),0)+1 FROM assets").fetchone()[0]
    d = {**d, "asset_id": f"A{n:03d}"}
    c.execute(f"INSERT INTO assets VALUES({','.join('?' * 16)})", [d.get(k) for k in COLS])
    c.commit()
    return d["asset_id"]


PROMPT = ("Extract licence terms from this contract. Return ONLY JSON with keys: platforms (comma list from "
          "Instagram, YouTube, Facebook, Website, TV, or ALL), regions (comma list from IN, UAE, UK, US, or GLOBAL), "
          "start_date, end_date (YYYY-MM-DD), commercial_ok (0/1), modification_ok (0/1), ai_generated (0/1), "
          "clauses (object mapping each of those keys to the exact quoted clause). Contract:\n")


def _sentence(text, *kws):
    for s in re.split(r"(?<=[.!?])\s+", text):
        if any(k in s.lower() for k in kws):
            return s.strip()
    return ""


def extract_terms(text):
    """AI reader: Claude API if ANTHROPIC_API_KEY is set, otherwise a simple rule-based fallback."""
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            import anthropic
            msg = anthropic.Anthropic().messages.create(
                model="claude-sonnet-5-5", max_tokens=800, messages=[{"role": "user", "content": PROMPT + text}])
            out = json.loads(re.sub(r"```json|```", "", msg.content[0].text).strip())
            out["method"] = "Claude API"
            return out
        except Exception:
            pass
    low = text.lower()
    names = {"india": "IN", "uae": "UAE", "united arab emirates": "UAE", "united kingdom": "UK",
             "uk": "UK", "united states": "US", "usa": "US"}
    regs = sorted({v for k, v in names.items() if re.search(rf"\b{k}\b", low)})
    if "worldwide" in low or "global" in low:
        regs = ["GLOBAL"]
    dates = re.findall(r"\d{4}-\d{2}-\d{2}", text)
    return {
        "platforms": ",".join(p for p in PLATFORMS if p.lower() in low), "regions": ",".join(regs),
        "start_date": dates[0] if dates else "", "end_date": dates[-1] if len(dates) > 1 else "",
        "commercial_ok": 0 if ("non-commercial" in low or "personal use only" in low) else 1,
        "modification_ok": 0 if re.search(r"(not|never) be (modified|remixed|edited)|no (modification|derivative)", low) else 1,
        "ai_generated": 1 if ("ai-generated" in low or "generative" in low) else 0,
        "clauses": {"platforms": _sentence(text, "instagram", "youtube", "facebook", "website", "platform"),
                    "regions": _sentence(text, "india", "uae", "kingdom", "territor", "worldwide"),
                    "duration": _sentence(text, "from ", "term", "until"),
                    "commercial": _sentence(text, "commercial"),
                    "modification": _sentence(text, "modif", "remix", "derivative")},
        "method": "Rule-based fallback (set ANTHROPIC_API_KEY for the AI reader)"}
