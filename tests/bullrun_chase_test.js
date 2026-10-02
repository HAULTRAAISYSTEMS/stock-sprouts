// Headless chase-mechanics tests for Bull Run Chase Mode (static/js/quest.js).
// Stubs DOM/canvas, drives the game via the __BULLRUN_TEST__ hook.
const fs = require("fs");
const SRC = process.argv[2] || require("path").join(__dirname, "..", "static", "js", "quest.js");

const listeners = {};
let nowMs = 0;
global.performance = { now: () => nowMs };
const rafQ = [];
global.requestAnimationFrame = (f) => { rafQ.push(f); return rafQ.length; };
global.cancelAnimationFrame = () => {};
global.window = {
  __BULLRUN_TEST__: {},
  addEventListener: (t, f) => { (listeners[t] = listeners[t] || []).push(f); },
  removeEventListener: () => {},
  devicePixelRatio: 1,
};
global.Image = class {
  constructor() { this.complete = false; this.naturalWidth = 0; this.onload = null; }
  set src(v) { this.complete = true; this.naturalWidth = 200; if (this.onload) this.onload(); }
};
function makeCtx() {
  const grad = { addColorStop() {} };
  return new Proxy({}, {
    get(t, k) {
      if (k === "createLinearGradient" || k === "createRadialGradient") return () => grad;
      if (k === "measureText") return () => ({ width: 10 });
      return (...a) => {};
    },
    set() { return true; },
  });
}
const canvasListeners = {};
const canvas = {
  getBoundingClientRect: () => ({ width: 360, left: 0, top: 0 }),
  getContext: () => makeCtx(),
  style: {},
  addEventListener: (t, f) => { (canvasListeners[t] = canvasListeners[t] || []).push(f); },
  width: 0, height: 0,
};
const classList = () => ({ toggle() {}, add() {}, remove() {}, contains: () => false });
function el() { return { textContent: "", innerHTML: "", style: {}, classList: classList() }; }
const els = {};
global.document = {
  getElementById: (id) => {
    if (id === "catchCanvas") return canvas;
    if (!els[id]) els[id] = el();
    return els[id];
  },
  querySelectorAll: () => [],
};

eval(fs.readFileSync(SRC, "utf8"));

let failures = 0;
function check(name, cond, extra) {
  console.log((cond ? "PASS" : "FAIL") + " " + name + (extra !== undefined ? " (" + extra + ")" : ""));
  if (!cond) failures++;
}
function step(ms) {
  const end = nowMs + ms;
  let guard = 0;
  while (nowMs < end && guard++ < 100000) {
    nowMs += 16;
    const q = rafQ.splice(0);
    if (!q.length) break;
    q.forEach((f) => f(nowMs));
  }
}
function key(k) {
  (listeners.keydown || []).forEach((f) => f({ key: k, preventDefault() {} }));
}

// ---------- game 1: gap math + caught sequence ----------
let result = null;
initCoinCatch("catchCanvas", (r) => { result = r; });
const api = global.window.__BULLRUN_TEST__.api;
check("gap starts at 70", api.gap() === 70, "gap=" + api.gap());

api.hit();
check("one hit: gap 70 -> 48", api.gap() === 48, "gap=" + api.gap());
api.hit(); api.hit();
check("three hits: gap == 4", api.gap() === 4, "gap=" + api.gap());
api.hit(); // fourth hit -> caught
check("fourth hit: gap 0", api.gap() === 0, "gap=" + api.gap());
step(1600); // let the caught sequence play out
check("onDone fired after caught", !!result);
check("caught_by is liabilities", result && result.caught_by === "liabilities");
check("distance reported", result && Number.isInteger(result.distance) && result.distance >= 0, "distance=" + (result && result.distance));
check("score/ caught/ tokens present", result && Number.isInteger(result.score) && Number.isInteger(result.caught) && typeof result.tokens === "object");

// ---------- game 2: token pushes Lou back, crash drains faster ----------
nowMs = 0; rafQ.length = 0;
for (const k in listeners) listeners[k] = [];
result = null;
initCoinCatch("catchCanvas", (r) => { result = r; });
const api2 = global.window.__BULLRUN_TEST__.api;
api2.setGap(50);
api2.token("MCD");
check("token: gap 50 -> 68", api2.gap() === 68, "gap=" + api2.gap());

api2.setGap(80);
api2.crash();
check("crash active", api2.crashing() === true);
step(1000); // <1.8s: no spawned obstacle can have reached the player yet
const gAfterCrash = api2.gap();
check("crash drains gap (80 -> ~75.5)", Math.abs(gAfterCrash - 75.5) < 0.3, "gap=" + gAfterCrash.toFixed(1));

// ---------- game 3: near-miss bonus, no double count ----------
nowMs = 0; rafQ.length = 0;
for (const k in listeners) listeners[k] = [];
result = null;
initCoinCatch("catchCanvas", (r) => { result = r; });
const api3 = global.window.__BULLRUN_TEST__.api;
key("ArrowRight");
step(48); // lanePos eases to ~0.5
const lp = api3.lanePos();
check("lanePos in near-miss window", lp >= 0.45 && lp < 0.7, "lanePos=" + lp.toFixed(2));
const s0 = api3.score(), g0 = api3.gap();
const ent = { lane: 0, z: 0.9, type: "pit", done: false };
api3.collideWith(ent);
check("near-miss: +5 score, gap unchanged",
  api3.score() === s0 + 5 && api3.gap() === g0,
  "score " + s0 + "->" + api3.score());
api3.collideWith(ent);
check("near-miss not double-counted", api3.score() === s0 + 5, "score=" + api3.score());

// ---------- game 4: clean running rebuilds gap ----------
nowMs = 0; rafQ.length = 0;
for (const k in listeners) listeners[k] = [];
result = null;
initCoinCatch("catchCanvas", (r) => { result = r; });
const api4 = global.window.__BULLRUN_TEST__.api;
api4.setGap(50);
step(1000); // <1.8s: no spawned obstacle can have reached the player yet
check("clean run rebuilds gap (50 -> 51.5)", Math.abs(api4.gap() - 51.5) < 0.15, "gap=" + api4.gap().toFixed(2));
check("distance accumulates", api4.distance() > 5, "distance=" + api4.distance().toFixed(1));

console.log(failures === 0 ? "ALL CHASE TESTS OK" : failures + " FAILURES");
process.exit(failures === 0 ? 0 : 1);
