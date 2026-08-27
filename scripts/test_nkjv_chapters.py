import re
from pypdf import PdfReader

reader = PdfReader("/Users/Avidan/Scriptaz/Scriptures/new-king-james-version-en.pdf")
text = reader.pages[964].extract_text() + "\n" + reader.pages[965].extract_text()
lines = [l.strip() for l in text.splitlines() if l.strip()]

current_book = "John"
current_chapter = 14
verses = {}
curr_v = None
curr_txt = ""

for line in lines:
    chap_m = re.match(r"^CHAPTER\s+(\d+)", line, re.IGNORECASE)
    if chap_m:
        if curr_v and len(curr_txt.strip()) > 15:
            ref = f"{current_book} {current_chapter}:{curr_v}"
            verses[ref] = curr_txt.strip()
            curr_v = None
            curr_txt = ""
        current_chapter = int(chap_m.group(1))
        continue

    vm = re.match(r"^(\d+)\s+([A-Za-z“\"'].*)", line)
    if vm:
        if curr_v and len(curr_txt.strip()) > 15:
            ref = f"{current_book} {current_chapter}:{curr_v}"
            verses[ref] = curr_txt.strip()
        curr_v = int(vm.group(1))
        curr_txt = vm.group(2)
    elif curr_v:
        curr_txt += " " + line

if curr_v and len(curr_txt.strip()) > 15:
    ref = f"{current_book} {current_chapter}:{curr_v}"
    verses[ref] = curr_txt.strip()

print("John 14:27 ->", verses.get("John 14:27"))
print("John 15:27 ->", verses.get("John 15:27"))
