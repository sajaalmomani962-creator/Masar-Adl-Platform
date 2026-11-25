/* Local, read-only PDF rendering. Authorization stays on the existing raw route. */
const root = document.querySelector("[data-pdf-src]");
if (root) {
  const load = root.querySelector("[data-pdf-load]");
  const status = root.querySelector("[data-pdf-status]");
  const reader = root.querySelector("[data-pdf-reader]");
  const canvas = root.querySelector("[data-pdf-canvas]");
  const previous = root.querySelector("[data-pdf-prev]");
  const next = root.querySelector("[data-pdf-next]");
  const label = root.querySelector("[data-pdf-page]");
  let documentTask, pdf, pageNumber = 1, busy = false;
  const buttons = () => {
    previous.disabled = busy || pageNumber <= 1;
    next.disabled = busy || !pdf || pageNumber >= pdf.numPages;
    if (load) load.disabled = busy;
  };
  const render = async (number) => {
    busy = true;
    buttons();
    status.textContent = "جارٍ عرض الصفحة…";
    try {
      const page = await pdf.getPage(number);
      const original = page.getViewport({ scale: 1 });
      const width = Math.min(root.clientWidth || 300, 1000);
      // Bound a single canvas to 4 million pixels; never allocate every page.
      const scale = Math.min(width / original.width * Math.min(devicePixelRatio || 1, 2),
        Math.sqrt(4000000 / (original.width * original.height)), 3);
      const viewport = page.getViewport({ scale });
      canvas.width = Math.max(1, Math.floor(viewport.width));
      canvas.height = Math.max(1, Math.floor(viewport.height));
      await page.render({ canvasContext: canvas.getContext("2d"), viewport }).promise;
      page.cleanup();
      pageNumber = number;
      label.textContent = `الصفحة ${pageNumber} من ${pdf.numPages}`;
      canvas.setAttribute("aria-label", `صورة الصفحة ${pageNumber} من ${pdf.numPages}؛ لقراءة النص بمساعد تقني استخدم PDF الأصلي`);
      canvas.dataset.renderedPage = String(pageNumber);
      reader.hidden = false;
      status.textContent = "تم عرض الصفحة. المعاينة صورة وليست بديلًا عن النص المتاح في PDF الأصلي.";
      if (load) load.hidden = true;
    } finally {
      busy = false;
      buttons();
    }
  };
  const failure = async () => {
    reader.hidden = true;
    status.textContent = "تعذّرت المعاينة. تحقق من الجلسة والصلاحيات وصلاحية ملف PDF، أو استخدم رابط عارض المتصفح.";
    if (documentTask) await documentTask.destroy().catch(() => {});
    documentTask = pdf = null;
    if (load) { load.hidden = false; load.disabled = false; }
    buttons();
  };
  if (load) load.addEventListener("click", async () => {
    if (busy) return;
    busy = true;
    buttons();
    status.textContent = "جارٍ تحميل PDF من المسار المحمي…";
    try {
      const library = await import("/static/vendor/pdfjs/pdf.mjs");
      library.GlobalWorkerOptions.workerSrc = "/static/vendor/pdfjs/pdf.worker.mjs";
      const response = await fetch(root.dataset.pdfSrc, { credentials: "same-origin", cache: "no-store" });
      if (!response.ok || response.redirected || !response.headers.get("content-type")?.includes("application/pdf")) throw new Error("PDF unavailable");
      const bytes = new Uint8Array(await response.arrayBuffer());
      if (bytes.length > 10 * 1024 * 1024) throw new Error("PDF too large");
      documentTask = library.getDocument({
        data: bytes, isEvalSupported: false, disableFontFace: true,
        useSystemFonts: true, isOffscreenCanvasSupported: false, disableWorkerRendering: true,
      });
      pdf = await documentTask.promise;
      await render(1);
    } catch {
      busy = false;
      await failure();
    }
  });
  previous.addEventListener("click", () => { if (!busy && pdf && pageNumber > 1) render(pageNumber - 1).catch(failure); });
  next.addEventListener("click", () => { if (!busy && pdf && pageNumber < pdf.numPages) render(pageNumber + 1).catch(failure); });
  buttons();
  window.addEventListener("pagehide", () => { if (documentTask) documentTask.destroy().catch(() => {}); });
}
