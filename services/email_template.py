"""
PingMe Email Summary Generator
Generates a beautiful HTML email with inline SVG charts
Place at: services/email_template.py
"""

import math
from datetime import datetime


def generate_pie_chart_svg(category_breakdown: dict, size: int = 200) -> str:
    """Generate an inline SVG donut/pie chart for category breakdown."""

    colors = {
        "deep_work": "#4ade80",
        "break": "#60a5fa",
        "admin": "#c084fc",
        "meetings": "#fbbf24",
        "distracted": "#f87171",
        "untracked": "#6b7280",
    }

    labels = {
        "deep_work": "Deep Work",
        "break": "Break",
        "admin": "Admin",
        "meetings": "Meetings",
        "distracted": "Distracted",
        "untracked": "Untracked",
    }

    total = sum(category_breakdown.values())
    if total == 0:
        return "<p style='color:#6b7280;text-align:center;'>No data yet</p>"

    cx = cy = size / 2
    r = size / 2 - 20
    inner_r = r * 0.55

    slices = []
    current_angle = -90

    for cat, count in category_breakdown.items():
        if count == 0:
            continue
        pct = count / total
        angle = pct * 360
        slices.append({
            "cat": cat,
            "count": count,
            "pct": pct,
            "angle": angle,
            "start": current_angle,
            "color": colors.get(cat, "#6b7280"),
            "label": labels.get(cat, cat),
        })
        current_angle += angle

    def polar_to_cart(cx, cy, r, angle_deg):
        angle_rad = math.radians(angle_deg)
        return cx + r * math.cos(angle_rad), cy + r * math.sin(angle_rad)

    paths = []
    for s in slices:
        if s["angle"] >= 359.9:
            paths.append(
                '<circle cx="{}" cy="{}" r="{}" fill="{}" />'.format(cx, cy, r, s["color"]) +
                '<circle cx="{}" cy="{}" r="{}" fill="#1a1a2e" />'.format(cx, cy, inner_r)
            )
            continue

        x1, y1 = polar_to_cart(cx, cy, r, s["start"])
        x2, y2 = polar_to_cart(cx, cy, r, s["start"] + s["angle"])
        ix1, iy1 = polar_to_cart(cx, cy, inner_r, s["start"])
        ix2, iy2 = polar_to_cart(cx, cy, inner_r, s["start"] + s["angle"])
        large_arc = 1 if s["angle"] > 180 else 0

        path = (
            "M {:.1f} {:.1f} "
            "A {} {} 0 {} 1 {:.1f} {:.1f} "
            "L {:.1f} {:.1f} "
            "A {} {} 0 {} 0 {:.1f} {:.1f} "
            "Z"
        ).format(x1, y1, r, r, large_arc, x2, y2, ix2, iy2, inner_r, inner_r, large_arc, ix1, iy1)

        paths.append('<path d="{}" fill="{}" stroke="#1a1a2e" stroke-width="2"/>'.format(path, s["color"]))

    top_cat = max(category_breakdown, key=category_breakdown.get) if category_breakdown else ""
    top_label = labels.get(top_cat, "")
    top_pct = int((category_breakdown.get(top_cat, 0) / total) * 100) if total else 0

    svg = (
        '<svg width="{0}" height="{0}" viewBox="0 0 {0} {0}" xmlns="http://www.w3.org/2000/svg">'
        '{1}'
        '<text x="{2}" y="{3}" text-anchor="middle" fill="#ffffff" '
        'font-size="22" font-weight="700" font-family="Courier New, monospace">{4}%</text>'
        '<text x="{2}" y="{5}" text-anchor="middle" fill="#9ca3af" '
        'font-size="10" font-family="Courier New, monospace">{6}</text>'
        '</svg>'
    ).format(size, "".join(paths), cx, cy - 8, top_pct, cy + 12, top_label)

    return svg


def generate_bar_chart_svg(category_breakdown: dict, interval_minutes: int = 15) -> str:
    """Generate an inline SVG horizontal bar chart."""

    colors = {
        "deep_work": "#4ade80",
        "break": "#60a5fa",
        "admin": "#c084fc",
        "meetings": "#fbbf24",
        "distracted": "#f87171",
        "untracked": "#6b7280",
    }

    labels = {
        "deep_work": "Deep Work",
        "break": "Break",
        "admin": "Admin",
        "meetings": "Meetings",
        "distracted": "Distracted",
        "untracked": "Untracked",
    }

    if not category_breakdown:
        return ""

    max_val = max(category_breakdown.values()) if category_breakdown else 1

    bar_height = 24
    gap = 12
    label_width = 90
    bar_max_width = 220
    chart_width = label_width + bar_max_width + 60
    chart_height = len(category_breakdown) * (bar_height + gap) + 10

    bars = []
    for i, (cat, count) in enumerate(sorted(category_breakdown.items(), key=lambda x: -x[1])):
        y = i * (bar_height + gap) + 5
        bar_w = int((count / max_val) * bar_max_width) if max_val > 0 else 0
        minutes = count * interval_minutes
        hours = minutes // 60
        mins = minutes % 60
        time_str = "{}h {}m".format(hours, mins) if hours > 0 else "{}m".format(mins)
        color = colors.get(cat, "#6b7280")
        label = labels.get(cat, cat)

        bars.append(
            '<text x="0" y="{}" fill="#9ca3af" font-size="11" font-family="Courier New, monospace">{}</text>'
            '<rect x="{}" y="{}" width="{}" height="{}" rx="4" fill="{}" opacity="0.9"/>'
            '<rect x="{}" y="{}" width="{}" height="{}" rx="4" fill="none" stroke="#2d2d4e" stroke-width="1"/>'
            '<text x="{}" y="{}" fill="{}" font-size="11" font-family="Courier New, monospace" font-weight="600">{}</text>'
            .format(
                y + bar_height - 7, label,
                label_width, y, bar_w, bar_height, color,
                label_width, y, bar_max_width, bar_height,
                label_width + bar_w + 6, y + bar_height - 7, color, time_str
            )
        )

    return (
        '<svg width="{}" height="{}" viewBox="0 0 {} {}" xmlns="http://www.w3.org/2000/svg">{}</svg>'
        .format(chart_width, chart_height, chart_width, chart_height, "".join(bars))
    )


def generate_html_email(
    logs: list,
    agenda: list,
    notes: list,
    stats: dict,
    date_str: str,
    interval_minutes: int = 15,
    ai_insight: str = ""
) -> str:
    """Generate the full HTML email with charts and optional AI insight."""

    category_breakdown = stats.get("categoryBreakdown", {})
    tracked = stats.get("trackedCount", 0)
    untracked_pct = stats.get("untrackedPercent", 0)
    total = stats.get("totalPings", 0)

    pie_svg = generate_pie_chart_svg(category_breakdown)
    bar_svg = generate_bar_chart_svg(category_breakdown, interval_minutes)

    # --- Agenda ---
    completed_items = [i for i in agenda if i.get("completed")]
    pending_items = [i for i in agenda if not i.get("completed")]
    completion_pct = int(len(completed_items) / len(agenda) * 100) if agenda else 0

    agenda_rows = ""
    for item in agenda:
        icon = "&#9989;" if item.get("completed") else "&#9203;"
        item_style = "text-decoration:line-through;color:#4b5563;" if item.get("completed") else "color:#e5e7eb;"
        carried = ""
        if item.get("carriedFrom"):
            carried = (
                " <span style='font-size:10px;color:#6b7280;background:#1f2937;"
                "padding:1px 5px;border-radius:3px;'>yesterday</span>"
            )
        agenda_rows += (
            "<tr>"
            "<td style='padding:8px 12px;border-bottom:1px solid #1f2937;font-size:15px;'>{}</td>"
            "<td style='padding:8px 12px;border-bottom:1px solid #1f2937;"
            "font-family:Courier New,monospace;font-size:13px;{}'>{}{}</td>"
            "</tr>"
        ).format(icon, item_style, item.get("content", ""), carried)

    if not agenda_rows:
        agenda_rows = "<tr><td style='padding:12px;color:#4b5563;font-size:13px;'>No agenda items.</td></tr>"

    # --- Notes ---
    notes_html = ""
    if notes:
        for note in notes:
            ts = note.get("timestamp", "")
            if isinstance(ts, str) and "T" in ts:
                try:
                    ts = datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%H:%M")
                except Exception:
                    ts = ""
            notes_html += (
                "<div style='border-left:3px solid #4ade80;padding:8px 12px;"
                "margin-bottom:8px;background:#0f1923;'>"
                "<div style='font-size:10px;color:#6b7280;margin-bottom:3px;"
                "font-family:Courier New,monospace;'>{}</div>"
                "<div style='font-size:13px;color:#d1d5db;font-family:Courier New,monospace;'>{}</div>"
                "</div>"
            ).format(ts, note.get("content", ""))
    else:
        notes_html = "<p style='color:#4b5563;font-size:13px;font-family:Courier New,monospace;'>No notes captured.</p>"

    # --- Timeline ---
    timeline_rows = ""
    recent_logs = logs[-8:] if len(logs) > 8 else logs
    cat_colors = {
        "deep_work": "#4ade80", "break": "#60a5fa", "admin": "#c084fc",
        "meetings": "#fbbf24", "distracted": "#f87171", "untracked": "#6b7280",
    }
    for log in recent_logs:
        ts = log.get("timestamp", "")
        if isinstance(ts, str) and "T" in ts:
            try:
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%H:%M")
            except Exception:
                ts = ""
        response = log.get("response") or ("[skipped]" if log.get("skipped") else "[untracked]")
        cat = log.get("category", "untracked")
        dot_color = cat_colors.get(cat, "#6b7280")
        timeline_rows += (
            "<tr>"
            "<td style='padding:6px 12px;border-bottom:1px solid #1a1a2e;"
            "font-family:Courier New,monospace;font-size:12px;color:#6b7280;white-space:nowrap;'>{}</td>"
            "<td style='padding:6px 12px;border-bottom:1px solid #1a1a2e;"
            "font-family:Courier New,monospace;font-size:12px;color:#d1d5db;'>{}</td>"
            "<td style='padding:6px 12px;border-bottom:1px solid #1a1a2e;text-align:right;'>"
            "<span style='display:inline-block;width:8px;height:8px;border-radius:50%;background:{};'></span>"
            "</td></tr>"
        ).format(ts, response, dot_color)

    if not timeline_rows:
        timeline_rows = "<tr><td style='padding:12px;color:#4b5563;font-size:13px;'>No logs.</td></tr>"

    # --- Score bar ---
    tracked_pct = 100 - untracked_pct
    score_color = "#4ade80" if tracked_pct >= 70 else "#fbbf24" if tracked_pct >= 50 else "#f87171"

    # --- AI insight block ---
    ai_block = ""
    if ai_insight:
        ai_block = (
            "<tr><td style='background:#0d1f12;padding:24px 36px;"
            "border-left:1px solid #1f2937;border-right:1px solid #1f2937;"
            "border-top:1px solid #1a1a2e;'>"
            "<div style='font-size:11px;color:#4ade80;letter-spacing:2px;"
            "margin-bottom:12px;'>&#129302; AI INSIGHT</div>"
            "<div style='font-size:14px;color:#d1fae5;font-family:Georgia,serif;"
            "line-height:1.8;font-style:italic;border-left:3px solid #4ade80;"
            "padding-left:16px;'>{}</div>"
            "</td></tr>"
        ).format(ai_insight)

    # --- Tomorrow priorities block ---
    priorities_block = ""
    if pending_items:
        priority_rows = "".join(
            "<div style='padding:8px 0;border-bottom:1px solid #1a1a2e;"
            "color:#d1d5db;font-size:13px;font-family:Courier New,monospace;'>"
            "&#8594; {}</div>".format(i.get("content", ""))
            for i in pending_items
        )
        priorities_block = (
            "<tr><td style='background:#0f1923;padding:28px 36px;"
            "border-left:1px solid #1f2937;border-right:1px solid #1f2937;"
            "border-top:1px solid #1a1a2e;'>"
            "<div style='font-size:11px;color:#fbbf24;letter-spacing:2px;"
            "margin-bottom:16px;'>&#128252; TOMORROW'S PRIORITIES</div>"
            "{}</td></tr>"
        ).format(priority_rows)

    # --- Legend ---
    legend_items = [
        ("Deep Work", "#4ade80"), ("Break", "#60a5fa"), ("Admin", "#c084fc"),
        ("Meetings", "#fbbf24"), ("Distracted", "#f87171"), ("Untracked", "#6b7280"),
    ]
    legend_html = "".join(
        "<span style='display:inline-block;margin-right:12px;font-size:11px;color:#6b7280;'>"
        "<span style='display:inline-block;width:8px;height:8px;border-radius:50%;"
        "background:{};margin-right:4px;vertical-align:middle;'></span>{}</span>".format(c, l)
        for l, c in legend_items
    )

    more_logs_note = (
        "<p style='font-size:11px;color:#4b5563;margin-top:8px;'>Showing last 8 entries</p>"
        if len(logs) > 8 else ""
    )

    # --- Assemble final HTML ---
    html = (
        "<!DOCTYPE html>"
        "<html lang='en'>"
        "<head>"
        "<meta charset='UTF-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1.0'>"
        "<title>PingMe &mdash; {date_str}</title>"
        "</head>"
        "<body style='margin:0;padding:0;background-color:#0a0a14;font-family:Courier New,Courier,monospace;'>"
        "<table width='100%' cellpadding='0' cellspacing='0' style='background:#0a0a14;padding:20px 0;'>"
        "<tr><td align='center'>"
        "<table width='600' cellpadding='0' cellspacing='0' style='max-width:600px;width:100%;'>"

        # Header
        "<tr><td style='background:#0f1923;border:1px solid #1f2937;"
        "border-radius:12px 12px 0 0;padding:32px 36px 28px;'>"
        "<div style='font-size:11px;color:#4ade80;letter-spacing:3px;"
        "text-transform:uppercase;margin-bottom:8px;'>DAILY REPORT</div>"
        "<div style='font-size:28px;font-weight:700;color:#ffffff;"
        "letter-spacing:-1px;margin-bottom:4px;'>&#128202; PingMe Summary</div>"
        "<div style='font-size:14px;color:#6b7280;'>{date_str}</div>"
        "</td></tr>"

        # Score band
        "<tr><td style='background:#111827;padding:16px 36px;"
        "border-left:1px solid #1f2937;border-right:1px solid #1f2937;'>"
        "<table width='100%' cellpadding='0' cellspacing='0'><tr>"
        "<td style='font-size:12px;color:#6b7280;'>TRACKED YESTERDAY</td>"
        "<td style='font-size:20px;font-weight:700;color:{score_color};text-align:center;'>{tracked_pct}%</td>"
        "<td style='font-size:12px;color:#374151;text-align:right;'>({tracked}/{total} pings)</td>"
        "</tr></table>"
        "<table width='100%' cellpadding='0' cellspacing='0' style='margin-top:8px;'><tr>"
        "<td width='{tracked_pct}%' style='height:6px;background:{score_color};border-radius:3px 0 0 3px;'></td>"
        "<td width='{untracked_pct}%' style='height:6px;background:#1f2937;border-radius:0 3px 3px 0;'></td>"
        "</tr></table>"
        "</td></tr>"

        # AI block
        "{ai_block}"

        # Charts
        "<tr><td style='background:#0f1923;padding:28px 36px;"
        "border-left:1px solid #1f2937;border-right:1px solid #1f2937;border-top:1px solid #1a1a2e;'>"
        "<div style='font-size:11px;color:#4ade80;letter-spacing:2px;margin-bottom:20px;'>&#9201; TIME BREAKDOWN</div>"
        "<table width='100%' cellpadding='0' cellspacing='0'><tr>"
        "<td width='200' valign='middle' align='center'>{pie_svg}</td>"
        "<td valign='middle' style='padding-left:24px;'>{bar_svg}</td>"
        "</tr></table>"
        "</td></tr>"

        # Agenda
        "<tr><td style='background:#0f1923;padding:28px 36px;"
        "border-left:1px solid #1f2937;border-right:1px solid #1f2937;border-top:1px solid #1a1a2e;'>"
        "<table width='100%' cellpadding='0' cellspacing='0' style='margin-bottom:16px;'><tr>"
        "<td style='font-size:11px;color:#4ade80;letter-spacing:2px;'>&#128203; AGENDA</td>"
        "<td style='font-size:12px;color:#6b7280;text-align:right;'>"
        "{completed_count}/{agenda_total} done ({completion_pct}%)</td>"
        "</tr></table>"
        "<table width='100%' cellpadding='0' cellspacing='0' "
        "style='border:1px solid #1f2937;border-radius:8px;overflow:hidden;'>"
        "{agenda_rows}"
        "</table></td></tr>"

        # Notes
        "<tr><td style='background:#0f1923;padding:28px 36px;"
        "border-left:1px solid #1f2937;border-right:1px solid #1f2937;border-top:1px solid #1a1a2e;'>"
        "<div style='font-size:11px;color:#4ade80;letter-spacing:2px;margin-bottom:16px;'>&#128221; NOTES CAPTURED</div>"
        "{notes_html}"
        "</td></tr>"

        # Timeline
        "<tr><td style='background:#0f1923;padding:28px 36px;"
        "border-left:1px solid #1f2937;border-right:1px solid #1f2937;border-top:1px solid #1a1a2e;'>"
        "<div style='font-size:11px;color:#4ade80;letter-spacing:2px;margin-bottom:16px;'>&#128336; RECENT ACTIVITY</div>"
        "<table width='100%' cellpadding='0' cellspacing='0' "
        "style='border:1px solid #1f2937;border-radius:8px;overflow:hidden;'>"
        "{timeline_rows}"
        "</table>{more_logs_note}"
        "</td></tr>"

        # Priorities
        "{priorities_block}"

        # Footer
        "<tr><td style='background:#080810;padding:20px 36px;"
        "border:1px solid #1f2937;border-top:1px solid #1a1a2e;border-radius:0 0 12px 12px;'>"
        "<div style='margin-bottom:12px;'>{legend_html}</div>"
        "<div style='font-size:11px;color:#374151;'>Sent by PingMe &middot; Your personal productivity tracker</div>"
        "</td></tr>"

        "</table></td></tr></table>"
        "</body></html>"
    ).format(
        date_str=date_str,
        score_color=score_color,
        tracked_pct=tracked_pct,
        tracked=tracked,
        total=total,
        untracked_pct=untracked_pct,
        ai_block=ai_block,
        pie_svg=pie_svg,
        bar_svg=bar_svg,
        completed_count=len(completed_items),
        agenda_total=len(agenda),
        completion_pct=completion_pct,
        agenda_rows=agenda_rows,
        notes_html=notes_html,
        timeline_rows=timeline_rows,
        more_logs_note=more_logs_note,
        priorities_block=priorities_block,
        legend_html=legend_html,
    )

    return html