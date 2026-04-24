import pdfplumber
import json

INPUT_FILE = "data/faculty.pdf"
OUTPUT_FILE = "data/faculty.json"


def clean(x):
    if not x:
        return ""
    # FIX 1: newlines inside cells (e.g. "Professor/Chairperso\nn- AI&ML")
    return str(x).replace("\n", " ").strip()


def process():
    result = []

    with pdfplumber.open(INPUT_FILE) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()

            for table in tables:
                for row in table[1:]:  # skip header
                    row = [clean(c) for c in row]

                    if len(row) < 4:
                        continue

                    # FIX 2: split "other domain" on commas into individual tags
                    core_domains = [d for d in row[4:7] if d]   # Domain-1, 2, 3
                    other_raw = row[7] if len(row) > 7 else ""
                    other_domains = [d.strip() for d in other_raw.split(",") if d.strip()]
                    all_domains = list(dict.fromkeys(core_domains + other_domains))  # dedupe

                    faculty = {
                        "name": row[1],
                        "designation": row[2],
                        "email": row[3],
                        "domains": all_domains
                    }

                    # FIX 3: skip rows with no name AND no email (truly empty rows)
                    if faculty["name"] and (faculty["email"] or faculty["domains"]):
                        result.append(faculty)

    return result


if __name__ == "__main__":
    data = process()

    with open(OUTPUT_FILE, "w") as f:
        json.dump(data, f, indent=4)

    print(f"✅ Faculty JSON ready! {len(data)} faculty extracted.")