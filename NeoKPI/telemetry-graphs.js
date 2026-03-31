const TELEMETRY_MAX_POINTS = 1200;
const TELEMETRY_PLAYHEAD_FPS = 24;
const SMOOTHING_WINDOWS = [1, 3, 5, 7, 9, 11];
const DEFAULT_SMOOTHING_INDEX = Math.max(0, SMOOTHING_WINDOWS.indexOf(7));

const ALERT_EVENT_CONFIG = {
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

class CustomEvent {
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

function createCustomEvents(metadata) {
  if (!metadata || typeof metadata !== "object") return [];

  // Override this hook with domain logic to generate dynamic custom events.
  return [];
}

function fmtSigned(value, digits = 3) {
  if (!Number.isFinite(value)) return "--";
  const normalized = Math.abs(value) < 1e-6 ? 0 : value;
  const sign = normalized < 0 ? "-" : "+";
  return `${sign}${Math.abs(normalized).toFixed(digits)}`;
}

function normalizeSeries(points, startEpochMs) {
  if (!Array.isArray(points)) return [];
  return points
    .filter(p => Array.isArray(p) && Number.isFinite(p[0]) && Number.isFinite(p[1]))
    .map(([t, v]) => ({ x: (t - startEpochMs) / 1000, y: v }));
}

function downsampleSeries(series, maxPoints = TELEMETRY_MAX_POINTS) {
  if (!Array.isArray(series) || series.length <= maxPoints) return series || [];
  const step = Math.ceil(series.length / maxPoints);
  const out = [];
  for (let i = 0; i < series.length; i += step) out.push(series[i]);
  if (out[out.length - 1] !== series[series.length - 1]) out.push(series[series.length - 1]);
  return out;
}

function smoothSeriesY(series, windowSize) {
  if (!Array.isArray(series) || !series.length || windowSize <= 1) {
    return (series || []).map(p => p.y);
  }

  const size = Math.max(1, Math.floor(windowSize));
  const half = Math.floor(size / 2);
  const y = series.map(p => p.y);
  const out = new Array(y.length);

  for (let i = 0; i < y.length; i += 1) {
    const start = Math.max(0, i - half);
    const end = Math.min(y.length - 1, i + half);
    let sum = 0;
    let count = 0;
    for (let j = start; j <= end; j += 1) {
      sum += y[j];
      count += 1;
    }
    out[i] = count > 0 ? sum / count : y[i];
  }

  return out;
}

function parseAccelerometerSeries(sensorMetaData, startEpochMs) {
  if (!Array.isArray(sensorMetaData)) return { accY: [], accZ: [] };

  const accY = [];
  const accZ = [];
  for (const entry of sensorMetaData) {
    if (!entry?.accelerometer) continue;
    const values = String(entry.accelerometer).trim().split(/\s+/);
    if (values.length < 4) continue;

    const y = parseFloat(values[1]);
    const z = parseFloat(values[2]);
    const t = parseInt(values[3], 10);
    if (!Number.isFinite(y) || !Number.isFinite(z) || !Number.isFinite(t)) continue;

    const x = (t - startEpochMs) / 1000;
    accY.push({ x, y });
    accZ.push({ x, y: z });
  }

  return { accY, accZ };
}

function parseYawSeries(sensorMetaData, startEpochMs) {
  if (!Array.isArray(sensorMetaData)) return [];

  const yawSeries = [];
  for (const entry of sensorMetaData) {
    if (!entry?.gyro) continue;
    const values = String(entry.gyro).trim().split(/\s+/);
    if (values.length < 4) continue;

    const yaw = parseFloat(values[0]);
    const t = parseInt(values[3], 10);
    if (!Number.isFinite(yaw) || !Number.isFinite(t)) continue;

    const x = (t - startEpochMs) / 1000;
    yawSeries.push({ x, y: yaw });
  }

  return yawSeries;
}

function getPilOffset(metadata) {
  const laneCalParams = metadata?.inference_data?.observations_data?.laneCalibrationParams;
  if (!Array.isArray(laneCalParams) || laneCalParams.length < 4) return 0;

  const CANONICAL_OUTWARD_IMAGE_WIDTH = 1920;
  const CANONICAL_OUTWARD_IMAGE_HEIGHT = 1080;

  let [vanishingPointEstimate, _unused, xInt, imageHeight] = laneCalParams;
  if (!Array.isArray(vanishingPointEstimate) || !Array.isArray(xInt) || !imageHeight) return 0;

  const scale = CANONICAL_OUTWARD_IMAGE_HEIGHT / imageHeight;
  vanishingPointEstimate = vanishingPointEstimate.map(x => x * scale);
  xInt = xInt.map(x => x * scale);

  const laneLeft = xInt[0] / CANONICAL_OUTWARD_IMAGE_WIDTH;
  const laneRight = xInt[1] / CANONICAL_OUTWARD_IMAGE_WIDTH;
  const vpX = vanishingPointEstimate[0] / CANONICAL_OUTWARD_IMAGE_WIDTH;
  const laneWidth = laneRight - laneLeft;
  if (!Number.isFinite(laneWidth) || laneWidth === 0) return 0;

  const laneMid = (laneLeft + laneRight) / 2;
  return (laneMid - vpX) / laneWidth;
}

function extractMinEpochMs(metadata, positionsInLane) {
  const candidates = [];

  if (Array.isArray(positionsInLane)) {
    for (const row of positionsInLane) {
      if (Array.isArray(row) && Number.isFinite(row[0])) candidates.push(row[0]);
    }
  }

  const sensorMetaData = metadata?.sensorMetaData;
  if (Array.isArray(sensorMetaData)) {
    for (const entry of sensorMetaData) {
      if (entry?.accelerometer) {
        const accValues = String(entry.accelerometer).trim().split(/\s+/);
        if (accValues.length >= 4) {
          const accT = parseInt(accValues[3], 10);
          if (Number.isFinite(accT)) candidates.push(accT);
        }
      }

      if (entry?.gyro) {
        const gyroValues = String(entry.gyro).trim().split(/\s+/);
        if (gyroValues.length >= 4) {
          const gyroT = parseInt(gyroValues[3], 10);
          if (Number.isFinite(gyroT)) candidates.push(gyroT);
        }
      }
    }
  }

  return candidates.length ? Math.min(...candidates) : null;
}

function computeMaxX(model) {
  const allSeries = [model.laneSeries, model.accY, model.accZ, model.yawSeries];
  let maxX = 0;
  for (const series of allSeries) {
    if (!Array.isArray(series) || !series.length) continue;
    const last = series[series.length - 1];
    if (Number.isFinite(last?.x) && last.x > maxX) maxX = last.x;
  }
  return Math.max(1, Math.round(maxX));
}

function extractAlertSpansByCode(metadata, eventCode, customEvents = []) {
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

function createShapesFromSpans(spans, xMax, markerColor, fillColor) {
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

function getAllAlertShapes(metadata, xMax, alertConfig = ALERT_EVENT_CONFIG, customEvents = []) {
  const allShapes = [];
  for (const [eventCode, config] of Object.entries(alertConfig)) {
    const spans = extractAlertSpansByCode(metadata, eventCode, customEvents);
    const shapes = createShapesFromSpans(spans, xMax, config.markerColor, config.fillColor);
    allShapes.push(...shapes);
  }
  return allShapes;
}

function getAllAlertHoverTraces(
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
          name: config.name, // this is showing in the legend
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

function buildTelemetryModel(metadata) {
  if (!metadata || typeof metadata !== "object") return null;

  const positionsInLane = metadata?.inference_data?.observations_data?.positionsInLane || [];
  const metadataStart = Number(metadata.startTime);
  const startEpochMs = Number.isFinite(metadataStart)
    ? metadataStart
    : (extractMinEpochMs(metadata, positionsInLane) ?? Date.now());
  const pilOffset = getPilOffset(metadata);

  const laneSeries = downsampleSeries(
    normalizeSeries(
      positionsInLane.map(([t, v]) => [t, (Number(v) || 0) + pilOffset]),
      startEpochMs,
    ),
  );

  const rawInertial = parseAccelerometerSeries(metadata?.sensorMetaData, startEpochMs);
  const accY = downsampleSeries(rawInertial.accY);
  const accZ = downsampleSeries(rawInertial.accZ);
  const yawSeries = downsampleSeries(parseYawSeries(metadata?.sensorMetaData, startEpochMs));
  const customEvents = createCustomEvents(metadata).filter(event => event?.isValid?.());

  if (!laneSeries.length && !accY.length && !accZ.length && !yawSeries.length) return null;

  const mergedAlertConfig = { ...ALERT_EVENT_CONFIG };
  for (const customEvent of customEvents) {
    mergedAlertConfig[customEvent.eventCode] = {
      name: customEvent.name,
      description: customEvent.description,
      markerColor: customEvent.markerColor,
      fillColor: customEvent.fillColor,
    };
  }

  const model = {
    laneSeries,
    accY,
    accZ,
    yawSeries,
    startEpochMs,
    customEvents,
    mergedAlertConfig,
  };
  model.xMax = computeMaxX(model);
  return model;
}

function computeRobustYRange(seriesList, fallbackMin, fallbackMax) {
  const values = [];
  for (const series of seriesList) {
    if (!Array.isArray(series)) continue;
    for (const p of series) {
      if (Number.isFinite(p?.y)) values.push(p.y);
    }
  }

  if (!values.length) return { min: fallbackMin, max: fallbackMax };

  values.sort((a, b) => a - b);
  const p = q => values[Math.min(values.length - 1, Math.max(0, Math.floor((values.length - 1) * q)))];
  const q02 = p(0.02);
  const q98 = p(0.98);

  const span = Math.max(0.1, q98 - q02);
  const pad = span * 0.15;
  let min = q02 - pad;
  let max = q98 + pad;

  if (!Number.isFinite(min) || !Number.isFinite(max) || min >= max) {
    return { min: fallbackMin, max: fallbackMax };
  }

  min = Math.max(min, fallbackMin * 4);
  max = Math.min(max, fallbackMax * 4);
  if (min >= max) return { min: fallbackMin, max: fallbackMax };

  return { min, max };
}

function plotLayout(yLabel, xMax = 1, yMin = undefined, yMax = undefined, extraShapes = []) {
  return {
    paper_bgcolor: "#171b28",
    plot_bgcolor: "#171b28",
    margin: { l: 48, r: 14, t: 8, b: 34 },
    showlegend: true,
    legend: {
      orientation: "h",
      x: 0,
      y: 1.12,
      font: { color: "#dde1ef", size: 10 },
    },
    xaxis: {
      title: { text: "Time (s)", font: { color: "#8b92b8", size: 11 } },
      range: [0, xMax],
      color: "#8b92b8",
      gridcolor: "rgba(255,255,255,0.05)",
      zeroline: false,
    },
    yaxis: {
      title: { text: yLabel, font: { color: "#8b92b8", size: 11 } },
      range: [yMin, yMax],
      color: "#8b92b8",
      gridcolor: "rgba(255,255,255,0.05)",
      zeroline: false,
    },
    shapes: [{
      type: "line",
      x0: 0,
      x1: 0,
      y0: 0,
      y1: 1,
      yref: "paper",
      line: { color: "#ffffff", width: 1, dash: "solid" },
    }, ...extraShapes],
  };
}

function interpolateSeries(series, tSec) {
  if (!Array.isArray(series) || !series.length || !Number.isFinite(tSec)) return null;
  if (tSec <= series[0].x) return series[0].y;
  if (tSec >= series[series.length - 1].x) return series[series.length - 1].y;

  let lo = 0;
  let hi = series.length - 1;
  while (lo <= hi) {
    const mid = Math.floor((lo + hi) / 2);
    if (series[mid].x < tSec) lo = mid + 1;
    else hi = mid - 1;
  }

  const right = series[Math.max(1, lo)];
  const left = series[Math.max(0, lo - 1)];
  const span = right.x - left.x;
  if (span <= 0) return right.y;
  const ratio = (tSec - left.x) / span;
  return left.y + ratio * (right.y - left.y);
}

function createJsonToken(className, text) {
  const span = document.createElement("span");
  span.className = className;
  span.textContent = text;
  return span;
}

function createJsonPrimitiveNode(value) {
  if (value === null) return createJsonToken("telemetry-json-null", "null");
  if (typeof value === "string") return createJsonToken("telemetry-json-string", `"${value}"`);
  if (typeof value === "number") return createJsonToken("telemetry-json-number", String(value));
  if (typeof value === "boolean") return createJsonToken("telemetry-json-boolean", String(value));
  return createJsonToken("telemetry-json-null", String(value));
}

function createJsonBranchNode(value, depth = 0) {
  const isArray = Array.isArray(value);
  const entries = isArray
    ? value.map((item, index) => [String(index), item])
    : Object.entries(value || {});

  const details = document.createElement("details");
  details.className = "telemetry-json-branch";
  details.open = depth < 1;

  const summary = document.createElement("summary");
  summary.className = "telemetry-json-summary";
  const countLabel = isArray
    ? `${entries.length} items`
    : `${entries.length} keys`;
  summary.textContent = `${isArray ? "[" : "{"} ${countLabel} ${isArray ? "]" : "}"}`;
  details.appendChild(summary);

  const children = document.createElement("div");
  children.className = "telemetry-json-children";

  for (const [key, childValue] of entries) {
    const row = document.createElement("div");
    row.className = "telemetry-json-row";

    if (isArray) row.appendChild(createJsonToken("telemetry-json-index", `[${key}]`));
    else row.appendChild(createJsonToken("telemetry-json-key", `"${key}"`));

    row.appendChild(createJsonToken("telemetry-json-sep", ":"));

    if (childValue && typeof childValue === "object") {
      row.appendChild(createJsonBranchNode(childValue, depth + 1));
    } else {
      row.appendChild(createJsonPrimitiveNode(childValue));
    }

    children.appendChild(row);
  }

  details.appendChild(children);
  return details;
}

function renderExtendedEventHistory(metadata, eventHistoryEl) {
  if (!eventHistoryEl) return;

  const extdEh = metadata?.inference_data?.observations_data?.drowsy_sensor_fusion_events_extended_event_history ?? {};
  eventHistoryEl.innerHTML = "";

  const root = document.createElement("div");
  root.className = "telemetry-json-tree";

  if (extdEh && typeof extdEh === "object") {
    root.appendChild(createJsonBranchNode(extdEh));
  } else {
    root.appendChild(createJsonPrimitiveNode(extdEh));
  }

  eventHistoryEl.appendChild(root);
}

export function createTelemetryGraphs({
  laneChartEl,
  inertialChartEl,
  yawChartEl,
  eventHistoryEl,
  laneValueEl,
  lateralValueEl,
  drivingValueEl,
  yawValueEl,
  smoothSliderEl,
  smoothValueEl,
  yawSmoothSliderEl,
  yawSmoothValueEl,
}) {
  let telemetryModel = null;
  let laneChart = null;
  let inertialChart = null;
  let yawChart = null;
  let lastTelemetryDrawMs = 0;
  let playheadRafId = null;
  let pendingPlayheadTime = 0;
  let smoothedAccYByWindow = null;
  let smoothedAccZByWindow = null;
  let smoothedYawByWindow = null;

  function setTelemetryValues(lane, accY, accZ, yaw) {
    if (laneValueEl) laneValueEl.textContent = `PIL: ${fmtSigned(lane, 3)}`;
    if (lateralValueEl) lateralValueEl.textContent = `Acc Y: ${fmtSigned(accY, 3)}`;
    if (drivingValueEl) drivingValueEl.textContent = `Acc Z: ${fmtSigned(accZ, 3)}`;
    if (yawValueEl) yawValueEl.textContent = `Yaw: ${fmtSigned(yaw, 3)}`;
  }

  function drawPlayhead(t) {
    if (laneChart && window.Plotly && laneChartEl) {
      window.Plotly.relayout(laneChartEl, {
        "shapes[0].x0": t,
        "shapes[0].x1": t,
      });
    }
    if (inertialChart && window.Plotly && inertialChartEl) {
      window.Plotly.relayout(inertialChartEl, {
        "shapes[0].x0": t,
        "shapes[0].x1": t,
      });
    }
    if (yawChart && window.Plotly && yawChartEl) {
      window.Plotly.relayout(yawChartEl, {
        "shapes[0].x0": t,
        "shapes[0].x1": t,
      });
    }
  }

  function schedulePlayheadDraw(t) {
    pendingPlayheadTime = t;
    if (playheadRafId !== null) return;
    playheadRafId = requestAnimationFrame(() => {
      playheadRafId = null;
      drawPlayhead(pendingPlayheadTime);
    });
  }

  function destroy() {
    if (playheadRafId !== null) {
      cancelAnimationFrame(playheadRafId);
      playheadRafId = null;
    }
    if (window.Plotly) {
      if (laneChart && laneChartEl) window.Plotly.purge(laneChartEl);
      if (inertialChart && inertialChartEl) window.Plotly.purge(inertialChartEl);
      if (yawChart && yawChartEl) window.Plotly.purge(yawChartEl);
    }
    laneChart = null;
    inertialChart = null;
    yawChart = null;
    telemetryModel = null;
    smoothedAccYByWindow = null;
    smoothedAccZByWindow = null;
    smoothedYawByWindow = null;
    if (eventHistoryEl) eventHistoryEl.innerHTML = "";
    setTelemetryValues(null, null, null, null);
    if (smoothSliderEl) {
      smoothSliderEl.disabled = true;
      smoothSliderEl.value = String(DEFAULT_SMOOTHING_INDEX);
    }
    if (smoothValueEl) smoothValueEl.textContent = String(SMOOTHING_WINDOWS[DEFAULT_SMOOTHING_INDEX]);
    if (yawSmoothSliderEl) {
      yawSmoothSliderEl.disabled = true;
      yawSmoothSliderEl.value = String(DEFAULT_SMOOTHING_INDEX);
    }
    if (yawSmoothValueEl) yawSmoothValueEl.textContent = String(SMOOTHING_WINDOWS[DEFAULT_SMOOTHING_INDEX]);
  }

  function initFromMetadata(metadata, initialTimeSec = 0) {
    destroy();
    renderExtendedEventHistory(metadata, eventHistoryEl);

    telemetryModel = buildTelemetryModel(metadata);
    if (!telemetryModel || !window.Plotly || !laneChartEl || !inertialChartEl || !yawChartEl) return;

    const inertialRange = computeRobustYRange([telemetryModel.accY, telemetryModel.accZ], -10, 10);
    const yawRange = computeRobustYRange([telemetryModel.yawSeries], -3, 3);

    const laneTrace = {
      type: "scattergl",
      mode: "lines",
      name: "PIL Corrected",
      x: telemetryModel.laneSeries.map(p => p.x),
      y: telemetryModel.laneSeries.map(p => p.y),
      line: { color: "#00e5ff", width: 1.8 },
      hovertemplate: "t=%{x:.2f}s<br>PIL=%{y:.4f}<extra></extra>",
    };

    const accYTrace = {
      type: "scattergl",
      mode: "lines",
      name: "Acc Y (Lateral)",
      x: telemetryModel.accY.map(p => p.x),
      y: telemetryModel.accY.map(p => p.y),
      line: { color: "#2ecc71", width: 1.8 },
      hovertemplate: "t=%{x:.2f}s<br>AccY=%{y:.4f}<extra></extra>",
    };

    const accZTrace = {
      type: "scattergl",
      mode: "lines",
      name: "Acc Z (Driving)",
      x: telemetryModel.accZ.map(p => p.x),
      y: telemetryModel.accZ.map(p => p.y),
      line: { color: "#e74c3c", width: 1.8 },
      hovertemplate: "t=%{x:.2f}s<br>AccZ=%{y:.4f}<extra></extra>",
    };

    const yawTrace = {
      type: "scattergl",
      mode: "lines",
      name: "Yaw",
      x: telemetryModel.yawSeries.map(p => p.x),
      y: telemetryModel.yawSeries.map(p => p.y),
      line: { color: "#4da3ff", width: 1.8 },
      hovertemplate: "t=%{x:.2f}s<br>Yaw=%{y:.4f}<extra></extra>",
    };

    smoothedAccYByWindow = Object.fromEntries(
      SMOOTHING_WINDOWS.map(w => [w, smoothSeriesY(telemetryModel.accY, w)]),
    );
    smoothedAccZByWindow = Object.fromEntries(
      SMOOTHING_WINDOWS.map(w => [w, smoothSeriesY(telemetryModel.accZ, w)]),
    );
    smoothedYawByWindow = Object.fromEntries(
      SMOOTHING_WINDOWS.map(w => [w, smoothSeriesY(telemetryModel.yawSeries, w)]),
    );

    const cfg = { displayModeBar: false, responsive: true, staticPlot: false };
    const alertShapes = getAllAlertShapes(
      metadata,
      telemetryModel.xMax,
      telemetryModel.mergedAlertConfig,
      telemetryModel.customEvents,
    );
    const laneAlertHoverTraces = getAllAlertHoverTraces(
      metadata,
      telemetryModel.xMax,
      -0.5,
      0.5,
      telemetryModel.mergedAlertConfig,
      telemetryModel.customEvents,
    );

    window.Plotly.react(
      laneChartEl,
      [laneTrace, ...laneAlertHoverTraces],
      plotLayout("Lane Offset", telemetryModel.xMax, -0.5, 0.5, [
        {
          type: "line",
          x0: 0,
          x1: telemetryModel.xMax,
          y0: 0.2,
          y1: 0.2,
          line: { color: "rgba(0, 229, 255, 0.5)", width: 1.2, dash: "dot" },
        },
        {
          type: "line",
          x0: 0,
          x1: telemetryModel.xMax,
          y0: -0.2,
          y1: -0.2,
          line: { color: "rgba(0, 229, 255, 0.5)", width: 1.2, dash: "dot" },
        },
        ...alertShapes,
      ]),
      cfg,
    );
    window.Plotly.react(
      inertialChartEl,
      [accYTrace, accZTrace],
      plotLayout("Acceleration", telemetryModel.xMax, inertialRange.min, inertialRange.max),
      cfg,
    );
    window.Plotly.react(
      yawChartEl,
      [yawTrace],
      plotLayout("Yaw", telemetryModel.xMax, yawRange.min, yawRange.max),
      cfg,
    );

    laneChart = true;
    inertialChart = true;
    yawChart = true;

    if (smoothSliderEl) {
      smoothSliderEl.max = String(SMOOTHING_WINDOWS.length - 1);
      smoothSliderEl.value = String(DEFAULT_SMOOTHING_INDEX);
      smoothSliderEl.disabled = false;
    }
    if (smoothValueEl) smoothValueEl.textContent = String(SMOOTHING_WINDOWS[DEFAULT_SMOOTHING_INDEX]);
    if (yawSmoothSliderEl) {
      yawSmoothSliderEl.max = String(SMOOTHING_WINDOWS.length - 1);
      yawSmoothSliderEl.value = String(DEFAULT_SMOOTHING_INDEX);
      yawSmoothSliderEl.disabled = false;
    }
    if (yawSmoothValueEl) yawSmoothValueEl.textContent = String(SMOOTHING_WINDOWS[DEFAULT_SMOOTHING_INDEX]);

    applySmoothingByIndex(DEFAULT_SMOOTHING_INDEX);
    applyYawSmoothingByIndex(DEFAULT_SMOOTHING_INDEX);

    updateForTime(initialTimeSec, true);
  }

  function applySmoothingByIndex(index) {
    if (!inertialChart || !window.Plotly || !smoothedAccYByWindow || !smoothedAccZByWindow || !inertialChartEl) return;

    const idx = Math.max(0, Math.min(SMOOTHING_WINDOWS.length - 1, Number(index) || 0));
    const w = SMOOTHING_WINDOWS[idx];
    if (smoothValueEl) smoothValueEl.textContent = String(w);

    window.Plotly.restyle(
      inertialChartEl,
      { y: [smoothedAccYByWindow[w], smoothedAccZByWindow[w]] },
      [0, 1],
    );
  }

  function applyYawSmoothingByIndex(index) {
    if (!yawChart || !window.Plotly || !smoothedYawByWindow || !yawChartEl) return;

    const idx = Math.max(0, Math.min(SMOOTHING_WINDOWS.length - 1, Number(index) || 0));
    const w = SMOOTHING_WINDOWS[idx];
    if (yawSmoothValueEl) yawSmoothValueEl.textContent = String(w);

    window.Plotly.restyle(
      yawChartEl,
      { y: [smoothedYawByWindow[w]] },
      [0],
    );
  }

  function updateForTime(tSec, forceDraw = false) {
    if (!telemetryModel) return;

    const lane = interpolateSeries(telemetryModel.laneSeries, tSec);
    const accY = interpolateSeries(telemetryModel.accY, tSec);
    const accZ = interpolateSeries(telemetryModel.accZ, tSec);
    const yaw = interpolateSeries(telemetryModel.yawSeries, tSec);
    setTelemetryValues(lane, accY, accZ, yaw);

    const now = performance.now();
    if (!forceDraw && now - lastTelemetryDrawMs < (1000 / TELEMETRY_PLAYHEAD_FPS)) return;
    lastTelemetryDrawMs = now;

    if (forceDraw) drawPlayhead(tSec);
    else schedulePlayheadDraw(tSec);
  }

  return {
    destroy,
    initFromMetadata,
    applySmoothingByIndex,
    applyYawSmoothingByIndex,
    updateForTime,
  };
}
