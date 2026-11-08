const INK = "#28253b";
const FONT = 1;
const LAVENDER = "#edecfb";
const MINT = "#e5f4ec";
const SAND = "#f8eee6";
const PAPER = "#ffffff";
const INDIGO = "#d9dcfb";

let seed = 1200;

function nextSeed() {
  seed += 19;
  return seed;
}

const placed = new Map();

function box(id, x, y, text, fill, width = 200, height = 76) {
  placed.set(id, { x, y, w: width, h: height });
  return {
    type: "rectangle",
    id,
    x,
    y,
    width,
    height,
    strokeColor: INK,
    backgroundColor: fill,
    fillStyle: "solid",
    strokeWidth: 2,
    roughness: 1,
    seed: nextSeed(),
    roundness: { type: 3 },
    label: { text, fontSize: 16, fontFamily: FONT, strokeColor: INK },
  };
}

function toward(from, to) {
  const gap = 10;
  const separated = from.y + from.h <= to.y || to.y + to.h <= from.y;
  if (separated) {
    const above = from.y + from.h <= to.y;
    const x = Math.min(from.x + from.w - 18, Math.max(from.x + 18, to.x + to.w / 2));
    return { x, y: above ? from.y + from.h + gap : from.y - gap };
  }
  const left = from.x + from.w <= to.x;
  const y = Math.min(from.y + from.h - 16, Math.max(from.y + 16, to.y + to.h / 2));
  return { x: left ? from.x + from.w + gap : from.x - gap, y };
}

function arrow(startId, endId, text) {
  const startBox = placed.get(startId);
  const endBox = placed.get(endId);
  const start = toward(startBox, endBox);
  const end = toward(endBox, startBox);
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const id = `${startId}-${endId}`;
  const elements = [
    {
      type: "arrow",
      id,
      x: start.x,
      y: start.y,
      width: dx,
      height: dy,
      points: [[0, 0], [dx, dy]],
      strokeColor: INK,
      strokeWidth: 2,
      roughness: 1,
      seed: nextSeed(),
      endArrowhead: "arrow",
    },
  ];
  if (text) {
    const vertical = Math.abs(dy) >= Math.abs(dx);
    elements.push({
      type: "text",
      id: `${id}-label`,
      x: vertical ? (start.x + end.x) / 2 + 10 : (start.x + end.x) / 2 - text.length * 3.5,
      y: vertical ? (start.y + end.y) / 2 - 12 : (start.y + end.y) / 2 - 22,
      text,
      fontSize: 14,
      fontFamily: FONT,
      strokeColor: INK,
    });
  }
  return elements;
}

function scene(nodes) {
  return nodes.flat();
}

export const handoffScene = scene([
  box("batch", 270, 16, "Synthetic batch", PAPER),
  box("orch", 270, 132, "Orchestrator", LAVENDER),
  box("ext", 270, 248, "Extractor", LAVENDER),
  box("res", 16, 392, "Researcher", LAVENDER),
  box("cls", 524, 392, "Classifier", LAVENDER),
  box("val", 270, 536, "Validator\ncode, no model", MINT),
  box("repair", 524, 536, "One repair\nthen stop", SAND),
  box("hold", 16, 692, "To verify", SAND),
  box("aud", 270, 692, "Auditor", LAVENDER),
  box("human", 524, 692, "Approver", PAPER),
  box("pack", 524, 820, "Bounded pack", INDIGO),
  arrow("batch", "orch"),
  arrow("orch", "ext", "split"),
  arrow("ext", "res", "fields"),
  arrow("ext", "cls", "fields"),
  arrow("res", "cls", "citation"),
  arrow("cls", "val", "proposal"),
  arrow("val", "repair"),
  arrow("val", "hold", "still failing"),
  arrow("val", "aud", "pass"),
  arrow("aud", "hold", "disagree"),
  arrow("aud", "human", "agree"),
  arrow("human", "pack", "sign"),
]);

export const stackScene = scene([
  box("desk", 16, 16, "React desk\nnginx :8420", PAPER, 200, 84),
  box("api", 276, 16, "FastAPI\nSSE :8421", LAVENDER, 200, 84),
  box("gate", 536, 16, "Residency\ngate", SAND, 180, 84),
  box("refuse", 16, 200, "Other uploads\nrefused", SAND, 200, 84),
  box("graph", 360, 200, "LangGraph\nin the process", MINT, 210, 84),
  box("omni", 680, 200, "OmniRoute :20128\nterra, then luna", LAVENDER, 230, 84),
  box("db", 360, 390, "SQLite\ntenant volume", PAPER, 210, 84),
  box("bak", 680, 390, "Backup\nvolume", PAPER, 180, 84),
  arrow("desk", "api"),
  arrow("api", "gate"),
  arrow("gate", "refuse", "anything else"),
  arrow("gate", "graph", "synthetic run"),
  arrow("graph", "omni", "model call"),
  arrow("graph", "db", "audit row"),
  arrow("db", "bak"),
]);

export const rubricScene = scene([
  box("problem", 16, 16, "Problem\nA PDF is not an eInvoice", SAND, 320, 118),
  box("tech", 372, 16, "Technical credibility\nCode checks the model", MINT, 340, 118),
  box("create", 16, 176, "Creativity\nOne agent catches another", LAVENDER, 320, 118),
  box("vision", 372, 176, "Strategic vision\nA pack, then a verified host", PAPER, 340, 118),
]);
