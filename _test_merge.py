from pathlib import Path
from pypdf import PdfReader, PdfWriter
import fitz

work = Path("out/.pdfstudio")
out = work / "test-merge-pypdf.pdf"
w = PdfWriter()
for f in [work / "cover.pdf", work / "body.pdf"]:
    for p in PdfReader(str(f)).pages:
        w.add_page(p)
with open(out, "wb") as fh:
    w.write(fh)

d = fitz.open(out)
cat = d.pdf_catalog()
print("pypdf merge:", d.page_count, "struct", d.xref_get_key(cat, "StructTreeRoot"), "lang", d.xref_get_key(cat, "Lang"))

d.set_metadata({"title": "Test", "author": "Test"})
d.xref_set_key(cat, "Lang", "(en-GB)")
d.xref_set_key(cat, "PageMode", "/UseOutlines")
d.save(work / "test-merge-stamped.pdf", garbage=3, deflate=True)
d.close()

d2 = fitz.open(work / "test-merge-stamped.pdf")
c2 = d2.pdf_catalog()
print("after fitz save:", d2.metadata.get("title"), "struct", d2.xref_get_key(c2, "StructTreeRoot"), "lang", d2.xref_get_key(c2, "Lang"))
