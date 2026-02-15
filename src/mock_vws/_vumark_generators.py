"""Generate placeholder VuMark images for the mock API."""

import io
from xml.sax.saxutils import escape

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
    escaped_id = escape(data=instance_id)
    svg_content = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" '
        'viewBox="0 0 200 200">'
        '<rect width="200" height="200" fill="white" stroke="black" '
        'stroke-width="2"/>'
        '<text x="100" y="90" text-anchor="middle" font-family="Arial" '
        'font-size="14">VuMark Mock</text>'
        '<text x="100" y="120" text-anchor="middle" font-family="monospace" '
        f'font-size="10">{escaped_id}</text>'
        "</svg>"
    )
    return svg_content.encode()


@beartype
def generate_png(instance_id: str) -> bytes:
    """Generate a placeholder PNG image for a VuMark instance.

    Args:
        instance_id: The VuMark instance ID.

    Returns:
        PNG image data as bytes.
    """
    img = Image.new(mode="RGB", size=(200, 200), color=(255, 255, 255))
    draw = ImageDraw.Draw(im=img)

    draw.rectangle(xy=[0, 0, 199, 199], outline="black")
    draw.text(xy=(100, 80), text="VuMark Mock", fill="black")
    draw.text(xy=(100, 110), text=instance_id[:20], fill="black")

    buffer = io.BytesIO()
    img.save(fp=buffer, format="PNG")
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
    # Escape parentheses in instance_id for PDF string literals.
    safe_id = instance_id.replace("\\", "\\\\")
    safe_id = safe_id.replace("(", "\\(")
    safe_id = safe_id.replace(")", "\\)")

    # Build the stream content first so we can measure its length.
    stream = (
        "BT\n"
        "/F1 12 Tf\n"
        "50 150 Td\n"
        "(VuMark Mock) Tj\n"
        "0 -20 Td\n"
        f"({safe_id}) Tj\n"
        "ET\n"
    )
    stream_bytes = stream.encode()
    stream_length = len(stream_bytes)

    # Build each object, tracking byte offsets for the xref table.
    obj1 = "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    obj2 = "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    obj3 = (
        "3 0 obj\n"
        "<< /Type /Page /Parent 2 0 R"
        " /MediaBox [0 0 200 200]"
        " /Contents 4 0 R"
        " /Resources << /Font << /F1 5 0 R >> >> >>\n"
        "endobj\n"
    )
    obj4 = (
        f"4 0 obj\n<< /Length {stream_length} >>\n"
        f"stream\n{stream}endstream\nendobj\n"
    )
    obj5 = (
        "5 0 obj\n"
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\n"
        "endobj\n"
    )

    header = "%PDF-1.4\n"
    offsets: list[int] = []
    body = header
    for obj in (obj1, obj2, obj3, obj4, obj5):
        offsets.append(len(body.encode()))
        body += obj

    xref_offset = len(body.encode())
    xref = f"xref\n0 {len(offsets) + 1}\n0000000000 65535 f \n"
    for offset in offsets:
        xref += f"{offset:010d} 00000 n \n"

    trailer = (
        "trailer\n"
        f"<< /Size {len(offsets) + 1} /Root 1 0 R >>\n"
        "startxref\n"
        f"{xref_offset}\n"
        "%%EOF"
    )

    return (body + xref + trailer).encode()
