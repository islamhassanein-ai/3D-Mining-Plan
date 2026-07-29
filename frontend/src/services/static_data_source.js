// StaticDataSource is isolated here so the export viewer bundle (viewer_main.js)
// can import it without pulling api_client.js into the artifact (T023/T022).
import { computeTrueThickness } from './true_thickness.js';

export class StaticDataSource {
  constructor(payload) {
    this.payload = payload;
    this.isStatic = true;
  }

  async getScene() { return this.payload.scene; }

  async getCollarDetails(collarId) {
    const details = this.payload.collar_details[collarId];
    if (!details) throw new Error(`Unknown collar ID in static payload: ${collarId}`);
    return details;
  }

  async getTrueThickness(collarId, intervalId, dipDirection, dip) {
    const details = this.payload.collar_details[collarId];
    if (!details) throw new Error(`Unknown collar ID in static payload: ${collarId}`);
    const surveys = (details.surveys || []).map(s => ({
      depth: s.depth, dip: s.dip, azimuth: s.azimuth,
    }));
    let fromDepth = null, toDepth = null;
    for (const interval of [...(details.assays || []), ...(details.lithologies || []), ...(details.merged_intervals || [])]) {
      if (interval.id === intervalId) {
        fromDepth = interval.from_depth;
        toDepth = interval.to_depth;
        break;
      }
    }
    if (fromDepth === null) throw new Error(`Interval ${intervalId} not found in collar ${collarId}`);
    return computeTrueThickness({ surveys, fromDepth, toDepth, dipDirection, dip, collarId, intervalId });
  }

  async getTopographyPoints(topographyRef) {
    const topo = this.payload.topography;
    if (!topo || !topo.included || !topo.points || topo.points.length === 0) return null;
    return topo.points.map(([e, n, el]) => ({ e, n, el }));
  }

  // Payload wireframes always have vertices/faces embedded; the inline path
  // in wireframes.js handles them. This resolver is never called for a well-formed
  // static payload, but returns null (causing a console.warn + skip) if reached.
  async getWireframeGeometry(wireframe) { return null; }
}
