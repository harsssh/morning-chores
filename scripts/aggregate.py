#!/usr/bin/env python3
import csv, datetime as dt, json, re, subprocess, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DOCS = ROOT / "docs"

SUBJECT_RE = re.compile(r"^check-in\s+(\d{4}-\d{2}-\d{2})\s+@(\S+)", re.I|re.M)
DATE_RE    = re.compile(r"^Check-In-Date:\s*(\d{4}-\d{2}-\d{2})\s*$", re.M)
USER_RE    = re.compile(r"^Check-In-User:\s*(\S+)\s*$", re.M)

def git_log():
    fmt = "%H%x1f%ad%x1f%s%x1f%b%x1e"
    out = subprocess.check_output(
        ["git","log","--date=short","--pretty=format:"+fmt], cwd=ROOT
    )
    raw = out.decode("utf-8", errors="replace").strip("\n\x1e")
    for rec in raw.split("\x1e"):
        if not rec: continue
        _id, _ad, _subj, _body = rec.split("\x1f")
        yield _id, _ad, _subj, _body

def extract_checkins():
    rows = []
    for cid, adate, subj, body in git_log():
        # トレイラーがあるもののみをチェックインとして扱う（件名は任意）
        if not DATE_RE.search(body) or not USER_RE.search(body):
            continue
        date = DATE_RE.search(body).group(1)
        user = USER_RE.search(body).group(1)
        rows.append({"commit": cid, "date": date, "user": user})
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
        w = csv.writer(fp); w.writerow(["date","user","commit"])
        for r in sorted(rows, key=lambda x:(x["date"], x["user"])):
            w.writerow([r["date"], r["user"], r["commit"]])
    (DATA/"daily_counts.json").write_text(json.dumps(daily, ensure_ascii=False, indent=2), encoding="utf-8")
    (DATA/"per_user.json").write_text(json.dumps(per_user, ensure_ascii=False, indent=2), encoding="utf-8")

def make_heatmap_svg(daily, days=365):
    end = dt.date.today(); start = end - dt.timedelta(days=days-1)
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
    x0, y0 = pad, pad + 10; col = 0
    for d in dates:
        v = daily.get(d.isoformat(), 0)
        x = x0 + col*(cell+gap); y = y0 + d.weekday()*(cell+gap)
        svg.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{color(v)}"><title>{d} : {v} participants</title></rect>')
        if d.weekday() == 6: col += 1
    svg.append("</svg>")
    return "\n".join(svg)

def write_docs(daily, per_user):
    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS/"heatmap.svg").write_text(make_heatmap_svg(daily, 365), encoding="utf-8")
    total = sum(per_user.values())
    top = sorted(per_user.items(), key=lambda x: x[1], reverse=True)[:10]
    html = f"""<!doctype html><meta charset="utf-8"><title>ダッシュボード</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{{font-family:system-ui,sans-serif;margin:20px}}.card{{border:1px solid #e5e7eb;border-radius:12px;padding:16px;margin:16px 0}}
table{{border-collapse:collapse}}th,td{{padding:6px 10px;border-bottom:1px solid #eee;text-align:left}}
.badge{{display:inline-block;padding:2px 8px;border-radius:999px;background:#f3f4f6}}</style>
<h1>朝の活動ログ</h1>
<p class="badge">累計参加回数: <strong>{total}</strong></p>
<div class="card"><h2>日別ヒートマップ（直近1年）</h2><img src="./heatmap.svg" alt="heatmap"></div>
<div class="card"><h2>参加者ランキング（Top 10）</h2>
<table><thead><tr><th>参加者</th><th>回数</th></tr></thead><tbody>
{''.join(f'<tr><td>{u}</td><td>{c}</td></tr>' for u,c in top)}
</tbody></table></div>
<p style="color:#6b7280">最終更新: {dt.datetime.now().isoformat(timespec='seconds')}</p>"""
    (DOCS/"index.html").write_text(html, encoding="utf-8")

def main():
    rows = extract_checkins()
    validate(rows)
    daily, per_user = aggregate(rows)
    write_data(rows, daily, per_user)
    write_docs(daily, per_user)

if __name__ == "__main__":
    main()

