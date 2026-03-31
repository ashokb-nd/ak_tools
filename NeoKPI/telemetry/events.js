import { ALERT_EVENT_CONFIG } from "./constants.js";

export class CustomEvent {
  constructor(eventCode, startOffsetMs, endOffsetMs, config = {}) {
    this.eventCode = String(eventCode);
    this.startOffsetMs = Number(startOffsetMs);
    this.endOffsetMs = Number(endOffsetMs);
    this.name = config.name || `Event ${eventCode}`;
    this.description = config.description || `Custom event ${eventCode}`;
    this.markerColor = config.markerColor || "rgba(200, 100, 255, 0.95)";
    this.fillColor = config.fillColor || "rgba(200, 100, 255, 0.14)";
  }

  isValid() {
    return (
      Number.isFinite(this.startOffsetMs)
      && Number.isFinite(this.endOffsetMs)
      && this.endOffsetMs >= this.startOffsetMs
    );
  }
}

export function createCustomEvents(metadata) {
  if (!metadata || typeof metadata !== "object") return [];

  // Override this hook with domain logic to generate dynamic custom events.
  return [];
}

export function extractAlertSpansByCode(metadata, eventCode, customEvents = []) {
  const events = metadata?.inference_data?.events_data?.alerts;
  const spans = [];

  if (Array.isArray(events)) {
    for (const event of events) {
      if (String(event?.event_code) !== eventCode) continue;

      const startOffsetMs = Number(event?.start_timestamp);
      const endOffsetMs = Number(event?.end_timestamp);
      const startSec = Number.isFinite(startOffsetMs) ? startOffsetMs / 1000 : null;
      const endSec = Number.isFinite(endOffsetMs) ? endOffsetMs / 1000 : null;

      if (!Number.isFinite(startSec) || !Number.isFinite(endSec) || endSec < startSec) continue;

      spans.push({ startSec, endSec });
    }
  }

  for (const customEvent of customEvents) {
    if (String(customEvent?.eventCode) !== eventCode) continue;
    if (typeof customEvent?.isValid !== "function" || !customEvent.isValid()) continue;

    spans.push({
      startSec: customEvent.startOffsetMs / 1000,
      endSec: customEvent.endOffsetMs / 1000,
    });
  }

  return spans;
}

export function createShapesFromSpans(spans, xMax, markerColor, fillColor) {
  return spans
    .map(span => ({
      startSec: Math.max(0, Math.min(span.startSec, xMax)),
      endSec: Math.max(0, Math.min(span.endSec, xMax)),
    }))
    .flatMap(span => {
      if (span.endSec < span.startSec) return [];
      if (span.endSec === span.startSec) {
        return [{
          type: "line",
          x0: span.startSec,
          x1: span.startSec,
          y0: 0,
          y1: 1,
          yref: "paper",
          line: { color: markerColor, width: 1.5, dash: "dot" },
        }];
      }

      return [{
        type: "rect",
        x0: span.startSec,
        x1: span.endSec,
        y0: 0,
        y1: 1,
        yref: "paper",
        line: { width: 0 },
        fillcolor: fillColor,
        layer: "below",
      }];
    });
}

export function getAllAlertShapes(metadata, xMax, alertConfig = ALERT_EVENT_CONFIG, customEvents = []) {
  const allShapes = [];
  for (const [eventCode, config] of Object.entries(alertConfig)) {
    const spans = extractAlertSpansByCode(metadata, eventCode, customEvents);
    const shapes = createShapesFromSpans(spans, xMax, config.markerColor, config.fillColor);
    allShapes.push(...shapes);
  }
  return allShapes;
}

export function getAllAlertHoverTraces(
  metadata,
  xMax,
  yMin,
  yMax,
  alertConfig = ALERT_EVENT_CONFIG,
  customEvents = [],
) {
  const traces = [];
  for (const [eventCode, config] of Object.entries(alertConfig)) {
    const spans = extractAlertSpansByCode(metadata, eventCode, customEvents);
    for (const span of spans) {
      const x0 = Math.max(0, Math.min(span.startSec, xMax));
      const x1 = Math.max(0, Math.min(span.endSec, xMax));
      if (x1 < x0) continue;

      if (x0 === x1) {
        traces.push({
          type: "scatter",
          mode: "markers",
          marker: { opacity: 0, size: 8 },
          x: [x0],
          y: [(yMin + yMax) / 2],
          hovertemplate: `<b>${config.name}</b><br><span style="font-size:11px">${config.description}</span><extra></extra>`,
          showlegend: false,
          name: config.name,
        });
      } else {
        traces.push({
          type: "scatter",
          mode: "none",
          x: [x0, x1, x1, x0, x0],
          y: [yMin, yMin, yMax, yMax, yMin],
          fill: "toself",
          fillcolor: "rgba(0,0,0,0)",
          line: { width: 0 },
          hoveron: "fills",
          hovertemplate: `<b>${config.name}</b><br><span style="font-size:11px">${config.description}</span><extra></extra>`,
          showlegend: false,
          name: config.name,
        });
      }
    }
  }
  return traces;
}

export function buildMergedAlertConfig(customEvents, baseConfig = ALERT_EVENT_CONFIG) {
  const mergedAlertConfig = { ...baseConfig };
  for (const customEvent of customEvents) {
    mergedAlertConfig[customEvent.eventCode] = {
      name: customEvent.name,
      description: customEvent.description,
      markerColor: customEvent.markerColor,
      fillColor: customEvent.fillColor,
    };
  }
  return mergedAlertConfig;
}
