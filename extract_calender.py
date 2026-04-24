import pdfplumber
import re
import json

CALENDARS = [
    {
        "file": "data/oddsem_calender.pdf",
        "session": "Aug-Dec 2025",
        "semesters": [1, 3, 5, 7],
        "day_order": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
        "day_anchor_cols": [2, 5, 6, 9, 12, 15],
        "col_working_days": 18,
        "col_activity": 19,
        "data_start_row": 5,
    },
    {
        "file": "data/evensem_calender.pdf",
        "session": "Jan-May 2026",
        "semesters": [2, 4, 6, 8],
        "day_order": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
        "day_anchor_cols": [2, 5, 8, 11, 14, 17],
        "col_working_days": 20,
        "col_activity": 21,
        "data_start_row": 5,
    }
]

def clean(x):
    return str(x).replace("\n", " ").strip() if x else ""

def parse_cell(cell_text):
    if not cell_text:
        return None
    lines = [l.strip() for l in str(cell_text).split("\n") if l.strip()]
    if not lines:
        return None
    date_num = None
    tags = []
    for line in lines:
        if re.match(r"^\d+$", line):
            date_num = int(line)
        else:
            tags.append(line)
    return {"date": date_num, "tags": tags}

def assign_day(col_idx, anchor_cols, day_names):
    for i, anchor in enumerate(anchor_cols):
        next_anchor = anchor_cols[i + 1] if i + 1 < len(anchor_cols) else anchor + 4
        if anchor <= col_idx < next_anchor:
            return day_names[i]
    return None

def extract_calendar(config):
    weeks = []
    with pdfplumber.open(config["file"]) as pdf:
        table = pdf.pages[0].extract_tables()[0]
        anchors = config["day_anchor_cols"]
        day_names = config["day_order"]
        col_wd = config["col_working_days"]
        col_act = config["col_activity"]
        current_week = None

        # Skip legend rows (rows where col0 contains "FAM:" or "CCM:" or "PTM:")
        for row in table[config["data_start_row"]:]:
            if row[0] and any(x in str(row[0]) for x in ["FAM:", "CCM:", "PTM:"]):
                break
            week_raw = clean(row[0])
            month = clean(row[1])
            is_new_week = bool(week_raw and re.match(r"^\d+\.", week_raw))

            if is_new_week:
                if current_week:
                    weeks.append(current_week)
                activity = clean(row[col_act]) if col_act < len(row) else ""
                raw_wd = clean(row[col_wd]) if col_wd < len(row) else ""
                working_days = int(raw_wd) if re.match(r"^\d+$", raw_wd) else None
                current_week = {
                    "week": int(week_raw.replace(".", "").strip()),
                    "month": month,
                    "working_days": working_days,
                    "activity": activity,
                    "days": {d: None for d in day_names}
                }
            elif not current_week:
                continue

            for col_idx, cell in enumerate(row):
                if col_idx <= 1 or col_idx >= col_wd:
                    continue
                if not cell:
                    continue
                day_name = assign_day(col_idx, anchors, day_names)
                if not day_name:
                    continue
                parsed = parse_cell(cell)
                if not parsed:
                    continue
                if parsed["date"] is not None:
                    current_week["days"][day_name] = {"date": parsed["date"], "tags": parsed["tags"]}
                else:
                    if current_week["days"].get(day_name):
                        current_week["days"][day_name]["tags"].extend(parsed["tags"])

        if current_week:
            weeks.append(current_week)

    for week in weeks:
        for day_name, day_data in week["days"].items():
            if not day_data:
                continue
            tags = day_data.pop("tags", [])
            day_data["is_holiday"] = "H" in tags
            events = [t for t in tags if t != "H"]
            if events:
                day_data["events"] = events
        week["days"] = {k: v for k, v in week["days"].items() if v}
        if week.get("activity"):
            week["note"] = week.pop("activity")
        else:
            week.pop("activity", None)

    return {
        "session": config["session"],
        "semesters": config["semesters"],
        "total_weeks": len(weeks),
        "weeks": weeks
    }

def main():
    output = []
    for config in CALENDARS:
        print(f"\nProcessing: {config['session']}...")
        cal = extract_calendar(config)
        output.append(cal)
        print(f"  ✅ {cal['total_weeks']} weeks extracted")
        for w in cal["weeks"]:
            holidays = [f"{d}={v['date']}" for d, v in w["days"].items() if v.get("is_holiday")]
            events = [f"{d} {v['date']}:{v.get('events')}" for d, v in w["days"].items() if v.get("events")]
            if holidays or events or w.get("note"):
                print(f"  Wk{w['week']} ({w['month']}): H={holidays} ev={events} | {w.get('note','')}")

    with open("data/calendar.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4, ensure_ascii=False)
    print("\n✅ calendar.json ready!")

if __name__ == "__main__":
    main()