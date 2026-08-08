// Turning the section SVG into a file on someone's disk.
//
// Split out from plan_section_svg.js because that module has to stay runnable
// under `node --test`: everything here touches document, Blob or Image, none of
// which exist there.
//
// PNG is the default rather than SVG. The drawing's destination is a Word
// proposal or a slide, and SVG pastes badly into both -- but the SVG is offered
// alongside it because it is the one that survives being scaled up for an A3
// plot.

const PNG_SCALE = 2;   // a 1100px drawing rasterised at 2200px still prints sharp

export function svgBlob(svg) {
  return new Blob([svg], { type: 'image/svg+xml;charset=utf-8' });
}

/**
 * Rasterise the SVG through an <img> and a canvas.
 *
 * The SVG is self-contained by construction -- no external fonts, no <image>
 * hrefs -- which is what keeps the canvas untainted and toBlob() legal. Adding
 * a webfont or a logo URL to the drawing later would break this silently, so
 * the failure path below reports rather than swallows it.
 */
export function svgToPngBlob(svg, scale = PNG_SCALE) {
  return new Promise((resolve, reject) => {
    const match = /width="(\d+)" height="(\d+)"/.exec(svg);
    const width = match ? Number(match[1]) : 1100;
    const height = match ? Number(match[2]) : 720;

    const url = URL.createObjectURL(svgBlob(svg));
    const img = new Image();

    img.onload = () => {
      try {
        const canvas = document.createElement('canvas');
        canvas.width = Math.round(width * scale);
        canvas.height = Math.round(height * scale);
        const ctx = canvas.getContext('2d');
        ctx.setTransform(scale, 0, 0, scale, 0, 0);
        ctx.drawImage(img, 0, 0, width, height);
        canvas.toBlob(
          (blob) => {
            URL.revokeObjectURL(url);
            blob ? resolve(blob) : reject(new Error('The browser could not encode the PNG.'));
          },
          'image/png'
        );
      } catch (err) {
        URL.revokeObjectURL(url);
        reject(err);
      }
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error('The browser could not render the section image.'));
    };
    img.src = url;
  });
}

export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  // Revoking immediately cancels the download in some browsers; one tick is
  // enough for the click to have been handed off.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** A filename that sorts by date and says which plan it came from. */
export function sectionFilename(base, ext) {
  const stamp = new Date().toISOString().slice(0, 10);
  const safe = String(base || 'drill-plan')
    .trim()
    .replace(/[^A-Za-z0-9_-]+/g, '-')
    .replace(/^-+|-+$/g, '') || 'drill-plan';
  return `${safe}-section-${stamp}.${ext}`;
}
