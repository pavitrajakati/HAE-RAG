import pdfplumber
import re
import json

INPUT_FILE = "data/UG-CSE.pdf"
OUTPUT_FILE = "data/final_courses_fixed.json"

BULLET = "(cid:0)"


def clean(text):
    if not text:
        return ""
    text = text.replace(BULLET, "").strip()
    text = re.sub(r"\s+", " ", text)
    return text


def extract_bullets(text):
    import re as _re
    parts = text.split(BULLET)
    raw = []
    for part in parts[1:]:
        lines = [l.strip() for l in part.split("\n")]
        combined = ""
        for line in lines:
            if line.startswith("(cid"): break
            if not line:
                if combined: break
                continue
            combined += " " + line
        combined = clean(combined)
        if combined:
            raw.append(combined)
    results = []
    for part in raw:
        words = part.split()
        if not words: continue
        if results and words[0][0].islower():
            first_upper = _re.search(r'\s([A-Z][a-z]{2,})', part)
            if first_upper:
                tail      = part[:first_upper.start()].strip()
                new_start = part[first_upper.start():].strip()
                results[-1] = results[-1].rstrip() + " " + tail
                if new_start:
                    results.append(new_start)
            else:
                results[-1] = results[-1].rstrip() + " " + part
        else:
            results.append(part)
    return results


def extract_units(content):
    raw = re.findall(
        r"(Unit\s*\d+[:\s]+.*?)(?=Unit\s*\d+[:\s]|Laboratory|Text Book|Course Outcome|$)",
        content,
        re.S | re.I
    )
    units = []
    seen = set()
    for u in raw:
        title_match = re.search(r"(Unit\s*\d+[:\s]+[^\n]+)", u)
        title = clean(title_match.group(1)) if title_match else ""
        unit_num = re.search(r"Unit\s*(\d+)", title)
        if not unit_num:
            continue
        num = unit_num.group(1)
        if num in seen:
            continue
        seen.add(num)

        hours_match = re.search(r"(\d+)\s*[Hh]ours?", u)
        hours = int(hours_match.group(1)) if hours_match else None

        body = re.sub(r"Unit\s*\d+[:\s]+[^\n]+\n?", "", u, count=1)
        body = re.sub(r"\d+\s*[Hh]ours?", "", body)

        # FIX 2: strip page noise from unit content
        body = re.sub(r"P\.E\.S\..*?\d+\s*\|\s*Page", "", body, flags=re.S)

        units.append({
            "unit_number": int(num),
            "title": title,
            "hours": hours,
            "content": clean(body)
        })

    return sorted(units, key=lambda x: x["unit_number"])


def extract_courses(full_text):
    chunks = re.split(r"Course Code\s+(UE\d+[A-Z]+\d+[A-Z0-9]*)", full_text)
    courses = []

    for i in range(1, len(chunks), 2):
        code = chunks[i].strip()
        content = chunks[i + 1]

        course = {"course_code": code}

        # TITLE
        title = re.search(r"Course Title\s+(.+)", content)
        if title:
            course["course_title"] = clean(title.group(1))

        # FIX 1: PROGRAM — exclude "Hours" false match
        prog = re.search(r"(B\.Tech(?:\s+(?!Hours)\w+)?)", content)
        if prog:
            course["program"] = prog.group(1).strip()

        # SEMESTER
        sem = re.search(r"Semester\s+(\d+)", content)
        if sem:
            course["semester"] = int(sem.group(1))

        # TYPE OF COURSE
        ctype = re.search(r"Type of Course\s+(.+)", content)
        if ctype:
            raw = clean(ctype.group(1))
            raw = re.sub(r"\b[LTPSC]\b.*", "", raw).strip()
            if raw:
                course["type"] = raw

        # CREDITS
        credits_match = re.search(
            r"Credit\s+Assigned\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)",
            content
        ) or re.search(
            r"L\s+T\s+P\s+S\s+C\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)",
            content
        )
        if credits_match:
            course["credits"] = {
                "L": int(credits_match.group(1)),
                "T": int(credits_match.group(2)),
                "P": int(credits_match.group(3)),
                "S": int(credits_match.group(4)),
                "C": int(credits_match.group(5)),
            }

        # TOOLS
        tools_match = re.search(
            r"(?:AI Tools?|/Tools?/Languages?)\s+(.*?)(?:Desirable|Prelude)",
            content, re.S
        )
        if tools_match:
            raw_tools = tools_match.group(1)
            tools = []
            for line in raw_tools.split("\n"):
                line = clean(line)
                if line and len(line) > 2:
                    for t in line.split(","):
                        t = t.strip()
                        if t and len(t) > 2:
                            tools.append(t)
            if tools:
                course["tools"] = list(dict.fromkeys(tools))

        # PRELUDE
        prelude = re.search(r"Prelude\s+(.*?)Course\s*Objectives?", content, re.S)
        if prelude:
            course["prelude"] = clean(prelude.group(1))

        # OBJECTIVES
        obj_section = re.search(
            r"Objectives?:\s*(.*?)(?:Course\s*Contents|Unit\s*1)",
            content, re.S
        )
        if obj_section:
            objectives = extract_bullets(obj_section.group(1))
            if objectives:
                course["objectives"] = objectives

        # UNITS
        units_section = re.search(
            r"(Unit\s*1:.*?)(?:Laboratory|Text Book|Course Outcome)",
            content, re.S
        )
        if units_section:
            course["units"] = extract_units(units_section.group(1))

        # LABS
        labs_section = re.search(
            r"Laboratory\s*(.*?)(?:Text Book|Reference Book|Course Outcome)",
            content, re.S
        )
        if labs_section:
            labs = re.findall(r"\d+\.\s*(.+)", labs_section.group(1))
            clean_labs = [clean(l) for l in labs if len(l.strip()) > 5]
            if clean_labs:
                course["labs"] = clean_labs

        # FIX 3: TEXTBOOKS — strip URLs and license notes, keep the actual title
        tb_section = re.search(
            r"Text Book\(s\):(.*?)(?:Reference Book|Course Outcome)",
            content, re.S
        )
        if tb_section:
            raw = tb_section.group(1)
            # Strip license/URL noise blocks first, before splitting
            raw = re.sub(r"\(Available under.*?(?=\d+\.|Reference|Course Outcome|$)", "", raw, flags=re.S)
            raw = re.sub(r"\(Download.*?(?=\d+\.|Reference|Course Outcome|$)", "", raw, flags=re.S)
            raw = re.sub(r"https?://\S+", "", raw)
            # Split on numbered entries — first book may have no "1." prefix
            books = re.findall(
                r'(?:(?<=\n)|(?<=\())?\s*(?:\d+\.\s*)?("[\w].+?)(?=\s*\d+\.|Reference|Course Outcome|$)',
                raw, re.S
            )
            # Fallback: simpler split if above finds nothing
            if not books:
                books = re.findall(r'\d+\.\s*(.+?)(?=\d+\.|Reference|Course Outcome|$)', raw, re.S)
            clean_books = []
            for b in books:
                b = re.sub(r"\s+", " ", b).strip().rstrip(",")
                if len(b) > 20 and re.match(r'^["\w]', b):
                    clean_books.append(b)
            if clean_books:
                course["textbooks"] = clean_books
            if clean_books:
                course["textbooks"] = clean_books

        # REFERENCES
        ref_section = re.search(
            r"Reference\s*Book\(s\):(.*?)(?:Course Outcome)",
            content, re.S
        )
        if ref_section:
            refs = re.findall(
                r"\d+\.\s*(.+?)(?=\d+\.|Course Outcome|$)",
                ref_section.group(1), re.S
            )
            clean_refs = [re.sub(r"\s+", " ", r).strip() for r in refs if len(r.strip()) > 15]
            if clean_refs:
                course["references"] = clean_refs

        # OUTCOMES
        outcome_section = re.search(r"Course\s*Outcome\s*(.*?)(?:P\.E\.S\.|$)", content, re.S)
        if outcome_section:
            outcomes = extract_bullets(outcome_section.group(1))
            # FIX 4: remove cut-off sentences
            outcomes = [o for o in outcomes if len(o) > 20 and not o.endswith("and")]
            if outcomes:
                course["outcomes"] = outcomes

        if "course_title" in course:
            courses.append(course)

    return courses


def main():
    full_text = ""

    with pdfplumber.open(INPUT_FILE) as pdf:
        for page in pdf.pages:
            try:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"
            except Exception as e:
                print(f"⚠️  Skipping page: {e}")

    data = extract_courses(full_text)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    print(f"✅ Extracted {len(data)} courses successfully!")

    # Quality check
    print("\n--- PROGRAM FIELD SAMPLE ---")
    for c in data[:5]:
        print(f"  {c['course_code']}: {c.get('program')}")

    print("\n--- TEXTBOOK SAMPLE (course 1) ---")
    for b in data[0].get("textbooks", []):
        print(f"  [{len(b)}] {b[:90]}")

    print("\n--- OUTCOME SAMPLE (course 1) ---")
    for o in data[0].get("outcomes", []):
        print(f"  {o}")

    # Check for any remaining bad outcomes
    bad = [(c["course_code"], o) for c in data for o in c.get("outcomes", [])
           if len(o) <= 20 or o.endswith("and")]
    print(f"\n--- BAD OUTCOMES REMAINING: {len(bad)} ---")
    for code, o in bad:
        print(f"  [{code}]: {repr(o)}")


if __name__ == "__main__":
    main()