// Document Image Extractor & Printout Layout Engine

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
