import io
import os
import uuid
import hashlib
import zipfile
from typing import List, Dict, Any, Optional
from PIL import Image
import pymupdf as fitz

def get_image_hash(image_bytes: bytes) -> str:
    return hashlib.md5(image_bytes).hexdigest()

def optimize_thumbnail(img: Image.Image, max_dim: int = 400) -> str:
    """Create a lightweight base64 thumbnail for frontend preview."""
    import base64
    thumb = img.copy()
    thumb.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
    if thumb.mode in ("RGBA", "P"):
        thumb = thumb.convert("RGB")
    buf = io.BytesIO()
    thumb.save(buf, format="JPEG", quality=80)
    return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode('utf-8')}"

class DocumentImageExtractor:
    def __init__(self, min_dimension: int = 50):
        self.min_dimension = min_dimension

    def extract_from_file(self, filename: str, file_bytes: bytes) -> List[Dict[str, Any]]:
        ext = os.path.splitext(filename)[1].lower()
        if ext == ".pdf":
            return self.extract_from_pdf(file_bytes)
        elif ext == ".docx":
            return self.extract_from_docx(file_bytes)
        elif ext == ".pptx":
            return self.extract_from_pptx(file_bytes)
        elif ext in [".zip"]:
            return self.extract_from_zip(file_bytes)
        elif ext in [".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tiff"]:
            return self.extract_single_image(filename, file_bytes)
        else:
            try:
                return self.extract_from_pdf(file_bytes)
            except Exception:
                raise ValueError(f"Unsupported file format: {ext}")

    def extract_single_image(self, filename: str, file_bytes: bytes) -> List[Dict[str, Any]]:
        try:
            img = Image.open(io.BytesIO(file_bytes))
            width, height = img.size
            if width < self.min_dimension or height < self.min_dimension:
                return []
            
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGB")
            
            thumb_b64 = optimize_thumbnail(img)
            img_id = str(uuid.uuid4())
            
            return [{
                "id": img_id,
                "name": filename,
                "page": 1,
                "width": width,
                "height": height,
                "aspect_ratio": round(width / height, 2) if height else 1.0,
                "format": img.format or "JPEG",
                "bytes": file_bytes,
                "thumbnail": thumb_b64,
                "hash": get_image_hash(file_bytes),
                "rotation": 0
            }]
        except Exception as e:
            print(f"Error reading image: {e}")
            return []

    def extract_from_pdf(self, file_bytes: bytes) -> List[Dict[str, Any]]:
        extracted = []
        seen_hashes = set()
        
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        total_pages = len(doc)
        
        for page_idx in range(total_pages):
            page = doc[page_idx]
            page_num = page_idx + 1
            image_list = page.get_images(full=True)
            
            for img_info in image_list:
                xref = img_info[0]
                try:
                    base_image = doc.extract_image(xref)
                    if not base_image:
                        continue
                    
                    img_bytes = base_image["image"]
                    img_ext = base_image["ext"]
                    width = base_image["width"]
                    height = base_image["height"]
                    
                    if width < self.min_dimension or height < self.min_dimension:
                        continue
                    
                    img_hash = get_image_hash(img_bytes)
                    
                    pil_img = Image.open(io.BytesIO(img_bytes))
                    if pil_img.mode in ("CMYK", "P"):
                        pil_img = pil_img.convert("RGB")
                        buf = io.BytesIO()
                        pil_img.save(buf, format="JPEG", quality=95)
                        img_bytes = buf.getvalue()
                        img_ext = "jpeg"
                    
                    thumb_b64 = optimize_thumbnail(pil_img)
                    img_id = str(uuid.uuid4())
                    
                    extracted.append({
                        "id": img_id,
                        "name": f"Page_{page_num}_img_{xref}.{img_ext}",
                        "page": page_num,
                        "width": width,
                        "height": height,
                        "aspect_ratio": round(width / height, 2) if height else 1.0,
                        "format": img_ext.upper(),
                        "bytes": img_bytes,
                        "thumbnail": thumb_b64,
                        "hash": img_hash,
                        "rotation": 0
                    })
                    seen_hashes.add(img_hash)
                except Exception as e:
                    print(f"Error extracting image xref {xref} from page {page_num}: {e}")
                    continue
        
        if not extracted and total_pages > 0:
            for page_idx in range(min(total_pages, 50)):
                page = doc[page_idx]
                page_num = page_idx + 1
                pix = page.get_pixmap(dpi=200)
                img_bytes = pix.tobytes("png")
                pil_img = Image.open(io.BytesIO(img_bytes))
                thumb_b64 = optimize_thumbnail(pil_img)
                img_id = str(uuid.uuid4())
                extracted.append({
                    "id": img_id,
                    "name": f"Page_{page_num}_full.png",
                    "page": page_num,
                    "width": pix.width,
                    "height": pix.height,
                    "aspect_ratio": round(pix.width / pix.height, 2) if pix.height else 1.0,
                    "format": "PNG",
                    "bytes": img_bytes,
                    "thumbnail": thumb_b64,
                    "hash": get_image_hash(img_bytes),
                    "rotation": 0
                })
                
        doc.close()
        return extracted

    def extract_from_docx(self, file_bytes: bytes) -> List[Dict[str, Any]]:
        extracted = []
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
                media_files = [f for f in z.namelist() if f.startswith("word/media/")]
                media_files.sort()
                
                for idx, media_name in enumerate(media_files):
                    try:
                        img_bytes = z.read(media_name)
                        pil_img = Image.open(io.BytesIO(img_bytes))
                        width, height = pil_img.size
                        
                        if width < self.min_dimension or height < self.min_dimension:
                            continue
                        
                        if pil_img.mode not in ("RGB", "RGBA"):
                            pil_img = pil_img.convert("RGB")
                            
                        thumb_b64 = optimize_thumbnail(pil_img)
                        base_name = os.path.basename(media_name)
                        img_id = str(uuid.uuid4())
                        
                        extracted.append({
                            "id": img_id,
                            "name": base_name,
                            "page": idx + 1,
                            "width": width,
                            "height": height,
                            "aspect_ratio": round(width / height, 2) if height else 1.0,
                            "format": (pil_img.format or "PNG").upper(),
                            "bytes": img_bytes,
                            "thumbnail": thumb_b64,
                            "hash": get_image_hash(img_bytes),
                            "rotation": 0
                        })
                    except Exception as e:
                        print(f"Error parsing docx media {media_name}: {e}")
        except Exception as e:
            print(f"Error opening DOCX: {e}")
        return extracted

    def extract_from_pptx(self, file_bytes: bytes) -> List[Dict[str, Any]]:
        extracted = []
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
                media_files = [f for f in z.namelist() if f.startswith("ppt/media/")]
                media_files.sort()
                
                for idx, media_name in enumerate(media_files):
                    try:
                        img_bytes = z.read(media_name)
                        pil_img = Image.open(io.BytesIO(img_bytes))
                        width, height = pil_img.size
                        
                        if width < self.min_dimension or height < self.min_dimension:
                            continue
                        
                        if pil_img.mode not in ("RGB", "RGBA"):
                            pil_img = pil_img.convert("RGB")
                            
                        thumb_b64 = optimize_thumbnail(pil_img)
                        base_name = os.path.basename(media_name)
                        img_id = str(uuid.uuid4())
                        
                        extracted.append({
                            "id": img_id,
                            "name": base_name,
                            "page": idx + 1,
                            "width": width,
                            "height": height,
                            "aspect_ratio": round(width / height, 2) if height else 1.0,
                            "format": (pil_img.format or "PNG").upper(),
                            "bytes": img_bytes,
                            "thumbnail": thumb_b64,
                            "hash": get_image_hash(img_bytes),
                            "rotation": 0
                        })
                    except Exception as e:
                        print(f"Error parsing pptx media {media_name}: {e}")
        except Exception as e:
            print(f"Error opening PPTX: {e}")
        return extracted

    def extract_from_zip(self, file_bytes: bytes) -> List[Dict[str, Any]]:
        extracted = []
        try:
            with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
                for file_info in z.infolist():
                    if file_info.is_dir():
                        continue
                    fname = file_info.filename
                    ext = os.path.splitext(fname)[1].lower()
                    if ext in [".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tiff"]:
                        b = z.read(fname)
                        extracted.extend(self.extract_single_image(os.path.basename(fname), b))
                    elif ext in [".pdf", ".docx", ".pptx"]:
                        b = z.read(fname)
                        extracted.extend(self.extract_from_file(fname, b))
        except Exception as e:
            print(f"Error opening ZIP: {e}")
        return extracted
