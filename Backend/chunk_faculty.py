import json
import re

INPUT_FILE  = "data/faculty.json"
OUTPUT_FILE = "data/chunks_faculty_v2.json"


def normalize_designation(raw):
    raw = raw.strip()
    raw = re.sub(r"\s+", " ", raw)
    fixes = {
        "Associate Prof.":   "Associate Professor",
        "Assoc. Prof.":      "Associate Professor",
        "Assistant Prof.":   "Assistant Professor",
        "Asst. Prof.":       "Assistant Professor",
        "Faculty Associate": "Faculty Associate",
    }
    for k, v in fixes.items():
        if k in raw:
            return v
    return raw


def make_metadata(faculty, chunk_type):
    return {
        "source":      "faculty",
        "chunk_type":  chunk_type,
        "name":        faculty["name"],
        "designation": normalize_designation(faculty.get("designation", "")),
        "email":       faculty.get("email", ""),
    }


def chunk_profile(faculty):
    name  = faculty["name"]
    desig = normalize_designation(faculty.get("designation", "faculty member"))
    email = faculty.get("email", "")
    domains = faculty.get("domains", [])
    top_domains = ", ".join(domains[:3]) if domains else "not specified"

    # FIX 2: Make email very explicit and repeated so retrieval hits it
    text = f"{name} is a {desig} in the CSE department at PES University."
    if email:
        text += f" Their email address is {email}."
        text += f" Contact: {email}."   # repeated for stronger retrieval signal
    else:
        text += " Email not available."
    text += f" Research areas: {top_domains}."

    name_id = re.sub(r"[^a-zA-Z0-9]", "_", name.lower())
    return {
        "chunk_id": f"faculty_{name_id}_profile",
        "text":     text.strip(),
        "metadata": make_metadata(faculty, "profile")
    }


def chunk_expertise(faculty):
    name    = faculty["name"]
    desig   = normalize_designation(faculty.get("designation", "faculty member"))
    email   = faculty.get("email", "")
    domains = faculty.get("domains", [])
    if not domains:
        return None

    domain_str = ", ".join(domains)
    # FIX 2: Also include email in expertise chunk so either chunk can answer
    text = (f"{name} ({desig}) at PES University CSE department "
            f"specialises in: {domain_str}.")
    if email:
        text += f" Email: {email}."

    name_id = re.sub(r"[^a-zA-Z0-9]", "_", name.lower())
    return {
        "chunk_id": f"faculty_{name_id}_expertise",
        "text":     text.strip(),
        "metadata": {**make_metadata(faculty, "expertise"), "domains": domains}
    }


# ── FIX 2: DOMAIN SUMMARY CHUNKS ─────────────────────────────────
# One chunk per major domain listing ALL faculty who work on it
# Fixes "who teaches ML" → returns a single chunk with all names + emails
def chunk_domain_summaries(faculty_list):
    from collections import defaultdict

    # Collect faculty per domain (normalized)
    domain_map = defaultdict(list)

    DOMAIN_ALIASES = {
        "machine learning":                     "Machine Learning",
        "ml":                                   "Machine Learning",
        "deep learning":                        "Deep Learning",
        "dl":                                   "Deep Learning",
        "natural language processing":          "Natural Language Processing",
        "nlp":                                  "Natural Language Processing",
        "computer vision":                      "Computer Vision",
        "cv":                                   "Computer Vision",
        "artificial intelligence":              "Artificial Intelligence",
        "ai":                                   "Artificial Intelligence",
        "cyber security":                       "Cyber Security",
        "cybersecurity":                        "Cyber Security",
        "data analytics":                       "Data Analytics",
        "big data":                             "Data Analytics",
        "cloud computing":                      "Cloud Computing",
        "iot":                                  "IoT",
        "internet of things":                   "IoT",
        "blockchain":                           "Blockchain",
        "block chain":                          "Blockchain",
        "image processing":                     "Image Processing",
        "generative ai":                        "Generative AI",
        "gen ai":                               "Generative AI",
        "reinforcement learning":               "Reinforcement Learning",
        "knowledge graph":                      "Knowledge Graphs",
    }

    for faculty in faculty_list:
        name  = faculty["name"]
        email = faculty.get("email", "")
        desig = normalize_designation(faculty.get("designation", ""))

        for raw_domain in faculty.get("domains", []):
            # Normalize
            lower = raw_domain.lower().strip()
            matched = None
            for alias, canonical in DOMAIN_ALIASES.items():
                if alias in lower:
                    matched = canonical
                    break
            if not matched:
                # Use raw domain cleaned up
                matched = raw_domain.strip()

            domain_map[matched].append({
                "name":  name,
                "email": email,
                "desig": desig,
            })

    chunks = []
    for domain, members in sorted(domain_map.items()):
        # Dedupe by name
        seen = set()
        unique = []
        for m in members:
            if m["name"] not in seen:
                seen.add(m["name"])
                unique.append(m)

        if len(unique) < 2:
            continue   # skip single-person domains — already in profile chunk

        lines = [f"Faculty members with expertise in {domain} at PES University CSE:"]
        lines.append("")
        for m in unique:
            line = f"  - {m['name']} ({m['desig']})"
            if m["email"]:
                line += f" — email: {m['email']}"
            lines.append(line)

        text = "\n".join(lines)
        domain_id = re.sub(r"[^a-zA-Z0-9]", "_", domain.lower())

        chunks.append({
            "chunk_id": f"faculty_domain_{domain_id}",
            "text":     text.strip(),
            "metadata": {
                "source":      "faculty",
                "chunk_type":  "domain_summary",
                "domain":      domain,
                "total_faculty": len(unique),
            }
        })

    return chunks


def main():
    with open(INPUT_FILE, encoding="utf-8") as f:
        faculty_list = json.load(f)

    all_chunks = []
    for faculty in faculty_list:
        all_chunks.append(chunk_profile(faculty))
        exp = chunk_expertise(faculty)
        if exp:
            all_chunks.append(exp)

    # Add domain summary chunks
    domain_chunks = chunk_domain_summaries(faculty_list)
    all_chunks.extend(domain_chunks)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, indent=2, ensure_ascii=False)

    by_type = {}
    for c in all_chunks:
        t = c["metadata"]["chunk_type"]
        by_type[t] = by_type.get(t, 0) + 1

    print(f"✅ {len(all_chunks)} chunks from {len(faculty_list)} faculty")
    print()
    for t, count in by_type.items():
        print(f"  {t:20s}: {count}")

    print()
    # Show ML domain chunk
    ml_chunk = next((c for c in all_chunks if c["metadata"].get("domain") == "Machine Learning"), None)
    if ml_chunk:
        print("--- Machine Learning domain chunk ---")
        print(ml_chunk["text"][:600])

    print()
    # Show Ankita profile with email
    ankita = next(c for c in all_chunks if "ankita" in c["chunk_id"] and "profile" in c["chunk_id"])
    print("--- Ankita profile chunk ---")
    print(ankita["text"])

if __name__ == "__main__":
    main()