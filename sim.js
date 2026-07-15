/* =============================================================================
   sim.js
   -----------------------------------------------------------------------------
   Illusztratív lakossági hitelkockázati stressztest -- fut kizárólag a
   böngészőben, szerver nélkül. NEM valódi bankfelügyeleti modell: a
   ügyfélszintű DSTI-eloszlás szintetikusan generált (lognormális), az
   alapkamat -> törlesztőrészlet átgyűrűzés pedig egyszerűsített, lineáris
   közelítés. A pontos módszertan a lapon, a "Módszertan" dobozban olvasható.
============================================================================= */

(function () {
  "use strict";

  const N = 4000;          // szintetikus ügyfélszám a portfólióban
  const MEDIAN_DSTI = 32;  // medián induló DSTI (%) -- feltételezés
  const SIGMA = 0.38;      // lognormális eloszlás szórásparamétere
  const CURRENT_POLICY_RATE = 6.5;

  // --- Determinisztikus PRNG (mulberry32), hogy az oldal minden betöltésnél
  //     ugyanazt a szintetikus portfóliót adja -------------------------------
  function mulberry32(seed) {
    return function () {
      seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
      let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  const rand = mulberry32(20260701);
  function randNormal() {
    const u1 = Math.max(rand(), 1e-9);
    const u2 = rand();
    return Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
  }

  // --- Szintetikus induló portfólió (DSTI0 minden ügyfélre) ------------------
  const DSTI0 = new Float64Array(N);
  for (let i = 0; i < N; i++) {
    const z = randNormal();
    let v = MEDIAN_DSTI * Math.exp(SIGMA * z);
    DSTI0[i] = Math.min(Math.max(v, 4), 95);
  }

  // --- Állapot / vezérlők -----------------------------------------------------
  const els = {
    deltaR: document.getElementById("ctrl-deltaR"),
    variableShare: document.getElementById("ctrl-variableShare"),
    sensitivity: document.getElementById("ctrl-sensitivity"),
    threshold: document.getElementById("ctrl-threshold"),
  };
  const valEls = {
    deltaR: document.getElementById("val-deltaR"),
    variableShare: document.getElementById("val-variableShare"),
    sensitivity: document.getElementById("val-sensitivity"),
    threshold: document.getElementById("val-threshold"),
  };
  const resultEls = {
    effRate: document.getElementById("res-effRate"),
    stressedPct: document.getElementById("res-stressedPct"),
    avgDSTI: document.getElementById("res-avgDSTI"),
    deltaVsBase: document.getElementById("res-deltaVsBase"),
  };

  function computeNewDSTI(deltaR, variableSharePct, sensitivityPct) {
    const mult = 1 + (variableSharePct / 100) * (sensitivityPct / 100) * deltaR;
    const out = new Float64Array(N);
    for (let i = 0; i < N; i++) out[i] = DSTI0[i] * mult;
    return out;
  }

  function stressedShare(newDSTI, threshold) {
    let c = 0;
    for (let i = 0; i < N; i++) if (newDSTI[i] > threshold) c++;
    return (100 * c) / N;
  }

  function baselineStressedShare(variableSharePct, sensitivityPct, threshold) {
    const base = computeNewDSTI(0, variableSharePct, sensitivityPct);
    return stressedShare(base, threshold);
  }

  const GOLD = "#C9A24B", RUST = "#B4552D", TEAL = "#4E8B7C";
  const INK = "#0E1B2C", PAPER = "#F3EFE4", PAPER_DIM = "#B9BFC9", INK_LINE = "#2B3E56";
  const FONT = { family: "IBM Plex Mono, monospace", color: PAPER_DIM, size: 11 };

  function baseLayout(extra) {
    return Object.assign({
      paper_bgcolor: INK,
      plot_bgcolor: INK,
      font: FONT,
      margin: { l: 44, r: 16, t: 10, b: 36 },
      showlegend: false,
    }, extra || {});
  }

  let histDrawn = false, curveDrawn = false;

  function drawHistogram(newDSTI, threshold) {
    const trace = {
      x: Array.from(newDSTI),
      type: "histogram",
      xbins: { start: 0, end: 100, size: 3 },
      marker: { color: GOLD, opacity: 0.85 },
      name: "Ügyfelek",
    };
    const layout = baseLayout({
      height: 250,
      xaxis: { title: "DSTI (%)", gridcolor: INK_LINE, zerolinecolor: INK_LINE, range: [0, 100] },
      yaxis: { title: "Ügyfélszám", gridcolor: INK_LINE, zerolinecolor: INK_LINE },
      shapes: [{
        type: "line", x0: threshold, x1: threshold, y0: 0, y1: 1, yref: "paper",
        line: { color: RUST, width: 2, dash: "dot" },
      }],
      annotations: [{
        x: threshold, y: 1, yref: "paper", yanchor: "bottom", showarrow: false,
        text: "küszöb", font: { color: RUST, size: 10, family: FONT.family },
      }],
    });
    if (!histDrawn) {
      Plotly.newPlot("sim-histogram", [trace], layout, { displaylogo: false, responsive: true });
      histDrawn = true;
    } else {
      Plotly.react("sim-histogram", [trace], layout, { displaylogo: false, responsive: true });
    }
  }

  function drawSensitivityCurve(variableSharePct, sensitivityPct, threshold, currentDeltaR) {
    const xs = [];
    for (let d = -3; d <= 6.001; d += 0.25) xs.push(Math.round(d * 100) / 100);
    const ys = xs.map((d) => stressedShare(computeNewDSTI(d, variableSharePct, sensitivityPct), threshold));

    const curve = {
      x: xs, y: ys, type: "scatter", mode: "lines",
      line: { color: TEAL, width: 2.5 },
      name: "Stresszben (%)",
    };
    const marker = {
      x: [currentDeltaR],
      y: [stressedShare(computeNewDSTI(currentDeltaR, variableSharePct, sensitivityPct), threshold)],
      type: "scatter", mode: "markers",
      marker: { color: GOLD, size: 11, line: { color: PAPER, width: 1 } },
      name: "Jelenlegi forgatókönyv",
    };
    const layout = baseLayout({
      height: 250,
      xaxis: { title: "Alapkamat-változás (pp)", gridcolor: INK_LINE, zerolinecolor: INK_LINE },
      yaxis: { title: "Stresszben lévő ügyfelek (%)", gridcolor: INK_LINE, zerolinecolor: INK_LINE, rangemode: "tozero" },
    });
    if (!curveDrawn) {
      Plotly.newPlot("sim-curve", [curve, marker], layout, { displaylogo: false, responsive: true });
      curveDrawn = true;
    } else {
      Plotly.react("sim-curve", [curve, marker], layout, { displaylogo: false, responsive: true });
    }
  }

  function render() {
    const deltaR = parseFloat(els.deltaR.value);
    const variableShare = parseFloat(els.variableShare.value);
    const sensitivity = parseFloat(els.sensitivity.value);
    const threshold = parseFloat(els.threshold.value);

    valEls.deltaR.textContent = (deltaR > 0 ? "+" : "") + deltaR.toFixed(2) + " pp";
    valEls.variableShare.textContent = variableShare.toFixed(0) + "%";
    valEls.sensitivity.textContent = sensitivity.toFixed(1) + "%/pp";
    valEls.threshold.textContent = threshold.toFixed(0) + "%";

    const newDSTI = computeNewDSTI(deltaR, variableShare, sensitivity);
    const stressedPct = stressedShare(newDSTI, threshold);
    const basePct = baselineStressedShare(variableShare, sensitivity, threshold);
    const avgDSTI = newDSTI.reduce((a, b) => a + b, 0) / N;
    const effRate = CURRENT_POLICY_RATE + deltaR;

    resultEls.effRate.textContent = effRate.toFixed(2) + "%";
    resultEls.stressedPct.textContent = stressedPct.toFixed(1) + "%";
    resultEls.avgDSTI.textContent = avgDSTI.toFixed(1) + "%";
    const diff = stressedPct - basePct;
    resultEls.deltaVsBase.textContent = (diff >= 0 ? "+" : "") + diff.toFixed(1) + " pp";

    resultEls.stressedPct.classList.remove("flag-high", "flag-ok");
    resultEls.stressedPct.classList.add(stressedPct >= 25 ? "flag-high" : "flag-ok");

    drawHistogram(newDSTI, threshold);
    drawSensitivityCurve(variableShare, sensitivity, threshold, deltaR);
  }

  Object.values(els).forEach((el) => el.addEventListener("input", render));

  document.getElementById("sim-reset").addEventListener("click", function () {
    els.deltaR.value = 0;
    els.variableShare.value = 60;
    els.sensitivity.value = 7;
    els.threshold.value = 40;
    render();
  });

  document.addEventListener("DOMContentLoaded", render);
  if (document.readyState !== "loading") render();
})();
