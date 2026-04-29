from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "THE_BRIDGE_CODE_WALKTHROUGH.md"
OUTPUT = ROOT / "THE_BRIDGE_Code_Walkthrough.pdf"


def make_styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="DocTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=28,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#111827"),
            spaceAfter=18,
        )
    )
    styles.add(
        ParagraphStyle(
            name="H2",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=20,
            textColor=colors.HexColor("#0f172a"),
            spaceBefore=12,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Body",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#334155"),
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BulletBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            leftIndent=14,
            firstLineIndent=-8,
            bulletIndent=0,
            textColor=colors.HexColor("#334155"),
            spaceAfter=4,
        )
    )
    return styles


def markdown_to_story(text: str):
    styles = make_styles()
    story = []
    first_heading = True

    for raw_line in text.splitlines():
        line = raw_line.strip()

        if not line:
            story.append(Spacer(1, 0.08 * inch))
            continue

        escaped = (
            line.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

        if line.startswith("# "):
            style_name = "DocTitle" if first_heading else "H2"
            story.append(Paragraph(escaped[2:], styles[style_name]))
            first_heading = False
            continue

        if line.startswith("## "):
            story.append(Paragraph(escaped[3:], styles["H2"]))
            continue

        if line.startswith("- "):
            story.append(Paragraph(escaped[2:], styles["BulletBody"], bulletText="•"))
            continue

        if line[:2].isdigit() and line[1:3] == ". ":
            story.append(Paragraph(escaped[3:], styles["BulletBody"], bulletText=f"{line[0]}."))  # simple ordered item support
            continue

        story.append(Paragraph(escaped, styles["Body"]))

    return story


def main():
    text = SOURCE.read_text(encoding="utf-8")
    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        rightMargin=0.7 * inch,
        leftMargin=0.7 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
        title="The Bridge Code Walkthrough",
        author="Cursor",
    )
    doc.build(markdown_to_story(text))
    print(f"Created {OUTPUT}")


if __name__ == "__main__":
    main()
