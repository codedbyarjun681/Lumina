"""Conversation export — markdown and PDF."""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

DEJAVU = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")


def to_markdown(name: str, messages: list) -> str:
    lines = [f"# {name}", "", "_Exported from Lumina_", ""]
    for m in messages:
        speaker = "**You**" if m.role == "user" else "**Lumina**"
        lines.append(f"{speaker}:")
        lines.append(m.content)
        lines.append("")
    return "\n".join(lines)


def to_pdf(name: str, messages: list) -> bytes:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    if DEJAVU.is_file():
        pdf.add_font("DejaVu", "", str(DEJAVU))
        font = "DejaVu"
        safe = lambda s: s  # noqa: E731
    else:
        font = "helvetica"
        safe = lambda s: s.encode("latin-1", "replace").decode("latin-1")  # noqa: E731

    # fpdf2's multi_cell defaults to new_x=RIGHT, which leaves the cursor at
    # the right margin and starves the next full-width cell — always reset.
    def cell(text: str, size: float, h: float) -> None:
        pdf.set_font(font, size=size)
        pdf.multi_cell(
            0, h, safe(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT
        )

    cell(name, 17, 9)
    cell("Exported from Lumina", 9, 5)
    pdf.ln(4)

    for m in messages:
        speaker = "You" if m.role == "user" else "Lumina"
        cell(speaker, 11, 7)
        cell(m.content, 10, 5.5)
        pdf.ln(3)

    return bytes(pdf.output())
