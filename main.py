import io
import os
import time
import uuid
import zipfile
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageDraw, ImageFont

try:
    from app.extractor import DocumentImageExtractor, optimize_thumbnail
    from app.pdf_builder import PDFPrintBuilder
except ImportError:
    from extractor import DocumentImageExtractor, optimize_thumbnail
    from pdf_builder import PDFPrintBuilder

app = FastAPI(title="Document Image Extractor & Printout Layout", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SESSION_STORE: Dict[str, Dict[str, Any]] = {}
SESSION_EXPIRY_SECONDS = 3600 * 2  # 2 hours

def cleanup_old_sessions():
    now = time.time()
    expired = [sid for sid, sdata in SESSION_STORE.items() if now - sdata.get("created_at", 0) > SESSION_EXPIRY_SECONDS]
    for sid in expired:
        SESSION_STORE.pop(sid, None)

extractor = DocumentImageExtractor(min_dimension=40)

class PrintConfig(BaseModel):
    session_id: str
    image_ids: List[str]
    rotations: Optional[Dict[str, int]] = {}
    images_per_page: int = 9
    paper_size: str = "a4"
    orientation: str = "portrait"
    margin: str = "standard"
    gap: str = "standard"
    fit_mode: str = "contain"
    show_cut_lines: bool = False
    show_labels: bool = False
    show_page_numbers: bool = True

MARGIN_MAP = {
    "none": 0.0,
    "compact": 14.17,
    "standard": 28.35,
    "spacious": 42.52
}

GAP_MAP = {
    "none": 0.0,
    "compact": 6.0,
    "standard": 12.0,
    "spacious": 18.0
}

@app.post("/api/upload")
async def upload_document(files: List[UploadFile] = File(...)):
    cleanup_old_sessions()
    session_id = str(uuid.uuid4())
    all_extracted = []
    
    for file in files:
        contents = await file.read()
        try:
            items = extractor.extract_from_file(file.filename, contents)
            all_extracted.extend(items)
        except Exception as e:
            print(f"Error processing file {file.filename}: {e}")
            
    if not all_extracted:
        return {
            "status": "error",
            "message": "No images found in the uploaded file(s). Ensure the document contains images or pages.",
            "session_id": session_id,
            "images": []
        }
        
    SESSION_STORE[session_id] = {
        "created_at": time.time(),
        "images": {item["id"]: item for item in all_extracted}
    }
    
    client_images = []
    for item in all_extracted:
        client_images.append({
            "id": item["id"],
            "name": item["name"],
            "page": item["page"],
            "width": item["width"],
            "height": item["height"],
            "aspect_ratio": item["aspect_ratio"],
            "format": item["format"],
            "thumbnail": item["thumbnail"],
            "rotation": item.get("rotation", 0)
        })
        
    return {
        "status": "success",
        "session_id": session_id,
        "total_count": len(client_images),
        "images": client_images
    }

@app.get("/api/image/{session_id}/{img_id}")
async def get_image(session_id: str, img_id: str):
    session = SESSION_STORE.get(session_id)
    if not session or img_id not in session["images"]:
        raise HTTPException(status_code=404, detail="Image or session not found")
        
    img_data = session["images"][img_id]
    fmt = img_data.get("format", "JPEG").lower()
    media_type = f"image/{fmt}" if fmt in ["jpeg", "png", "webp", "gif"] else "image/jpeg"
    
    return Response(content=img_data["bytes"], media_type=media_type)

@app.post("/api/generate-pdf")
async def generate_printable_pdf(config: PrintConfig):
    session = SESSION_STORE.get(config.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session expired or not found. Please re-upload your document.")
        
    ordered_images = []
    for img_id in config.image_ids:
        if img_id in session["images"]:
            item = dict(session["images"][img_id])
            rot = config.rotations.get(img_id, 0)
            item["rotation"] = rot
            ordered_images.append(item)
            
    if not ordered_images:
        raise HTTPException(status_code=400, detail="No valid images selected for printing.")
        
    margin_pt = MARGIN_MAP.get(config.margin, MARGIN_MAP["standard"])
    gap_pt = GAP_MAP.get(config.gap, GAP_MAP["standard"])
    
    pdf_bytes = PDFPrintBuilder.build_printable_pdf(
        images=ordered_images,
        images_per_page=config.images_per_page,
        paper_size=config.paper_size,
        orientation=config.orientation,
        margin_pt=margin_pt,
        gap_pt=gap_pt,
        fit_mode=config.fit_mode,
        show_cut_lines=config.show_cut_lines,
        show_labels=config.show_labels,
        show_page_numbers=config.show_page_numbers
    )
    
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="printable_photos_grid.pdf"'}
    )

@app.post("/api/download-zip")
async def download_images_zip(config: PrintConfig):
    session = SESSION_STORE.get(config.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session expired")
        
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for idx, img_id in enumerate(config.image_ids):
            if img_id in session["images"]:
                item = session["images"][img_id]
                raw_bytes = item["bytes"]
                rot = config.rotations.get(img_id, 0) % 360
                
                if rot != 0:
                    pil_img = Image.open(io.BytesIO(raw_bytes))
                    pil_img = pil_img.rotate(-rot, expand=True)
                    buf = io.BytesIO()
                    pil_img.save(buf, format="JPEG", quality=95)
                    raw_bytes = buf.getvalue()
                    
                fname = f"extracted_image_{idx+1:03d}_{item['name']}"
                zf.writestr(fname, raw_bytes)
                
    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="extracted_images.zip"'}
    )

@app.post("/api/generate-sample")
async def generate_sample_doc():
    cleanup_old_sessions()
    session_id = str(uuid.uuid4())
    
    sample_images = []
    colors = [
        ("#3b82f6", "#1d4ed8", "Landscape Mountain View"),
        ("#ec4899", "#be185d", "City Sunset Horizon"),
        ("#10b981", "#047857", "Tropical Forest Nature"),
        ("#f59e0b", "#b45309", "Golden Desert Dunes"),
        ("#8b5cf6", "#6d28d9", "Space Nebula Stars"),
        ("#06b6d4", "#0e7490", "Ocean Coral Reef"),
        ("#f43f5e", "#be123c", "Autumn Red Maple"),
        ("#84cc16", "#4d7c0f", "Spring Blossom Flora"),
        ("#6366f1", "#4338ca", "Architecture Geometry"),
    ]
    
    for idx, (c1, c2, title) in enumerate(colors):
        img = Image.new("RGB", (600, 450), color=c1)
        draw = ImageDraw.Draw(img)
        for y in range(450):
            r_ratio = y / 450.0
            draw.line([(0, y), (600, y)], fill=(int(40 + r_ratio*60), int(50 + r_ratio*80), int(120 + r_ratio*100)))
            
        draw.rectangle([(20, 20), (580, 430)], outline="white", width=3)
        draw.rectangle([(40, 40), (560, 350)], fill=c2)
        
        draw.text((60, 60), f"PHOTO #{idx+1}", fill="white")
        draw.text((60, 100), title, fill="yellow")
        draw.text((60, 380), f"600x450 | Auto-extracted", fill="white")
        
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        img_bytes = buf.getvalue()
        
        item_id = str(uuid.uuid4())
        thumb = optimize_thumbnail(img)
        
        sample_images.append({
            "id": item_id,
            "name": f"Sample_Photo_{idx+1}.jpg",
            "page": (idx // 3) + 1,
            "width": 600,
            "height": 450,
            "aspect_ratio": 1.33,
            "format": "JPEG",
            "bytes": img_bytes,
            "thumbnail": thumb,
            "hash": str(idx),
            "rotation": 0
        })
        
    SESSION_STORE[session_id] = {
        "created_at": time.time(),
        "images": {item["id"]: item for item in sample_images}
    }
    
    client_images = [{
        "id": item["id"],
        "name": item["name"],
        "page": item["page"],
        "width": item["width"],
        "height": item["height"],
        "aspect_ratio": item["aspect_ratio"],
        "format": item["format"],
        "thumbnail": item["thumbnail"],
        "rotation": 0
    } for item in sample_images]
    
    return {
        "status": "success",
        "session_id": session_id,
        "total_count": len(client_images),
        "images": client_images
    }

# Check static location (works whether static is in ./static or ./app/static)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    static_dir = os.path.join(os.path.dirname(__file__), "app", "static")

if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>DocImagePrint API</h1>"
