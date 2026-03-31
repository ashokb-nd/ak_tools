export function plotLayout(yLabel, xMax = 1, yMin = undefined, yMax = undefined, extraShapes = []) {
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
