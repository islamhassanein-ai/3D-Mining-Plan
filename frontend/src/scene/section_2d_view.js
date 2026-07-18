import { getLithologyColor } from './lithology_intervals.js';

export class Section2DView {
  constructor(canvasElement) {
    this.canvas = canvasElement;
    this.ctx = this.canvas.getContext('2d');
    
    // Zoom/pan state
    this.zoom = 1.0;
    this.panX = 0;
    this.panY = 0;
  }

  resize(width, height) {
    this.canvas.width = width;
    this.canvas.height = height;
  }

  draw(slicedData) {
    const ctx = this.ctx;
    const canvas = this.canvas;
    
    // 1. Clear Canvas
    ctx.fillStyle = '#0b0f19'; // Match 3D viewport dark theme
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    
    const { traces, assays, lithologies, limits } = slicedData;
    if (traces.length === 0) {
      ctx.fillStyle = '#64748b';
      ctx.font = '14px Inter, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('No drillholes intersected by this slicing plane.', canvas.width / 2, canvas.height / 2);
      return;
    }
    
    const { minU, maxU, minV, maxV } = limits;
    
    // 2. Compute scale and centering
    const viewWidth = maxU - minU;
    const viewHeight = maxV - minV;
    
    const scaleX = canvas.width / viewWidth;
    const scaleY = canvas.height / viewHeight;
    const scale = Math.min(scaleX, scaleY) * 0.9 * this.zoom; // Apply zoom + margin
    
    // Center of data
    const midU = (minU + maxU) / 2;
    const midV = (minV + maxV) / 2;
    
    // Mapping functions: 2D plane -> pixels
    const toPixelX = (u) => {
      return (u - midU) * scale + canvas.width / 2 + this.panX;
    };
    
    const toPixelY = (v) => {
      // Flip vertical Y-axis for screen coordinate space
      return canvas.height / 2 - (v - midV) * scale + this.panY;
    };

    // 3. Draw Grid/Elevation markers
    ctx.strokeStyle = 'rgba(255,255,255,0.05)';
    ctx.lineWidth = 1;
    ctx.fillStyle = 'rgba(255,255,255,0.3)';
    ctx.font = '10px monospace';
    
    // Elevation horizontal lines (every 20 meters)
    const stepV = 20;
    const startV = Math.floor(minV / stepV) * stepV;
    for (let v = startV; v <= maxV; v += stepV) {
      const y = toPixelY(v);
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(canvas.width, y);
      ctx.stroke();
      ctx.textAlign = 'left';
      ctx.fillText(`EL: ${v}m`, 10, y - 4);
    }
    
    // Horizontal distance vertical lines (every 50 meters)
    const stepU = 50;
    const startU = Math.floor(minU / stepU) * stepU;
    for (let u = startU; u <= maxU; u += stepU) {
      const x = toPixelX(u);
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, canvas.height);
      ctx.stroke();
      ctx.textAlign = 'center';
      ctx.fillText(`${u}m`, x, canvas.height - 10);
    }

    // 4. Draw Lithologies (thick background intervals)
    ctx.lineWidth = 12; // cylinder width in 2D
    ctx.lineCap = 'round';
    for (const lith of lithologies) {
      const color = getLithologyColor(lith.lith_code);
      ctx.strokeStyle = color;
      
      const x1 = toPixelX(lith.start.u);
      const y1 = toPixelY(lith.start.v);
      const x2 = toPixelX(lith.end.u);
      const y2 = toPixelY(lith.end.v);
      
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();
    }

    // 5. Draw Assays (overlapping highlighted intervals)
    ctx.lineWidth = 8; // slightly thinner than lithology for nesting look
    for (const assay of assays) {
      ctx.strokeStyle = assay.color;
      
      const x1 = toPixelX(assay.start.u);
      const y1 = toPixelY(assay.start.v);
      const x2 = toPixelX(assay.end.u);
      const y2 = toPixelY(assay.end.v);
      
      ctx.beginPath();
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
      ctx.stroke();
    }

    // 6. Draw Center Line Traces
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.4)';
    ctx.lineWidth = 1;
    for (const dh of traces) {
      for (const seg of dh.segments) {
        const x1 = toPixelX(seg.start.u);
        const y1 = toPixelY(seg.start.v);
        const x2 = toPixelX(seg.end.u);
        const y2 = toPixelY(seg.end.v);
        
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();
      }
      
      // Draw Hole ID text at the collar (first segment start point)
      if (dh.segments.length > 0) {
        const collarSeg = dh.segments[0];
        const cx = toPixelX(collarSeg.start.u);
        const cy = toPixelY(collarSeg.start.v);
        
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 11px Inter, sans-serif';
        ctx.textAlign = 'center';
        
        // Draw backing rect for text readability
        ctx.fillStyle = 'rgba(11, 15, 25, 0.8)';
        ctx.fillRect(cx - 30, cy - 20, 60, 14);
        
        ctx.fillStyle = '#3b82f6'; // Bright blue labels
        ctx.fillText(dh.hole_id, cx, cy - 9);
      }
    }
  }
}
