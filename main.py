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
    from extractor import DocumentImageExtractor, optimize_thumbnail
    from pdf_builder import PDFPrintBuilder
except ImportError:
    from app.extractor import DocumentImageExtractor, optimize_thumbnail
    from app.pdf_builder import PDFPrintBuilder

app = FastAPI(title="DocImagePrint", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SESSION_STORE: Dict[str, Dict[str, Any]] = {}
SESSION_EXPIRY_SECONDS = 3600 * 2

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

STANDALONE_HTML = """﻿<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>DocImagePrint - Document Image Extractor & Print Layout Generator</title>
  <!-- Tailwind CSS CDN -->
  <script src="https://cdn.tailwindcss.com"></script>
  <!-- Phosphor Icons -->
  <script src="https://unpkg.com/@phosphor-icons/web"></script>
  <!-- Custom CSS -->
  <style>
﻿/* Professional Red Theme & Clean Print Styles */

:root {
  --primary: #dc2626;
  --primary-hover: #b91c1c;
  --primary-light: #fef2f2;
  --primary-border: #fecaca;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* Drag Over Animation */
.drag-over {
  border-color: #dc2626 !important;
  background-color: #fef2f2 !important;
  transform: scale(1.005);
}

/* Live Sheet Preview Viewport */
.sheet-preview-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2rem;
  background: #f8fafc;
  padding: 2rem;
  border-radius: 1rem;
  border: 1px solid #e2e8f0;
  max-height: 85vh;
  overflow-y: auto;
}

/* Paper Sheet Simulation */
.paper-sheet {
  background: #ffffff;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 10px 15px -3px rgba(0, 0, 0, 0.08);
  border: 1px solid #e2e8f0;
  position: relative;
  box-sizing: border-box;
  transition: transform 0.2s ease;
}

/* Paper Standard Dimensions */
.paper-a4-portrait {
  width: 595px;
  height: 842px;
}
.paper-a4-landscape {
  width: 842px;
  height: 595px;
}

.paper-letter-portrait {
  width: 612px;
  height: 792px;
}
.paper-letter-landscape {
  width: 792px;
  height: 612px;
}

/* Print Cell */
.print-cell {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  box-sizing: border-box;
  background: transparent;
}

.print-cell.cut-lines {
  border: 1px dashed #cbd5e1;
}

.print-cell img {
  max-width: 100%;
  max-height: 100%;
  transition: transform 0.15s ease;
}

.print-cell.fit-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.print-cell.fit-contain img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

/* Gallery Cards */
.gallery-card {
  cursor: grab;
  transition: all 0.15s ease;
}

.gallery-card:hover {
  transform: translateY(-1px);
}

.gallery-card:active {
  cursor: grabbing;
}

.gallery-card.dragging {
  opacity: 0.35;
  transform: scale(0.96);
}

/* Custom Scrollbar for Smooth UX */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-track {
  background: #f1f5f9;
}

::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 9999px;
}

::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}

/* Print Specific Rules */
@media print {
  body * {
    visibility: hidden;
  }
  
  #print-render-zone,
  #print-render-zone * {
    visibility: visible;
  }
  
  #print-render-zone {
    position: absolute;
    left: 0;
    top: 0;
    width: 100%;
    margin: 0;
    padding: 0;
    background: transparent;
  }
  
  .print-page-break {
    page-break-after: always;
    break-after: page;
    box-shadow: none !important;
    border: none !important;
    margin: 0 !important;
    padding: 0 !important;
    width: 100% !important;
    height: 100vh !important;
  }
}

</style>
  <script>
    tailwind.config = {
      theme: {
        extend: {
          colors: {
            brand: {
              50: '#fef2f2',
              100: '#fee2e2',
              200: '#fecaca',
              500: '#ef4444',
              600: '#dc2626',
              700: '#b91c1c',
              800: '#991b1b',
              900: '#7f1d1d',
            }
          }
        }
      }
    }
  </script>
</head>
<body class="bg-slate-50/70 text-slate-800 min-h-screen flex flex-col antialiased">

  <!-- Clean Top Navigation Bar -->
  <header class="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-sm">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
      <div class="flex items-center space-x-3">
        <div class="w-9 h-9 rounded-xl bg-gradient-to-tr from-brand-600 to-rose-500 flex items-center justify-center text-white shadow-md shadow-brand-100">
          <i class="ph-bold ph-printer text-xl"></i>
        </div>
        <div class="flex items-center gap-2">
          <span class="text-xl font-extrabold tracking-tight bg-gradient-to-r from-brand-600 to-rose-600 bg-clip-text text-transparent">DocImagePrint</span>
          <span class="text-xs px-2 py-0.5 bg-brand-50 text-brand-700 font-semibold rounded-full border border-brand-200">Max 9 / Sheet</span>
        </div>
      </div>

      <div class="flex items-center space-x-3">
        <button id="btn-sample" class="text-xs font-semibold text-brand-700 hover:text-brand-800 bg-brand-50 hover:bg-brand-100 px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1.5 border border-brand-200 shadow-sm">
          <i class="ph-bold ph-sparkle text-amber-500 text-sm"></i>
          Try Sample Document
        </button>
      </div>
    </div>
  </header>

  <!-- Main Workspace Container -->
  <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex-1 w-full space-y-6">

    <!-- Upload Section -->
    <section id="upload-section" class="bg-white rounded-2xl p-8 border border-slate-200 shadow-sm text-center">
      <div class="max-w-2xl mx-auto">
        <div id="drop-zone" class="border-2 border-dashed border-slate-300 hover:border-brand-500 bg-slate-50/50 hover:bg-brand-50/30 rounded-2xl p-10 cursor-pointer transition-all duration-200">
          <input type="file" id="file-input" class="hidden" accept=".pdf,.docx,.pptx,.zip,.png,.jpg,.jpeg,.webp" multiple>
          
          <div class="w-14 h-14 mx-auto bg-brand-50 rounded-2xl flex items-center justify-center text-brand-600 mb-4 border border-brand-100 shadow-sm">
            <i class="ph-bold ph-cloud-arrow-up text-3xl"></i>
          </div>
          
          <h3 class="text-base font-bold text-slate-800 mb-1">Upload PDF or Document</h3>
          <p class="text-xs text-slate-500 mb-5">Drag & drop your file here, or click to browse</p>
          
          <div class="flex flex-wrap items-center justify-center gap-2 mb-5">
            <span class="inline-flex items-center gap-1 px-2.5 py-1 bg-red-50 text-red-700 rounded-md text-xs font-medium border border-red-200">
              <i class="ph-bold ph-file-pdf"></i> PDF
            </span>
            <span class="inline-flex items-center gap-1 px-2.5 py-1 bg-blue-50 text-blue-700 rounded-md text-xs font-medium border border-blue-200">
              <i class="ph-bold ph-file-doc"></i> Word (.docx)
            </span>
            <span class="inline-flex items-center gap-1 px-2.5 py-1 bg-orange-50 text-orange-700 rounded-md text-xs font-medium border border-orange-200">
              <i class="ph-bold ph-file-ppt"></i> PowerPoint (.pptx)
            </span>
            <span class="inline-flex items-center gap-1 px-2.5 py-1 bg-emerald-50 text-emerald-700 rounded-md text-xs font-medium border border-emerald-200">
              <i class="ph-bold ph-image"></i> Images / ZIP
            </span>
          </div>

          <button type="button" class="px-5 py-2.5 bg-brand-600 hover:bg-brand-700 text-white text-xs font-bold rounded-xl shadow-sm shadow-brand-200 transition-colors inline-flex items-center gap-2">
            <i class="ph-bold ph-folder-open text-sm"></i> Browse Files
          </button>
        </div>

        <!-- Extraction Loader -->
        <div id="loader" class="hidden mt-6 p-6 bg-slate-50 rounded-xl border border-slate-200 flex flex-col items-center justify-center">
          <div class="w-8 h-8 border-3 border-brand-200 border-t-brand-600 rounded-full animate-spin mb-3"></div>
          <p class="text-xs font-semibold text-slate-700" id="loader-status">Extracting images...</p>
          <p class="text-[11px] text-slate-400 mt-0.5">Preserving original photo quality</p>
        </div>
      </div>
    </section>

    <!-- Workspace (Revealed after document upload) -->
    <div id="workspace" class="hidden space-y-6">
      
      <!-- Status & Bulk Actions Bar -->
      <div class="bg-white rounded-xl px-5 py-3.5 border border-slate-200 shadow-sm flex flex-wrap items-center justify-between gap-3">
        <div class="flex items-center gap-3">
          <div class="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center border border-emerald-200 font-bold">
            <i class="ph-bold ph-check text-lg"></i>
          </div>
          <div>
            <h2 class="text-sm font-bold text-slate-800">
              <span id="extracted-count">0</span> Photos Extracted
            </h2>
            <p class="text-[11px] text-slate-500">
              Selected: <strong id="selected-count" class="text-brand-600">0</strong> &bull; Total sheets: <strong id="sheet-count" class="text-brand-600">0</strong>
            </p>
          </div>
        </div>

        <!-- Bulk Action Controls -->
        <div class="flex items-center flex-wrap gap-2">
          <button id="btn-select-all" class="text-xs font-medium px-2.5 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg transition-colors">
            Select All
          </button>
          <button id="btn-deselect-all" class="text-xs font-medium px-2.5 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg transition-colors">
            Deselect All
          </button>
          <button id="btn-filter-small" class="text-xs font-medium px-2.5 py-1.5 bg-amber-50 hover:bg-amber-100 text-amber-700 border border-amber-200 rounded-lg transition-colors" title="Hide small icons & bullets">
            <i class="ph-bold ph-funnel"></i> Remove Small Icons
          </button>
          <button id="btn-new-upload" class="text-xs font-semibold px-2.5 py-1.5 bg-brand-50 hover:bg-brand-100 text-brand-700 border border-brand-200 rounded-lg transition-colors flex items-center gap-1">
            <i class="ph-bold ph-plus"></i> Upload New
          </button>
        </div>
      </div>

      <!-- Main 2-Column Interface -->
      <div class="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        
        <!-- Left Column: Settings & Photos List (5 Cols) -->
        <div class="lg:col-span-5 space-y-6">

          <!-- Printout Layout Settings (Max 9 / sheet) -->
          <div class="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-5">
            <div class="flex items-center justify-between border-b border-slate-100 pb-3">
              <div class="flex items-center gap-2">
                <i class="ph-bold ph-sliders-horizontal text-lg text-brand-600"></i>
                <h3 class="text-sm font-bold text-slate-800">Print Layout Settings</h3>
              </div>
              <span class="text-[11px] bg-brand-50 text-brand-700 font-semibold px-2 py-0.5 rounded-full border border-brand-200">Max 9 / Paper</span>
            </div>

            <!-- Pictures Per Paper Selection -->
            <div>
              <label class="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-2">Pictures Per Sheet</label>
              <div class="grid grid-cols-3 gap-2">
                <!-- 9 Pictures (Primary default requirement) -->
                <button type="button" class="grid-btn border-2 border-brand-600 bg-brand-50/70 text-brand-900 rounded-xl p-2.5 text-center flex flex-col items-center justify-center transition-all shadow-sm" data-count="9">
                  <span class="text-xs font-extrabold flex items-center gap-1">
                    <i class="ph-bold ph-grid-nine text-brand-600 text-sm"></i> 9 Pictures
                  </span>
                  <span class="text-[10px] text-brand-700 font-medium">3 × 3 Grid</span>
                </button>

                <!-- 6 Pictures -->
                <button type="button" class="grid-btn border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 rounded-xl p-2.5 text-center flex flex-col items-center justify-center transition-all" data-count="6">
                  <span class="text-xs font-bold">6 Pictures</span>
                  <span class="text-[10px] text-slate-400">3 × 2 Grid</span>
                </button>

                <!-- 4 Pictures -->
                <button type="button" class="grid-btn border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 rounded-xl p-2.5 text-center flex flex-col items-center justify-center transition-all" data-count="4">
                  <span class="text-xs font-bold">4 Pictures</span>
                  <span class="text-[10px] text-slate-400">2 × 2 Grid</span>
                </button>

                <!-- 3 Pictures -->
                <button type="button" class="grid-btn border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 rounded-xl p-2.5 text-center flex flex-col items-center justify-center transition-all" data-count="3">
                  <span class="text-xs font-bold">3 Pictures</span>
                  <span class="text-[10px] text-slate-400">3 × 1 Grid</span>
                </button>

                <!-- 2 Pictures -->
                <button type="button" class="grid-btn border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 rounded-xl p-2.5 text-center flex flex-col items-center justify-center transition-all" data-count="2">
                  <span class="text-xs font-bold">2 Pictures</span>
                  <span class="text-[10px] text-slate-400">2 × 1 Grid</span>
                </button>

                <!-- 1 Picture -->
                <button type="button" class="grid-btn border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 rounded-xl p-2.5 text-center flex flex-col items-center justify-center transition-all" data-count="1">
                  <span class="text-xs font-bold">1 Picture</span>
                  <span class="text-[10px] text-slate-400">Full Page</span>
                </button>
              </div>
            </div>

            <!-- Paper Format & Orientation -->
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1">Paper Size</label>
                <select id="select-paper-size" class="w-full bg-slate-50 border border-slate-200 rounded-xl p-2 text-xs font-medium focus:ring-2 focus:ring-brand-500 focus:outline-none">
                  <option value="a4" selected>A4 (210 × 297 mm)</option>
                  <option value="letter">US Letter (8.5 × 11 in)</option>
                  <option value="legal">Legal (8.5 × 14 in)</option>
                  <option value="a3">A3 (297 × 420 mm)</option>
                  <option value="a5">A5 (148 × 210 mm)</option>
                </select>
              </div>

              <div>
                <label class="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1">Orientation</label>
                <select id="select-orientation" class="w-full bg-slate-50 border border-slate-200 rounded-xl p-2 text-xs font-medium focus:ring-2 focus:ring-brand-500 focus:outline-none">
                  <option value="portrait" selected>Portrait</option>
                  <option value="landscape">Landscape</option>
                </select>
              </div>
            </div>

            <!-- Margins & Gap -->
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1">Margins</label>
                <select id="select-margin" class="w-full bg-slate-50 border border-slate-200 rounded-xl p-2 text-xs font-medium focus:ring-2 focus:ring-brand-500 focus:outline-none">
                  <option value="standard" selected>Standard (10mm)</option>
                  <option value="compact">Compact (5mm)</option>
                  <option value="spacious">Spacious (15mm)</option>
                  <option value="none">None (0mm)</option>
                </select>
              </div>

              <div>
                <label class="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1">Picture Spacing</label>
                <select id="select-gap" class="w-full bg-slate-50 border border-slate-200 rounded-xl p-2 text-xs font-medium focus:ring-2 focus:ring-brand-500 focus:outline-none">
                  <option value="standard" selected>Standard (4mm)</option>
                  <option value="compact">Compact (2mm)</option>
                  <option value="spacious">Spacious (6mm)</option>
                  <option value="none">No Gap</option>
                </select>
              </div>
            </div>

            <!-- Fit Mode & Clean Toggles -->
            <div class="space-y-2.5 pt-2 border-t border-slate-100">
              <div class="flex items-center justify-between">
                <label class="text-xs font-medium text-slate-700 flex items-center gap-1.5">
                  <i class="ph-bold ph-aspect-ratio text-brand-600"></i> Photo Fitting
                </label>
                <select id="select-fit-mode" class="bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1 text-xs font-medium focus:ring-2 focus:ring-brand-500">
                  <option value="contain" selected>Fit (Keep full photo)</option>
                  <option value="cover">Fill (Crop to box)</option>
                </select>
              </div>

              <div class="flex items-center justify-between">
                <label for="toggle-page-numbers" class="text-xs font-medium text-slate-700 flex items-center gap-1.5 cursor-pointer">
                  <i class="ph-bold ph-hash text-slate-400"></i> Page Numbers Footer
                </label>
                <input type="checkbox" id="toggle-page-numbers" checked class="w-4 h-4 text-brand-600 rounded focus:ring-brand-500 cursor-pointer">
              </div>

              <div class="flex items-center justify-between">
                <label for="toggle-labels" class="text-xs font-medium text-slate-700 flex items-center gap-1.5 cursor-pointer">
                  <i class="ph-bold ph-tag text-slate-400"></i> Photo Number (#1, #2...)
                </label>
                <input type="checkbox" id="toggle-labels" class="w-4 h-4 text-brand-600 rounded focus:ring-brand-500 cursor-pointer">
              </div>

              <div class="flex items-center justify-between">
                <label for="toggle-cut-lines" class="text-xs font-medium text-slate-700 flex items-center gap-1.5 cursor-pointer">
                  <i class="ph-bold ph-scissors text-amber-500"></i> Cutting Guides
                </label>
                <input type="checkbox" id="toggle-cut-lines" class="w-4 h-4 text-brand-600 rounded focus:ring-brand-500 cursor-pointer">
              </div>
            </div>

            <!-- Action Export Buttons -->
            <div class="pt-3 border-t border-slate-100 space-y-2">
              <button id="btn-print-native" class="w-full py-3 bg-brand-600 hover:bg-brand-700 text-white font-bold rounded-xl shadow-md shadow-brand-200 flex items-center justify-center gap-2 transition-all transform active:scale-98 text-sm">
                <i class="ph-bold ph-printer text-lg"></i>
                Print Layout Now
              </button>

              <div class="grid grid-cols-2 gap-2">
                <button id="btn-download-pdf" class="py-2.5 bg-white hover:bg-slate-50 text-brand-700 border border-brand-200 font-semibold rounded-xl text-xs flex items-center justify-center gap-1.5 transition-colors shadow-sm">
                  <i class="ph-bold ph-file-pdf text-sm text-brand-600"></i>
                  Download PDF
                </button>
                <button id="btn-download-zip" class="py-2.5 bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 font-semibold rounded-xl text-xs flex items-center justify-center gap-1.5 transition-colors shadow-sm">
                  <i class="ph-bold ph-download-simple text-sm"></i>
                  Download ZIP
                </button>
              </div>
            </div>
          </div>

          <!-- Extracted Pictures Manager -->
          <div class="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-3">
            <div class="flex items-center justify-between border-b border-slate-100 pb-3">
              <div class="flex items-center gap-2">
                <i class="ph-bold ph-images text-lg text-brand-600"></i>
                <h3 class="text-sm font-bold text-slate-800">Extracted Photos</h3>
              </div>
              <span class="text-[11px] text-slate-400">Drag to reorder</span>
            </div>

            <!-- Gallery Cards Container -->
            <div id="gallery-container" class="grid grid-cols-2 sm:grid-cols-3 gap-2.5 max-h-96 overflow-y-auto p-1">
              <!-- Dynamically populated -->
            </div>
          </div>

        </div>

        <!-- Right Column: Live Printable Sheet Preview (7 Cols) -->
        <div class="lg:col-span-7 bg-white rounded-2xl p-6 border border-slate-200 shadow-sm space-y-4">
          <div class="flex items-center justify-between border-b border-slate-100 pb-3">
            <div class="flex items-center gap-2">
              <i class="ph-bold ph-eye text-lg text-brand-600"></i>
              <h3 class="text-sm font-bold text-slate-800">Live Printout Preview</h3>
            </div>
            <span id="preview-info-badge" class="bg-brand-50 text-brand-700 text-xs px-2.5 py-1 rounded-full font-semibold border border-brand-200">
              9 Photos per sheet
            </span>
          </div>

          <!-- Sheet Viewport -->
          <div id="sheet-preview-viewport" class="sheet-preview-container">
            <!-- Dynamically populated sheets -->
          </div>
        </div>

      </div>

    </div>

  </main>

  <!-- Print Render Container (Used by window.print()) -->
  <div id="print-render-zone" class="hidden"></div>

  <!-- Lightbox Modal -->
  <div id="lightbox-modal" class="fixed inset-0 z-50 bg-black/80 hidden items-center justify-center p-4">
    <div class="relative max-w-4xl max-h-[90vh] bg-white rounded-2xl overflow-hidden p-2 flex flex-col items-center shadow-2xl">
      <button id="btn-close-lightbox" class="absolute top-3 right-3 w-8 h-8 rounded-full bg-slate-900/60 text-white flex items-center justify-center hover:bg-slate-900 transition-colors">
        <i class="ph-bold ph-x text-base"></i>
      </button>
      <img id="lightbox-img" src="" alt="Full view" class="max-h-[80vh] max-w-full object-contain rounded-xl">
      <div id="lightbox-caption" class="text-xs text-slate-600 py-2 font-medium"></div>
    </div>
  </div>

  <!-- Minimalist Footer -->
  <footer class="bg-white border-t border-slate-200 py-4 mt-auto">
    <div class="max-w-7xl mx-auto px-4 text-center text-xs text-slate-400">
      DocImagePrint &bull; Professional Document Image Extractor & Printout Layout Engine
    </div>
  </footer>

  <script>
﻿// Document Image Extractor & Printout Layout Engine

// Application State
const state = {
  sessionId: null,
  images: [],
  imagesPerPage: 9, // Max 9 per page requirement
  paperSize: "a4",
  orientation: "portrait",
  margin: "standard",
  gap: "standard",
  fitMode: "contain",
  showCutLines: false,
  showLabels: false,
  showPageNumbers: true,
  draggedIdx: null
};

// DOM Elements
const dropZone = document.getElementById("drop-zone");
const fileInput = document.getElementById("file-input");
const loader = document.getElementById("loader");
const loaderStatus = document.getElementById("loader-status");
const workspace = document.getElementById("workspace");
const galleryContainer = document.getElementById("gallery-container");
const sheetPreviewViewport = document.getElementById("sheet-preview-viewport");
const printRenderZone = document.getElementById("print-render-zone");
const extractedCountEl = document.getElementById("extracted-count");
const selectedCountEl = document.getElementById("selected-count");
const sheetCountEl = document.getElementById("sheet-count");
const previewInfoBadge = document.getElementById("preview-info-badge");

// Initialize on DOM Ready
document.addEventListener("DOMContentLoaded", () => {
  setupUploadListeners();
  setupLayoutControls();
  setupExportButtons();
  setupLightbox();
});

// 1. Upload & Sample Handlers
function setupUploadListeners() {
  dropZone.addEventListener("click", () => fileInput.click());

  dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("drag-over");
  });

  dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("drag-over");
  });

  dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("drag-over");
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFiles(e.dataTransfer.files);
    }
  });

  fileInput.addEventListener("change", (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFiles(e.target.files);
    }
  });

  document.getElementById("btn-sample").addEventListener("click", loadSampleDocument);
  document.getElementById("btn-new-upload").addEventListener("click", () => {
    fileInput.value = "";
    fileInput.click();
  });
}

async function handleFiles(fileList) {
  const formData = new FormData();
  for (let i = 0; i < fileList.length; i++) {
    formData.append("files", fileList[i]);
  }

  showLoader("Extracting images from document(s)...");

  try {
    const res = await fetch("/api/upload", {
      method: "POST",
      body: formData
    });

    const data = await res.json();
    if (data.status === "success") {
      state.sessionId = data.session_id;
      state.images = data.images.map(img => ({ ...img, selected: true, rotation: 0 }));
      renderWorkspace();
    } else {
      alert(data.message || "Failed to extract images.");
    }
  } catch (err) {
    console.error(err);
    alert("Error uploading document. Please check console.");
  } finally {
    hideLoader();
  }
}

async function loadSampleDocument() {
  showLoader("Generating 9 sample photos...");
  try {
    const res = await fetch("/api/generate-sample", { method: "POST" });
    const data = await res.json();
    if (data.status === "success") {
      state.sessionId = data.session_id;
      state.images = data.images.map(img => ({ ...img, selected: true, rotation: 0 }));
      renderWorkspace();
    }
  } catch (err) {
    console.error(err);
    alert("Error loading sample.");
  } finally {
    hideLoader();
  }
}

function showLoader(msg) {
  loaderStatus.textContent = msg;
  loader.classList.remove("hidden");
}

function hideLoader() {
  loader.classList.add("hidden");
}

// 2. Workspace & Gallery Rendering
function renderWorkspace() {
  workspace.classList.remove("hidden");
  workspace.scrollIntoView({ behavior: "smooth" });
  renderGallery();
  renderSheetsPreview();
  updateCounts();
}

function updateCounts() {
  const total = state.images.length;
  const selected = state.images.filter(img => img.selected).length;
  const sheets = Math.ceil(selected / state.imagesPerPage) || 0;

  extractedCountEl.textContent = total;
  selectedCountEl.textContent = selected;
  sheetCountEl.textContent = sheets;
  previewInfoBadge.textContent = `${state.imagesPerPage} Photos per sheet (${sheets} ${sheets === 1 ? 'sheet' : 'sheets'})`;
}

function renderGallery() {
  galleryContainer.innerHTML = "";

  state.images.forEach((img, idx) => {
    const card = document.createElement("div");
    card.className = `gallery-card bg-slate-50/70 border ${img.selected ? 'border-brand-400 ring-2 ring-brand-100 bg-white' : 'border-slate-200 opacity-60'} rounded-xl p-2 flex flex-col space-y-1.5 relative transition-all`;
    card.draggable = true;
    card.dataset.index = idx;

    // Card Header
    const header = document.createElement("div");
    header.className = "flex items-center justify-between";

    const left = document.createElement("div");
    left.className = "flex items-center gap-1.5";
    const check = document.createElement("input");
    check.type = "checkbox";
    check.checked = img.selected;
    check.className = "w-3.5 h-3.5 text-brand-600 rounded cursor-pointer accent-red-600";
    check.addEventListener("change", (e) => {
      img.selected = e.target.checked;
      renderGallery();
      renderSheetsPreview();
      updateCounts();
    });

    const badge = document.createElement("span");
    badge.className = "text-[9px] font-semibold bg-slate-200/80 text-slate-600 px-1 py-0.5 rounded";
    badge.textContent = `P.${img.page || 1}`;

    left.appendChild(check);
    left.appendChild(badge);

    const delBtn = document.createElement("button");
    delBtn.className = "text-slate-400 hover:text-red-500 text-xs p-0.5 transition-colors";
    delBtn.title = "Delete photo";
    delBtn.innerHTML = '<i class="ph-bold ph-trash"></i>';
    delBtn.addEventListener("click", () => {
      state.images.splice(idx, 1);
      renderGallery();
      renderSheetsPreview();
      updateCounts();
    });

    header.appendChild(left);
    header.appendChild(delBtn);

    // Image Thumbnail Box
    const imgBox = document.createElement("div");
    imgBox.className = "w-full h-20 bg-slate-100 rounded-lg flex items-center justify-center overflow-hidden cursor-pointer relative border border-slate-100";
    
    const imageEl = document.createElement("img");
    imageEl.src = img.thumbnail;
    imageEl.alt = img.name;
    imageEl.className = "max-w-full max-h-full object-contain transition-transform duration-200";
    imageEl.style.transform = `rotate(${img.rotation || 0}deg)`;

    imgBox.appendChild(imageEl);
    imgBox.addEventListener("click", () => openLightbox(img));

    // Card Footer: Dimension & Rotate
    const footer = document.createElement("div");
    footer.className = "flex items-center justify-between pt-1 border-t border-slate-100";

    const dimText = document.createElement("span");
    dimText.className = "text-[9px] text-slate-400 font-mono";
    dimText.textContent = `${img.width}×${img.height}`;

    const rotBtn = document.createElement("button");
    rotBtn.className = "text-xs text-brand-600 hover:bg-brand-50 p-1 rounded transition-colors flex items-center";
    rotBtn.title = "Rotate 90°";
    rotBtn.innerHTML = '<i class="ph-bold ph-arrow-clockwise"></i>';
    rotBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      img.rotation = ((img.rotation || 0) + 90) % 360;
      imageEl.style.transform = `rotate(${img.rotation}deg)`;
      renderSheetsPreview();
    });

    footer.appendChild(dimText);
    footer.appendChild(rotBtn);

    card.appendChild(header);
    card.appendChild(imgBox);
    card.appendChild(footer);

    // Drag & Drop reorder
    card.addEventListener("dragstart", (e) => {
      state.draggedIdx = idx;
      card.classList.add("dragging");
      e.dataTransfer.effectAllowed = "move";
    });

    card.addEventListener("dragend", () => {
      card.classList.remove("dragging");
    });

    card.addEventListener("dragover", (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
    });

    card.addEventListener("drop", (e) => {
      e.preventDefault();
      if (state.draggedIdx !== null && state.draggedIdx !== idx) {
        const movedItem = state.images.splice(state.draggedIdx, 1)[0];
        state.images.splice(idx, 0, movedItem);
        state.draggedIdx = null;
        renderGallery();
        renderSheetsPreview();
      }
    });

    galleryContainer.appendChild(card);
  });
}

// 3. Layout Controls & Settings
function setupLayoutControls() {
  const gridBtns = document.querySelectorAll(".grid-btn");
  gridBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      gridBtns.forEach(b => {
        b.className = "grid-btn border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 rounded-xl p-2.5 text-center flex flex-col items-center justify-center transition-all";
      });
      btn.className = "grid-btn border-2 border-brand-600 bg-brand-50/70 text-brand-900 rounded-xl p-2.5 text-center flex flex-col items-center justify-center transition-all shadow-sm";
      state.imagesPerPage = parseInt(btn.dataset.count, 10);
      renderSheetsPreview();
      updateCounts();
    });
  });

  document.getElementById("select-paper-size").addEventListener("change", (e) => {
    state.paperSize = e.target.value;
    renderSheetsPreview();
  });

  document.getElementById("select-orientation").addEventListener("change", (e) => {
    state.orientation = e.target.value;
    renderSheetsPreview();
  });

  document.getElementById("select-margin").addEventListener("change", (e) => {
    state.margin = e.target.value;
    renderSheetsPreview();
  });

  document.getElementById("select-gap").addEventListener("change", (e) => {
    state.gap = e.target.value;
    renderSheetsPreview();
  });

  document.getElementById("select-fit-mode").addEventListener("change", (e) => {
    state.fitMode = e.target.value;
    renderSheetsPreview();
  });

  document.getElementById("toggle-cut-lines").addEventListener("change", (e) => {
    state.showCutLines = e.target.checked;
    renderSheetsPreview();
  });

  document.getElementById("toggle-page-numbers").addEventListener("change", (e) => {
    state.showPageNumbers = e.target.checked;
    renderSheetsPreview();
  });

  document.getElementById("toggle-labels").addEventListener("change", (e) => {
    state.showLabels = e.target.checked;
    renderSheetsPreview();
  });

  document.getElementById("btn-select-all").addEventListener("click", () => {
    state.images.forEach(img => img.selected = true);
    renderGallery();
    renderSheetsPreview();
    updateCounts();
  });

  document.getElementById("btn-deselect-all").addEventListener("click", () => {
    state.images.forEach(img => img.selected = false);
    renderGallery();
    renderSheetsPreview();
    updateCounts();
  });

  document.getElementById("btn-filter-small").addEventListener("click", () => {
    let removed = 0;
    state.images.forEach(img => {
      if (img.width < 120 || img.height < 120) {
        img.selected = false;
        removed++;
      }
    });
    renderGallery();
    renderSheetsPreview();
    updateCounts();
    alert(`Deselected ${removed} small icons/decorations.`);
  });
}

// 4. Live Printable Sheet Preview
function getGridConfig(count, orientation) {
  let rows = 1, cols = 1;
  if (count === 9) { rows = 3; cols = 3; }
  else if (count === 8) { rows = 4; cols = 2; }
  else if (count === 6) { rows = 3; cols = 2; }
  else if (count === 4) { rows = 2; cols = 2; }
  else if (count === 3) { rows = 3; cols = 1; }
  else if (count === 2) { rows = 2; cols = 1; }
  else { rows = 1; cols = 1; }

  if (orientation === "landscape" && rows > cols) {
    const tmp = rows;
    rows = cols;
    cols = tmp;
  }
  return { rows, cols };
}

function renderSheetsPreview() {
  sheetPreviewViewport.innerHTML = "";

  const selectedImages = state.images.filter(img => img.selected);
  const countPerPage = state.imagesPerPage;
  const totalSheets = Math.ceil(selectedImages.length / countPerPage) || 1;
  const { rows, cols } = getGridConfig(countPerPage, state.orientation);

  const marginPadMap = {
    "none": "p-0",
    "compact": "p-3",
    "standard": "p-6",
    "spacious": "p-9"
  };

  const gapMap = {
    "none": "gap-0",
    "compact": "gap-1.5",
    "standard": "gap-3",
    "spacious": "gap-5"
  };

  for (let sIdx = 0; sIdx < totalSheets; sIdx++) {
    const start = sIdx * countPerPage;
    const sheetImages = selectedImages.slice(start, start + countPerPage);

    const sheetWrapper = document.createElement("div");
    sheetWrapper.className = "flex flex-col items-center gap-2";

    const sheetLabel = document.createElement("span");
    sheetLabel.className = "text-[11px] font-bold text-slate-400 uppercase tracking-wider";
    sheetLabel.textContent = `Sheet ${sIdx + 1} of ${totalSheets} (${sheetImages.length} pictures)`;

    const sheet = document.createElement("div");
    const paperClass = `paper-${state.paperSize}-${state.orientation}`;
    sheet.className = `paper-sheet ${paperClass} ${marginPadMap[state.margin] || 'p-6'} flex flex-col justify-between`;

    const gridEl = document.createElement("div");
    gridEl.className = `grid w-full h-full ${gapMap[state.gap] || 'gap-3'}`;
    gridEl.style.gridTemplateColumns = `repeat(${cols}, minmax(0, 1fr))`;
    gridEl.style.gridTemplateRows = `repeat(${rows}, minmax(0, 1fr))`;

    sheetImages.forEach((img, idx) => {
      const cell = document.createElement("div");
      cell.className = `print-cell ${state.showCutLines ? 'cut-lines' : ''} ${state.fitMode === 'cover' ? 'fit-cover' : 'fit-contain'} rounded-sm relative`;

      const imgTag = document.createElement("img");
      imgTag.src = img.thumbnail;
      imgTag.style.transform = `rotate(${img.rotation || 0}deg)`;

      cell.appendChild(imgTag);

      if (state.showLabels) {
        const lbl = document.createElement("span");
        lbl.className = "absolute bottom-1 left-1 text-[9px] bg-white/90 px-1 py-0.5 rounded font-mono text-slate-700 shadow-xs";
        lbl.textContent = `#${start + idx + 1}`;
        cell.appendChild(lbl);
      }

      gridEl.appendChild(cell);
    });

    const emptyCount = (rows * cols) - sheetImages.length;
    for (let e = 0; e < emptyCount; e++) {
      const emptyCell = document.createElement("div");
      emptyCell.className = `print-cell ${state.showCutLines ? 'cut-lines opacity-30' : 'opacity-0'}`;
      gridEl.appendChild(emptyCell);
    }

    sheet.appendChild(gridEl);

    if (state.showPageNumbers) {
      const footer = document.createElement("div");
      footer.className = "text-center text-[10px] text-slate-400 font-medium pt-2";
      footer.textContent = `Page ${sIdx + 1} of ${totalSheets}`;
      sheet.appendChild(footer);
    }

    sheetWrapper.appendChild(sheetLabel);
    sheetWrapper.appendChild(sheet);
    sheetPreviewViewport.appendChild(sheetWrapper);
  }
}

// 5. Native Browser Print & File Exports
function setupExportButtons() {
  document.getElementById("btn-print-native").addEventListener("click", handleNativePrint);
  document.getElementById("btn-download-pdf").addEventListener("click", handleDownloadPdf);
  document.getElementById("btn-download-zip").addEventListener("click", handleDownloadZip);
}

function handleNativePrint() {
  const selectedImages = state.images.filter(img => img.selected);
  if (selectedImages.length === 0) {
    alert("Please select at least one image to print.");
    return;
  }

  printRenderZone.innerHTML = "";
  const countPerPage = state.imagesPerPage;
  const totalSheets = Math.ceil(selectedImages.length / countPerPage) || 1;
  const { rows, cols } = getGridConfig(countPerPage, state.orientation);

  for (let sIdx = 0; sIdx < totalSheets; sIdx++) {
    const start = sIdx * countPerPage;
    const sheetImages = selectedImages.slice(start, start + countPerPage);

    const sheet = document.createElement("div");
    sheet.className = "print-page-break flex flex-col justify-between p-6";
    sheet.style.width = "100vw";
    sheet.style.height = "100vh";
    sheet.style.boxSizing = "border-box";

    const grid = document.createElement("div");
    grid.className = "grid w-full h-full gap-3";
    grid.style.gridTemplateColumns = `repeat(${cols}, minmax(0, 1fr))`;
    grid.style.gridTemplateRows = `repeat(${rows}, minmax(0, 1fr))`;

    sheetImages.forEach((img, idx) => {
      const cell = document.createElement("div");
      cell.className = `print-cell ${state.showCutLines ? 'cut-lines' : ''} ${state.fitMode === 'cover' ? 'fit-cover' : 'fit-contain'}`;

      const imgTag = document.createElement("img");
      imgTag.src = `/api/image/${state.sessionId}/${img.id}`;
      imgTag.style.transform = `rotate(${img.rotation || 0}deg)`;

      cell.appendChild(imgTag);

      if (state.showLabels) {
        const lbl = document.createElement("span");
        lbl.className = "absolute bottom-1 left-1 text-[9px] bg-white/90 px-1 py-0.5 rounded font-mono text-slate-700";
        lbl.textContent = `#${start + idx + 1}`;
        cell.appendChild(lbl);
      }

      grid.appendChild(cell);
    });

    sheet.appendChild(grid);

    if (state.showPageNumbers) {
      const footer = document.createElement("div");
      footer.className = "text-center text-xs text-slate-500 pt-2";
      footer.textContent = `Page ${sIdx + 1} of ${totalSheets}`;
      sheet.appendChild(footer);
    }

    printRenderZone.appendChild(sheet);
  }

  window.print();
}

async function handleDownloadPdf() {
  const selectedImages = state.images.filter(img => img.selected);
  if (selectedImages.length === 0) {
    alert("Please select at least one image to print.");
    return;
  }

  const rotations = {};
  selectedImages.forEach(img => {
    rotations[img.id] = img.rotation || 0;
  });

  const payload = {
    session_id: state.sessionId,
    image_ids: selectedImages.map(img => img.id),
    rotations: rotations,
    images_per_page: state.imagesPerPage,
    paper_size: state.paperSize,
    orientation: state.orientation,
    margin: state.margin,
    gap: state.gap,
    fit_mode: state.fitMode,
    show_cut_lines: state.showCutLines,
    show_labels: state.showLabels,
    show_page_numbers: state.showPageNumbers
  };

  showLoader("Generating printable PDF...");

  try {
    const res = await fetch("/api/generate-pdf", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) throw new Error("PDF generation failed");

    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `printable_photos_${state.imagesPerPage}perpage.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
  } catch (err) {
    console.error(err);
    alert("Failed to download PDF.");
  } finally {
    hideLoader();
  }
}

async function handleDownloadZip() {
  const selectedImages = state.images.filter(img => img.selected);
  if (selectedImages.length === 0) {
    alert("Please select images to download.");
    return;
  }

  const rotations = {};
  selectedImages.forEach(img => {
    rotations[img.id] = img.rotation || 0;
  });

  const payload = {
    session_id: state.sessionId,
    image_ids: selectedImages.map(img => img.id),
    rotations: rotations,
    images_per_page: state.imagesPerPage
  };

  showLoader("Compressing images into ZIP...");

  try {
    const res = await fetch("/api/download-zip", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) throw new Error("ZIP generation failed");

    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "extracted_images.zip";
    document.body.appendChild(a);
    a.click();
    a.remove();
  } catch (err) {
    console.error(err);
    alert("Failed to download ZIP.");
  } finally {
    hideLoader();
  }
}

// 6. Lightbox Modal
function setupLightbox() {
  const modal = document.getElementById("lightbox-modal");
  const closeBtn = document.getElementById("btn-close-lightbox");

  closeBtn.addEventListener("click", () => {
    modal.classList.add("hidden");
    modal.classList.remove("flex");
  });

  modal.addEventListener("click", (e) => {
    if (e.target === modal) {
      modal.classList.add("hidden");
      modal.classList.remove("flex");
    }
  });
}

function openLightbox(img) {
  const modal = document.getElementById("lightbox-modal");
  const imgEl = document.getElementById("lightbox-img");
  const cap = document.getElementById("lightbox-caption");

  imgEl.src = `/api/image/${state.sessionId}/${img.id}`;
  imgEl.style.transform = `rotate(${img.rotation || 0}deg)`;
  cap.textContent = `${img.name} — ${img.width} × ${img.height} px (${img.format})`;

  modal.classList.remove("hidden");
  modal.classList.add("flex");
}

</script>
</body>
</html>
"""

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
            "message": "No images found in the uploaded file(s).",
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
        raise HTTPException(status_code=404, detail="Session expired or not found.")
        
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
        ("#dc2626", "#991b1b", "Crimson Mountain Sunrise"),
        ("#e11d48", "#9f1239", "Rose City Horizon"),
        ("#059669", "#065f46", "Emerald Forest Nature"),
        ("#d97706", "#92400e", "Amber Desert Vista"),
        ("#7c3aed", "#5b21b6", "Cosmic Violet Stars"),
        ("#0284c7", "#075985", "Deep Blue Ocean Reef"),
        ("#ea580c", "#9a3412", "Autumn Maple Woods"),
        ("#65a30d", "#3f6212", "Spring Blossom Flora"),
        ("#4f46e5", "#3730a3", "Modern Architecture"),
    ]
    
    for idx, (c1, c2, title) in enumerate(colors):
        img = Image.new("RGB", (600, 450), color=c1)
        draw = ImageDraw.Draw(img)
        for y in range(450):
            r_ratio = y / 450.0
            draw.line([(0, y), (600, y)], fill=(int(30 + r_ratio*50), int(30 + r_ratio*50), int(60 + r_ratio*80)))
            
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

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    return STANDALONE_HTML
