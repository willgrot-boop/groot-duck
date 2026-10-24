"""Package existing illustrations with vector diagrams; does not edit images."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A3, landscape
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/build-guide"


def image_page(stem):
    image = OUT / f"{stem}.png"
    destination = OUT / f"{stem}.pdf"
    with Image.open(image) as picture:
        width, height = picture.size
    page_width, page_height = landscape(A3)
    margin = 16
    scale = min((page_width - 2 * margin) / width, (page_height - 2 * margin) / height)
    draw_width, draw_height = width * scale, height * scale
    pdf = canvas.Canvas(str(destination), pagesize=(page_width, page_height))
    pdf.setTitle(stem.replace("-", " "))
    pdf.drawImage(str(image), (page_width - draw_width) / 2,
                  (page_height - draw_height) / 2, draw_width, draw_height)
    pdf.showPage()
    pdf.save()
    return destination


def main():
    pages = [image_page("01-component-placement"), image_page("02-mechanical-dry-fit"),
             OUT / "03-logic-wiring.pdf", OUT / "04-servo-power-and-channels.pdf"]
    combined = OUT / "microduck-build-guide.pdf"
    writer = PdfWriter()
    for path in pages:
        reader = PdfReader(path)
        assert len(reader.pages) == 1, f"Expected a single sheet: {path}"
        writer.add_page(reader.pages[0])
    writer.add_metadata({"/Title": "DIY Microduck — illustrated prototype build guide"})
    with combined.open("wb") as stream:
        writer.write(stream)
    assert len(PdfReader(combined).pages) == 4
    target = OUT / "microduck-build-images.zip"
    files = sorted(p for p in OUT.iterdir() if p.suffix in {".png", ".pdf", ".svg", ".md"})
    with ZipFile(target, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
        for path in files:
            archive.write(path, f"microduck-build-guide/{path.name}")
    with ZipFile(target) as archive:
        assert archive.testzip() is None
    print(f"Created {combined.name}: four pages")
    print(f"Created {target.name}: {len(files)} files, {target.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
