function createJsonToken(className, text) {
  const span = document.createElement("span");
  span.className = className;
  span.textContent = text;
  return span;
}

function getPathSegments(path) {
  return String(path || "").trim().match(/[^.[\]]+/g) || [];
}

function getValueAtPath(root, path) {
  const segments = getPathSegments(path);
  if (!segments.length) return { found: true, value: root };

  let current = root;
  for (const segment of segments) {
    if (current == null) return { found: false, value: null };
    if (Array.isArray(current) && /^\d+$/.test(segment)) {
      const index = Number(segment);
      if (index < 0 || index >= current.length) return { found: false, value: null };
      current = current[index];
      continue;
    }
    if (typeof current !== "object" || !(segment in current)) return { found: false, value: null };
    current = current[segment];
  }

  return { found: true, value: current };
}

function shouldConvertEpochValue(key, value, startTimeMs) {
  if (!Number.isFinite(value) || !Number.isFinite(startTimeMs)) return false;

  const keyText = String(key || "").toLowerCase();
  const looksLikeTimeKey = /(^ts$|time|timestamp|epoch)/.test(keyText);
  const closeToStartTime = Math.abs(value - startTimeMs) <= 24 * 60 * 60 * 1000;
  const looksLikeEpochMs = Math.abs(value) >= 1e11;
  return (looksLikeTimeKey && looksLikeEpochMs) || closeToStartTime;
}

function roundRelativeSeconds(value, startTimeMs) {
  return Math.round(((value - startTimeMs) / 1000) * 1000) / 1000;
}

function transformEpochsToRelativeSeconds(value, startTimeMs, key = "") {
  if (!Number.isFinite(startTimeMs)) return value;

  if (Array.isArray(value)) {
    return value.map((item, index) => transformEpochsToRelativeSeconds(item, startTimeMs, String(index)));
  }

  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([childKey, childValue]) => [
        childKey,
        transformEpochsToRelativeSeconds(childValue, startTimeMs, childKey),
      ]),
    );
  }

  if (shouldConvertEpochValue(key, value, startTimeMs)) {
    return roundRelativeSeconds(value, startTimeMs);
  }

  return value;
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

export function renderExtendedEventHistory(metadata, eventHistoryEl, options = {}) {
  if (!eventHistoryEl) return;

  const { path = "", relativeTimes = false } = options;

  eventHistoryEl.innerHTML = "";

  const empty = document.createElement("div");
  empty.className = "telemetry-json-empty";

  if (!metadata || typeof metadata !== "object") {
    empty.textContent = "No metadata loaded.";
    eventHistoryEl.appendChild(empty);
    return;
  }

  const { found, value } = getValueAtPath(metadata, path);

  if (!found) {
    empty.textContent = `Path not found: ${path}`;
    eventHistoryEl.appendChild(empty);
    return;
  }

  const startTimeMs = Number(metadata?.startTime);
  const displayValue = relativeTimes
    ? transformEpochsToRelativeSeconds(value, startTimeMs)
    : value;

  const root = document.createElement("div");
  root.className = "telemetry-json-tree";

  if (displayValue && typeof displayValue === "object") {
    root.appendChild(createJsonBranchNode(displayValue));
  } else {
    root.appendChild(createJsonPrimitiveNode(displayValue));
  }

  eventHistoryEl.appendChild(root);
}
