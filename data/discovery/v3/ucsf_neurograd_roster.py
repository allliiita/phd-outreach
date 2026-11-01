"""UCSF Neuroscience Graduate Program faculty, from the page the applicant saved in her own browser
(neurograd.ucsf.edu/faculty is behind a bot check for us). Names and topics are parsed by code from
data/snapshots/manual/ucsf-neurograd-faculty.txt; title / profile come from our UCSF Profiles rosters by name."""
import glob, json, re, sys
sys.path.insert(0, ".")
from outreach.validate import norm_name

SRC = "data/snapshots/manual/ucsf-neurograd-faculty.txt"
URL = "https://neurograd.ucsf.edu/faculty"
lines = [l.strip() for l in open(SRC) if l.strip()]
skip = re.compile(r"^(Home|Faculty$|The faculty|more information|laboratories|studies in|Sciences \(PIBS|give students|among faculty|designed to|University of California|\d+/\d+/\d+|https?://|[A-Z]$)")
body = [l for l in lines if not skip.match(l)]
start = next(i for i, l in enumerate(body) if l.startswith("Reza Abbasi-Asl"))
body = body[start:]
NAME = re.compile(r"^[A-Z][\w'’.\-]+(?: [A-Z][\w'’.\-]+){1,3}(?: \((Emeritus|Emerita)\))?$")
people, i = [], 0
while i < len(body):
    if NAME.match(body[i]) and i + 1 < len(body) and not NAME.match(body[i + 1]):
        people.append((body[i], body[i + 1])); i += 2
    else:
        i += 1
prof = {}
for f in glob.glob("data/roster/ucsf-*.jsonl"):
    for l in open(f):
        r = json.loads(l)
        if "name" in r and r.get("title_on_roster"):
            prof.setdefault(norm_name(r["name"]), r)
out = []
for name, topic in people:
    emer = "(Emerit" in name
    nm = re.sub(r" \((Emeritus|Emerita)\)", "", name)
    p = prof.get(norm_name(nm), {})
    out.append({"name": nm, "institution": "University of California San Francisco",
                "department": "Neuroscience Graduate Program (faculty)",
                "title_on_roster": "Emeritus" if emer else p.get("title_on_roster", ""),
                "roster_url": URL, "profile_url": p.get("profile_url", ""),
                "quote": f"{name} {topic}", "research_topic": topic,
                "source": "applicant-saved page (data/snapshots/manual/ucsf-neurograd-faculty.pdf)"})
open("data/roster/ucsf-neurograd.jsonl", "w").write("".join(json.dumps(r) + "\n" for r in out))
print(len(out), "people;", sum(bool(r["title_on_roster"]) for r in out), "with title from Profiles")
