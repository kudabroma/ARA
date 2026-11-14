import io
from typing import List

from app.schemas import Form8843Request

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas as pdf_canvas

    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


def _fallback_pdf(lines: List[str]) -> bytes:
    ops = ["BT", "/F1 10 Tf", "50 750 Td", "14 TL"]
    for line in lines:
        safe = line.encode("ascii", "replace").decode("ascii")
        safe = safe.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        ops.append(f"({safe}) Tj T*")
    ops.append("ET")
    stream = "\n".join(ops).encode("ascii")

    objs = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n",
        f"4 0 obj\n<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"\nendstream\nendobj\n",
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]
    buf = io.BytesIO()
    buf.write(b"%PDF-1.4\n")
    offsets = []
    for obj in objs:
        offsets.append(buf.tell())
        buf.write(obj)
    xref = buf.tell()
    buf.write(f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode("ascii"))
    for off in offsets:
        buf.write(f"{off:010d} 00000 n \n".encode("ascii"))
    buf.write(f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii"))
    return buf.getvalue()


def generate_form_8843_pdf(req: Form8843Request) -> bytes:
    if not HAS_REPORTLAB:
        return _fallback_pdf(
            [
                f"Form 8843 ({req.tax_year}) - Statement for Exempt Individuals",
                f"Name: {req.first_name} {req.last_name}",
                f"Home Address: {req.home_country_address}",
                f"US Address: {req.us_address}",
                f"1a. Visa & Entry Date: {req.visa_type} | {req.first_entry_date}",
                f"1b. Current Status: {req.current_nonimmigrant_status}",
                f"2. Citizenship: {req.country_of_citizenship}",
                f"3. Passport: {req.country_of_passport} ({req.passport_number})",
                f"4a. Days Present: {req.tax_year}={req.days_present_current_year}, {req.tax_year-1}={req.days_present_prior_year_1}, {req.tax_year-2}={req.days_present_prior_year_2}",
                f"4b. Excluded Days in {req.tax_year}: {req.days_excluded_current_year}",
                f"School/Program: {req.school_or_program_name}, {req.school_or_program_address}",
                f"DSO/Director: {req.director_or_dso_name}, {req.director_or_dso_phone}",
                "Signature: ___________________________________ Date: _______________",
                "Mail to: Department of the Treasury, IRS Center, Austin, TX 73301-0215",
            ]
        )

    buf = io.BytesIO()
    c = pdf_canvas.Canvas(buf, pagesize=letter)
    width, height = letter

    c.setStrokeColor(colors.black)
    c.setLineWidth(1.1)
    c.rect(36, height - 92, width - 72, 56)
    c.line(145, height - 92, 145, height - 36)
    c.line(width - 135, height - 92, width - 135, height - 36)

    c.setFont("Helvetica-Bold", 10.5)
    c.drawString(42, height - 55, "Form")
    c.setFont("Helvetica-Bold", 23)
    c.drawString(72, height - 55, "8843")
    c.setFont("Helvetica", 6.5)
    c.drawString(42, height - 66, "Department of the Treasury")
    c.drawString(42, height - 75, "Internal Revenue Service")

    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(width / 2 + 5, height - 52, "Statement for Exempt Individuals and")
    c.drawCentredString(width / 2 + 5, height - 65, "Individuals With a Medical Condition")
    c.setFont("Helvetica", 7.5)
    c.drawCentredString(width / 2 + 5, height - 78, "Go to www.irs.gov/Form8843 for instructions.")

    c.setFont("Helvetica", 7)
    c.drawString(width - 130, height - 50, "OMB No. 1545-0074")
    c.setFont("Helvetica-Bold", 16)
    c.drawString(width - 110, height - 74, str(req.tax_year))

    y = height - 110
    c.setFont("Helvetica", 8)
    c.drawString(36, y, f"For calendar year {req.tax_year}")

    y -= 8
    c.rect(36, y - 68, width - 72, 62)
    c.line(width - 180, y - 30, width - 180, y - 6)
    c.line(36, y - 30, width - 36, y - 30)
    c.line(width / 2, y - 68, width / 2, y - 30)

    c.setFont("Helvetica", 7)
    c.drawString(42, y - 14, "First name and initial")
    c.drawString(210, y - 14, "Last name")
    c.drawString(width - 175, y - 14, "U.S. taxpayer identification number (if any)")

    c.setFont("Helvetica-Bold", 10)
    c.drawString(42, y - 26, req.first_name)
    c.drawString(210, y - 26, req.last_name)
    c.setFont("Helvetica-Oblique", 8.5)
    c.drawString(width - 175, y - 26, "N/A (Standalone Form 8843)")

    c.setFont("Helvetica", 7)
    c.drawString(42, y - 40, "Address in country of residence")
    c.drawString(width / 2 + 6, y - 40, "Address in the United States")
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(42, y - 55, req.home_country_address[:52])
    c.drawString(width / 2 + 6, y - 55, req.us_address[:52])

    y -= 86
    c.setFillColor(colors.HexColor("#111827"))
    c.rect(36, y - 16, width - 72, 16, fill=1, stroke=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(42, y - 12, "Part I   General Information")
    c.setFillColor(colors.black)

    y -= 32
    rows_p1 = [
        ("1a", "Type of U.S. visa and date of first entry:", f"{req.visa_type} ({req.first_entry_date})"),
        ("1b", "Current nonimmigrant status:", req.current_nonimmigrant_status),
        ("2", "Country of citizenship:", req.country_of_citizenship),
        ("3a", "Country that issued passport:", req.country_of_passport),
        ("3b", "Passport number:", req.passport_number),
        ("4a", "Days present in the U.S.:", f"{req.tax_year}: {req.days_present_current_year} | {req.tax_year - 1}: {req.days_present_prior_year_1} | {req.tax_year - 2}: {req.days_present_prior_year_2}"),
        ("4b", f"Days in {req.tax_year} excluded for substantial presence test:", f"{req.days_excluded_current_year} days"),
    ]
    for num, label, val in rows_p1:
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(40, y, num)
        c.setFont("Helvetica", 8.5)
        c.drawString(62, y, label)
        c.setFont("Helvetica-Bold", 9)
        c.drawRightString(width - 42, y, val)
        c.setStrokeColor(colors.HexColor("#D1D5DB"))
        c.line(36, y - 5, width - 36, y - 5)
        y -= 20

    y -= 6
    c.setStrokeColor(colors.black)
    c.setFillColor(colors.HexColor("#111827"))
    c.rect(36, y - 16, width - 72, 16, fill=1, stroke=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(42, y - 12, "Part III Students (or Part II Teachers / Trainees)")
    c.setFillColor(colors.black)

    y -= 28
    rows_p3 = [
        ("9", "Academic institution (name, address, phone):", f"{req.school_or_program_name} — {req.school_or_program_address} — {req.school_or_program_phone}"),
        ("10", "Designated School Official / Director:", f"{req.director_or_dso_name} — {req.director_or_dso_Address} — {req.director_or_dso_phone}"),
        ("12", "Exempt as teacher/trainee/student for more than 5 calendar years?", "[ ] Yes   [X] No"),
        ("13", "Applied for lawful permanent resident status (Green Card)?", "[ ] Yes   [X] No"),
    ]
    for num, label, val in rows_p3:
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(40, y, num)
        c.setFont("Helvetica", 8)
        c.drawString(62, y, label)
        y -= 13
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(62, y, val[:98])
        c.setStrokeColor(colors.HexColor("#D1D5DB"))
        c.line(36, y - 4, width - 36, y - 4)
        y -= 17

    y -= 10
    c.setStrokeColor(colors.black)
    c.rect(36, y - 62, width - 72, 62)
    c.setFont("Helvetica", 7)
    c.drawString(42, y - 14, "Under penalties of perjury, I declare that I have examined this statement and it is true, correct, and complete.")
    c.setFont("Helvetica-Bold", 9)
    c.drawString(42, y - 46, "Your signature: ____________________________________________________")
    c.drawString(width - 210, y - 46, "Date: ________________________")

    y -= 80
    c.setFillColor(colors.HexColor("#F3F4F6"))
    c.rect(36, y - 38, width - 72, 38, fill=1, stroke=1)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(44, y - 14, "FILING INSTRUCTIONS:")
    c.setFont("Helvetica", 7.5)
    c.drawString(44, y - 26, "If filing standalone (no 1040-NR), print, sign in ink, and mail to: Department of the Treasury, IRS Center, Austin, TX 73301-0215.")

    c.showPage()
    c.save()
    return buf.getvalue()
