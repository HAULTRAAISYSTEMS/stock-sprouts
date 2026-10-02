/* Stock Sprouts — shared frontend helpers. No emojis; SVG art only. */

function toast(msg) {
  const el = document.getElementById("toast");
  if (!el) return;
  el.textContent = msg;
  el.style.display = "block";
  clearTimeout(el._t);
  el._t = setTimeout(() => { el.style.display = "none"; }, 3200);
}

async function api(path, data) {
  const opts = { headers: { "Content-Type": "application/json" } };
  if (data !== undefined) {
    opts.method = "POST";
    opts.body = JSON.stringify(data);
  }
  const res = await fetch(path, opts);
  const body = await res.json().catch(() => ({}));
  if (!res.ok || body.ok === false) {
    throw new Error(body.error || ("Request failed (" + res.status + ")"));
  }
  return body;
}

function money(n) {
  return "$" + Number(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function chgSpan(pct) {
  const cls = pct >= 0 ? "chg-up" : "chg-down";
  const arrow = pct >= 0 ? "▲" : "▼";
  return '<span class="' + cls + '">' + arrow + " " + Math.abs(pct).toFixed(2) + "%</span>";
}
