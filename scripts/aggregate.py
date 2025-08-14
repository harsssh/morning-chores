#!/usr/bin/env python3
import csv, datetime as dt, json, re, subprocess, sys
from collections import Counter
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT   = Path(__file__).resolve().parents[1]
DATA   = ROOT / "data"
ASSETS = ROOT  / "assets"
JST    = ZoneInfo("Asia/Tokyo")

DATE_RE = re.compile(r"^Check-In-Date:\s*(\d{4}-\d{2}-\d{2})\s*$", re.M)
SUBJECT_RE = re.compile(r"^check-in\b", re.I)

def git_log():
    # id | author-iso | author-name | author-email | subject | RAW body
    fmt = "%H%x1f%aI%x1f%an%x1f%ae%x1f%s%x1f%B%x1e"
    out = subprocess.check_output(
        ["git","log","--no-color","--no-notes","--pretty=format:"+fmt,"--date=iso-strict"],
        cwd=ROOT
    )
    raw = out.decode("utf-8", errors="replace").strip("\n\x1e")
    for rec in raw.split("\x1e"):
        if not rec: continue
        cid, aiso, an, ae, subj, body = rec.split("\x1f")
        yield cid, aiso, an, ae, subj, body

def canonical_user(author_name: str, author_email: str) -> str:
    ae = (author_email or "").lower()
    # GitHub noreply -> login 抽出
    m = re.match(r"\d+\+([a-z0-9-]+)@users\.noreply\.github\.com$", ae)
    if m: return m.group(1)
    m = re.match(r"([a-z0-9-]+)@users\.noreply\.github\.com$", ae)
    if m: return m.group(1)
    if ae and "@" in ae:
        return ae.split("@", 1)[0]
    # name をフォールバック（空白→-、小文字化）
    name = re.sub(r"\s+", "-", (author_name or "").strip().lower())
    return name or "unknown"

def jst_date_from_iso(iso: str) -> str:
    # 例: 2025-08-14T04:00:00+00:00
    dt_utc = dt.datetime.fromisoformat(iso)
    return dt_utc.astimezone(JST).date().isoformat()

def extract_checkins():
    rows = []
    for cid, aiso, an, ae, subj, body in git_log():
        # 対象コミットの判定
        if DATE_RE.search(body) is None and SUBJECT_RE.search(subj) is None:
            continue
        # 日付決定
        m = DATE_RE.search(body)
        date = m.group(1) if m else jst_date_from_iso(aiso)
        # ユーザー決定（author から導出）
        user = canonical_user(an, ae)
        rows.append({"commit": cid, "date": date, "user": user, "author_name": an, "author_email": ae})
    return rows

def validate(rows):
    seen = set(); dup = []
    for r in rows:
        key = (r["date"], r["user"])
        if key in seen: dup.append(r)
        seen.add(key)
    if dup:
        msg = "Duplicate check-ins detected:\n" + "\n".join(
            f"{d['date']} {d['user']} ({d['commit'][:7]})" for d in dup
        )
        raise SystemExit(msg)

def aggregate(rows):
    daily = Counter(); per_user = Counter()
    for r in rows:
        daily[r["date"]] += 1
        per_user[r["user"]] += 1
    return daily, per_user

def write_data(rows, daily, per_user):
    DATA.mkdir(parents=True, exist_ok=True)
    with (DATA/"attendance.csv").open("w", newline="", encoding="utf-8") as fp:
        w = csv.writer(fp)
        w.writerow(["date","user","commit","author_name","author_email"])
        for r in sorted(rows, key=lambda x:(x["date"], x["user"])):
            w.writerow([r["date"], r["user"], r["commit"], r["author_name"], r["author_email"]])
    (DATA/"daily_counts.json").write_text(json.dumps(daily, ensure_ascii=False, indent=2), encoding="utf-8")
    (DATA/"per_user.json").write_text(json.dumps(per_user, ensure_ascii=False, indent=2), encoding="utf-8")

def make_heatmap_svg(daily, days=365):
    end = dt.datetime.now(JST).date()
    start = end - dt.timedelta(days=days-1)
    dates = [start + dt.timedelta(days=i) for i in range(days)]
    cols = (days + start.weekday()) // 7 + 1
    cell, gap, pad = 14, 2, 30
    w = pad + cols*(cell+gap) + pad
    h = pad + 7*(cell+gap) + pad

    def color(v):
        if v == 0: return "#ebedf0"
        if v == 1: return "#c6e48b"
        if v == 2: return "#7bc96f"
        if v == 3: return "#239a3b"
        return "#196127"

    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" font-family="system-ui, sans-serif" font-size="10">']
    svg.append(f'<rect width="{w}" height="{h}" fill="white"/>')
    svg.append(f'<text x="{pad}" y="18" font-weight="600">Attendance (last {days} days)</text>')
    x0, y0, col = pad, pad + 10, 0
    for d in dates:
        v = daily.get(d.isoformat(), 0)
        x = x0 + col*(cell+gap)
        y = y0 + d.weekday()*(cell+gap)
        svg.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{color(v)}"><title>{d} : {v} participants</title></rect>')
        if d.weekday() == 6:
            col += 1
    svg.append("</svg>")
    return "\n".join(svg)

def write_assets(daily):
    ASSETS.mkdir(parents=True, exist_ok=True)
    (ASSETS/"heatmap.svg").write_text(make_heatmap_svg(daily, 365), encoding="utf-8")

def main():
    rows = extract_checkins()
    validate(rows)
    daily, per_user = aggregate(rows)
    write_data(rows, daily, per_user)
    write_assets(daily)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[aggregate.py] ERROR: {e}", file=sys.stderr)
        sys.exit(1)

