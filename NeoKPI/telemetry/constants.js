export const TELEMETRY_MAX_POINTS = 1200;
export const TELEMETRY_PLAYHEAD_FPS = 24;
export const SMOOTHING_WINDOWS = [1, 3, 5, 7, 9, 11];
export const DEFAULT_SMOOTHING_INDEX = Math.max(0, SMOOTHING_WINDOWS.indexOf(7));

export const ALERT_EVENT_CONFIG = {
  "900.0.1.0": {
    name: "DSF",
    description: "900.0.1.0 event",
    markerColor: "rgba(100, 200, 255, 0.95)",
    fillColor: "rgba(100, 200, 255, 0.14)",
  },
  "900.0.0.1": {
    name: "EEC_1S",
    description: "900.0.0.1 event",
    markerColor: "rgba(39, 168, 0, 0.95)",
    fillColor: "rgba(126, 236, 109, 0.14)",
  },
};
