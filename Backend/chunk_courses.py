import json
import re

INPUT_FILE  = "data/courses.json"
OUTPUT_FILE = "data/chunks_courses.json"

BULLET = "(cid:0)"

def normalize_type(raw):
    raw = raw.strip()
    raw = re.sub(r"\s+", " ", raw)
    replacements = {
        "CoreCourse":    "Core Course",
        "Elective – 1":  "Elective-1", "Elective - 1": "Elective-1",
        "Elective – 2":  "Elective-2", "Elective - 2": "Elective-2",
        "Elective - 3":  "Elective-3", "Elective – 3":  "Elective-3", "Elective -3": "Elective-3",
        "Elective -4":   "Elective-4", "Elective – 4":  "Elective-4",
    }
    return replacements.get(raw, raw)

def make_metadata(course, chunk_type):
    return {
        "source":       "courses",
        "chunk_type":   chunk_type,
        "course_code":  course["course_code"],
        "course_title": course.get("course_title", ""),
        "semester":     course.get("semester"),
        "program":      course.get("program", "B.Tech CSE"),
        "course_type":  normalize_type(course.get("type", "")),
        "credits":      course.get("credits", {}).get("C"),
    }

def chunk_overview(course):
    c       = course
    code    = c["course_code"]
    title   = c.get("course_title", "")
    sem     = c.get("semester", "")
    ctype   = normalize_type(c.get("type", ""))
    credits = c.get("credits", {})
    tools   = ", ".join(c.get("tools", [])) or "Not specified"
    prelude = c.get("prelude", "")

    credit_str = ""
    if credits:
        credit_str = (f"Credits: L={credits.get('L')} T={credits.get('T')} "
                      f"P={credits.get('P')} S={credits.get('S')} "
                      f"Total={credits.get('C')}")

    text = f"{title} ({code}) is a {ctype} offered in Semester {sem}. "
    if credit_str:
        text += f"{credit_str}. "
    text += f"Tools/Languages used: {tools}. "
    if prelude:
        text += f"About this course: {prelude}"

    return {
        "chunk_id": f"{code}_overview",
        "text":     text.strip(),
        "metadata": make_metadata(course, "overview")
    }

def chunk_units(course):
    chunks = []
    code  = course["course_code"]
    title = course.get("course_title", "")
    for unit in course.get("units", []):
        unit_title = unit.get("title", "")
        unit_content = unit.get("content", "")
        unit_num = unit.get("unit_number")
        hours = unit.get("hours")
        hour_str = f" ({hours} hours)" if hours else ""
        text = f"{title} — {unit_title}{hour_str}. Topics covered: {unit_content}"
        meta = make_metadata(course, "unit")
        meta["unit_number"] = unit_num
        meta["unit_title"]  = unit_title
        chunks.append({
            "chunk_id": f"{code}_unit{unit_num}",
            "text":     text.strip(),
            "metadata": meta
        })
    return chunks

def chunk_outcomes(course):
    outcomes = course.get("outcomes", [])
    if not outcomes: return None
    code  = course["course_code"]
    title = course.get("course_title", "")
    numbered = " ".join(f"{i+1}. {o}" for i, o in enumerate(outcomes))
    text = f"After completing {title} ({code}), students will be able to: {numbered}"
    return {"chunk_id": f"{code}_outcomes", "text": text.strip(), "metadata": make_metadata(course, "outcomes")}

def chunk_objectives(course):
    objectives = course.get("objectives", [])
    if not objectives: return None
    code  = course["course_code"]
    title = course.get("course_title", "")
    numbered = " ".join(f"{i+1}. {o}" for i, o in enumerate(objectives))
    text = f"The objectives of {title} ({code}) are: {numbered}"
    return {"chunk_id": f"{code}_objectives", "text": text.strip(), "metadata": make_metadata(course, "objectives")}

def chunk_labs(course):
    labs = course.get("labs", [])
    if not labs: return None
    code  = course["course_code"]
    title = course.get("course_title", "")
    lab_list = " ".join(f"{i+1}. {l}" for i, l in enumerate(labs))
    text = f"Laboratory experiments in {title} ({code}): {lab_list}"
    return {"chunk_id": f"{code}_labs", "text": text.strip(), "metadata": make_metadata(course, "labs")}


# ── FIX 1: SEMESTER SUMMARY CHUNKS ────────────────────────────────
# One chunk per semester listing ALL courses — fixes "list electives" queries
def chunk_semester_summaries(courses):
    from collections import defaultdict
    by_sem = defaultdict(list)
    for c in courses:
        sem = c.get("semester")
        if sem:
            by_sem[sem].append(c)

    chunks = []
    for sem in sorted(by_sem.keys()):
        sem_courses = by_sem[sem]

        # Group by type
        by_type = defaultdict(list)
        for c in sem_courses:
            ctype = normalize_type(c.get("type", "Other"))
            by_type[ctype].append(c)

        # Build text
        lines = [f"Semester {sem} — B.Tech CSE offers {len(sem_courses)} courses:"]
        lines.append("")

        for ctype, clist in sorted(by_type.items()):
            lines.append(f"{ctype} courses in Semester {sem}:")
            for c in clist:
                lines.append(f"  - {c['course_title']} ({c['course_code']})")
            lines.append("")

        text = "\n".join(lines).strip()

        chunks.append({
            "chunk_id": f"sem{sem}_all_courses",
            "text":     text,
            "metadata": {
                "source":      "courses",
                "chunk_type":  "semester_summary",
                "semester":    sem,
                "program":     "B.Tech CSE",
                "total_courses": len(sem_courses),
            }
        })

        # Also make a dedicated ELECTIVES-only chunk per semester
        electives = [c for c in sem_courses if "Elective" in c.get("type", "")]
        if electives:
            elines = [f"Elective courses available in Semester {sem} (B.Tech CSE):"]
            elines.append("")

            by_etype = defaultdict(list)
            for c in electives:
                etype = normalize_type(c.get("type", "Elective"))
                by_etype[etype].append(c)

            for etype, clist in sorted(by_etype.items()):
                elines.append(f"{etype}:")
                for c in clist:
                    elines.append(f"  - {c['course_title']} ({c['course_code']})")
                elines.append("")

            chunks.append({
                "chunk_id": f"sem{sem}_electives",
                "text":     "\n".join(elines).strip(),
                "metadata": {
                    "source":           "courses",
                    "chunk_type":       "electives_summary",
                    "semester":         sem,
                    "program":          "B.Tech CSE",
                    "total_electives":  len(electives),
                }
            })

    return chunks


def chunk_course(course):
    chunks = []
    chunks.append(chunk_overview(course))
    chunks.extend(chunk_units(course))
    for fn in [chunk_outcomes, chunk_objectives, chunk_labs]:
        result = fn(course)
        if result:
            chunks.append(result)
    return chunks


def main():
    with open(INPUT_FILE, encoding="utf-8") as f:
        courses = json.load(f)

    all_chunks = []
    for course in courses:
        all_chunks.extend(chunk_course(course))

    # Add semester summary + elective summary chunks
    summary_chunks = chunk_semester_summaries(courses)
    all_chunks.extend(summary_chunks)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, indent=2, ensure_ascii=False)

    by_type = {}
    for c in all_chunks:
        t = c["metadata"]["chunk_type"]
        by_type[t] = by_type.get(t, 0) + 1

    print(f"✅ {len(all_chunks)} chunks from {len(courses)} courses")
    print()
    for t, count in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f"  {t:25s}: {count}")

    # Show sem6 electives chunk
    sem6_el = next(c for c in all_chunks if c["chunk_id"] == "sem6_electives")
    print("\n--- Sem 6 electives chunk preview ---")
    print(sem6_el["text"][:600])

if __name__ == "__main__":
    main()