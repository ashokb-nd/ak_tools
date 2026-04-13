import { TELEMETRY_MAX_POINTS } from "./constants.js";
import { buildMergedAlertConfig, createCustomEvents } from "./events.js";

export function fmtSigned(value, digits = 3) {
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

export function smoothSeriesY(series, windowSize) {
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

function parseHeadPoseSeries(metadata, startEpochMs) {
  const detections = metadata?.inference_data?.dms?.detections;
  if (!Array.isArray(detections)) {
    return {
      headPitchSeries: [],
      headYawSeries: [],
      headRollSeries: [],
    };
  }

  const headPitchSeries = [];
  const headYawSeries = [];
  const headRollSeries = [];

  detections.forEach((det, idx) => {
    const headPyr = det?.head_pyr;
    if (
      !Array.isArray(headPyr)
      || headPyr.length !== 3
      || !headPyr.every(v => Number.isFinite(Number(v)))
    ) {
      return;
    }

    const tsRaw = Number(det?.ts);
    if (!(tsRaw > 1e11)) return;
    const x = (tsRaw - startEpochMs) / 1000;

    const pitch = Number(headPyr[0]);
    const yaw = Number(headPyr[1]);
    const roll = Number(headPyr[2]);
    headPitchSeries.push({ x, y: pitch });
    headYawSeries.push({ x, y: yaw });
    headRollSeries.push({ x, y: roll });
  });

  return {
    headPitchSeries: downsampleSeries(headPitchSeries),
    headYawSeries: downsampleSeries(headYawSeries),
    headRollSeries: downsampleSeries(headRollSeries),
  };
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
  const allSeries = [
    model.laneSeries,
    model.accY,
    model.accZ,
    model.yawSeries,
    model.headPitchSeries,
    model.headYawSeries,
    model.headRollSeries,
  ];
  let maxX = 0;
  for (const series of allSeries) {
    if (!Array.isArray(series) || !series.length) continue;
    const last = series[series.length - 1];
    if (Number.isFinite(last?.x) && last.x > maxX) maxX = last.x;
  }
  return Math.max(1, Math.round(maxX));
}

export function buildTelemetryModel(metadata) {
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
  const headPose = parseHeadPoseSeries(metadata, startEpochMs);
  const customEvents = createCustomEvents(metadata).filter(event => event?.isValid?.());

  if (
    !laneSeries.length
    && !accY.length
    && !accZ.length
    && !yawSeries.length
    && !headPose.headPitchSeries.length
    && !headPose.headYawSeries.length
    && !headPose.headRollSeries.length
  ) {
    return null;
  }

  const mergedAlertConfig = buildMergedAlertConfig(customEvents);
  const model = {
    laneSeries,
    accY,
    accZ,
    yawSeries,
    headPitchSeries: headPose.headPitchSeries,
    headYawSeries: headPose.headYawSeries,
    headRollSeries: headPose.headRollSeries,
    startEpochMs,
    customEvents,
    mergedAlertConfig,
  };
  model.xMax = computeMaxX(model);
  return model;
}

export function computeRobustYRange(seriesList, fallbackMin, fallbackMax) {
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

export function interpolateSeries(series, tSec) {
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
