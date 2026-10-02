/* Stock Quest v2 — mini-games. No emojis; canvas-drawn art only. */

/* ---------------- Coin Catch (Quest 1) ----------------
   Subway-Surfers-style 3-lane runner. The kid auto-runs through Fortune City:
   swipe / arrow keys / pad buttons to switch lanes, jump the barriers and
   money pits, slide under toll gates, and grab coins. 45 seconds.
   Calls onDone({score, caught}) when time runs out. */
function initCoinCatch(canvasId, onDone) {
  const cv = document.getElementById(canvasId);
  const ctx = cv.getContext("2d");
  const H = 460;
  let W = 320;
  function fit() {
    const r = cv.getBoundingClientRect();
    W = Math.max(300, Math.min(560, r.width || 320));
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    cv.width = W * dpr;
    cv.height = H * dpr;
    cv.style.height = H + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  fit();
  window.addEventListener("resize", fit);
  cv.style.touchAction = "none";

  // pseudo-3D: z=0 at the horizon, z=1 at the player
  const horizonY = H * 0.30;
  const groundY = H - 64;
  const spread = () => W * 0.30;
  const xFor = (lane, z) => W / 2 + lane * spread() * (0.12 + 0.88 * z);
  const yFor = (z) => horizonY + (groundY - horizonY) * Math.pow(Math.max(0, z), 0.92);
  const sFor = (z) => 0.22 + 0.78 * Math.max(0, z);

  // ---- player state ----
  let lane = 0, lanePos = 0;          // lanePos eases toward lane
  let jumpT = -1, slideT = -1;
  const JUMP_DUR = 0.62, SLIDE_DUR = 0.7;
  const jumpH = () => {
    if (jumpT < 0) return 0;
    const t = jumpT / JUMP_DUR;
    if (t >= 1) { jumpT = -1; return 0; }
    return Math.sin(t * Math.PI);
  };
  const sliding = () => slideT >= 0;

  // ---- run state ----
  let score = 0, caught = 0, running = true;
  const DUR = 45000;
  const t0 = performance.now();
  const tEnd = t0 + DUR;
  let invulnUntil = 0, shake = 0, dist = 0, rowTimer = 0.4;
  const ents = [];   // {lane, z, type: coin|pit|barrier|gate, y, done}
  const pops = [];
  const stars = [];
  for (let i = 0; i < 60; i++) {
    stars.push({ x: Math.random(), y: Math.random() * 0.26, r: Math.random() * 1.6 + 0.4, tw: Math.random() * 6.28 });
  }

  const hudT = document.getElementById("catchTime");
  const hudS = document.getElementById("catchScore");
  const setScore = () => { if (hudS) hudS.textContent = score; };

  // ---- input: swipe, keys, pad buttons ----
  function goLeft() { if (running) lane = Math.max(-1, lane - 1); }
  function goRight() { if (running) lane = Math.min(1, lane + 1); }
  function goJump() { if (running && jumpT < 0) { jumpT = 0; slideT = -1; } }
  function goSlide() { if (running && jumpT < 0) { slideT = 0; } }
  const keyH = (e) => {
    if (!running) return;
    const k = e.key;
    if (k === "ArrowLeft" || k === "a" || k === "A") { goLeft(); e.preventDefault(); }
    else if (k === "ArrowRight" || k === "d" || k === "D") { goRight(); e.preventDefault(); }
    else if (k === "ArrowUp" || k === "w" || k === "W" || k === " ") { goJump(); e.preventDefault(); }
    else if (k === "ArrowDown" || k === "s" || k === "S") { goSlide(); e.preventDefault(); }
  };
  window.addEventListener("keydown", keyH);
  let pStart = null;
  cv.addEventListener("pointerdown", (e) => { pStart = { x: e.clientX, y: e.clientY }; });
  cv.addEventListener("pointerup", (e) => {
    if (!pStart || !running) { pStart = null; return; }
    const dx = e.clientX - pStart.x, dy = e.clientY - pStart.y;
    pStart = null;
    if (Math.hypot(dx, dy) < 24) { goJump(); return; }   // tap = jump (kid-friendly)
    if (Math.abs(dx) > Math.abs(dy)) { if (dx < 0) goLeft(); else goRight(); }
    else { if (dy < 0) goJump(); else goSlide(); }
  });
  document.querySelectorAll("[data-runner]").forEach((b) => {
    b.addEventListener("pointerdown", (e) => {
      e.preventDefault();
      const a = b.getAttribute("data-runner");
      if (a === "left") goLeft();
      else if (a === "right") goRight();
      else if (a === "jump") goJump();
      else if (a === "slide") goSlide();
    });
  });

  // ---- spawner: pattern rows, always leave a way through ----
  const rndLane = () => [-1, 0, 1][Math.floor(Math.random() * 3)];
  const freeLanes = (used) => [-1, 0, 1].filter((l) => used.indexOf(l) < 0);
  const addCoin = (ln, z, y) => ents.push({ lane: ln, z, type: "coin", y: y || 0, done: false });
  function spawnRow() {
    const roll = Math.random();
    if (roll < 0.30) {
      const l = rndLane();                                    // coin line
      for (let i = 0; i < 6; i++) addCoin(l, 0.02 + i * 0.09, 0);
    } else if (roll < 0.45) {
      const l = rndLane();                                    // barrier + coin arc over it
      ents.push({ lane: l, z: 0.02, type: "barrier", done: false });
      for (let i = 0; i < 5; i++) addCoin(l, -0.04 + i * 0.07, Math.sin((i / 4) * Math.PI));
    } else if (roll < 0.62) {
      const used = [];                                        // pits in 1-2 lanes, coins in a free lane
      const n = Math.random() < 0.5 ? 1 : 2;
      while (used.length < n) { const l = rndLane(); if (used.indexOf(l) < 0) used.push(l); }
      used.forEach((l) => ents.push({ lane: l, z: 0.02, type: "pit", done: false }));
      const free = freeLanes(used)[0];
      for (let i = 0; i < 5; i++) addCoin(free, 0.02 + i * 0.09, 0);
    } else if (roll < 0.78) {
      const used = [];                                        // toll gates in 2 lanes: slide!
      while (used.length < 2) { const l = rndLane(); if (used.indexOf(l) < 0) used.push(l); }
      used.forEach((l) => ents.push({ lane: l, z: 0.02, type: "gate", done: false }));
      const free = freeLanes(used)[0];
      for (let i = 0; i < 5; i++) addCoin(free, 0.02 + i * 0.09, 0);
    } else {
      let l = rndLane();                                      // zigzag coins
      const order = [-1, 0, 1];
      for (let i = 0; i < 6; i++) {
        addCoin(l, 0.02 + i * 0.09, 0);
        l = order[(order.indexOf(l) + 1) % 3];
      }
    }
  }

  function pop(x, y, txt, color) { pops.push({ x, y, txt, color, life: 1 }); }

  function stumble(x, y) {
    score = Math.max(0, score - 15);
    invulnUntil = performance.now() + 1000;
    shake = 10;
    pop(x, y - 46, "-15", "#f87171");
    setScore();
  }

  function collide(e, now) {
    if (Math.abs(lanePos - e.lane) >= 0.45) return;
    const h = jumpH();
    if (e.type === "coin") {
      if (Math.abs(h - (e.y || 0)) < 0.5) {
        e.done = true;
        score += 10; caught++;
        pop(xFor(e.lane, e.z), yFor(e.z) - 34, "+10", "#4ade80");
        setScore();
      }
      return;
    }
    if (now < invulnUntil) return;
    const x = xFor(e.lane, e.z), y = yFor(e.z);
    if (e.type === "pit" && h < 0.3) { e.done = true; stumble(x, y); }
    else if (e.type === "barrier" && h < 0.6) { e.done = true; stumble(x, y); }
    else if (e.type === "gate" && !sliding()) { e.done = true; stumble(x, y); }
  }

  // ---- drawing ----
  function roundRectP(x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }
  function drawCoin(x, y, s) {
    const r = 20 * s;
    ctx.save(); ctx.translate(x, y);
    const g = ctx.createRadialGradient(-r * 0.3, -r * 0.35, r * 0.15, 0, 0, r * 1.15);
    g.addColorStop(0, "#ffe08a"); g.addColorStop(0.6, "#ffc93c"); g.addColorStop(1, "#e0a41c");
    ctx.fillStyle = g;
    ctx.beginPath(); ctx.arc(0, 0, r, 0, 7); ctx.fill();
    ctx.strokeStyle = "#a86e00"; ctx.lineWidth = Math.max(1.5, 3 * s); ctx.stroke();
    ctx.fillStyle = "#7a5200";
    ctx.font = "800 " + Math.max(10, Math.round(22 * s)) + "px 'Baloo 2', sans-serif";
    ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillText("$", 0, 1);
    ctx.restore();
  }
  function drawPit(x, y, s) {
    const r = 26 * s;
    ctx.save(); ctx.translate(x, y);
    ctx.fillStyle = "#04070f";
    ctx.beginPath(); ctx.ellipse(0, 0, r, r * 0.45, 0, 0, 7); ctx.fill();
    ctx.strokeStyle = "#f87171"; ctx.lineWidth = Math.max(1.5, 3 * s);
    ctx.setLineDash([7, 5]);
    ctx.beginPath(); ctx.ellipse(0, 0, r, r * 0.45, 0, 0, 7); ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = "#f87171";
    ctx.font = "800 " + Math.max(9, Math.round(18 * s)) + "px 'Baloo 2', sans-serif";
    ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillText("!", 0, 1);
    ctx.restore();
  }
  function drawBarrier(x, y, s) {
    const w = 64 * s, h = 74 * s;
    ctx.save(); ctx.translate(x, y);
    ctx.fillStyle = "#0b1530";
    ctx.fillRect(-w / 2, -h, 8 * s, h);
    ctx.fillRect(w / 2 - 8 * s, -h, 8 * s, h);
    for (let i = 0; i < 4; i++) {
      ctx.fillStyle = i % 2 ? "#f8fafc" : "#f59e0b";
      ctx.fillRect(-w / 2 + (w / 4) * i, -h, w / 4, 26 * s);
    }
    ctx.strokeStyle = "#7a5200"; ctx.lineWidth = Math.max(1, 2 * s);
    ctx.strokeRect(-w / 2, -h, w, 26 * s);
    ctx.restore();
  }
  function drawGate(x, y, s) {
    const w = 70 * s, h = 86 * s;
    ctx.save(); ctx.translate(x, y);
    ctx.fillStyle = "#0b1530";
    ctx.fillRect(-w / 2, -h, 7 * s, h);
    ctx.fillRect(w / 2 - 7 * s, -h, 7 * s, h);
    ctx.fillStyle = "#7c3aed";
    ctx.fillRect(-w / 2, -h, w, 20 * s);
    ctx.fillStyle = "#ede9fe";
    ctx.font = "800 " + Math.max(8, Math.round(13 * s)) + "px 'Baloo 2', sans-serif";
    ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillText("SLIDE", 0, -h + 10 * s);
    ctx.restore();
  }
  function drawPlayer(t) {
    const s = sFor(1);
    const x = xFor(lanePos, 1), gy = yFor(1);
    const lift = jumpH() * 130;
    const isSlide = sliding();
    const blink = performance.now() < invulnUntil && Math.floor(t / 90) % 2 === 0;
    ctx.save();
    ctx.translate(x, gy - lift);
    ctx.scale(s, s);
    if (isSlide) { ctx.translate(0, 26); ctx.scale(1.25, 0.62); }
    if (blink) ctx.globalAlpha = 0.35;
    const sw = isSlide || jumpH() > 0 ? 0 : Math.sin(t * 0.018) * 14;
    ctx.lineCap = "round";
    // legs + shoes
    ctx.strokeStyle = "#1e3a5f"; ctx.lineWidth = 13;
    ctx.beginPath(); ctx.moveTo(-6, -34); ctx.lineTo(-6 + sw, 0); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(6, -34); ctx.lineTo(6 - sw, 0); ctx.stroke();
    ctx.fillStyle = "#f59e0b";
    ctx.beginPath(); ctx.arc(-6 + sw, 2, 8, 0, 7); ctx.fill();
    ctx.beginPath(); ctx.arc(6 - sw, 2, 8, 0, 7); ctx.fill();
    // hoodie body
    ctx.fillStyle = "#16324f";
    roundRectP(-20, -78, 40, 48, 14); ctx.fill();
    ctx.fillStyle = "#ffc93c";
    ctx.fillRect(-20, -52, 40, 6);
    // arms
    ctx.strokeStyle = "#16324f"; ctx.lineWidth = 11;
    ctx.beginPath(); ctx.moveTo(-18, -68); ctx.lineTo(-26 - sw * 0.7, -40); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(18, -68); ctx.lineTo(26 + sw * 0.7, -40); ctx.stroke();
    // head + hair
    ctx.fillStyle = "#f2c89b";
    ctx.beginPath(); ctx.arc(0, -94, 17, 0, 7); ctx.fill();
    ctx.fillStyle = "#3b2a20";
    ctx.beginPath(); ctx.arc(0, -98, 17, Math.PI, 0); ctx.fill();
    ctx.restore();
    ctx.globalAlpha = 1;
  }
  function drawBuildings(par, color, bh) {
    ctx.fillStyle = color;
    const off = (dist * par) % 140;
    for (let x = -140; x < W + 140; x += 140) {
      const bx = x - off;
      const hgt = bh + (Math.abs(Math.sin(bx * 12.9898)) * 60 | 0);
      ctx.fillRect(bx, horizonY - hgt, 110, hgt);
      ctx.fillStyle = "rgba(255,200,60,0.45)";
      for (let wy = horizonY - hgt + 12; wy < horizonY - 10; wy += 22)
        for (let wx = bx + 12; wx < bx + 98; wx += 24)
          if ((wx * 7 + wy * 13) % 5 < 2) ctx.fillRect(wx, wy, 10, 12);
      ctx.fillStyle = color;
    }
  }
  function drawBG(t) {
    const g = ctx.createLinearGradient(0, 0, 0, H);
    g.addColorStop(0, "#070d24"); g.addColorStop(0.3, "#0d1b3e"); g.addColorStop(1, "#16294d");
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = "#ffffff";
    stars.forEach((st) => {
      ctx.globalAlpha = 0.35 + 0.6 * Math.abs(Math.sin(t * 0.001 + st.tw));
      ctx.beginPath(); ctx.arc(st.x * W, st.y * H, st.r, 0, 7); ctx.fill();
    });
    ctx.globalAlpha = 1;
    ctx.fillStyle = "#ffe08a";
    ctx.beginPath(); ctx.arc(W - 52, 54, 24, 0, 7); ctx.fill();
    drawBuildings(0.25, "#0a1430", 90);
    drawBuildings(0.5, "#0e1c40", 60);
    // track
    const hy = horizonY, cx = W / 2, sp = spread();
    ctx.fillStyle = "#101f42";
    ctx.beginPath();
    ctx.moveTo(cx - sp * 0.12, hy); ctx.lineTo(cx + sp * 0.12, hy);
    ctx.lineTo(cx + sp * 1.25, H); ctx.lineTo(cx - sp * 1.25, H);
    ctx.closePath(); ctx.fill();
    ctx.strokeStyle = "#ffc93c"; ctx.lineWidth = 3;
    ctx.globalAlpha = 0.45; ctx.setLineDash([14, 12]);
    [-0.5, 0.5].forEach((l) => {
      ctx.beginPath();
      ctx.moveTo(cx + l * sp * 0.12, hy);
      ctx.lineTo(cx + l * sp * 1.25, H);
      ctx.stroke();
    });
    ctx.setLineDash([]); ctx.globalAlpha = 1;
  }

  // ---- main loop ----
  let raf, lastT = 0;
  function frame(now) {
    if (!running) return;
    const dt = Math.min(0.05, (now - lastT) / 1000 || 0.016);
    lastT = now;
    const elapsed = now - t0;
    const remain = Math.max(0, Math.ceil((tEnd - now) / 1000));
    if (hudT) hudT.textContent = remain + "s";
    if (now >= tEnd) { finish(); return; }

    const progress = elapsed / DUR;
    const speed = 0.55 + 0.75 * progress;      // z-units per second; ramps up
    dist += speed * dt;

    if (jumpT >= 0) { jumpT += dt; if (jumpT >= JUMP_DUR) jumpT = -1; }
    if (slideT >= 0) { slideT += dt; if (slideT >= SLIDE_DUR) slideT = -1; }
    lanePos += (lane - lanePos) * Math.min(1, dt * 14);
    if (shake > 0) shake = Math.max(0, shake - dt * 30);

    rowTimer -= dt;
    if (rowTimer <= 0) { spawnRow(); rowTimer = 1.25 - 0.55 * progress; }

    for (let i = ents.length - 1; i >= 0; i--) {
      const e = ents[i];
      e.z += speed * dt;
      if (e.z > 1.2) { ents.splice(i, 1); continue; }
      if (!e.done && e.z >= 0.78 && e.z <= 1.05) collide(e, now);
    }

    ctx.save();
    if (shake > 0) ctx.translate((Math.random() - 0.5) * shake, (Math.random() - 0.5) * shake);
    drawBG(now);
    ents.slice().sort((a, b) => a.z - b.z).forEach((e) => {
      const x = xFor(e.lane, e.z), y = yFor(e.z), s = sFor(e.z);
      if (e.type === "coin") {
        const liftY = (e.y || 0) * 70 * s + Math.abs(Math.sin(now * 0.005 + e.z * 20)) * 4;
        drawCoin(x, y - liftY, s);
      }
      else if (e.type === "pit") drawPit(x, y, s);
      else if (e.type === "barrier") drawBarrier(x, y, s);
      else if (e.type === "gate") drawGate(x, y, s);
    });
    drawPlayer(now);
    for (let i = pops.length - 1; i >= 0; i--) {
      const p = pops[i];
      p.y -= 40 * dt; p.life -= dt * 1.4;
      if (p.life <= 0) { pops.splice(i, 1); continue; }
      ctx.globalAlpha = Math.max(0, p.life);
      ctx.fillStyle = p.color;
      ctx.font = "800 20px 'Baloo 2', sans-serif";
      ctx.textAlign = "center";
      ctx.fillText(p.txt, p.x, p.y);
      ctx.globalAlpha = 1;
    }
    ctx.restore();

    raf = requestAnimationFrame(frame);
  }

  function finish() {
    running = false;
    cancelAnimationFrame(raf);
    window.removeEventListener("keydown", keyH);
    onDone({ score, caught });
  }
  setScore();
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
