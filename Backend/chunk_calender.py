import json
import re

INPUT_FILE  = "data/calendar.json"
OUTPUT_FILE = "data/chunks_calendar.json"


# -------------------------------------------------------
# CHUNKING STRATEGY:
#
# Calendar produces 4 types of chunks:
#   1. WEEK      — one per week (what's happening this week)
#   2. EVENT     — one per event type collected across all weeks
#                  e.g. all ISA1 dates together, all holidays together
#   3. SUMMARY   — one per semester session (key dates overview)
#   4. HOLIDAY   — one chunk listing all holidays in the session
#
# Why collect events together?
#   Student asks "When is ISA 1?" → needs ALL ISA1 dates, not week-by-week
#   Student asks "What are all the holidays?" → same need
# -------------------------------------------------------

# Map raw event tags to clean readable names
EVENT_NAME_MAP = {
    "ISA 1": "ISA 1 (In Semester Assessment 1)",
    "ISA1":  "ISA 1 (In Semester Assessment 1)",
    "ISA 2": "ISA 2 (In Semester Assessment 2)",
    "ISA2":  "ISA 2 (In Semester Assessment 2)",
    "FAM I":   "Faculty Advisor Meeting 1",
    "FAM II":  "Faculty Advisor Meeting 2",
    "FAM":     "Faculty Advisor Meeting",
    "CCM I":   "Class Committee Meeting 1",
    "CCM II":  "Class Committee Meeting 2",
    "PTM I":   "Parent Teacher Meeting 1",
    "PTM II":  "Parent Teacher Meeting 2",
    "PTMI":    "Parent Teacher Meeting 1",
    "PTMII":   "Parent Teacher Meeting 2",
    "LWD":     "Last Working Day",
    "FAD":     "Final Attendance Display",
    "Wed TT":  "Wednesday Time Table",
    "Thurs TT": "Thursday Time Table",
    "TT":      "Time Table Change",
}

# Month number map for building proper dates
MONTH_MAP = {
    "Jan": 1, "Feb": 2, "Mar": 3, "March": 3,
    "Apr": 4, "April": 4, "May": 5,
    "Aug": 8, "Sept": 9, "Sep": 9,
    "Oct": 10, "Nov": 11, "Dec": 12,
}


def clean_event(tag):
    return EVENT_NAME_MAP.get(tag, tag)


def get_month(month_str, date_num=None):
    """
    Handle 'Aug/Sept', 'Oct/Nov' split-month weeks correctly.
    If date is small (1-7) in a split-month week, it belongs to the SECOND month.
    """
    parts = month_str.split("/")
    if len(parts) == 1:
        return parts[0].strip()
    first  = parts[0].strip()
    second = parts[1].strip()
    # Small date numbers (1-7) in a split-month week belong to the second month
    if date_num is not None and date_num <= 7:
        return second
    return first


def make_date_str(month_str, date_num, year):
    month = get_month(month_str, date_num)
    return f"{date_num} {month} {year}"


def make_metadata(session, semesters, chunk_type):
    return {
        "source":     "calendar",
        "chunk_type": chunk_type,
        "session":    session,
        "semesters":  semesters,
    }


def chunk_weeks(calendar):
    """One chunk per week — what's happening."""
    chunks = []
    session   = calendar["session"]
    semesters = calendar["semesters"]
    year      = re.search(r'\d{4}', session).group()

    for week in calendar["weeks"]:
        week_num     = week["week"]
        month        = week["month"]
        working_days = week.get("working_days")
        note         = week.get("note", "")
        days         = week.get("days", {})

        # Collect holidays and events
        holidays = []
        events   = []
        for day_name, day_data in days.items():
            if not day_data:
                continue
            date_str = make_date_str(month, day_data["date"], year)
            if day_data.get("is_holiday"):
                holidays.append(date_str)
            for tag in day_data.get("events", []):
                events.append(f"{clean_event(tag)} on {date_str}")

        # Build text
        text = f"Week {week_num} of {session} (Semesters {semesters}), {month}."
        if working_days is not None:
            text += f" Working days: {working_days}."
        if holidays:
            text += f" Holidays: {', '.join(holidays)}."
        if events:
            text += f" Events: {', '.join(events)}."
        if note:
            text += f" Note: {note}."

        sem_id = "_".join(str(s) for s in semesters)
        chunks.append({
            "chunk_id": f"cal_sem{sem_id}_week{week_num}",
            "text":     text.strip(),
            "metadata": {
                **make_metadata(session, semesters, "week"),
                "week_number":  week_num,
                "month":        month,
                "working_days": working_days,
            }
        })

    return chunks


def chunk_events(calendar):
    """
    Collect all occurrences of each event type across all weeks.
    Answers: 'When is ISA 1?', 'When are PTM dates?'
    """
    session   = calendar["session"]
    semesters = calendar["semesters"]
    year      = re.search(r'\d{4}', session).group()

    # Gather all event occurrences: {normalized_tag: [date_str, ...]}
    event_dates = {}
    for week in calendar["weeks"]:
        month = week["month"]
        for day_name, day_data in week.get("days", {}).items():
            if not day_data:
                continue
            date_str = make_date_str(month, day_data["date"], year)
            for tag in day_data.get("events", []):
                # Normalize tag
                norm = EVENT_NAME_MAP.get(tag, tag)
                # Group ISA1 variants together
                if "ISA 1" in norm:
                    norm = "ISA 1 (In Semester Assessment 1)"
                if "ISA 2" in norm:
                    norm = "ISA 2 (In Semester Assessment 2)"
                event_dates.setdefault(norm, []).append(date_str)

    chunks = []
    sem_id = "_".join(str(s) for s in semesters)

    for event_name, dates in event_dates.items():
        unique_dates = list(dict.fromkeys(dates))  # dedupe, preserve order
        dates_str = ", ".join(unique_dates)
        text = (f"{event_name} for Semesters {semesters} "
                f"({session}) is scheduled on: {dates_str}.")

        event_id = re.sub(r"[^a-zA-Z0-9]", "_", event_name.lower())[:30]
        chunks.append({
            "chunk_id": f"cal_sem{sem_id}_{event_id}",
            "text":     text.strip(),
            "metadata": {
                **make_metadata(session, semesters, "event"),
                "event_name": event_name,
                "dates":      unique_dates,
            }
        })

    return chunks


def chunk_holidays(calendar):
    """
    All holidays in one chunk with names, sorted chronologically.
    Answers: 'What are all the holidays this semester?'
    """
    session   = calendar["session"]
    semesters = calendar["semesters"]
    year      = re.search(r'\d{4}', session).group()

    holidays = []
    for week in calendar["weeks"]:
        month = week["month"]
        note  = week.get("note", "")
        for day_name, day_data in week.get("days", {}).items():
            if day_data and day_data.get("is_holiday"):
                date_num = day_data["date"]
                date_str = make_date_str(month, date_num, year)

                # Extract holiday name from note
                # Notes look like "15th - Independence Day" or "1st – Kannada Rajyotsava"
                name = ""
                name_match = re.search(
                    rf'{date_num}(?:st|nd|rd|th)?\s*[-–]\s*(.+?)(?:\n|,|$)',
                    note, re.I
                )
                if name_match:
                    name = name_match.group(1).strip()

                # Sort key: month number + date
                month_name = get_month(month, date_num)
                month_num  = MONTH_MAP.get(month_name, 0)
                sort_key   = month_num * 100 + date_num

                holidays.append((sort_key, date_str, name))

    if not holidays:
        return None

    # Sort chronologically and dedupe by date
    holidays.sort(key=lambda x: x[0])
    seen = set()
    unique = []
    for sort_key, date_str, name in holidays:
        if date_str not in seen:
            seen.add(date_str)
            unique.append((date_str, name))

    # Build readable list
    items = []
    for date_str, name in unique:
        if name:
            items.append(f"{date_str} ({name})")
        else:
            items.append(date_str)

    sem_id = "_".join(str(s) for s in semesters)
    odd_even = "odd" if semesters[0] % 2 == 1 else "even"
    text = (
        f"Holidays for {odd_even} semesters {semesters} during {session}: "
        f"{chr(10).join(f'  {i+1}. {item}' for i, item in enumerate(items))}. "
        f"Total holidays: {len(unique)}."
    )

    return {
        "chunk_id": f"cal_sem{sem_id}_holidays",
        "text":     text.strip(),
        "metadata": {
            **make_metadata(session, semesters, "holidays"),
            "holiday_dates":  [d for d,_ in unique],
            "total_holidays": len(unique),
            "odd_even":       odd_even,
        }
    }


def chunk_summary(calendar):
    """
    Key dates overview for the whole session.
    Answers: 'When does Semester 5 start?', 'When are results announced?'
    """
    session   = calendar["session"]
    semesters = calendar["semesters"]

    # Extract start/end from week 1 and last week
    weeks = calendar["weeks"]
    first_week = weeks[0]
    last_week  = weeks[-1]

    first_month = first_week["month"]
    last_month  = last_week["month"]
    year        = re.search(r'\d{4}', session).group()

    # Get first working day
    first_day = None
    for day_name in ["Mon", "Tue", "Wed", "Thu", "Fri"]:
        d = first_week["days"].get(day_name)
        if d and not d.get("is_holiday"):
            first_day = make_date_str(first_month, d["date"], year)
            break

    text = (f"Academic calendar for Semesters {semesters}, session {session}. "
            f"Classes run from {first_month} to {last_month} {year}. "
            f"Total weeks: {calendar['total_weeks']}. ")
    if first_day:
        text += f"Classes commence: {first_day}. "

    # Add key events from notes
    key_notes = [w["note"] for w in weeks if w.get("note")]
    if key_notes:
        text += "Key events: " + " | ".join(key_notes[:8]) + "."

    sem_id = "_".join(str(s) for s in semesters)
    return {
        "chunk_id": f"cal_sem{sem_id}_summary",
        "text":     text.strip(),
        "metadata": make_metadata(session, semesters, "summary")
    }


def main():
    with open(INPUT_FILE, encoding="utf-8") as f:
        calendars = json.load(f)

    all_chunks = []

    for calendar in calendars:
        all_chunks.extend(chunk_weeks(calendar))
        all_chunks.extend(chunk_events(calendar))
        h = chunk_holidays(calendar)
        if h:
            all_chunks.append(h)
        all_chunks.append(chunk_summary(calendar))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, indent=2, ensure_ascii=False)

    by_type = {}
    for c in all_chunks:
        t = c["metadata"]["chunk_type"]
        by_type[t] = by_type.get(t, 0) + 1

    print(f"✅ {len(all_chunks)} chunks from {len(calendars)} calendars")
    print()
    print("--- Chunks by type ---")
    for t, count in by_type.items():
        print(f"  {t:15s}: {count}")
    print()

    # Show one of each
    shown = set()
    for c in all_chunks:
        t = c["metadata"]["chunk_type"]
        if t not in shown:
            shown.add(t)
            print(f"=== {t.upper()} SAMPLE ===")
            print(c["text"])
            print()


if __name__ == "__main__":
    main()