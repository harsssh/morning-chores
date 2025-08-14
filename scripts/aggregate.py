#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aggregate commit-based check-ins and render artifacts.

仕様:
- ユーザー名はコミットの author から導出（トレイラー不要）。
- 日付はトレイラー "Check-In-Date: YYYY-MM-DD" を優先、無ければ author の日時を JST 変換。
- 対象コミットの判定は「本文に Check-In-Date がある」または「件名が 'check-in' で始まる」。
- (date × user) の重複はジョブ失敗にせず自動でデデュープ（最初=earliestを採用）。重複は data/duplicates.csv と Actions の警告に出力。
- 出力:
    data/attendance.csv, data/daily_counts.json, data/per_user.json, data/duplicates.csv
    assets/heatmap.svg
"""

import csv
import datetime as dt
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from zoneinfo import ZoneInfo

# パス
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ASSETS = ROOT / "assets"

# タイムゾーン
JST = ZoneInfo("Asia/Tokyo")

# 検出ルール
DATE_RE = re.compile(r"^Check-In-Date:\s*(\d{4}-\d{2}-\d{2})\s*$", re.M)
SUBJECT_RE = re.compile(r"^check-in\b", re.I)

# 重複時の採用ルール: "earliest" or "latest"
PREFER_ON_DUP = "earliest"


# ------------------------------
# Git ログ取得
# ------------------------------
def git_log():
    """
    1 レコード:
      commit_id | author_iso | author_name | author_email | subject | RAW body
    """
    fmt = "%H%x1f%aI%x1f%an%x1f%ae%x1f%s%x1f%B%x1e"
    out = subprocess.check_output(
        ["git", "log", "--no-color", "--no-notes", "--pretty=format:" + fmt, "--date=iso-strict"],
        cwd=ROOT,
    )
    raw = out.decode("utf-8", errors="replace").strip("\n\x1e")
    if not raw:
        return
    for rec in raw.split("\x1e"):
        if not rec:
            continue
        cid, aiso, an, ae, subj, body = rec.split("\x1f")
        yield cid, aiso, an, ae, subj, body


# ------------------------------
# ユーザー ID 正規化
# ------------------------------
def canonical_user(author_name: str, author_email: str) -> str:
    """
    author 情報から安定 ID を導出。
    - 12345+login@users.noreply.github.com -> login
    - login@users.noreply.github.com       -> login
    - それ以外は email のローカル部、なければ name を整形
    """
    ae = (author_email or "").strip().lower()
    if ae:
        m = re.match(r"\d+\+([a-z0-9-]+)@users\.noreply\.github\.com$", ae)
        if m:
            return m.group(1)
        m = re.match(r"([a-z0-9-]+)@users\.noreply\.github\.com$", ae)
        if m:
            return m.group(1)
        if "@" in ae:
            return ae.split("@", 1)[0]

    name = (author_name or "").strip().lower()
    name = re.sub(r"\s+", "-", name)  # 空白→ハイフン
    return name or "unknown"


def jst_date_from_iso(iso_str: str) -> str:
    """ISO 8601 の日時文字列を JST 日付に変換して YYYY-MM-DD で返す"""
    # 例: 2025-08-14T04:00:00+00:00
    dt_aware = dt.datetime.fromisoformat(iso_str)
    return dt_aware.astimezone(JST).date().isoformat()


# ------------------------------
# チェックイン抽出
# ------------------------------
def extract_checkins():
    rows = []
    for cid, aiso, an, ae, subj, body in git_log() or []:
        # 対象コミット判定
        has_trailer = DATE_RE.search(body) is not None
        looks_checkin = SUBJECT_RE.search(subj) is not None
        if not (has_trailer or looks_checkin):
            continue

        # 日付: トレイラー優先、無ければ author 日時を JST 変換
        m = DATE_RE.search(body)
        date = m.group(1) if m else jst_date_from_iso(aiso)

        # ユーザー: author から導出
        user = canonical_user(an, ae)

        rows.append(
            {
                "commit": cid,
                "date": date,
                "user": user,
                "author_iso": aiso,
                "author_name": an,
                "author_email": ae,
                "subject": subj,
            }
        )
    return rows


# ------------------------------
# 重複解消（非致命）
# ------------------------------
def dedupe(rows, prefer: str = PREFER_ON_DUP):
    """
    (date × user) の重複を解消。
    prefer: "earliest"（author_iso が早いものを採用） or "latest"
    戻り値: (unique_rows, duplicates)
    """
    if not rows:
        return [], []

    reverse = prefer == "latest"
    sorted_rows = sorted(rows, key=lambda r: r["author_iso"], reverse=reverse)

    chosen = {}
    dups = []
    for r in sorted_rows:
        k = (r["date"], r["user"])
        if k in chosen:
            dups.append(r)  # 2件目以降は重複として記録
        else:
            chosen[k] = r

    return list(chosen.values()), dups


# ------------------------------
# 集計
# ------------------------------
def aggregate(rows):
    daily = Counter()
    per_user = Counter()
    for r in rows:
        daily[r["date"]] += 1
        per_user[r["user"]] += 1
    return daily, per_user


# ------------------------------
# 出力
# ------------------------------
def write_data(rows, daily, per_user, duplicates):
    DATA.mkdir(parents=True, exist_ok=True)

    # 正規化データ
    with (DATA / "attendance.csv").open("w", newline="", encoding="utf-8") as fp:
        w = csv.writer(fp)
        w.writerow(["date", "user", "commit", "author_name", "author_email"])
        for r in sorted(rows, key=lambda x: (x["date"], x["user"], x["commit"])):
            w.writerow([r["date"], r["user"], r["commit"], r["author_name"], r["author_email"]])

    # 日別・ユーザー別
    (DATA / "daily_counts.json").write_text(
        json.dumps(daily, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (DATA / "per_user.json").write_text(
        json.dumps(per_user, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 重複リスト
    with (DATA / "duplicates.csv").open("w", newline="", encoding="utf-8") as fp:
        w = csv.writer(fp)
        w.writerow(["date", "user", "commit", "author_name", "author_email", "author_iso"])
        for r in sorted(duplicates, key=lambda x: (x["date"], x["user"], x["author_iso"], x["commit"])):
            w.writerow([r["date"], r["user"], r["commit"], r["author_name"], r["author_email"], r["author_iso"]])


def make_heatmap_svg(daily: dict, days: int = 365) -> str:
    """
    GitHub 風の週×曜日ヒートマップ（直近 days 日）
    """
    end = dt.datetime.now(JST).date()
    start = end - dt.timedelta(days=days - 1)
    dates = [start + dt.timedelta(days=i) for i in range(days)]

    # ざっくり列数
    cols = (days + start.weekday()) // 7 + 1
    cell, gap, pad = 14, 2, 30
    w = pad + cols * (cell + gap) + pad
    h = pad + 7 * (cell + gap) + pad

    def color(v: int) -> str:
        if v == 0:
            return "#ebedf0"
        if v == 1:
            return "#c6e48b"
        if v == 2:
            return "#7bc96f"
        # 3人以上
        return "#196127"

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        f'font-family="system-ui, sans-serif" font-size="10">'
    ]
    svg.append(f'<rect width="{w}" height="{h}" fill="white"/>')
    svg.append(f'<text x="{pad}" y="18" font-weight="600">Attendance (last {days} days)</text>')

    x0, y0, col = pad, pad + 10, 0
    for d in dates:
        v = int(daily.get(d.isoformat(), 0))
        x = x0 + col * (cell + gap)
        y = y0 + d.weekday() * (cell + gap)
        svg.append(
            f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{color(v)}">'
            f'<title>{d} : {v} participants</title></rect>'
        )
        if d.weekday() == 6:
            col += 1

    svg.append("</svg>")
    return "\n".join(svg)


def write_assets(daily):
    ASSETS.mkdir(parents=True, exist_ok=True)
    (ASSETS / "heatmap.svg").write_text(make_heatmap_svg(daily, 365), encoding="utf-8")


# ------------------------------
# メイン
# ------------------------------
def main():
    rows_all = extract_checkins()

    # 重複を自動解消（最初=earliestを採用）
    unique_rows, duplicates = dedupe(rows_all, prefer=PREFER_ON_DUP)

    # 重複があれば Actions 警告（アノテーション）
    for d in duplicates:
        print(f"::warning::Duplicate check-in {d['date']} {d['user']} ({d['commit'][:7]})", file=sys.stdout)

    # 集計
    daily, per_user = aggregate(unique_rows)

    # 出力
    write_data(unique_rows, daily, per_user, duplicates)
    write_assets(daily)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # 例外はエラーとして明示しつつ終了（duplicates はここに来ない設計）
        print(f"[aggregate.py] ERROR: {e}", file=sys.stderr)
        sys.exit(1)

