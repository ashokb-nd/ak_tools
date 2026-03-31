import {
  DEFAULT_SMOOTHING_INDEX,
  SMOOTHING_WINDOWS,
  TELEMETRY_PLAYHEAD_FPS,
} from "./constants.js";
import {
  buildTelemetryModel,
  computeRobustYRange,
  fmtSigned,
  interpolateSeries,
  smoothSeriesY,
} from "./model.js";
import { getAllAlertHoverTraces, getAllAlertShapes } from "./events.js";
import { plotLayout } from "./plot.js";
import { renderExtendedEventHistory } from "./json-view.js";

export function createTelemetryGraphs({
  laneChartEl,
  inertialChartEl,
  yawChartEl,
  eventHistoryEl,
  eventHistoryPathEl,
  eventHistoryRelativeTimeEl,
  eventHistoryKeepOpenEl,
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
  let currentMetadata = null;

  function renderMetadataViewer() {
    renderExtendedEventHistory(currentMetadata, eventHistoryEl, {
      path: eventHistoryPathEl?.value?.trim() || "",
      relativeTimes: Boolean(eventHistoryRelativeTimeEl?.checked),
      keepOpen: Boolean(eventHistoryKeepOpenEl?.checked),
    });
  }

  if (eventHistoryPathEl) {
    eventHistoryPathEl.addEventListener("input", () => {
      renderMetadataViewer();
    });
  }

  if (eventHistoryRelativeTimeEl) {
    eventHistoryRelativeTimeEl.addEventListener("change", () => {
      renderMetadataViewer();
    });
  }

  if (eventHistoryKeepOpenEl) {
    eventHistoryKeepOpenEl.addEventListener("change", () => {
      renderMetadataViewer();
    });
  }

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
    currentMetadata = null;
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
    currentMetadata = metadata;
    renderMetadataViewer();

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
