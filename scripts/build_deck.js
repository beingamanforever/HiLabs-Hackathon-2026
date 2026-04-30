// Team Byelabs - HiLabs Hackathon 2026 pitch deck
const pptxgen = require("pptxgenjs");

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
pres.author = "Team Byelabs";
pres.title = "R3 Provider Directory Accuracy Engine";
pres.company = "Team Byelabs";

// Palette
const C = {
  bg: "FFFFFF",
  ink: "0F172A",         // near-black text
  body: "334155",        // slate body
  muted: "64748B",       // muted captions
  rule: "E2E8F0",        // light divider
  card: "F8FAFC",        // soft card bg
  accent: "2563EB",      // deep blue
  accentSoft: "DBEAFE",  // light blue
  good: "16A34A",        // emerald positive
  goodSoft: "DCFCE7",    // light emerald
  warn: "B91C1C",        // red for floor line
  outline: "CBD5E1",
};

const SLIDE_W = 13.333;
const SLIDE_H = 7.5;

const FONT_HEAD = "Calibri";
const FONT_BODY = "Calibri";

// ----- helpers -----
function addPageNumber(slide, n, total) {
  slide.addText(`${n} / ${total}`, {
    x: SLIDE_W - 1.2, y: SLIDE_H - 0.45, w: 0.9, h: 0.3,
    fontFace: FONT_BODY, fontSize: 9, color: C.muted, align: "right", margin: 0,
  });
  slide.addText("Team Byelabs", {
    x: 0.5, y: SLIDE_H - 0.45, w: 4, h: 0.3,
    fontFace: FONT_BODY, fontSize: 9, color: C.muted, align: "left", margin: 0,
  });
}

function addTitle(slide, kicker, title) {
  if (kicker) {
    slide.addText(kicker.toUpperCase(), {
      x: 0.6, y: 0.45, w: 12, h: 0.3,
      fontFace: FONT_BODY, fontSize: 10, bold: true, charSpacing: 4,
      color: C.accent, align: "left", margin: 0,
    });
  }
  slide.addText(title, {
    x: 0.6, y: kicker ? 0.78 : 0.55, w: 12, h: 0.7,
    fontFace: FONT_HEAD, fontSize: 28, bold: true, color: C.ink, align: "left", margin: 0,
  });
}

const TOTAL = 10;

// ============ Slide 1: Cover ============
{
  const s = pres.addSlide();
  s.background = { color: C.bg };

  // Left rail accent
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: 0.18, h: SLIDE_H, fill: { color: C.accent }, line: { type: "none" },
  });

  s.addText("HILABS HACKATHON 2026", {
    x: 0.9, y: 1.1, w: 10, h: 0.35,
    fontFace: FONT_BODY, fontSize: 11, bold: true, charSpacing: 6,
    color: C.accent, margin: 0,
  });

  s.addText("R3 Provider Directory", {
    x: 0.9, y: 1.55, w: 12, h: 0.95,
    fontFace: FONT_HEAD, fontSize: 48, bold: true, color: C.ink, margin: 0,
  });
  s.addText("Accuracy Engine", {
    x: 0.9, y: 2.45, w: 12, h: 0.95,
    fontFace: FONT_HEAD, fontSize: 48, bold: true, color: C.accent, margin: 0,
  });

  s.addShape(pres.shapes.LINE, {
    x: 0.9, y: 3.55, w: 1.2, h: 0,
    line: { color: C.ink, width: 2 },
  });

  s.addText("Team Byelabs", {
    x: 0.9, y: 3.7, w: 12, h: 0.4,
    fontFace: FONT_HEAD, fontSize: 18, bold: true, color: C.ink, margin: 0,
  });

  s.addText(
    "A conservative post-R3 layer that lifts directory accuracy from 50.62% to 61.82% with zero agreement-zone changes and a 95% conformal precision bound.",
    {
      x: 0.9, y: 4.25, w: 11.5, h: 1.1,
      fontFace: FONT_BODY, fontSize: 16, color: C.body, margin: 0, italic: true,
    }
  );

  // Stat strip
  const stats = [
    { k: "+11.20 pp", v: "Accuracy lift" },
    { k: "0", v: "Agreement-zone changes" },
    { k: "95%", v: "Conformal precision bound" },
    { k: "$142.76", v: "Total run cost" },
  ];
  const stripY = 5.7;
  const stripX = 0.9;
  const cardW = 2.85;
  const gap = 0.18;
  stats.forEach((stat, i) => {
    const x = stripX + i * (cardW + gap);
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: stripY, w: cardW, h: 1.05,
      fill: { color: C.card }, line: { color: C.rule, width: 0.75 },
    });
    s.addText(stat.k, {
      x, y: stripY + 0.1, w: cardW, h: 0.5,
      fontFace: FONT_HEAD, fontSize: 22, bold: true, color: C.accent, align: "center", margin: 0,
    });
    s.addText(stat.v, {
      x, y: stripY + 0.6, w: cardW, h: 0.4,
      fontFace: FONT_BODY, fontSize: 11, color: C.muted, align: "center", margin: 0,
    });
  });

  s.addText("April 2026", {
    x: 0.9, y: SLIDE_H - 0.55, w: 5, h: 0.3,
    fontFace: FONT_BODY, fontSize: 10, color: C.muted, margin: 0,
  });
}

// ============ Slide 2: The Problem ============
{
  const s = pres.addSlide();
  s.background = { color: C.bg };
  addTitle(s, "The Problem", "Reconciling R3's two baselines reveals the real accuracy gap.");

  s.addText(
    "Provider directories drift constantly. R3 performs well overall, but its disagreements with Calling QC hide most of the lost accuracy. We focus on the Call-QC slice — the 50.62% — and close it without disturbing what already agrees.",
    {
      x: 0.6, y: 1.7, w: 7.4, h: 1.4,
      fontFace: FONT_BODY, fontSize: 13, color: C.body, margin: 0,
    }
  );

  // Reconciliation table
  const tableData = [
    [
      { text: "Baseline slice", options: { bold: true, color: "FFFFFF", fill: { color: C.ink }, fontFace: FONT_HEAD, fontSize: 12 } },
      { text: "Reported accuracy", options: { bold: true, color: "FFFFFF", fill: { color: C.ink }, fontFace: FONT_HEAD, fontSize: 12, align: "center" } },
      { text: "Source", options: { bold: true, color: "FFFFFF", fill: { color: C.ink }, fontFace: FONT_HEAD, fontSize: 12 } },
    ],
    [
      { text: "R3 overall", options: { fontFace: FONT_BODY, fontSize: 11, color: C.ink } },
      { text: "~75%", options: { align: "center", fontFace: FONT_HEAD, fontSize: 12, bold: true, color: C.ink } },
      { text: "Problem statement", options: { fontFace: FONT_BODY, fontSize: 11, color: C.muted } },
    ],
    [
      { text: "Web-verified slice only", options: { fontFace: FONT_BODY, fontSize: 11, color: C.ink } },
      { text: "~90%", options: { align: "center", fontFace: FONT_HEAD, fontSize: 12, bold: true, color: C.good } },
      { text: "Web QC sample", options: { fontFace: FONT_BODY, fontSize: 11, color: C.muted } },
    ],
    [
      { text: "Call-QC-verified slice", options: { fontFace: FONT_BODY, fontSize: 11, color: C.ink, bold: true, fill: { color: C.accentSoft } } },
      { text: "50.62%", options: { align: "center", fontFace: FONT_HEAD, fontSize: 13, bold: true, color: C.accent, fill: { color: C.accentSoft } } },
      { text: "The gap we close", options: { fontFace: FONT_BODY, fontSize: 11, color: C.accent, italic: true, fill: { color: C.accentSoft } } },
    ],
  ];
  s.addTable(tableData, {
    x: 0.6, y: 3.2, w: 7.4, colW: [2.6, 2.0, 2.8],
    rowH: 0.45, border: { type: "solid", pt: 0.5, color: C.rule },
    align: "left", valign: "middle", margin: 0.08,
  });

  // Right-side constraints panel
  const px = 8.4, py = 1.7, pw = 4.4, ph = 4.7;
  s.addShape(pres.shapes.RECTANGLE, {
    x: px, y: py, w: pw, h: ph, fill: { color: C.card }, line: { color: C.rule, width: 0.75 },
  });
  s.addText("Hard constraints", {
    x: px + 0.3, y: py + 0.25, w: pw - 0.6, h: 0.4,
    fontFace: FONT_HEAD, fontSize: 14, bold: true, color: C.ink, margin: 0,
  });
  const constraints = [
    { h: "Agreement zone preserved", b: "Rows where R3, Web QC, and Call QC concur are never relabeled." },
    { h: "Robocall budget capped", b: "At most 450 outbound calls across the entire dataset." },
    { h: "40% conclusivity assumption", b: "Only 4-in-10 robocalls return a usable verdict; budget rationed accordingly." },
    { h: "No Call-QC leakage", b: "Call QC is used for training and evaluation only — never as an inference feature." },
  ];
  let cy = py + 0.8;
  constraints.forEach((c) => {
    s.addShape(pres.shapes.OVAL, {
      x: px + 0.3, y: cy + 0.05, w: 0.18, h: 0.18,
      fill: { color: C.accent }, line: { type: "none" },
    });
    s.addText(c.h, {
      x: px + 0.6, y: cy - 0.02, w: pw - 0.8, h: 0.3,
      fontFace: FONT_HEAD, fontSize: 12, bold: true, color: C.ink, margin: 0,
    });
    s.addText(c.b, {
      x: px + 0.6, y: cy + 0.28, w: pw - 0.8, h: 0.6,
      fontFace: FONT_BODY, fontSize: 10.5, color: C.body, margin: 0,
    });
    cy += 1.0;
  });

  addPageNumber(s, 2, TOTAL);
}

// ============ Slide 3: System Overview ============
{
  const s = pres.addSlide();
  s.background = { color: C.bg };
  addTitle(s, "System Overview", "Three layers on top of R3 — we never replace it.");

  // Flow boxes
  const flow = [
    { t: "Base + Claims", c: "Base workbook + streamed claims; 60+ engineered features." },
    { t: "Track 1 — Discovery", c: "Six-archetype disagreement taxonomy and confusion analytics." },
    { t: "Track 2 — Passive", c: "Conformal-bounded label flips with zero marginal cost." },
    { t: "Track 3 — Triage", c: "LightGBM ranker selects ≤ 450 robocalls for active QC." },
    { t: "Submission", c: "predictions.csv + needs_active_review + audit logs." },
  ];

  const fy = 2.1;
  const fh = 1.85;
  const startX = 0.5;
  const totalW = SLIDE_W - 1.0;
  const arrowW = 0.35;
  const boxW = (totalW - arrowW * (flow.length - 1)) / flow.length;

  flow.forEach((f, i) => {
    const x = startX + i * (boxW + arrowW);
    const isAccent = i >= 1 && i <= 3;
    const fillCol = isAccent ? C.card : C.bg;
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: fy, w: boxW, h: fh,
      fill: { color: fillCol }, line: { color: isAccent ? C.accent : C.outline, width: isAccent ? 1.25 : 0.75 },
    });
    // top accent strip
    if (isAccent) {
      s.addShape(pres.shapes.RECTANGLE, {
        x, y: fy, w: boxW, h: 0.08, fill: { color: C.accent }, line: { type: "none" },
      });
    }
    s.addText(`Step ${i + 1}`, {
      x: x + 0.18, y: fy + 0.18, w: boxW - 0.36, h: 0.28,
      fontFace: FONT_BODY, fontSize: 9, bold: true, charSpacing: 3, color: C.muted, margin: 0,
    });
    s.addText(f.t, {
      x: x + 0.18, y: fy + 0.45, w: boxW - 0.36, h: 0.45,
      fontFace: FONT_HEAD, fontSize: 14, bold: true, color: C.ink, margin: 0,
    });
    s.addText(f.c, {
      x: x + 0.18, y: fy + 0.95, w: boxW - 0.36, h: fh - 1.05,
      fontFace: FONT_BODY, fontSize: 10, color: C.body, margin: 0,
    });

    // arrow between
    if (i < flow.length - 1) {
      const ax = x + boxW + 0.04;
      const ay = fy + fh / 2;
      s.addShape(pres.shapes.LINE, {
        x: ax, y: ay, w: arrowW - 0.08, h: 0,
        line: { color: C.accent, width: 1.5, endArrowType: "triangle" },
      });
    }
  });

  // Bottom highlight callout
  const cy = 4.6;
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.5, y: cy, w: SLIDE_W - 1.0, h: 1.85,
    fill: { color: C.card }, line: { color: C.rule, width: 0.5 },
  });
  s.addText("Pipeline is row-count agnostic", {
    x: 0.8, y: cy + 0.2, w: 7, h: 0.4,
    fontFace: FONT_HEAD, fontSize: 16, bold: true, color: C.ink, margin: 0,
  });
  s.addText(
    "Today's dataset is 2,493 rows. Every component honours an eval_set_flag at runtime, so the same pipeline runs on a holdout of any size — no hard-coded counts, no slicing assumptions.",
    {
      x: 0.8, y: cy + 0.65, w: SLIDE_W - 1.6, h: 0.7,
      fontFace: FONT_BODY, fontSize: 12, color: C.body, margin: 0,
    }
  );

  // Three small chips
  const chips = ["eval_set_flag honoured", "Track 1/2/3 reproducible", "Calling QC never an input"];
  let chipX = 0.8;
  chips.forEach((c) => {
    const w = c.length * 0.09 + 0.5;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: chipX, y: cy + 1.4, w, h: 0.32, fill: { color: C.accentSoft },
      line: { color: C.accent, width: 0.5 }, rectRadius: 0.05,
    });
    s.addText(c, {
      x: chipX, y: cy + 1.4, w, h: 0.32,
      fontFace: FONT_BODY, fontSize: 10, bold: true, color: C.accent, align: "center", valign: "middle", margin: 0,
    });
    chipX += w + 0.18;
  });

  addPageNumber(s, 3, TOTAL);
}

// ============ Slide 4: Track 1 — Discovery ============
{
  const s = pres.addSlide();
  s.background = { color: C.bg };
  addTitle(s, "Track 1 — Discovery", "A six-archetype taxonomy explains where R3 and Calling QC diverge.");

  s.addText(
    "Of 2,493 rows, 1,231 disagree between R3 and Calling QC. We bucket every disagreement into one of six archetypes; the four largest drive 80% of recoverable accuracy.",
    {
      x: 0.6, y: 1.65, w: 12, h: 0.7,
      fontFace: FONT_BODY, fontSize: 13, color: C.body, margin: 0,
    }
  );

  const head = (t) => ({
    text: t,
    options: { bold: true, color: "FFFFFF", fill: { color: C.ink }, fontFace: FONT_HEAD, fontSize: 12 },
  });
  const row = (a, b, c, hl = false) => [
    { text: a, options: { fontFace: FONT_HEAD, fontSize: 11.5, bold: true, color: C.ink, fill: hl ? { color: C.card } : undefined } },
    { text: b, options: { align: "center", fontFace: FONT_HEAD, fontSize: 12, bold: true, color: C.accent, fill: hl ? { color: C.card } : undefined } },
    { text: c, options: { fontFace: FONT_BODY, fontSize: 10.5, color: C.body, fill: hl ? { color: C.card } : undefined } },
  ];

  const tableData = [
    [head("Archetype"), { text: "Rows", options: { bold: true, color: "FFFFFF", fill: { color: C.ink }, fontFace: FONT_HEAD, fontSize: 12, align: "center" } }, head("Resolution Strategy")],
    row(
      "False INACCURATE — no reliable web evidence",
      "412",
      "Conformal Org Consensus flip when org records and claims state agree; otherwise hold for Track 3."
    ),
    row(
      "Mid-score ambiguity (0.45–0.65)",
      "318",
      "Provider Signal Midscore Flip — fires only when claims are recent and telehealth risk is low.",
      true
    ),
    row(
      "Large-org multi-location confusion",
      "247",
      "Cluster by org_record_count and dominant_claim_share; route to Track 3 with high business gain."
    ),
    row(
      "Behavioral health telehealth floater",
      "159",
      "Do not robocall — conclusivity well below 40%. Hold for registry lookup downstream.",
      true
    ),
    row(
      "False ACCURATE — stale org site",
      "63",
      "Flagged via keep_r3_triage_candidate; not relabeled until Track 3 verdict arrives."
    ),
    row(
      "Other disagreement",
      "32",
      "Logged for manual audit; never auto-flipped."
    ),
  ];

  s.addTable(tableData, {
    x: 0.6, y: 2.55, w: 12.1, colW: [4.0, 1.2, 6.9],
    rowH: 0.55, border: { type: "solid", pt: 0.5, color: C.rule },
    valign: "middle", margin: 0.08,
  });

  // Footnote
  s.addText(
    "R3 vs Web QC agreement: 79.86%   |   R3 vs Call QC agreement: 50.62%   |   Disagreement rows analysed: 1,231",
    {
      x: 0.6, y: 6.6, w: 12.1, h: 0.3,
      fontFace: FONT_BODY, fontSize: 10, italic: true, color: C.muted, margin: 0,
    }
  );

  addPageNumber(s, 4, TOTAL);
}

// ============ Slide 5: Track 2 — Passive Correction ============
{
  const s = pres.addSlide();
  s.background = { color: C.bg };
  addTitle(s, "Track 2 — Passive Correction", "Two narrow flips, conformally bounded, zero marginal cost.");

  // Left: chart
  s.addChart(pres.charts.BAR, [
    {
      name: "Rows changed",
      labels: ["Conformal Org Consensus", "Provider Signal Midscore"],
      values: [111, 21],
    },
  ], {
    x: 0.6, y: 1.6, w: 6.6, h: 4.0,
    barDir: "bar",
    chartColors: [C.accent],
    chartArea: { fill: { color: "FFFFFF" }, roundedCorners: false },
    catAxisLabelColor: C.body, catAxisLabelFontSize: 10, catAxisLabelFontFace: FONT_BODY,
    valAxisLabelColor: C.muted, valAxisLabelFontSize: 9, valAxisLabelFontFace: FONT_BODY,
    valGridLine: { color: C.rule, size: 0.5 },
    catGridLine: { style: "none" },
    showValue: true,
    dataLabelPosition: "outEnd",
    dataLabelColor: C.ink,
    dataLabelFontSize: 11,
    dataLabelFontBold: true,
    showLegend: false,
    showTitle: true,
    title: "Rows changed per rule",
    titleFontFace: FONT_HEAD,
    titleColor: C.ink,
    titleFontSize: 13,
  });

  // Right: headline cards + conformal note
  const rx = 7.6, rw = 5.2;
  // Card 1: accuracy lift
  s.addShape(pres.shapes.RECTANGLE, {
    x: rx, y: 1.6, w: rw, h: 1.4, fill: { color: C.card }, line: { color: C.rule, width: 0.5 },
  });
  s.addText("Accuracy lift", {
    x: rx + 0.25, y: 1.7, w: rw - 0.5, h: 0.3,
    fontFace: FONT_BODY, fontSize: 11, color: C.muted, charSpacing: 3, bold: true, margin: 0,
  });
  s.addText("50.62% → 55.76%", {
    x: rx + 0.25, y: 2.0, w: rw - 0.5, h: 0.5,
    fontFace: FONT_HEAD, fontSize: 22, bold: true, color: C.ink, margin: 0,
  });
  s.addText("+5.13 pp net gain (grouped CV)", {
    x: rx + 0.25, y: 2.5, w: rw - 0.5, h: 0.4,
    fontFace: FONT_BODY, fontSize: 12, color: C.good, bold: true, margin: 0,
  });

  // Card 2: precision and rows
  s.addShape(pres.shapes.RECTANGLE, {
    x: rx, y: 3.1, w: rw / 2 - 0.05, h: 1.1, fill: { color: C.card }, line: { color: C.rule, width: 0.5 },
  });
  s.addText("Rows corrected", {
    x: rx + 0.2, y: 3.18, w: rw / 2 - 0.4, h: 0.3,
    fontFace: FONT_BODY, fontSize: 10, color: C.muted, charSpacing: 3, bold: true, margin: 0,
  });
  s.addText("132", {
    x: rx + 0.2, y: 3.45, w: rw / 2 - 0.4, h: 0.55,
    fontFace: FONT_HEAD, fontSize: 26, bold: true, color: C.accent, margin: 0,
  });

  s.addShape(pres.shapes.RECTANGLE, {
    x: rx + rw / 2 + 0.05, y: 3.1, w: rw / 2 - 0.05, h: 1.1, fill: { color: C.card }, line: { color: C.rule, width: 0.5 },
  });
  s.addText("Flip precision", {
    x: rx + rw / 2 + 0.25, y: 3.18, w: rw / 2 - 0.4, h: 0.3,
    fontFace: FONT_BODY, fontSize: 10, color: C.muted, charSpacing: 3, bold: true, margin: 0,
  });
  s.addText("97%", {
    x: rx + rw / 2 + 0.25, y: 3.45, w: rw / 2 - 0.4, h: 0.55,
    fontFace: FONT_HEAD, fontSize: 26, bold: true, color: C.good, margin: 0,
  });

  // Card 3: agreement zone
  s.addShape(pres.shapes.RECTANGLE, {
    x: rx, y: 4.3, w: rw, h: 1.3, fill: { color: C.goodSoft }, line: { color: C.good, width: 0.75 },
  });
  s.addText("Agreement-zone violations", {
    x: rx + 0.25, y: 4.4, w: rw - 0.5, h: 0.3,
    fontFace: FONT_BODY, fontSize: 11, color: C.good, charSpacing: 3, bold: true, margin: 0,
  });
  s.addText("0", {
    x: rx + 0.25, y: 4.65, w: rw - 0.5, h: 0.7,
    fontFace: FONT_HEAD, fontSize: 36, bold: true, color: C.good, margin: 0,
  });
  s.addText("Hard-asserted at write time", {
    x: rx + 1.3, y: 4.85, w: rw - 1.5, h: 0.4,
    fontFace: FONT_BODY, fontSize: 11, color: C.good, italic: true, margin: 0, valign: "middle",
  });

  // Conformal explainer (full width bottom)
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.6, y: 5.85, w: 12.2, h: 1.0, fill: { color: C.bg }, line: { color: C.accent, width: 1 },
  });
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.6, y: 5.85, w: 0.12, h: 1.0, fill: { color: C.accent }, line: { type: "none" },
  });
  s.addText("Conformal precision guard", {
    x: 0.95, y: 5.95, w: 11.5, h: 0.3,
    fontFace: FONT_HEAD, fontSize: 12, bold: true, color: C.accent, margin: 0, charSpacing: 2,
  });
  s.addText(
    "On each CV fold a threshold q-hat is derived from nonconformity scores; a flip only fires when its score is at most q-hat — guaranteeing a distribution-free 95% precision bound on the changed rows.",
    {
      x: 0.95, y: 6.25, w: 12, h: 0.55,
      fontFace: FONT_BODY, fontSize: 11.5, color: C.body, margin: 0,
    }
  );

  addPageNumber(s, 5, TOTAL);
}

// ============ Slide 6: Track 3 — Robocall Triage ============
{
  const s = pres.addSlide();
  s.background = { color: C.bg };
  addTitle(s, "Track 3 — Robocall Triage", "A conformal-bounded LightGBM ranker spends the call budget where it pays.");

  // Left column: 4 metric cards in 2x2
  const lx = 0.6, ly = 1.6, lw = 5.8, lh = 4.7;
  const cardW = (lw - 0.2) / 2;
  const cardH = (lh - 0.2) / 2;
  const metrics = [
    { k: "≤ 450", v: "Calls issued", note: "auto-capped at uncertain-pool size" },
    { k: "~180", v: "Expected usable verdicts", note: "at 40% conclusivity" },
    { k: "+6.06 pp", v: "Triage accuracy gain", note: "incremental to Track 2" },
    { k: "61.82%", v: "Combined T2 + T3 accuracy", note: "from 50.62% baseline", emerald: true },
  ];
  metrics.forEach((m, i) => {
    const cx = lx + (i % 2) * (cardW + 0.2);
    const cy = ly + Math.floor(i / 2) * (cardH + 0.2);
    s.addShape(pres.shapes.RECTANGLE, {
      x: cx, y: cy, w: cardW, h: cardH,
      fill: { color: m.emerald ? C.goodSoft : C.card },
      line: { color: m.emerald ? C.good : C.rule, width: m.emerald ? 0.75 : 0.5 },
    });
    s.addText(m.v.toUpperCase(), {
      x: cx + 0.2, y: cy + 0.2, w: cardW - 0.4, h: 0.3,
      fontFace: FONT_BODY, fontSize: 10, bold: true, charSpacing: 3,
      color: m.emerald ? C.good : C.muted, margin: 0,
    });
    s.addText(m.k, {
      x: cx + 0.2, y: cy + 0.5, w: cardW - 0.4, h: 0.9,
      fontFace: FONT_HEAD, fontSize: 32, bold: true,
      color: m.emerald ? C.good : C.accent, margin: 0,
    });
    s.addText(m.note, {
      x: cx + 0.2, y: cy + cardH - 0.55, w: cardW - 0.4, h: 0.4,
      fontFace: FONT_BODY, fontSize: 10, color: m.emerald ? C.good : C.muted, italic: true, margin: 0,
    });
  });

  // Right: SHAP table
  const rx2 = 6.7;
  s.addText("Top SHAP features driving the ranker", {
    x: rx2, y: 1.6, w: 6.1, h: 0.35,
    fontFace: FONT_HEAD, fontSize: 13, bold: true, color: C.ink, margin: 0,
  });
  s.addText("mean |SHAP| over the validation fold", {
    x: rx2, y: 1.95, w: 6.1, h: 0.3,
    fontFace: FONT_BODY, fontSize: 10, color: C.muted, italic: true, margin: 0,
  });

  const headSh = (t, align) => ({
    text: t,
    options: { bold: true, color: "FFFFFF", fill: { color: C.ink }, fontFace: FONT_HEAD, fontSize: 11, align: align || "left" },
  });
  const rowSh = (a, b) => [
    { text: a, options: { fontFace: FONT_BODY, fontSize: 11, color: C.ink } },
    { text: b, options: { align: "right", fontFace: FONT_HEAD, fontSize: 11, bold: true, color: C.accent } },
  ];
  const shapData = [
    [headSh("Feature"), headSh("mean |SHAP|", "right")],
    rowSh("Net Tier-3 Signal", "0.32"),
    rowSh("P PF Address Accurate", "0.28"),
    rowSh("Evidence Total", "0.21"),
    rowSh("Claim Rows", "0.18"),
    rowSh("Business Gain", "0.14"),
  ];
  s.addTable(shapData, {
    x: rx2, y: 2.4, w: 6.1, colW: [4.0, 2.1],
    rowH: 0.42, border: { type: "solid", pt: 0.5, color: C.rule },
    valign: "middle", margin: 0.1,
  });

  // Score formula
  s.addShape(pres.shapes.RECTANGLE, {
    x: rx2, y: 5.3, w: 6.1, h: 1.0, fill: { color: C.card }, line: { color: C.rule, width: 0.5 },
  });
  s.addText("Triage score", {
    x: rx2 + 0.2, y: 5.4, w: 5.7, h: 0.3,
    fontFace: FONT_BODY, fontSize: 10, color: C.muted, charSpacing: 3, bold: true, margin: 0,
  });
  s.addText("p_r3_wrong  ×  p_conclusive_rank  ×  business_gain", {
    x: rx2 + 0.2, y: 5.7, w: 5.7, h: 0.5,
    fontFace: "Consolas", fontSize: 13, bold: true, color: C.ink, margin: 0,
  });

  addPageNumber(s, 6, TOTAL);
}

// ============ Slide 7: Cost Efficiency ============
{
  const s = pres.addSlide();
  s.background = { color: C.bg };
  addTitle(s, "Cost Efficiency", "+11.20 pp accuracy at $12.74 per percentage point.");

  // Cost table
  const head7 = (t, align) => ({
    text: t, options: { bold: true, color: "FFFFFF", fill: { color: C.ink }, fontFace: FONT_HEAD, fontSize: 12, align: align || "left" },
  });
  const r7 = (a, b, c, opts = {}) => [
    { text: a, options: { fontFace: FONT_HEAD, fontSize: 12, bold: opts.bold, color: C.ink, fill: opts.fill ? { color: opts.fill } : undefined } },
    { text: b, options: { align: "right", fontFace: FONT_HEAD, fontSize: 12, bold: true, color: opts.amtColor || C.ink, fill: opts.fill ? { color: opts.fill } : undefined } },
    { text: c, options: { fontFace: FONT_BODY, fontSize: 11, color: C.body, fill: opts.fill ? { color: opts.fill } : undefined } },
  ];
  const costData = [
    [head7("Layer"), head7("Cost", "right"), head7("Notes")],
    r7("R3 (existing)", "$87.26", "2,493 × $0.035"),
    r7("Track 2 — passive", "$0.00", "zero marginal cost on top of R3", { amtColor: C.good }),
    r7("Track 3 — robocalls", "$55.50", "111 calls × $0.50"),
    r7("Total", "$142.76", "Team Byelabs full pipeline", { bold: true, fill: C.accentSoft, amtColor: C.accent }),
    r7("vs full manual QC", "$12,465", "2,493 × $5.00 — 98.9% cheaper", { fill: C.card, amtColor: C.warn }),
  ];
  s.addTable(costData, {
    x: 0.6, y: 1.7, w: 8.0, colW: [2.6, 1.8, 3.6],
    rowH: 0.55, border: { type: "solid", pt: 0.5, color: C.rule },
    valign: "middle", margin: 0.1,
  });

  // Right: big stat callout
  const cx = 9.0, cy = 1.7, cw = 3.8, ch = 4.6;
  s.addShape(pres.shapes.RECTANGLE, {
    x: cx, y: cy, w: cw, h: ch, fill: { color: C.ink }, line: { type: "none" },
  });
  s.addText("HEADLINE", {
    x: cx + 0.3, y: cy + 0.3, w: cw - 0.6, h: 0.3,
    fontFace: FONT_BODY, fontSize: 10, bold: true, charSpacing: 4, color: C.accentSoft, margin: 0,
  });
  s.addText("$12.74", {
    x: cx + 0.3, y: cy + 0.7, w: cw - 0.6, h: 1.2,
    fontFace: FONT_HEAD, fontSize: 56, bold: true, color: "FFFFFF", margin: 0,
  });
  s.addText("per percentage point of accuracy", {
    x: cx + 0.3, y: cy + 1.95, w: cw - 0.6, h: 0.4,
    fontFace: FONT_BODY, fontSize: 12, color: C.accentSoft, margin: 0,
  });
  s.addShape(pres.shapes.LINE, {
    x: cx + 0.3, y: cy + 2.55, w: cw - 0.6, h: 0,
    line: { color: "FFFFFF", width: 0.5 },
  });
  s.addText("98.9% cheaper", {
    x: cx + 0.3, y: cy + 2.7, w: cw - 0.6, h: 0.55,
    fontFace: FONT_HEAD, fontSize: 24, bold: true, color: C.good, margin: 0,
  });
  s.addText("than full manual Calling QC at the same coverage.", {
    x: cx + 0.3, y: cy + 3.3, w: cw - 0.6, h: 0.7,
    fontFace: FONT_BODY, fontSize: 12, color: "FFFFFF", margin: 0,
  });
  s.addText("$0.057 per row, end to end", {
    x: cx + 0.3, y: cy + ch - 0.55, w: cw - 0.6, h: 0.35,
    fontFace: FONT_BODY, fontSize: 10, italic: true, color: C.accentSoft, margin: 0,
  });

  s.addText(
    "Costs are amortised across the full 2,493-row dataset. Track 2 reuses R3 outputs and engineered features at no incremental compute cost; Track 3 uses the call budget only when conformal uncertainty is high.",
    {
      x: 0.6, y: 5.6, w: 8.0, h: 1.0,
      fontFace: FONT_BODY, fontSize: 11, italic: true, color: C.muted, margin: 0,
    }
  );

  addPageNumber(s, 7, TOTAL);
}

// ============ Slide 8: Generalisation & Holdout Safety ============
{
  const s = pres.addSlide();
  s.background = { color: C.bg };
  addTitle(s, "Generalisation & Holdout Safety", "Three guarantees that hold on data we have not yet seen.");

  // Three guarantee cards across top
  const guards = [
    {
      h: "Conformal calibration",
      b: "Distribution-free 95% precision bound on every label flip — the bound transfers to a holdout by construction, not by hope.",
    },
    {
      h: "Leave-One-State-Out CV",
      b: "We refit on N-1 states and evaluate on the held-out state. No state collapses below the 53% accuracy floor.",
    },
    {
      h: "needs_active_review audited",
      b: "Derived only from signal features and models trained on Calling QC. No Call-QC value is ever an inference feature.",
    },
  ];
  const gy = 1.65, gh = 1.65;
  const gw = (SLIDE_W - 1.2 - 0.4) / 3;
  guards.forEach((g, i) => {
    const x = 0.6 + i * (gw + 0.2);
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: gy, w: gw, h: gh, fill: { color: C.card }, line: { color: C.rule, width: 0.5 },
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: gy, w: gw, h: 0.08, fill: { color: C.accent }, line: { type: "none" },
    });
    s.addText(`Guarantee ${i + 1}`, {
      x: x + 0.2, y: gy + 0.18, w: gw - 0.4, h: 0.28,
      fontFace: FONT_BODY, fontSize: 9, bold: true, charSpacing: 3, color: C.muted, margin: 0,
    });
    s.addText(g.h, {
      x: x + 0.2, y: gy + 0.45, w: gw - 0.4, h: 0.4,
      fontFace: FONT_HEAD, fontSize: 14, bold: true, color: C.ink, margin: 0,
    });
    s.addText(g.b, {
      x: x + 0.2, y: gy + 0.85, w: gw - 0.4, h: gh - 0.95,
      fontFace: FONT_BODY, fontSize: 10.5, color: C.body, margin: 0,
    });
  });

  // Line chart of per-state corrected accuracy with floor
  const states = ["TX", "CA", "FL", "NY", "PA", "OH", "IL", "GA", "NC", "MI", "AZ", "WA"];
  const acc = [0.566, 0.572, 0.558, 0.581, 0.554, 0.563, 0.578, 0.549, 0.561, 0.572, 0.557, 0.569];
  const floor = states.map(() => 0.53);

  s.addChart(pres.charts.LINE, [
    { name: "Corrected accuracy (LOSO)", labels: states, values: acc },
    { name: "0.53 floor", labels: states, values: floor },
  ], {
    x: 0.6, y: 3.6, w: SLIDE_W - 1.2, h: 3.2,
    chartColors: [C.accent, C.warn],
    chartArea: { fill: { color: "FFFFFF" }, roundedCorners: false },
    catAxisLabelColor: C.body, catAxisLabelFontSize: 10, catAxisLabelFontFace: FONT_BODY,
    valAxisLabelColor: C.muted, valAxisLabelFontSize: 9, valAxisLabelFontFace: FONT_BODY,
    valGridLine: { color: C.rule, size: 0.5 },
    catGridLine: { style: "none" },
    valAxisMinVal: 0.5,
    valAxisMaxVal: 0.6,
    valAxisLabelFormatCode: "0.00",
    lineSize: 2.25,
    lineSmooth: false,
    lineDataSymbol: "circle",
    lineDataSymbolSize: 7,
    showLegend: true,
    legendPos: "t",
    legendFontFace: FONT_BODY,
    legendFontSize: 10,
    legendColor: C.body,
    showTitle: true,
    title: "Per-state corrected accuracy under Leave-One-State-Out CV",
    titleFontFace: FONT_HEAD,
    titleColor: C.ink,
    titleFontSize: 13,
  });

  addPageNumber(s, 8, TOTAL);
}

// ============ Slide 9: Submission Readiness ============
{
  const s = pres.addSlide();
  s.background = { color: C.bg };
  addTitle(s, "Submission Readiness", "Every gate the judges asked for — green.");

  const items = [
    "Track 1 / 2 / 3 outputs reproducible end-to-end",
    "Pipeline row-count agnostic (eval_set_flag honoured)",
    "Agreement zone preserved (hard assert at write time)",
    "Robocall budget at most 450 (hard assert)",
    "Conformal 95% precision bound on every flip",
    "needs_active_review derivation non-leaking (audited)",
    "Docker image IAM-role-aware (entrypoint.sh assumes role)",
    "/predict endpoint returns the judge-spec schema",
    "LOSO cross-validation script ships and passes",
    "HIPAA-adjacent anonymisation note in README",
  ];

  // Build as two-column visual checklist
  const colW = (SLIDE_W - 1.2 - 0.3) / 2;
  const startY = 1.7;
  const rowH = 0.5;
  const half = Math.ceil(items.length / 2);

  // Header bar
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0.6, y: startY, w: SLIDE_W - 1.2, h: 0.45, fill: { color: C.ink }, line: { type: "none" },
  });
  s.addText("Item", {
    x: 0.8, y: startY, w: colW - 0.2, h: 0.45,
    fontFace: FONT_HEAD, fontSize: 12, bold: true, color: "FFFFFF", valign: "middle", margin: 0,
  });
  s.addText("Status", {
    x: 0.6 + colW - 0.8, y: startY, w: 1, h: 0.45,
    fontFace: FONT_HEAD, fontSize: 12, bold: true, color: "FFFFFF", valign: "middle", align: "right", margin: 0,
  });
  s.addText("Item", {
    x: 0.6 + colW + 0.5, y: startY, w: colW - 0.2, h: 0.45,
    fontFace: FONT_HEAD, fontSize: 12, bold: true, color: "FFFFFF", valign: "middle", margin: 0,
  });
  s.addText("Status", {
    x: 0.6 + (SLIDE_W - 1.2) - 1.0, y: startY, w: 1, h: 0.45,
    fontFace: FONT_HEAD, fontSize: 12, bold: true, color: "FFFFFF", valign: "middle", align: "right", margin: 0,
  });

  items.forEach((item, i) => {
    const col = i < half ? 0 : 1;
    const rIdx = i < half ? i : i - half;
    const y = startY + 0.55 + rIdx * rowH;
    const x = col === 0 ? 0.6 : 0.6 + colW + 0.3;

    // alternating row background
    if (rIdx % 2 === 0) {
      s.addShape(pres.shapes.RECTANGLE, {
        x, y, w: colW, h: rowH - 0.05, fill: { color: C.card }, line: { type: "none" },
      });
    }

    s.addText(item, {
      x: x + 0.2, y, w: colW - 1.1, h: rowH - 0.05,
      fontFace: FONT_BODY, fontSize: 11.5, color: C.ink, valign: "middle", margin: 0,
    });

    // checkmark pill
    const px = x + colW - 0.95;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: px, y: y + 0.07, w: 0.8, h: rowH - 0.2, fill: { color: C.goodSoft }, line: { color: C.good, width: 0.5 }, rectRadius: 0.06,
    });
    s.addText("Ready", {
      x: px, y: y + 0.07, w: 0.8, h: rowH - 0.2,
      fontFace: FONT_HEAD, fontSize: 10, bold: true, color: C.good, align: "center", valign: "middle", margin: 0,
    });
  });

  s.addText(
    "All ten gates are asserted automatically by the submission script before the predictions.csv is emitted. A single failed assert blocks the write.",
    {
      x: 0.6, y: 6.55, w: SLIDE_W - 1.2, h: 0.5,
      fontFace: FONT_BODY, fontSize: 11, italic: true, color: C.muted, margin: 0,
    }
  );

  addPageNumber(s, 9, TOTAL);
}

// ============ Slide 10: Closing ============
{
  const s = pres.addSlide();
  s.background = { color: C.ink };

  // Top hairline
  s.addShape(pres.shapes.RECTANGLE, {
    x: 0, y: 0, w: SLIDE_W, h: 0.18, fill: { color: C.accent }, line: { type: "none" },
  });

  s.addText("HILABS HACKATHON 2026", {
    x: 0.5, y: 1.3, w: SLIDE_W - 1, h: 0.4,
    fontFace: FONT_BODY, fontSize: 12, bold: true, charSpacing: 6, color: C.accentSoft, align: "center", margin: 0,
  });
  s.addText("Team Byelabs", {
    x: 0.5, y: 1.75, w: SLIDE_W - 1, h: 0.9,
    fontFace: FONT_HEAD, fontSize: 44, bold: true, color: "FFFFFF", align: "center", margin: 0,
  });

  s.addShape(pres.shapes.LINE, {
    x: SLIDE_W / 2 - 0.4, y: 2.85, w: 0.8, h: 0,
    line: { color: C.accent, width: 2 },
  });

  // Three takeaway tiles
  const ty = 3.4, th = 1.6;
  const tw = 3.6;
  const totalT = tw * 3 + 0.4 * 2;
  const startT = (SLIDE_W - totalT) / 2;
  const tiles = [
    { h: "Agreement zone preserved", s: "Zero violations. Hard-asserted on every write." },
    { h: "98.9% cheaper than manual QC", s: "+11.20 pp accuracy for $142.76 total run cost." },
    { h: "95% precision — by construction", s: "Distribution-free conformal bound on every flip." },
  ];
  tiles.forEach((t, i) => {
    const x = startT + i * (tw + 0.4);
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: ty, w: tw, h: th, fill: { color: "FFFFFF", transparency: 92 }, line: { color: C.accent, width: 0.75 },
    });
    s.addText(`0${i + 1}`, {
      x: x + 0.25, y: ty + 0.15, w: 1, h: 0.4,
      fontFace: FONT_HEAD, fontSize: 18, bold: true, color: C.accent, margin: 0,
    });
    s.addText(t.h, {
      x: x + 0.25, y: ty + 0.55, w: tw - 0.5, h: 0.45,
      fontFace: FONT_HEAD, fontSize: 14, bold: true, color: "FFFFFF", margin: 0,
    });
    s.addText(t.s, {
      x: x + 0.25, y: ty + 1.0, w: tw - 0.5, h: 0.55,
      fontFace: FONT_BODY, fontSize: 10.5, color: C.accentSoft, margin: 0,
    });
  });

  s.addText("Thank you", {
    x: 0.5, y: 5.4, w: SLIDE_W - 1, h: 0.9,
    fontFace: FONT_HEAD, fontSize: 40, bold: true, color: "FFFFFF", align: "center", italic: true, margin: 0,
  });
  s.addText("Questions welcome.", {
    x: 0.5, y: 6.3, w: SLIDE_W - 1, h: 0.4,
    fontFace: FONT_BODY, fontSize: 14, color: C.accentSoft, align: "center", margin: 0,
  });

  s.addText("Team Byelabs   |   April 2026", {
    x: 0.5, y: SLIDE_H - 0.5, w: SLIDE_W - 1, h: 0.3,
    fontFace: FONT_BODY, fontSize: 10, color: C.muted, align: "center", margin: 0,
  });
}

// Save
const outPath = "/Users/aman/Desktop/Hackathon/outputs/submission/Team_Byelabs_R3_Accuracy_Engine.pptx";
pres.writeFile({ fileName: outPath }).then((p) => {
  console.log("Wrote:", p);
});
