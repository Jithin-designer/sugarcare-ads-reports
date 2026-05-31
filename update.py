#!/usr/bin/env python3
"""
SugarCARE Meta Ads Report Updater
Usage:  python update.py reports/2026-05-31.md
Reads structured markdown, fills %%TOKENS%% in template.html, writes index.html.
"""

import sys
import re
from pathlib import Path
from datetime import datetime


def parse_date(stem):
    dt = datetime.strptime(stem, "%Y-%m-%d")
    return dt.strftime(f"%A, {dt.day} %B %Y")


def parse_md(text):
    data = {}
    sections = {}
    current = None
    for line in text.split("\n"):
        if line.startswith("## "):
            current = line[3:].strip().lower()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)

    if "summary" in sections:
        for line in sections["summary"]:
            m = re.match(r"\s*[-*]\s*(.+?):\s*(.+)", line)
            if m:
                key = "summary_" + m.group(1).strip().lower()
                data[key] = m.group(2).strip()

    campaigns = []
    if "campaigns" in sections:
        header_seen = False
        for line in sections["campaigns"]:
            if line.startswith("|") and "---" not in line:
                if not header_seen:
                    header_seen = True
                    continue
                cells = [c.strip() for c in line.strip("|").split("|")]
                if len(cells) >= 6:
                    campaigns.append({
                        "name": cells[0], "spend": cells[1], "leads": cells[2],
                        "cpl": cells[3], "ctr": cells[4], "status": cells[5].lower().strip(),
                    })
    data["campaigns"] = campaigns

    for md_key, data_key in [("best cpl", "winner_cpl"), ("most leads", "winner_leads")]:
        if md_key in sections:
            data[data_key] = " ".join(l for l in sections[md_key] if l.strip()).strip()

    issues = []
    if "watch" in sections:
        for line in sections["watch"]:
            m = re.match(r"\s*[-*]\s*\[(\w+)\]\s*(.+?)(?:—|-)\s*(.+)", line)
            if m:
                issues.append({"type": m.group(1).lower(),
                               "title": m.group(2).strip(),
                               "body": m.group(3).strip()})
    data["issues"] = issues

    return data


def _cpl_class(cpl_str):
    n = re.sub(r"[^\d.]", "", cpl_str)
    try:
        v = float(n)
        return "good" if v < 60 else "danger" if v > 120 else "warn"
    except ValueError:
        return ""


def _leads_class(leads_str):
    try:
        v = int(re.sub(r"[^\d]", "", leads_str))
        return "good" if v >= 8 else "warn" if v <= 3 else ""
    except ValueError:
        return ""


_ROW_CLASS = {
    "good": "good", "top": "good", "top_cpl": "good", "top_leads": "good",
    "danger": "danger", "warn": "warn", "dead": "",
}
_BADGES = {
    "top":      '<span class="flag-badge good">&#10003; Top performer</span>',
    "top_cpl":  '<span class="flag-badge good">&#10003; Lowest CPL</span>',
    "top_leads":'<span class="flag-badge good">&#10003; Most leads</span>',
    "danger":   '<span class="flag-badge danger">&#9888; High CPL &#8212; review</span>',
    "warn":     '<span class="flag-badge warn">&#9651; Watch</span>',
    "dead":     '<span class="flag-badge dead">&#9711; No activity</span>',
}


def build_campaign_rows(campaigns):
    rows = []
    for c in campaigns:
        rc = _ROW_CLASS.get(c["status"], "")
        cc = _cpl_class(c["cpl"])
        lc = _leads_class(c["leads"])
        badge = _BADGES.get(c["status"], "")
        rows.append(
            f'    <div class="campaign-row {rc}">\n'
            f'      <div class="campaign-name">{c["name"]}</div>\n'
            f'      <div class="campaign-meta">\n'
            f'        <div class="meta-item"><div class="meta-key">Spend</div>'
            f'<div class="meta-val">{c["spend"]}</div></div>\n'
            f'        <div class="meta-item"><div class="meta-key">Leads</div>'
            f'<div class="meta-val {lc}">{c["leads"]}</div></div>\n'
            f'        <div class="meta-item"><div class="meta-key">CPL</div>'
            f'<div class="meta-val {cc}">{c["cpl"]}</div></div>\n'
            f'        <div class="meta-item"><div class="meta-key">CTR</div>'
            f'<div class="meta-val">{c["ctr"]}</div></div>\n'
            f'      </div>\n'
            f'      {badge}\n'
            f'    </div>'
        )
    return "\n".join(rows)


def build_alerts(issues):
    _CSS = {"danger": "danger", "dead": "dead", "warn": "warn"}
    _ICON = {"danger": "&#9888;", "dead": "&#9711;", "warn": "&#9651;"}
    parts = []
    for issue in issues:
        css = _CSS.get(issue["type"], "warn")
        icon = _ICON.get(issue["type"], "!")
        parts.append(
            f'  <div class="alert-card {css}">\n'
            f'    <div class="alert-title">{icon} {issue["title"]}</div>\n'
            f'    <div class="alert-body">{issue["body"]}</div>\n'
            f'  </div>'
        )
    return "\n".join(parts)


def parse_winner(s):
    parts = re.split(r"\s*[—\-]\s*", s.strip(), 1)
    if len(parts) == 2:
        sub = re.split(r"\s*[—\-]\s*", parts[1])
        return parts[0].strip(), " · ".join(p.strip() for p in sub)
    return s.strip(), ""


def run(md_path_str):
    md_path = Path(md_path_str)
    base = Path(__file__).parent
    template = (base / "template.html").read_text(encoding="utf-8")
    text = md_path.read_text(encoding="utf-8")

    date_str = parse_date(md_path.stem)
    data = parse_md(text)

    cpl_name, cpl_detail = parse_winner(data.get("winner_cpl", ""))
    leads_name, leads_detail = parse_winner(data.get("winner_leads", ""))

    tokens = {
        "%%REPORT_DATE%%":       date_str,
        "%%TOTAL_LEADS%%":       data.get("summary_leads", "—"),
        "%%AVG_CPL%%":           data.get("summary_cpl", "—"),
        "%%TOTAL_SPEND%%":       data.get("summary_spend", "—"),
        "%%REACH%%":             data.get("summary_reach", "—"),
        "%%IMPRESSIONS%%":       data.get("summary_impressions", "—"),
        "%%CAMPAIGN_ROWS%%":     build_campaign_rows(data.get("campaigns", [])),
        "%%WINNER_CPL_NAME%%":   cpl_name,
        "%%WINNER_CPL_DETAIL%%": cpl_detail,
        "%%WINNER_LEADS_NAME%%": leads_name,
        "%%WINNER_LEADS_DETAIL%%": leads_detail,
        "%%ALERTS%%":            build_alerts(data.get("issues", [])),
    }

    html = template
    for k, v in tokens.items():
        html = html.replace(k, v)

    out = base / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"✓  index.html updated — {date_str}")
    print(f"   Leads: {tokens['%%TOTAL_LEADS%%']}  CPL: {tokens['%%AVG_CPL%%']}  Spend: {tokens['%%TOTAL_SPEND%%']}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python update.py reports/YYYY-MM-DD.md")
        sys.exit(1)
    run(sys.argv[1])
