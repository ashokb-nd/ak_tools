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

export function renderExtendedEventHistory(metadata, eventHistoryEl) {
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
