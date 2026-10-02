/* Stock Quest v2 — mini-games. No emojis; canvas-drawn art only. */

/* ---------------- Coin Catch (Quest 1) ----------------
   Coins fall — tap to catch (+10). Money pits fall too — don't tap them (-5).
   30 seconds. Calls onDone({score, caught}) when time runs out. */
function initCoinCatch(canvasId, onDone) {
  const cv = document.getElementById(canvasId);
  const ctx = cv.getContext("2d");
  const H = 420;
  let W = 300;
  function fit() {
    const r = cv.getBoundingClientRect();
    W = Math.max(280, r.width);
    const dpr = window.devicePixelRatio || 1;
    cv.width = W * dpr;
    cv.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  fit();
  window.addEventListener("resize", fit);

  const items = [];
  const pops = [];
  let score = 0, caught = 0, running = true;
  const tEnd = performance.now() + 30000;
  let lastSpawn = 0;

  function spawn() {
    const kind = Math.random() < 0.72 ? "coin" : "pit";
    items.push({
      x: 30 + Math.random() * (W - 60),
      y: -30,
      vy: 1.6 + Math.random() * 2.2,
      r: kind === "coin" ? 22 : 20,
      kind,
      wob: Math.random() * 6.28
    });
  }

  function drawCoin(it) {
    ctx.save();
    ctx.translate(it.x, it.y);
    const g = ctx.createRadialGradient(-6, -8, 4, 0, 0, it.r + 4);
    g.addColorStop(0, "#ffe08a");
    g.addColorStop(0.6, "#ffc93c");
    g.addColorStop(1, "#e0a41c");
    ctx.fillStyle = g;
    ctx.beginPath(); ctx.arc(0, 0, it.r, 0, 7); ctx.fill();
    ctx.strokeStyle = "#a86e00"; ctx.lineWidth = 3; ctx.stroke();
    ctx.fillStyle = "#7a5200";
    ctx.font = "800 22px 'Baloo 2', sans-serif";
    ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillText("$", 0, 1);
    ctx.restore();
  }

  function drawPit(it) {
    ctx.save();
    ctx.translate(it.x, it.y);
    ctx.fillStyle = "#050914";
    ctx.beginPath(); ctx.arc(0, 0, it.r, 0, 7); ctx.fill();
    ctx.strokeStyle = "#f87171"; ctx.lineWidth = 3;
    ctx.setLineDash([6, 4]);
    ctx.beginPath(); ctx.arc(0, 0, it.r, 0, 7); ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = "#f87171";
    ctx.font = "800 22px 'Baloo 2', sans-serif";
    ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillText("!", 0, 1);
    ctx.restore();
  }

  function pop(x, y, txt, color) {
    pops.push({ x, y, txt, color, life: 1 });
  }

  function tap(px, py) {
    const r = cv.getBoundingClientRect();
    const x = px - r.left, y = py - r.top;
    for (let i = items.length - 1; i >= 0; i--) {
      const it = items[i];
      const d = Math.hypot(it.x - x, it.y - y);
      if (d < it.r + 14) {
        items.splice(i, 1);
        if (it.kind === "coin") {
          score += 10; caught++;
          pop(it.x, it.y, "+10", "#4ade80");
        } else {
          score = Math.max(0, score - 5);
          pop(it.x, it.y, "-5", "#f87171");
        }
        updateHud();
        return;
      }
    }
  }
  cv.addEventListener("pointerdown", e => { if (running) tap(e.clientX, e.clientY); });

  const hudT = document.getElementById("catchTime");
  const hudS = document.getElementById("catchScore");
  function updateHud() { if (hudS) hudS.textContent = score; }

  let raf;
  function frame(now) {
    if (!running) return;
    const remain = Math.max(0, Math.ceil((tEnd - now) / 1000));
    if (hudT) hudT.textContent = remain + "s";
    if (now >= tEnd) { finish(); return; }
    if (now - lastSpawn > 550) { spawn(); lastSpawn = now; }

    ctx.clearRect(0, 0, W, H);
    for (let i = items.length - 1; i >= 0; i--) {
      const it = items[i];
      it.y += it.vy;
      it.wob += 0.05;
      it.x += Math.sin(it.wob) * 0.6;
      if (it.y > H + 40) { items.splice(i, 1); continue; }
      if (it.kind === "coin") drawCoin(it); else drawPit(it);
    }
    for (let i = pops.length - 1; i >= 0; i--) {
      const p = pops[i];
      p.y -= 1.2; p.life -= 0.03;
      if (p.life <= 0) { pops.splice(i, 1); continue; }
      ctx.globalAlpha = Math.max(0, p.life);
      ctx.fillStyle = p.color;
      ctx.font = "800 20px 'Baloo 2', sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(p.txt, p.x, p.y);
      ctx.globalAlpha = 1;
    }
    raf = requestAnimationFrame(frame);
  }

  function finish() {
    running = false;
    cancelAnimationFrame(raf);
    onDone({ score, caught });
  }
  updateHud();
  raf = requestAnimationFrame(frame);
}

/* ---------------- Needs vs. Wants sorting (Quest 2) ----------------
   items: [{name, kind, icon, note}]. Renders one card at a time; the player
   taps NEEDS or WANTS. Calls onDone({correct, total, answers}). */
function initSortGame(boxId, items, onDone) {
  const box = document.getElementById(boxId);
  const order = items.slice();
  for (let i = order.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [order[i], order[j]] = [order[j], order[i]];
  }
  let idx = 0, correct = 0;
  const answers = [];

  const ICONS = {
    drop: '<svg class="ic lg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3c3.5 4.5 6.5 7.8 6.5 11a6.5 6.5 0 1 1-13 0c0-3.2 3-6.5 6.5-11z"/></svg>',
    apple: '<svg class="ic lg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 8.5c-3.5-2.8-8.5-.3-8.5 5 0 3.8 2.8 6.5 5.7 6.5 1.4 0 2-.5 2.8-.5s1.4.5 2.8.5c2.9 0 5.7-2.7 5.7-6.5 0-5.3-5-7.8-8.5-5z"/><path d="M12 8.5c0-2.5 1-4.5 3-5.5"/></svg>',
    house: '<svg class="ic lg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 11L12 3.5 20.5 11"/><path d="M5.5 9.5V20h13V9.5"/><path d="M10 20v-5h4v5"/></svg>',
    shoe: '<svg class="ic lg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 16.5h18v2.5H3z"/><path d="M3 16.5c.5-4.5 2.5-6.5 6-8.5l5.5-3 1 3.5 5.5 2v6"/></svg>',
    gamepad: '<svg class="ic lg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2.5" y="7.5" width="19" height="10" rx="5"/><path d="M8 10.5v4M6 12.5h4"/><circle cx="15.5" cy="11.5" r="1"/><circle cx="18" cy="14" r="1"/></svg>',
    teddy: '<svg class="ic lg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="7.5" cy="7" r="2.5"/><circle cx="16.5" cy="7" r="2.5"/><circle cx="12" cy="11" r="5"/><circle cx="12" cy="19" r="4"/></svg>'
  };

  function render() {
    if (idx >= order.length) {
      onDone({ correct, total: order.length, answers });
      return;
    }
    const it = order[idx];
    box.innerHTML =
      '<div class="sort-item">' +
      (ICONS[it.icon] || "") +
      "<b>" + it.name + "</b>" +
      '<div class="pick-row">' +
      '<button class="bin-btn bin-need" data-pick="need">NEEDS</button>' +
      '<button class="bin-btn bin-want" data-pick="want">WANTS</button>' +
      "</div>" +
      '<p class="note" id="sortNote"></p>' +
      '<p class="game-tip">Item ' + (idx + 1) + " of " + order.length + "</p>" +
      "</div>";
    box.querySelectorAll("[data-pick]").forEach(btn => {
      btn.addEventListener("click", () => {
        const pick = btn.dataset.pick;
        const ok = pick === it.kind;
        if (ok) correct++;
        answers.push({ name: it.name, pick, ok });
        const card = box.querySelector(".sort-item");
        card.classList.add(ok ? "right" : "wrong");
        box.querySelector("#sortNote").textContent =
          (ok ? "Right! " : "Not quite — it's a " + it.kind.toUpperCase() + ". ") + it.note;
        box.querySelectorAll("[data-pick]").forEach(b => (b.disabled = true));
        const next = document.createElement("button");
        next.className = "btn-gold mt";
        next.textContent = idx + 1 >= order.length ? "See my score" : "Next item";
        next.addEventListener("click", () => { idx++; render(); });
        card.appendChild(next);
      });
    });
  }
  render();
}
