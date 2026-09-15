#!/usr/bin/env python3
"""Assemble index.html, embedding the tested fmb_core.py verbatim."""
import pathlib

core = pathlib.Path("fmb_core.py").read_text(encoding="utf-8")
assert "</script>" not in core, "core must not contain a closing script tag"

HTML = r"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fast Money Back – Abschlagszahlung</title>
<script src="https://cdn.jsdelivr.net/pyodide/v0.26.0/full/pyodide.js"></script>
<style>
  :root{
    --paper:#FAFAF7; --ink:#17181A; --muted:#6B6E73; --rule:#E2E1DB;
    --rule-strong:#C9C8C0; --primary:#26445E; --stamp:#A23B34; --field:#FFFFFF;
    --dim:#9A9CA0;
  }
  *{box-sizing:border-box}
  html{-webkit-text-size-adjust:100%}
  body{
    margin:0; background:var(--paper); color:var(--ink);
    font:15px/1.5 ui-sans-serif,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    font-variant-numeric:tabular-nums;
  }
  .wrap{max-width:820px; margin:0 auto; padding:28px 22px 80px}
  /* letterhead */
  header{border-bottom:3px double var(--rule-strong); padding-bottom:14px; margin-bottom:26px}
  header h1{margin:0; font-size:23px; font-weight:650; letter-spacing:-.01em}
  header p{margin:4px 0 0; color:var(--muted); font-size:13px}
  .status{margin-left:auto; font-size:12.5px; color:var(--muted); white-space:nowrap}
  .headrow{display:flex; align-items:baseline; gap:14px; flex-wrap:wrap}

  section{margin:22px 0}
  .step{display:flex; align-items:baseline; gap:10px; margin:0 0 12px}
  .step .n{flex:0 0 auto; width:22px; height:22px; border:1px solid var(--primary);
    color:var(--primary); border-radius:50%; font-size:12px; font-weight:600;
    display:grid; place-items:center; transform:translateY(2px)}
  .step h2{margin:0; font-size:15px; font-weight:600}
  .step .hint{color:var(--muted); font-size:13px; margin-left:2px}

  .drop{border:1px dashed var(--rule-strong); background:var(--field); border-radius:6px;
    padding:16px; display:flex; gap:12px; align-items:center; flex-wrap:wrap}
  .files{margin:8px 0 0; font-size:13px; color:var(--muted)}
  .files b{color:var(--ink); font-weight:600}

  .params{display:grid; grid-template-columns:repeat(2,minmax(220px,1fr)); gap:14px 26px}
  label.f{display:block; font-size:12.5px; color:var(--muted); margin:0 0 4px}
  input[type=text],input[type=number]{
    width:100%; padding:8px 10px; border:1px solid var(--rule-strong); border-radius:5px;
    background:var(--field); color:var(--ink); font:inherit}
  input:focus{outline:2px solid var(--primary); outline-offset:0; border-color:var(--primary)}

  .group h3{font-size:13px; font-weight:600; color:var(--primary); margin:18px 0 6px;
    padding-bottom:5px; border-bottom:1px solid var(--rule)}
  .row{display:flex; align-items:center; gap:12px; padding:7px 4px; border-bottom:1px solid var(--rule)}
  .row:last-child{border-bottom:0}
  .row input[type=checkbox]{width:17px; height:17px; accent-color:var(--primary); flex:0 0 auto}
  .row .lbl{flex:1 1 auto; min-width:0}
  .row .tag{display:inline-block; margin-left:8px; font-size:11px; color:var(--stamp);
    border:1px solid var(--stamp); border-radius:3px; padding:0 5px}
  .row .amt{flex:0 0 auto; font-weight:600}
  .row.off{color:var(--dim)}
  .row.off .amt{text-decoration:line-through; color:var(--dim)}
  .empty{color:var(--muted); font-size:13px; padding:8px 4px}

  /* the one bold element: the stamped figure */
  .summary{position:sticky; bottom:14px; margin-top:24px; background:var(--field);
    border:1px solid var(--rule-strong); border-radius:6px; padding:14px 16px;
    display:flex; align-items:center; gap:18px; flex-wrap:wrap;
    box-shadow:0 6px 20px -14px rgba(0,0,0,.35)}
  .summary .lines{font-size:13px; color:var(--muted); line-height:1.7}
  .summary .lines b{color:var(--ink); font-weight:600}
  .stamped{margin-left:auto; text-align:right}
  .stamped .k{font-size:11px; letter-spacing:.04em; color:var(--stamp)}
  .stamped .v{font-size:30px; font-weight:700; color:var(--stamp);
    border:2px solid var(--stamp); border-radius:4px; padding:2px 12px;
    display:inline-block; transform:rotate(-1.2deg)}

  .actions{display:flex; gap:10px; align-items:center; margin-top:18px; flex-wrap:wrap}
  button{font:inherit; cursor:pointer; border-radius:5px; padding:9px 16px; border:1px solid transparent}
  button:disabled{opacity:.45; cursor:not-allowed}
  .btn-primary{background:var(--stamp); color:#fff; border-color:var(--stamp)}
  .btn-primary:hover:not(:disabled){background:#8f322c}
  .btn-ghost{background:transparent; color:var(--primary); border-color:var(--rule-strong)}
  .btn-ghost:hover:not(:disabled){border-color:var(--primary)}

  .warn{background:#fbf5e9; border:1px solid #e7d6ad; color:#6b5316; border-radius:5px;
    padding:9px 12px; font-size:13px; margin:10px 0}
  .err{background:#fbeceb; border:1px solid #e3b6b2; color:#7c2a24; border-radius:5px;
    padding:9px 12px; font-size:13px; margin:10px 0; white-space:pre-wrap}
  .hide{display:none}
  @media (max-width:560px){ .params{grid-template-columns:1fr} }
  @media (prefers-reduced-motion:reduce){ *{transition:none!important} }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="headrow">
      <div>
        <h1>Antrag auf Abschlagszahlung</h1>
        <p>Reisekosten · Hochschulservice Finanzen · läuft vollständig im Browser</p>
      </div>
      <div class="status" id="status">Initialisiere …</div>
    </div>
  </header>

  <section>
    <div class="step"><span class="n">1</span>
      <div><h2>Unterlagen wählen</h2></div>
      <span class="hint">Abrechnungsantrag &amp; alle Belege (PDF/PNG) – nichts verlässt Ihren Rechner</span>
    </div>
    <div class="drop">
      <input type="file" id="files" multiple accept=".pdf,.png">
      <button class="btn-ghost" id="analyzeBtn" disabled>Analysieren</button>
    </div>
    <div class="files" id="fileList">Noch keine Dateien gewählt.</div>
    <div class="files" id="expected"></div>
    <div id="warnBox"></div>
    <div id="errBox"></div>
  </section>

  <section id="paramSec" class="hide">
    <div class="step"><span class="n">2</span>
      <div><h2>Prüfen &amp; anpassen</h2></div>
      <span class="hint">Häkchen = Beleg vorhanden</span>
    </div>

    <div class="params">
      <div><label class="f" for="pct">Abschlag (%)</label>
        <input type="number" id="pct" min="1" max="100" value="80"></div>
      <div><label class="f" for="jahr">Haushaltsjahr</label>
        <input type="number" id="jahr" min="2000" max="2100"></div>
      <div><label class="f" for="sachb">Sachbearbeiter*in (optional)</label>
        <input type="text" id="sachb" placeholder="z.H. …"></div>
      <div><label class="f" for="zusatz">Zusatzkosten Übernachtung (€)</label>
        <input type="number" id="zusatz" step="0.01" value="0"></div>
      <div><label class="f" for="manual">Gesamt manuell (€, leer = aus Belegen)</label>
        <input type="text" id="manual" placeholder=""></div>
      <div><label class="f" for="stamp">Stempel-Vorlage (amtlicher THWS-Stempel ist eingebettet – nur bei Bedarf ersetzen)</label>
        <input type="file" id="stamp" accept=".jpg,.jpeg,.png"></div>
    </div>

    <div class="group"><h3>Reisetage / Übernachtung</h3><div id="lst_reisetage"></div></div>
    <div class="group"><h3>Verkehrsmittel</h3><div id="lst_verkehrsmittel"></div></div>
    <div class="group"><h3>Nebenkosten</h3><div id="lst_nebenkosten"></div></div>

    <div class="summary">
      <div class="lines" id="breakdown">–</div>
      <div class="stamped">
        <div class="k" id="pctLabel">Abschlag 80 %</div>
        <div class="v" id="abschlag">–</div>
      </div>
    </div>

    <div class="step" style="margin-top:26px"><span class="n">3</span>
      <div><h2>Antrag erstellen</h2></div>
    </div>
    <div class="actions">
      <button class="btn-primary" id="createBtn">Antrag erstellen &amp; herunterladen</button>
      <span id="doneMsg" class="files"></span>
    </div>
  </section>
</div>

<!-- The tested Python core, run unchanged inside Pyodide -->
<script type="text/x-python" id="fmb_core_py">
__FMB_CORE_SOURCE__
</script>

<script>
const $ = (id)=>document.getElementById(id);
const status = (t)=>{ $("status").textContent = t; };
let core=null, parsed=null, selectedFiles=[];

const SECTIONS = ["reisetage","verkehrsmittel","nebenkosten"];
const DEFAULT_STAMP_B64 = "__DEFAULT_STAMP_B64__";
function b64ToBytes(b64){
  const bin=atob(b64), a=new Uint8Array(bin.length);
  for(let i=0;i<bin.length;i++) a[i]=bin.charCodeAt(i);
  return a;
}

async function boot(){
  try{
    status("Lade Python-Laufzeit …");
    const pyodide = await loadPyodide();
    status("Lade Pakete (Pillow, cryptography) …");
    await pyodide.loadPackage(["micropip","Pillow","cryptography"]);
    status("Installiere PDF-Bibliotheken …");
    const micropip = pyodide.pyimport("micropip");
    await micropip.install(["pdfplumber","fpdf2","pypdf"]);
    pyodide.FS.writeFile("fmb_core.py", $("fmb_core_py").textContent);
    await pyodide.runPythonAsync("import fmb_core");
    core = pyodide.pyimport("fmb_core");
    window._py = pyodide;
    status("Bereit.");
    $("analyzeBtn").disabled = selectedFiles.length===0;
  }catch(e){
    status("Start fehlgeschlagen");
    showErr("Konnte die Browser-Laufzeit nicht starten (Internet für den ersten Start nötig).\n"+e);
  }
}

function showErr(msg){ $("errBox").innerHTML = '<div class="err"></div>'; $("errBox").firstChild.textContent = msg; }
function clearErr(){ $("errBox").innerHTML=""; }

$("files").addEventListener("change", (ev)=>{
  selectedFiles = Array.from(ev.target.files);
  const antrag = selectedFiles.find(f=>/abrechnungsantrag/i.test(f.name));
  const names = selectedFiles.map(f=>f.name).join(", ");
  $("fileList").innerHTML = selectedFiles.length
    ? `<b>${selectedFiles.length}</b> Datei(en): ${names}` +
      (antrag ? "" : ' — <span style="color:var(--stamp)">kein Abrechnungsantrag erkannt</span>')
    : "Noch keine Dateien gewählt.";
  $("analyzeBtn").disabled = !(core && antrag);
  if(parsed) updateExpected();
});

$("analyzeBtn").addEventListener("click", analyze);
["pct","zusatz","manual"].forEach(id=>$(id).addEventListener("input", recompute));

async function analyze(){
  clearErr(); $("warnBox").innerHTML="";
  const antrag = selectedFiles.find(f=>/abrechnungsantrag/i.test(f.name));
  if(!antrag){ showErr("Bitte eine Datei mit »Abrechnungsantrag« im Namen mitwählen."); return; }
  try{
    status("Analysiere Antrag …");
    const buf = new Uint8Array(await antrag.arrayBuffer());
    const jsonStr = core.browser_parse(buf, antrag.name);
    parsed = JSON.parse(jsonStr);
    if(!$("jahr").value) $("jahr").value = new Date().getFullYear();
    render();
    $("paramSec").classList.remove("hide");
    updateExpected();
    status("Bereit.");
  }catch(e){
    status("Analyse fehlgeschlagen");
    showErr(String(e.message||e));
  }
}

function updateExpected(){
  const box = $("expected");
  const exp = (parsed && parsed.zugehoerige_dateien) || [];
  if(!exp.length){ box.innerHTML=""; return; }
  const have = new Set(selectedFiles.map(f=>f.name.toLowerCase()));
  const chips = exp.map(n=>{
    const ok = have.has(n.toLowerCase());
    return `<span style="display:inline-block;margin-right:12px;color:${ok?'var(--primary)':'var(--muted)'}">`
         + `${ok?'✓':'○'} ${n}</span>`;
  }).join("");
  const missing = exp.filter(n=>!have.has(n.toLowerCase()));
  box.innerHTML = `<div style="margin-top:6px">Im Antrag gelistete Belege: ${chips}</div>`
    + (missing.length ? `<div class="warn">Diese Belege sind im Antrag genannt, aber noch nicht ausgewählt: ${missing.join(", ")}</div>` : "");
}

function render(){
  if(parsed.warnings && parsed.warnings.length){
    $("warnBox").innerHTML = parsed.warnings
      .map(w=>`<div class="warn">⚠ ${w}</div>`).join("");
  }
  for(const sec of SECTIONS){
    const host = $("lst_"+sec); host.innerHTML="";
    const items = parsed[sec] || [];
    if(!items.length){ host.innerHTML='<div class="empty">Keine Positionen erkannt.</div>'; continue; }
    items.forEach((it, i)=>{
      const row = document.createElement("div");
      row.className = "row" + (it.present?"":" off");
      const cb = document.createElement("input");
      cb.type="checkbox"; cb.checked=it.present;
      cb.addEventListener("change", ()=>{ it.present=cb.checked; row.classList.toggle("off",!cb.checked); recompute(); });
      const lbl = document.createElement("div"); lbl.className="lbl";
      lbl.textContent = it.label;
      if(it.is_pkw){ const t=document.createElement("span"); t.className="tag"; t.textContent="PKW"; lbl.appendChild(t); }
      const amt = document.createElement("div"); amt.className="amt";
      amt.textContent = eur(it.betrag);
      row.append(cb,lbl,amt); host.appendChild(row);
    });
  }
  recompute();
}

function eur(n){ return (n||0).toLocaleString("de-DE",{minimumFractionDigits:2,maximumFractionDigits:2})+" €"; }
function num(v){ v=String(v).trim().replace(",","."); if(v==="") return 0; const f=parseFloat(v); return isNaN(f)?0:f; }
function sum(sec){ return (parsed[sec]||[]).reduce((a,it)=> a + (it.present? it.betrag:0), 0); }

function recompute(){
  if(!parsed) return;
  const pct = Math.max(1, Math.min(100, num($("pct").value)||80));
  const zus = num($("zusatz").value);
  const manRaw = $("manual").value.trim();
  const rt = sum("reisetage") + zus;
  const vk = sum("verkehrsmittel");
  const nk = sum("nebenkosten");
  const gesamt = manRaw!=="" ? num(manRaw) : (rt+vk+nk);
  const abschlag = gesamt * pct/100;
  $("breakdown").innerHTML =
    `Übernachtung <b>${eur(rt)}</b> &nbsp;·&nbsp; Verkehr <b>${eur(vk)}</b> &nbsp;·&nbsp; `+
    `Neben <b>${eur(nk)}</b><br>Gesamt <b>${eur(gesamt)}</b>`;
  $("pctLabel").textContent = `Abschlag ${pct} %`;
  $("abschlag").textContent = eur(abschlag);
}

$("createBtn").addEventListener("click", generate);
async function generate(){
  if(!parsed){ return; }
  clearErr();
  try{
    status("Erstelle PDF …"); $("createBtn").disabled=true; $("doneMsg").textContent="";
    const params = {
      percent: Math.max(1,Math.min(100,num($("pct").value)||80))/100,
      zusatz: num($("zusatz").value),
      manual: $("manual").value.trim()==="" ? null : num($("manual").value),
      sachbearbeiter: $("sachb").value,
      jahr: parseInt($("jahr").value||new Date().getFullYear(),10),
      selections: Object.fromEntries(SECTIONS.map(s=>[s,(parsed[s]||[]).map(it=>!!it.present)]))
    };
    const files = [];
    for(const f of selectedFiles){ files.push([f.name, new Uint8Array(await f.arrayBuffer())]); }
    const stampFile = $("stamp").files[0];
    const stamp = stampFile ? new Uint8Array(await stampFile.arrayBuffer())
                            : (DEFAULT_STAMP_B64 ? b64ToBytes(DEFAULT_STAMP_B64) : null);
    const b64 = core.browser_assemble(JSON.stringify(params), files, stamp);
    const name = core.browser_final_name();
    downloadPdf(b64, name);
    $("doneMsg").innerHTML = `✓ Erstellt: <b>${name}</b> — anschließend unterschreiben lassen und per Hauspost senden.`;
    status("Fertig.");
  }catch(e){
    status("Erstellung fehlgeschlagen");
    showErr(String(e.message||e));
  }finally{
    $("createBtn").disabled=false;
  }
}

function downloadPdf(b64, name){
  const bin = atob(b64), arr = new Uint8Array(bin.length);
  for(let i=0;i<bin.length;i++) arr[i]=bin.charCodeAt(i);
  const url = URL.createObjectURL(new Blob([arr],{type:"application/pdf"}));
  const a = document.createElement("a"); a.href=url; a.download=name; a.click();
  setTimeout(()=>URL.revokeObjectURL(url), 4000);
}

boot();
</script>
</body>
</html>
"""

out = HTML.replace("__FMB_CORE_SOURCE__", core)

import base64
stamp_path = pathlib.Path("stamp_blank.jpg")
stamp_b64 = base64.b64encode(stamp_path.read_bytes()).decode("ascii") if stamp_path.exists() else ""
out = out.replace("__DEFAULT_STAMP_B64__", stamp_b64)

pathlib.Path("index.html").write_text(out, encoding="utf-8")
print("index.html written:", len(out), "bytes; stamp embedded:", bool(stamp_b64))
