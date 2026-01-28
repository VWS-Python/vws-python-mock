"""Generate placeholder VuMark images for the mock API."""

import io

from beartype import beartype
from PIL import Image, ImageDraw


@beartype
def generate_svg(instance_id: str) -> bytes:
    """Generate a placeholder SVG image for a VuMark instance.

    Args:
        instance_id: The VuMark instance ID.

    Returns:
        SVG image data as bytes.
    """
    svg_content = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" '
        'viewBox="0 0 200 200">'
        '<rect width="200" height="200" fill="white" stroke="black" '
        'stroke-width="2"/>'
        '<text x="100" y="90" text-anchor="middle" font-family="Arial" '
        'font-size="14">VuMark Mock</text>'
        '<text x="100" y="120" text-anchor="middle" font-family="monospace" '
        f'font-size="10">{instance_id}</text>'
        "</svg>"
    )
    return svg_content.encode("utf-8")


@beartype
def generate_png(instance_id: str) -> bytes:
    """Generate a placeholder PNG image for a VuMark instance.

    Args:
        instance_id: The VuMark instance ID.

    Returns:
        PNG image data as bytes.
    """
    # Create a simple 200x200 image
    img = Image.new("RGB", (200, 200), color="white")
    draw = ImageDraw.Draw(img)

    # Draw a border
    draw.rectangle([0, 0, 199, 199], outline="black", width=2)

    # Add text
    draw.text((100, 80), "VuMark Mock", fill="black", anchor="mm")
    draw.text((100, 110), instance_id[:20], fill="black", anchor="mm")

    # Save to bytes
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


@beartype
def generate_pdf(instance_id: str) -> bytes:
    """Generate a placeholder PDF document for a VuMark instance.

    This creates a minimal valid PDF with the instance ID.

    Args:
        instance_id: The VuMark instance ID.

    Returns:
        PDF document data as bytes.
    """
    # Create a minimal valid PDF
    # This is a simple PDF 1.4 document with one page and text
    pdf_content = f"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Contents 4 0 R
/Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length 100 >>
stream
BT
/F1 12 Tf
50 150 Td
(VuMark Mock) Tj
0 -20 Td
({instance_id}) Tj
ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000266 00000 n
0000000416 00000 n
trailer
<< /Size 6 /Root 1 0 R >>
startxref
496
%%EOF"""
    return pdf_content.encode("latin-1")
