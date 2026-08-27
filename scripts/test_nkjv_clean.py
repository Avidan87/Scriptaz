import re
from pypdf import PdfReader

reader = PdfReader("/Users/Avidan/Scriptaz/Scriptures/new-king-james-version-en.pdf")
text = reader.pages[964].extract_text()
lines = [l.strip() for l in text.splitlines() if l.strip()]

verses = {}
curr_v = None
curr_txt = ""

for line in lines[1:]:
    if "Page " in line or re.match(r"^[a-z]?\[?[1-3]?[A-Z][a-z]+\.?\s+\d+:\d+", line) or "1Lit." in line:
        continue
    vm = re.match(r"^(\d+)\s+([A-Za-z“\"'].*)", line)
    if vm:
        if curr_v and len(curr_txt.strip()) > 15:
            clean = re.sub(r"^[a-z](?=[A-Z“\"])", "", curr_txt).strip()
            verses[curr_v] = clean
        curr_v = int(vm.group(1))
        curr_txt = vm.group(2)
    elif curr_v:
        curr_txt += " " + line

if curr_v and len(curr_txt.strip()) > 15:
    clean = re.sub(r"^[a-z](?=[A-Z“\"])", "", curr_txt).strip()
    verses[curr_v] = clean

print("Clean Verse 27 in NKJV:")
print(verses.get(27))
