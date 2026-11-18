"use strict";
const $ = (s) => document.querySelector(s);
const nf0 = new Intl.NumberFormat("it-IT", { maximumFractionDigits: 0, useGrouping: "always" });
const nf1 = new Intl.NumberFormat("it-IT", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const nf2 = new Intl.NumberFormat("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const PAL = { blue: "#2a78d6", orange: "#eb6834", aqua: "#1baf7a", yellow: "#eda100", magenta: "#e87ba4", violet: "#6250d6", red: "#e34948", grey: "#98a2b3" };
let file = null, charts = {};

function fmt(v, f) {
  if (v === null || v === undefined || Number.isNaN(v)) return "n.d.";
  switch (f) {
    case "pct": return nf0.format(v * 100) + "%";
    case "pct1": return nf1.format(v * 100) + "%";
    case "dec2": return nf2.format(v);
    case "eur": return "€ " + nf0.format(v);
    default: return nf0.format(v);
  }
}
const eur = (v) => "€ " + nf0.format(v);
const meseIt = (ym) => { const [y, m] = ym.split("-"); return new Date(+y, +m - 1, 1).toLocaleDateString("it-IT", { month: "short", year: "2-digit" }); };

function el(tag, text, cls) { const e = document.createElement(tag); if (text !== undefined) e.textContent = text; if (cls) e.className = cls; return e; }
function badge(stato) { return el("span", stato === "N.D." ? "N.D." : stato, "badge " + (stato === "N.D." ? "ND" : stato)); }

async function init() {
  try { const c = await (await fetch("/api/config")).json();
    $("#target").value = c.target_mensile; $("#tasso").value = c.tasso_vittoria_stimato; $("#correggi").checked = c.correggi_date; } catch (e) {}
  const drop = $("#drop");
  ["dragenter", "dragover"].forEach(t => drop.addEventListener(t, e => { e.preventDefault(); drop.classList.add("over"); }));
  ["dragleave", "drop"].forEach(t => drop.addEventListener(t, e => { e.preventDefault(); drop.classList.remove("over"); }));
  drop.addEventListener("drop", e => setFile(e.dataTransfer.files[0]));
  $("#file").addEventListener("change", e => setFile(e.target.files[0]));
  $("#vai").addEventListener("click", () => calcola());
  document.querySelectorAll(".tab").forEach(b => b.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(x => x.classList.toggle("active", x === b));
    document.querySelectorAll(".tabpane").forEach(p => p.hidden = p.id !== "tab-" + b.dataset.tab);
  }));
}
function setFile(f) {
  if (!f) return;
  if (!/\.xlsx$/i.test(f.name)) return mostraErrore("Serve un file Excel .xlsx.");
  file = f; $("#nomefile").textContent = f.name; $("#vai").disabled = false; mostraErrore("");
  calcola(true);
}
function mostraErrore(t) { const e = $("#errore"); e.hidden = !t; e.textContent = t || ""; }

async function calcola(primo) {
  if (!file) return;
  const fd = new FormData();
  fd.append("file", file);
  if (!primo) {
    if ($("#mese").value) fd.append("mese", $("#mese").value);
    if ($("#controllo").value) fd.append("controllo", $("#controllo").value);
  }
  fd.append("target", $("#target").value); fd.append("tasso_vittoria", $("#tasso").value);
  fd.append("correggi_date", $("#correggi").checked ? "true" : "false");
  $("#vai").disabled = true; $("#vai").textContent = "Calcolo…"; mostraErrore("");
  try {
    const r = await fetch("/api/analizza", { method: "POST", body: fd });
    const j = await r.json();
    if (!r.ok) throw new Error(j.errore || "Errore");
    mostra(j, primo);
  } catch (e) { mostraErrore(e.message); }
  finally { $("#vai").disabled = false; $("#vai").textContent = "Calcola"; }
}

function mostra(j, primo) {
  if (primo || $("#mese").options.length <= 1) {
    const s = $("#mese"); s.innerHTML = "";
    j.mesi_disponibili.forEach(m => { const o = el("option", m); o.value = m; s.appendChild(o); });
  }
  $("#mese").value = j.mese; $("#controllo").value = j.controllo;
  $("#risultati").hidden = false; $("#tabs").hidden = false;
  const p = j.pacing, last = j.trend[j.trend.length - 1];

  const cards = $("#cards"); cards.innerHTML = "";
  [["New MRR firmato", eur(last.new_mrr), "su target " + eur(j.target)],
   ["% sul target", fmt(last.new_mrr / j.target, "pct"), "Won: " + last.won],
   ["Pacing vs media 3 mesi", fmt(j.semaforo.find(s => s.id === "pacing").valore, "pct"), "al giorno " + p.giorno],
   ["Gap residuo", eur(Math.max(0, p.gap)), p.gap <= 0 ? "target raggiunto" : "verso il target"],
   ["Allarmi / attenzioni", j.conteggio.allarmi + " / " + j.conteggio.attenzioni, "su " + j.semaforo.length + " indicatori"]]
    .forEach(([l, v, s]) => { const c = el("div", undefined, "card"); c.append(el("div", l, "l"), el("div", v, "v"), el("div", s, "s")); cards.appendChild(c); });
  $("#conteggio").textContent = "— " + j.conteggio.allarmi + " allarmi, " + j.conteggio.attenzioni + " attenzioni · " + meseIt(j.mese);

  const tb = $("#semaforo tbody"); tb.innerHTML = "";
  j.semaforo.forEach(s => {
    const tr = el("tr"); const sogl = (v) => fmt(v, s.formato);
    const e = el("td"); e.appendChild(badge(s.stato));
    tr.append(el("td", s.etichetta), el("td", fmt(s.valore, s.formato), "n"), el("td", (s.direzione === "alto" ? "< " : "> ") + sogl(s.attenzione), "n"),
      el("td", (s.direzione === "alto" ? "< " : "> ") + sogl(s.allarme), "n"), e, el("td", s.stato === "OK" ? "" : s.suggerimento));
    tb.appendChild(tr);
  });
  $("#nota-cop").textContent = p.nota_copertura ? "Copertura pipeline: " + p.nota_copertura + "." : "";

  const rb = $("#ruoli tbody"); rb.innerHTML = "";
  j.ruoli_meta.forEach(r => { const tr = el("tr"); const e = el("td"); e.appendChild(badge(r.segnale === "BASSA RESA" ? "ALLARME" : r.segnale === "ok" ? "OK" : "N.D.")); e.firstChild.textContent = r.segnale;
    tr.append(el("td", r.ruolo), el("td", nf0.format(r.lead_meta), "n"), el("td", nf0.format(r.opportunity), "n"), el("td", fmt(r.pct, "pct1"), "n"), e); rb.appendChild(tr); });

  const qb = $("#qualita tbody"); qb.innerHTML = "";
  j.qualita.forEach(q => { const tr = el("tr"); tr.append(el("td", q.controllo), el("td", fmt(q.valore, q.formato), "n"), el("td", q.nota)); qb.appendChild(tr); });

  disegna(j);
}

function chart(id, cfg) {
  if (charts[id]) charts[id].destroy();
  cfg.options = Object.assign({ responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
    plugins: { legend: { position: "bottom", labels: { boxWidth: 12 } } } }, cfg.options || {});
  charts[id] = new Chart($(id), cfg);
}
function disegna(j) {
  const T = j.trend, lab = T.map(t => meseIt(t.mese)), p = j.pacing;
  const ytick = { ticks: { callback: v => nf0.format(v) } };
  chart("#c-pacing", { type: "line", data: { labels: p.giorni, datasets: [
    { label: "Mese in esame", data: p.mese.map((v, i) => i < p.giorno ? v : null), borderColor: PAL.blue, backgroundColor: PAL.blue, pointRadius: 0, borderWidth: 2.5 },
    { label: "Media ultimi 3 mesi", data: p.serie_media3, borderColor: PAL.grey, pointRadius: 0, borderWidth: 2 },
    { label: "Percorso lineare verso target", data: p.lineare, borderColor: PAL.orange, borderDash: [6, 4], pointRadius: 0, borderWidth: 2 }] },
    options: { scales: { y: ytick, x: { title: { display: true, text: "Giorno del mese" } } } } });
  chart("#c-mrr", { type: "bar", data: { labels: lab, datasets: [
    { label: "New MRR firmato", data: T.map(t => t.new_mrr), backgroundColor: PAL.blue, borderRadius: 4 },
    { type: "line", label: "Target", data: T.map(t => t.target), borderColor: PAL.orange, borderDash: [6, 4], pointRadius: 0, borderWidth: 2 }] },
    options: { scales: { y: ytick } } });
  chart("#c-eff", { type: "line", data: { labels: lab, datasets: [
    { label: "New MRR per € di costo sales", data: T.map(t => t.mrr_per_costo), borderColor: PAL.violet, backgroundColor: PAL.violet, borderWidth: 2.5, pointRadius: 4, spanGaps: false }] },
    options: { scales: { y: { beginAtZero: true } } } });
  chart("#c-funnel", { type: "line", data: { labels: lab, datasets: [
    { label: "Lead → Opportunity", data: T.map(t => t.lead_opp * 100), borderColor: PAL.blue, backgroundColor: PAL.blue, borderWidth: 2.5, pointRadius: 4 },
    { label: "Vittorie su opportunity chiuse", data: T.map(t => t.vitt_opp * 100), borderColor: PAL.aqua, backgroundColor: PAL.aqua, borderWidth: 2.5, pointRadius: 4 },
    { label: "Lead → Won", data: T.map(t => t.lead_won * 100), borderColor: PAL.orange, backgroundColor: PAL.orange, borderWidth: 2.5, pointRadius: 4 }] },
    options: { scales: { y: { ticks: { callback: v => v + "%" }, beginAtZero: true } } } });

  const cols = [PAL.blue, PAL.orange, PAL.aqua, PAL.yellow, PAL.violet, PAL.magenta, PAL.grey];
  const keys = ["AE IB FC", "BDR IB", "BDR OB SMB", "BDR MM", "OBFC", "AE MM", "Altri / non assegnato"];
  chart("#c-ruoli", { type: "bar", data: { labels: j.meta_per_ruolo.map(r => meseIt(r.mese)),
    datasets: keys.map((k, i) => ({ label: k, data: j.meta_per_ruolo.map(r => r[k]), backgroundColor: cols[i], borderColor: "#fff", borderWidth: 1 })) },
    options: { scales: { x: { stacked: true }, y: { stacked: true, ticks: { callback: v => nf0.format(v) } } } } });
  const line2 = (id, a, b, la, lb) => chart(id, { type: "line", data: { labels: lab, datasets: [
    { label: la, data: T.map(t => t[a]), borderColor: PAL.blue, backgroundColor: PAL.blue, borderWidth: 2.5, pointRadius: 4 },
    { label: lb, data: T.map(t => t[b]), borderColor: PAL.orange, backgroundColor: PAL.orange, borderWidth: 2.5, pointRadius: 4 }] },
    options: { scales: { y: { beginAtZero: true, ticks: { callback: v => nf0.format(v) } } } } });
  line2("#c-cpl", "cpl_meta", "cpl_google", "Meta", "Google");
  line2("#c-cpo", "cpo_meta", "cpo_google", "Meta", "Google");
  const chn = ["Meta paid", "Google paid", "Altri paid", "Outbound e outreach", "Altri canali"];
  chart("#c-canali", { type: "bar", data: { labels: lab, datasets: chn.map((k, i) => ({ label: k, data: T.map(t => t["mrr_" + k]), backgroundColor: cols[i], borderColor: "#fff", borderWidth: 1 })) },
    options: { scales: { x: { stacked: true }, y: { stacked: true, ticks: { callback: v => nf0.format(v) } } } } });
}
init();
