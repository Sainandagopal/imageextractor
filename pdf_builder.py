import io
import math
from typing import List, Dict, Any, Tuple
from PIL import Image
import pymupdf as fitz

PAPER_SIZES = {
    "a4": (595.28, 841.89),       # 210 x 297 mm
    "letter": (612.0, 792.0),     # 8.5 x 11 in
    "legal": (612.0, 1008.0),     # 8.5 x 14 in
    "a3": (841.89, 1190.55),
    "a5": (419.53, 595.28),
}

GRID_PRESETS = {
    1: (1, 1),
    2: (2, 1),  # 2 rows, 1 col (or 1x2 in landscape)
    3: (3, 1),  # 3 rows, 1 col
    4: (2, 2),  # 2x2
    6: (3, 2),  # 3 rows, 2 cols
    8: (4, 2),  # 4 rows, 2 cols
    9: (3, 3),  # 3 rows, 3 cols (Max 9 per page)
}

def get_grid_dimensions(count_per_page: int, orientation: str) -> Tuple[int, int]:
    count_per_page = max(1, min(9, count_per_page))
    if count_per_page in GRID_PRESETS:
        rows, cols = GRID_PRESETS[count_per_page]
    else:
        cols = math.ceil(math.sqrt(count_per_page))
        rows = math.ceil(count_per_page / cols)
        
    if orientation == "landscape" and rows > cols:
        rows, cols = cols, rows
        
    return rows, cols

class PDFPrintBuilder:
    @staticmethod
    def build_printable_pdf(
        images: List[Dict[str, Any]],
        images_per_page: int = 9,
        paper_size: str = "a4",
        orientation: str = "portrait",
        margin_pt: float = 24.0,  # ~8.5 mm
        gap_pt: float = 12.0,     # ~4.2 mm
        fit_mode: str = "contain", # "contain" or "cover"
        show_cut_lines: bool = False,
        show_labels: bool = False,
        show_page_numbers: bool = True
    ) -> bytes:
        images_per_page = max(1, min(9, int(images_per_page)))
        base_size = PAPER_SIZES.get(paper_size.lower(), PAPER_SIZES["a4"])
        
        if orientation == "landscape":
            page_w, page_h = max(base_size), min(base_size)
        else:
            page_w, page_h = min(base_size), max(base_size)
            
        rows, cols = get_grid_dimensions(images_per_page, orientation)
        
        printable_w = page_w - (2 * margin_pt)
        printable_h = page_h - (2 * margin_pt)
        
        cell_w = (printable_w - ((cols - 1) * gap_pt)) / cols
        cell_h = (printable_h - ((rows - 1) * gap_pt)) / rows
        
        doc = fitz.open()
        total_images = len(images)
        total_pages = math.ceil(total_images / images_per_page) if total_images > 0 else 1
        
        for p_idx in range(total_pages):
            page = doc.new_page(width=page_w, height=page_h)
            start_idx = p_idx * images_per_page
            page_images = images[start_idx : start_idx + images_per_page]
            
            for idx, img_data in enumerate(page_images):
                r = idx // cols
                c = idx % cols
                
                cell_x0 = margin_pt + c * (cell_w + gap_pt)
                cell_y0 = margin_pt + r * (cell_h + gap_pt)
                cell_x1 = cell_x0 + cell_w
                cell_y1 = cell_y0 + cell_h
                
                if show_cut_lines:
                    shape = page.new_shape()
                    shape.draw_rect(fitz.Rect(cell_x0, cell_y0, cell_x1, cell_y1))
                    shape.finish(color=(0.75, 0.75, 0.75), width=0.5, dashes="[2 2] 0")
                    shape.commit()
                
                raw_bytes = img_data.get("bytes", b"")
                rotation = img_data.get("rotation", 0) % 360
                
                if rotation != 0:
                    pil_img = Image.open(io.BytesIO(raw_bytes))
                    pil_img = pil_img.rotate(-rotation, expand=True)
                    buf = io.BytesIO()
                    img_fmt = "PNG" if pil_img.mode == "RGBA" else "JPEG"
                    pil_img.save(buf, format=img_fmt, quality=95)
                    raw_bytes = buf.getvalue()
                    img_w, img_h = pil_img.size
                else:
                    img_w = img_data.get("width", cell_w)
                    img_h = img_data.get("height", cell_h)
                
                padding = 2.0
                target_cell_w = cell_w - (2 * padding)
                target_cell_h = cell_h - (2 * padding)
                
                if fit_mode == "contain":
                    aspect = img_w / img_h if img_h else 1.0
                    cell_aspect = target_cell_w / target_cell_h if target_cell_h else 1.0
                    
                    if aspect > cell_aspect:
                        draw_w = target_cell_w
                        draw_h = target_cell_w / aspect
                    else:
                        draw_h = target_cell_h
                        draw_w = target_cell_h * aspect
                        
                    offset_x = (target_cell_w - draw_w) / 2.0
                    offset_y = (target_cell_h - draw_h) / 2.0
                    
                    img_rect = fitz.Rect(
                        cell_x0 + padding + offset_x,
                        cell_y0 + padding + offset_y,
                        cell_x0 + padding + offset_x + draw_w,
                        cell_y0 + padding + offset_y + draw_h
                    )
                else:
                    img_rect = fitz.Rect(
                        cell_x0 + padding,
                        cell_y0 + padding,
                        cell_x1 - padding,
                        cell_y1 - padding
                    )
                    
                try:
                    page.insert_image(img_rect, stream=raw_bytes, keep_proportion=True)
                except Exception as e:
                    print(f"Error inserting image into PDF: {e}")
                    
                if show_labels:
                    label_text = f"#{start_idx + idx + 1}"
                    page.insert_text(
                        (cell_x0 + 4, cell_y1 - 4),
                        label_text,
                        fontsize=8,
                        color=(0.4, 0.4, 0.4)
                    )
            
            if show_page_numbers:
                page_text = f"Page {p_idx + 1} of {total_pages} ({len(images)} photos total)"
                page.insert_text(
                    (page_w / 2 - 40, page_h - 10),
                    page_text,
                    fontsize=8,
                    color=(0.5, 0.5, 0.5)
                )
                
        pdf_bytes = doc.tobytes(garbage=3, deflate=True)
        doc.close()
        return pdf_bytes
