#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
00 — Scrapes Truth Social posts from the American Presidency Project (UCSB).

The timestamp is derived from the snowflake ID, not from the time printed on
the page, and checked against it. Reasons and limits: report/project_status.typ.

    python 00_scrape_ucsb.py --inspect 2024-12-01
    python 00_scrape_ucsb.py

Dependencies: requests, beautifulsoup4, lxml, pandas.
"""

import re
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime, date, timedelta, timezone

import pandas as pd
import requests
from bs4 import BeautifulSoup


# ==============================================================================
# CONFIGURATION
# ==============================================================================

START_DATE = date(2024, 12, 1)
END_DATE = date(2026, 7, 31)       # inclusive

CACHE_DIR = Path("cache_ucsb")
OUTPUT_DIR = Path("data")

BASE = "https://www.presidency.ucsb.edu/documents/truth-social-posts-{m}-{d}-{y}"

PAUSE_SECONDS = 0.2
TIMEOUT = 30
USER_AGENT = "Academic research - master's thesis (contact: j.arma.ac@gmail.com)"

MONTHS = ["january", "february", "march", "april", "may", "june",
          "july", "august", "september", "october", "november", "december"]

PAGE_TIMEZONE = "America/Los_Angeles"
TOLERANCE_MINUTES = 1


# ==============================================================================
# ID DECODING
# ==============================================================================

def id_to_utc(post_id):
    """Mastodon snowflake -> UTC datetime."""
    ms = int(post_id) >> 16
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def id_to_sequence(post_id):
    """The 16 low bits: they order posts within the same millisecond."""
    return int(post_id) & 0xFFFF


# ==============================================================================
# DOWNLOAD
# ==============================================================================

def day_url(d):
    return BASE.format(m=MONTHS[d.month - 1], d=d.day, y=d.year)


def download(d, session):
    """HTML of the day, from the cache if present. A 404 is cached as an empty
    string; a network error returns None and will be retried."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    f = CACHE_DIR / f"{d.isoformat()}.html"

    if f.exists():
        return f.read_text(encoding="utf-8")

    url = day_url(d)
    try:
        r = session.get(url, timeout=TIMEOUT)
    except requests.RequestException as e:
        print(f"  {d} network error: {e}")
        return None

    time.sleep(PAUSE_SECONDS)

    if r.status_code == 404:
        f.write_text("", encoding="utf-8")
        return ""
    if r.status_code != 200:
        print(f"  {d} HTTP {r.status_code}")
        return None

    f.write_text(r.text, encoding="utf-8")
    return r.text


# ==============================================================================
# PARSING
# ==============================================================================

RE_ID = re.compile(r"truthsocial\.com/@[\w.]+/posts/(\d+)")

# The archive uses two formats: 24-hour with no suffix ("18:11") and 12-hour
# with a meridiem ("1:17 PM", "7:05 A.M."). The time is matched first, then the
# meridiem anchored right after it. The word boundary and the uppercase match
# keep the start of the text following a 24-hour time from being read as a
# meridiem ("10:08 Amazing...", "09:36 A MUST WATCH...").
RE_TIME = re.compile(r"(\d{1,2}):(\d{2})")
RE_MERIDIEM = re.compile(r"\s*([AP])\.?\s?M\b\.?")


def to_24h(hour, minute, meridiem):
    """('1', '17', 'P') -> '13:17'. Without a meridiem the hour is already 24h."""
    hour = int(hour)
    if meridiem == "A" and hour == 12:
        hour = 0
    elif meridiem == "P" and hour != 12:
        hour += 12
    return f"{hour:02d}:{minute}"


def inspect(html):
    """Prints the page structure, to adjust the selectors."""
    soup = BeautifulSoup(html, "lxml")

    print("--- candidate containers ---")
    for cls in ["field-docs-content", "node__content", "field-item"]:
        for el in soup.select(f"div.{cls}"):
            text = el.get_text(" ", strip=True)[:200]
            print(f"\ndiv.{cls}\n  {text}")

    print("\n--- truthsocial links found ---")
    for a in soup.find_all("a", href=RE_ID):
        print(" ", a["href"])

    print("\n--- first 3000 characters of the main content ---")
    main = soup.select_one("div.field-docs-content") or soup.body
    print(main.get_text("\n", strip=True)[:3000])


def extract_posts(html, day):
    """Extracts posts starting from the truthsocial links, which carry the ID.
    Each link closes the text block that precedes it."""
    soup = BeautifulSoup(html, "lxml")
    content = soup.select_one("div.field-docs-content") or soup.body
    if content is None:
        return []

    full_text = content.get_text("\n", strip=True)

    links = [a for a in content.find_all("a", href=RE_ID)]
    if not links:
        return []

    posts = []
    pieces = re.split(r"https?://truthsocial\.com/@[\w.]+/posts/\d+", full_text)
    ids = [RE_ID.search(a["href"]).group(1) for a in links]

    for i, pid in enumerate(ids):
        block = pieces[i] if i < len(pieces) else ""

        m = RE_TIME.search(block[:200])
        page_time, text = None, block
        if m:
            mer = RE_MERIDIEM.match(block, m.end())
            page_time = to_24h(m.group(1), m.group(2),
                               mer.group(1) if mer else None)
            text = block[mer.end() if mer else m.end():]
        text = re.sub(r"^\s*[\-\*•]\s*", "", text)
        text = re.sub(r"\s+", " ", text).strip()

        posts.append({
            "post_id": pid,
            "page_date": day.isoformat(),
            "page_time_pacific": page_time,
            "text": text,
            "url": f"https://truthsocial.com/@realDonaldTrump/posts/{pid}",
        })

    return posts


# ==============================================================================
# VALIDATION
# ==============================================================================

def validate(df):
    """Compares the timestamp derived from the ID with the Pacific time on the page."""
    df = df.copy()
    df["timestamp_utc"] = df["post_id"].apply(id_to_utc)
    df["sequence"] = df["post_id"].apply(id_to_sequence)

    local = df["timestamp_utc"].dt.tz_convert(PAGE_TIMEZONE)
    df["id_time_pacific"] = local.dt.strftime("%H:%M")
    df["id_date_pacific"] = local.dt.date.astype(str)

    expected = pd.to_datetime(df["id_date_pacific"] + " " + df["id_time_pacific"],
                              errors="coerce")
    observed = pd.to_datetime(df["page_date"] + " " + df["page_time_pacific"],
                              errors="coerce")
    offset = (expected - observed).dt.total_seconds().abs().div(60)

    df["offset_minutes"] = offset
    df["verified"] = offset <= TOLERANCE_MINUTES

    return df


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inspect", metavar="YYYY-MM-DD",
                    help="download a single day and print the HTML structure")
    args = ap.parse_args()

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    if args.inspect:
        d = date.fromisoformat(args.inspect)
        html = download(d, session)
        if not html:
            print("Empty or missing page.")
            return
        inspect(html)
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    everything, empty, failed = [], 0, []
    d = START_DATE
    while d <= END_DATE:
        html = download(d, session)

        if html is None:
            failed.append(d.isoformat())
        elif html == "":
            empty += 1
        else:
            p = extract_posts(html, d)
            if not p:
                failed.append(d.isoformat())
            everything.extend(p)

        if d.day == 1:
            print(f"{d.strftime('%Y-%m')}  ...  {len(everything)} posts so far")

        d += timedelta(days=1)

    if not everything:
        print("\nNo posts extracted. Run --inspect and adjust the selectors.")
        return

    df = pd.DataFrame(everything).drop_duplicates(subset="post_id")
    df = validate(df).sort_values("timestamp_utc").reset_index(drop=True)

    print("\n" + "=" * 78)
    print(f"Posts extracted        : {len(df)}")
    print(f"Days without a page    : {empty}")
    print(f"Problematic days       : {len(failed)}")
    print(f"Period (UTC)           : {df['timestamp_utc'].min()} -> "
          f"{df['timestamp_utc'].max()}")

    n_ok = int(df["verified"].sum())
    print(f"\nVerified rows (ID == page time): {n_ok} ({n_ok/len(df):.1%})")
    if n_ok / len(df) < 0.95:
        print("  Most frequent offsets (minutes):")
        print(df.loc[~df["verified"], "offset_minutes"]
              .round().value_counts().head(5).to_string())

    per_day = df.groupby(df["timestamp_utc"].dt.date).size()
    print(f"\nPosts per day: median {per_day.median():.0f}, "
          f"max {per_day.max()}, days covered {len(per_day)}")
    print(f"Non-zero seconds: "
          f"{(df['timestamp_utc'].dt.second != 0).mean():.1%}")

    df.to_csv(OUTPUT_DIR / "truth_posts.csv", index=False)
    df[~df["verified"]].to_csv(OUTPUT_DIR / "anomalies.csv", index=False)
    if failed:
        (OUTPUT_DIR / "failed_days.txt").write_text("\n".join(failed))

    print(f"\nSaved to {OUTPUT_DIR}/truth_posts.csv")


if __name__ == "__main__":
    main()
