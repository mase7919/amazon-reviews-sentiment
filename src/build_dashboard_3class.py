#!/usr/bin/env python3
"""Step 6: build the balanced three-class dashboard (single self-contained HTML).

Reads the SAVED Step 6 results (results/step6_metrics.json + step6_llm.jsonl) and
bakes all figures into a dependency-free static HTML file (pure CSS + a small
client-side filter script). Nothing is recomputed inconsistently by JS.

This REPLACES dashboard/dashboard.html as the main dashboard (per the assignment,
the three-class run now carries through). The earlier Step 2 binary dashboard is
preserved as a historical artifact (copy it to dashboard/step2_binary_dashboard.html
before regenerating via the build_dashboard.py script).

Output: dashboard/dashboard.html
"""

from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = json.loads((ROOT / "results" / "step6_metrics.json").read_text(encoding="utf-8"))
RAW = [json.loads(l) for l in
       (ROOT / "results" / "step6_llm.jsonl").read_text(encoding="utf-8").splitlines()
       if l.strip()]
OUT = ROOT / "dashboard" / "dashboard.html"

THREE = ("POSITIVE", "NEUTRAL", "NEGATIVE")
M = RESULTS
conf = M["confusion_matrix_rows_actual_cols_predicted"]
rec, prec = M["class_recall_pct"], M["class_precision_pct"]
mismatches = M["mismatches"]
mismatch_count = len(mismatches)
total = M["total"]
accuracy = M["overall_accuracy_pct"]
correct = M["total_correct"]
incorrect = M["total_incorrect"]
macro = M["macro_recall_pct"]
neut_split = M["neutral_distribution"]
actual_counts = {c: sum(conf[c][p] for p in THREE) for c in THREE}  # 50/50/50


def esc(s) -> str:
    return html.escape(str(s) if s is not None else "")


def cm_shade(count: int, tot: int, ok: bool) -> str:
    if ok:
        return f"background:rgba(52,211,153,{0.08 + 0.55*(count/ tot if tot else 0):.2f})"
    return f"background:rgba(248,113,113,{0.08 + 0.40*(count/max(count,1)):.2f})"


# --- table rows ---
mismatch_rows = {m_["row"] for m_ in mismatches}
tbl = []
for r in RAW:
    cls = "row-err" if r["row"] in mismatch_rows else ""
    pred = r["predicted"] or "?"
    exp = r["ground_truth"]
    rating = r["rating"]
    rating_int = int(round(rating)) if isinstance(rating, (int, float)) else ""
    stars = "★" * rating_int if isinstance(rating_int, int) and rating_int else "—"
    ts = (r["text"] or "[no body]").strip()
    ts = (ts[:140] + "…") if len(ts) > 140 else ts
    matched = (pred == exp)
    tbl.append(f"""
    <tr class="{cls}" data-match="{'1' if matched else '0'}" data-actual="{exp.lower()}"
        data-pred="{pred.lower()}" data-rating="{rating_int}">
      <td class="c">{r['row']}</td>
      <td class="c"><span class="stars" title="rating {esc(rating)}">{esc(stars)}&nbsp;{esc(rating)}</span></td>
      <td class="t">{esc(r['title'])}</td>
      <td class="t" title="{esc(r['text'] or '')}">{esc(ts)}</td>
      <td class="c"><span class="chip {exp.lower()}">{exp}</span></td>
      <td class="c"><span class="chip {pred.lower()}">{pred}</span></td>
      <td class="c">{'<span class="dot ok">✓</span>' if matched else '<span class="dot bad">✗</span>'}</td>
    </tr>""")
TABLE_HTML = "".join(tbl)

# --- mismatch cards (first 12 shown fully in spotlight; all in table/filter) ---
mc = []
for m_ in mismatches[:12]:
    ts = (m_.get("text") or "[no body]").strip()
    ts = (ts[:180] + "…") if len(ts) > 180 else ts
    mc.append(f"""
    <div class="mcard">
      <div class="mcard-top"><span class="mcard-row">Row {m_.get('row')}</span><span class="mcard-rating">rating {esc(m_.get('rating'))}</span></div>
      <div class="mcard-title">{esc(m_.get('title'))}</div>
      <div class="mcard-text">{esc(ts)}</div>
      <div class="mcard-pred"><span class="chip {(m_.get('ground_truth') or '').lower()}">actual {esc(m_.get('ground_truth'))}</span>
        <span class="arrow">→</span><span class="chip {(m_.get('predicted') or '').lower()}">predicted {esc(m_.get('predicted'))}</span></div>
    </div>""")
MCARDS = "".join(mc)

# --- precompute matrix rows + perf cards (single-level f-strings, no nesting) ---
MATRIX_ROWS = ""
for a in THREE:
    cells = ""
    for p in THREE:
        ok = (a == p)
        tag = "ok" if ok else f"{a[:1]}→{p[:1]}"
        cls = 'class="cell emph"' if (a == "NEUTRAL" and p == "NEGATIVE") else 'class="cell"'
        cells += (f'<td {cls} style="{cm_shade(conf[a][p], actual_counts[a], ok)}">'
                  f"{conf[a][p]}<span class=\"sub\">{tag}</span></td>")
    MATRIX_ROWS += f'<tr><th class="rowhead">Actual {a} ({actual_counts[a]})</th>{cells}</tr>'

PERF_HTML = ""
for c in THREE:
    col = {"POSITIVE": "g", "NEUTRAL": "b", "NEGATIVE": "r"}[c]
    color = {"POSITIVE": "var(--positive)", "NEUTRAL": "var(--neutral)", "NEGATIVE": "var(--negative)"}[c]
    PERF_HTML += (f'<div class="perf"><div class="cls" style="color:{color}">{c}</div>'
                  f'<div class="row"><span>Recall ({conf[c][c]}/{actual_counts[c]})</span><b>{rec[c]}%</b></div>'
                  f'<div class="track"><div class="fill {col}" style="width:{rec[c]}%"></div></div>'
                  f'<div class="row"><span>Precision</span><b>{prec[c]}%</b></div>'
                  f'<div class="track"><div class="fill {col}" style="width:{prec[c]}%"></div></div></div>')


CSS = r"""
:root{
  --bg:#0d1017; --panel:#151a24; --panel-2:#1b2130; --line:#262e3f;
  --text:#e9ecf3; --muted:#98a2b8; --faint:#6b7689;
  --positive:#34d399; --positive-soft:rgba(52,211,153,.14);
  --neutral:#a3a3ff;  --neutral-soft:rgba(163,163,255,.14);
  --negative:#fb7185; --negative-soft:rgba(251,113,133,.14);
  --correct:#2dd4bf; --incorrect:#fb7185; --accent:#a78bfa; --warn:#fbbf24;
}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:"Segoe UI",system-ui,-apple-system,Roboto,Helvetica,Arial,sans-serif;
  background:var(--bg); color:var(--text); line-height:1.5; -webkit-font-smoothing:antialiased}
.wrap{max-width:1200px;margin:0 auto;padding:40px 28px 72px}
header{border-bottom:1px solid var(--line);padding-bottom:22px;margin-bottom:30px}
.kicker{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--faint);margin-bottom:8px}
h1{font-size:29px;font-weight:650;letter-spacing:-.01em}
.sub{color:var(--muted);font-size:14px;margin-top:8px}
.meta{color:var(--faint);font-size:12px;margin-top:12px}.meta code{background:var(--panel-2);padding:1px 5px;border-radius:4px;color:var(--accent)}
section{margin-bottom:44px}
h2{font-size:19px;font-weight:600;margin-bottom:6px}
.sec-desc{color:var(--muted);font-size:13.5px;margin-bottom:18px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px}
.stat .label{font-size:12px;color:var(--muted)} .stat .value{font-size:27px;font-weight:700;margin-top:6px}
.stat .note{font-size:12px;color:var(--faint);margin-top:2px}
.value.teal{color:var(--correct)}.value.rose{color:var(--incorrect)}.value.purple{color:var(--accent)}
.value.green{color:var(--positive)}.value.blu{color:var(--neutral)}.value.red{color:var(--negative)}
.two-col{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.chartbox{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:20px 20px 22px}
.chartbox h3{font-size:14px;font-weight:600;margin-bottom:4px}.chartbox .cap{font-size:12.5px;color:var(--muted);margin-bottom:14px}
.bar{display:flex;height:30px;border-radius:8px;overflow:hidden;border:1px solid var(--line)}
.bar .seg{display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:600;min-width:0;color:#0d1017}
.bar .seg.pos{background:var(--positive)}.bar .seg.neu{background:var(--neutral);color:#0d1017}
.bar .seg.neg{background:var(--negative)}
.bar .seg.ok{background:var(--correct)}.bar .seg.no{background:var(--incorrect)}
.legend{display:flex;gap:18px;margin-top:12px;flex-wrap:wrap}.legend span{font-size:12.5px;color:var(--muted);display:flex;align-items:center;gap:7px}
.legend i{width:11px;height:11px;border-radius:3px;display:inline-block}
.donut-wrap{display:flex;align-items:center;gap:24px}
.donut{width:132px;height:132px;border-radius:50%;display:grid;place-items:center;flex:none}
.donut .inner{width:84px;height:84px;border-radius:50%;background:var(--panel);display:grid;place-items:center;text-align:center}
.donut .inner b{font-size:18px;display:block;line-height:1.1}.donut .inner small{font-size:11px;color:var(--muted)}
.matrix{width:100%;border-collapse:collapse;max-width:560px;border:1px solid var(--line);border-radius:12px;overflow:hidden}
.matrix th,.matrix td{padding:13px 12px;text-align:center;font-size:13px}
.matrix thead th{color:var(--muted);background:var(--panel-2);font-size:12px}
.matrix .rowhead{font-weight:600;background:var(--panel-2);white-space:nowrap;text-align:left}
.matrix td.cell{font-size:20px;font-weight:700;border:1px solid var(--line)}
.matrix td .sub{display:block;font-size:10.5px;color:var(--faint);font-weight:500;margin-top:2px}
.cmat{display:flex;gap:20px;align-items:flex-start;flex-wrap:wrap}
.perf-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}
.perf{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px 20px}
.perf .cls{font-weight:650;font-size:14.5px}
.perf .row{display:flex;justify-content:space-between;margin:11px 0 4px;font-size:12.5px;color:var(--muted)}
.perf .track{height:9px;border-radius:6px;background:var(--panel-2);overflow:hidden}
.perf .fill{height:100%;border-radius:6px}
.fill.g{background:var(--positive)}.fill.b{background:var(--neutral)}.fill.r{background:var(--negative)}
.context{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--accent);border-radius:10px;padding:18px 20px;font-size:14px}
.context ul{list-style:none;display:grid;gap:8px}.context li{color:var(--muted)}.context b{color:var(--text)}.context .hl{color:var(--warn)}
/* step7: star rating distribution */
.rating-wrap{display:flex;align-items:flex-end;gap:22px;justify-content:center;padding-top:8px}
.rbar{display:flex;flex-direction:column;align-items:center;gap:8px}
.rbar .rbar-val{font-size:15px;font-weight:700}
.rbar .rbar-fill{width:30px;border-radius:5px 5px 2px 2px;min-height:3px}
.rbar .rbar-label{font-size:11.5px;color:var(--muted)}
.rbar.c1 .rbar-fill{background:var(--negative)}
.rbar.c2 .rbar-fill{background:#fb923c}
.rbar.c3 .rbar-fill{background:var(--neutral)}
.rbar.c4 .rbar-fill{background:#34d399}
.rbar.c5 .rbar-fill{background:var(--positive)}
/* step7: actual vs predicted */
.ap-row{display:grid;grid-template-columns:110px 1fr 1fr;gap:14px;align-items:center;margin:12px 0}
.ap-label{font-size:13px;font-weight:650}
.ap-track{display:flex;align-items:center;gap:8px}
.ap-track .ap-cap{font-size:11px;color:var(--faint);min-width:34px;text-align:right}
.ap-track .ap-bar{height:18px;border-radius:5px;min-width:2px}
.ap-legend{display:flex;gap:18px;margin-top:14px;color:var(--muted);font-size:12.5px}
/* step7: recall rows */
.recall-rows{display:grid;gap:16px}
.recall-row .rr-top{display:flex;justify-content:space-between;font-size:13.5px;margin-bottom:5px}
.recall-row .rr-top b{font-weight:700}
.recall-row .rr-track{height:22px;border-radius:6px;background:var(--panel-2);overflow:hidden;position:relative}
.recall-row .rr-fill{height:100%;border-radius:6px}
.recall-row .rr-fill.g{background:var(--positive)}.recall-row .rr-fill.b{background:var(--neutral)}.recall-row .rr-fill.r{background:var(--negative)}
.recall-row .rr-pct{position:absolute;right:8px;top:50%;transform:translateY(-50%);font-size:12px;font-weight:700;color:#0d1017}
/* confusion emphasis (scale preserved) */
td.emph{box-shadow:inset 0 -3px 0 var(--incorrect);color:#fff}
td.emph .sub{color:var(--incorrect);font-weight:700}
/* step2 vs step6 compare */
.compare{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.cmp{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px}
.cmp .cmp-tag{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--faint)}
.cmp .cmp-num{font-size:26px;font-weight:700;margin-top:4px}
.cmp .cmp-sub{font-size:12px;color:var(--muted)}
.cmp .cmp-note{font-size:12px;color:var(--faint);margin-top:6px;font-style:italic}
.warn{color:var(--warn)}
/* emotion compact */
.emo-2col{display:grid;grid-template-columns:1fr 1fr;gap:18px}
.emo-box h4{font-size:13px;font-weight:650;margin-bottom:10px}
.emo-pair{display:grid;grid-template-columns:90px 1fr 34px;gap:8px;align-items:center;font-size:12px;margin:4px 0;color:var(--muted)}
.emo-pair b{color:var(--text);text-align:right}
.emo-pair .th{height:9px;border-radius:5px}
.emo-agree{margin-top:14px;font-size:13px;color:var(--muted)}
.emo-agree b{color:var(--accent)}
.mcards{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}
.mcard{background:var(--negative-soft);border:1px solid rgba(251,113,133,.35);border-radius:12px;padding:14px}
.mcard-top{display:flex;justify-content:space-between;font-size:12px;color:var(--incorrect);margin-bottom:6px}
.mcard-row{font-weight:700}.mcard-title{font-weight:650;font-size:13.5px}.mcard-text{font-size:12.5px;color:var(--muted);margin:7px 0 10px}
.mcard-pred{display:flex;align-items:center;gap:8px}.arrow{color:var(--muted)}
.mcard+.mcard-note{display:block}
.chip{font-size:11px;font-weight:650;padding:3px 9px;border-radius:20px;display:inline-block}
.chip.positive{color:var(--positive);background:var(--positive-soft)}
.chip.neutral{color:var(--neutral);background:var(--neutral-soft)}
.chip.negative{color:var(--negative);background:var(--negative-soft)}
.dot{display:inline-block;width:20px;height:20px;border-radius:50%;line-height:20px;font-size:11px;font-weight:700;text-align:center}
.dot.ok{background:var(--positive-soft);color:var(--positive)}.dot.bad{background:var(--negative-soft);color:var(--negative)}
.stars{color:var(--warn);letter-spacing:1px}
.filter-bar{display:flex;flex-wrap:wrap;gap:16px;align-items:flex-end;margin-bottom:12px}
.fil-group{display:flex;flex-direction:column;gap:6px}
.fil-label{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--faint)}
.fbtns{display:flex;background:var(--panel-2);border:1px solid var(--line);border-radius:10px;padding:3px;gap:2px}
.fbtn{background:transparent;border:0;color:var(--muted);font-family:inherit;font-size:12px;font-weight:600;padding:6px 11px;border-radius:8px;cursor:pointer}
.fbtn:hover{color:var(--text)}.fbtn.active{background:var(--accent);color:#12141c}
tr.hidden-row{display:none}
.live-count{margin-left:auto;font-size:13px;font-weight:600;color:var(--text);background:var(--panel-2);border:1px solid var(--line);border-radius:20px;padding:8px 14px;white-space:nowrap}
.live-count b{color:var(--accent)}
.table-wrap{overflow-x:auto;border:1px solid var(--line);border-radius:12px}
table.reviews{width:100%;border-collapse:collapse;font-size:12.5px;min-width:860px}
table.reviews th{position:sticky;top:0;background:var(--panel-2);text-align:left;padding:10px 12px;font-size:11px;letter-spacing:.05em;color:var(--muted);border-bottom:1px solid var(--line)}
table.reviews td{padding:9px 12px;border-bottom:1px solid var(--line);vertical-align:top}
table.reviews td.c{text-align:center;white-space:nowrap}
table.reviews tr:hover td{background:rgba(167,139,250,.04)}
table.reviews tr.row-err td{background:rgba(251,113,133,.09)}
table.reviews tr.row-err:hover td{background:rgba(251,113,133,.15)}
footer{color:var(--faint);font-size:12px;border-top:1px solid var(--line);padding-top:18px}
@media (max-width:840px){.two-col,.perf-grid{grid-template-columns:1fr}.wrap{padding:24px 16px 56px}h1{font-size:23px}}
"""

JS_SCRIPT = r"""
(function(){
  var rows = Array.prototype.slice.call(document.querySelectorAll('table.reviews tbody tr'));
  var countEl = document.getElementById('liveCount');
  var total = rows.length;
  var state = {result:'all', actual:'all', pred:'all', rating:'all'};
  var groups = document.querySelectorAll('.fbtns');
  function apply(){
    var visible=0,i,tr,m,ok;
    for (i=0;i<rows.length;i++){
      tr=rows[i];
      m = tr.getAttribute('data-match')==='1' ? 'correct' : 'mismatched';
      ok = (state.result==='all'||m===state.result)
        && (state.actual==='all'||tr.getAttribute('data-actual')===state.actual)
        && (state.pred==='all'||tr.getAttribute('data-pred')===state.pred)
        && (state.rating==='all'||tr.getAttribute('data-rating')===state.rating);
      if (ok){tr.classList.remove('hidden-row'); visible++;}
      else{tr.classList.add('hidden-row');}
    }
    countEl.innerHTML='Showing <b>'+visible+'</b> of '+total+' reviews';
  }
  var g,b,grp,btns,btn;
  for (g=0;g<groups.length;g++){
    grp=groups[g]; btns=grp.querySelectorAll('.fbtn');
    (function(grp){
      for (b=0;b<btns.length;b++){
        (function(btn){btn.addEventListener('click',function(){
          var sibs=grp.querySelectorAll('.fbtn'),x; for(x=0;x<sibs.length;x++)sibs[x].classList.remove('active');
          btn.classList.add('active'); state[grp.getAttribute('data-group')]=btn.getAttribute('data-v'); apply();
        });})(btns[b]);
      }
    })(grp);
  }
  apply();
})();
"""

def d3(label):
    pass  # unused
actual_filter = "".join(f'<button class="fbtn" data-v="{c.lower()}">{c}</button>' for c in THREE)
pred_filter = actual_filter
ratings = "".join(f'<button class="fbtn" data-v="{r}">{r}</button>' for r in (1,2,3,4,5))

# Another balanced sample means each actual class is 50; note in imbalance chart.
pos, neu, neg = actual_counts["POSITIVE"], actual_counts["NEUTRAL"], actual_counts["NEGATIVE"]

# --- Step 7 derived data (all from saved Step 6 results) ---
manifest_reviews = json.loads((ROOT / "results" / "step6_manifest.json").read_text(
    encoding="utf-8"))["reviews"]
star_counts = {s: 0 for s in (1, 2, 3, 4, 5)}
for rc in manifest_reviews:
    star_counts[int(round(rc["rating"]))] += 1
star_total = sum(star_counts.values())

# predicted class counts = column totals of the confusion matrix
pred_counts = {c: sum(conf[a][c] for a in THREE) for c in THREE}

# class recall for the dedicated chart (from saved metrics -> consistent by construction)
recall_frac = {c: conf[c][c] / actual_counts[c] for c in THREE}  # POS .92 NEU .24 NEG .98

# --- Star rating distribution bars ---
star_scale = 200.0 / max(star_counts.values())
star_colors = {1: "c1", 2: "c2", 3: "c3", 4: "c4", 5: "c5"}
STAR_HTML = ""
for s in (1, 2, 3, 4, 5):
    n = star_counts[s]
    h = 10 + star_scale * n
    STAR_HTML += (f'<div class="rbar {star_colors[s]}"><div class="rbar-val">{n}</div>'
                  f'<div class="rbar-fill" style="height:{h:.0f}px"></div>'
                  f'<div class="rbar-label">{s}&#9733;</div></div>')

# --- Actual vs predicted (grouped) ---
max_ap = max(max(actual_counts.values()), max(pred_counts.values()))
AP_HTML = ""
for c in THREE:
    a, p = actual_counts[c], pred_counts[c]
    aw = ""
    pw = ""
    ac = {"POSITIVE": "var(--positive)", "NEUTRAL": "var(--neutral)", "NEGATIVE": "var(--negative)"}[c]
    aw = f"{max(a/max_ap*100, 2):.1f}%"
    pw = f"{max(p/max_ap*100, 2):.1f}%"
    AP_HTML += (f'<div class="ap-row"><div class="ap-label">{c}</div>'
                f'<div class="ap-track"><span class="ap-cap">Actual {a}</span>'
                f'<div class="ap-bar" style="width:{aw};background:{ac}"></div></div>'
                f'<div class="ap-track"><span class="ap-cap">Pred {p}</span>'
                f'<div class="ap-bar" style="width:{pw};background:var(--accent)"></div></div></div>')

# --- Class recall (correctly classified %) ---
RECALL_HTML = ""
for c in THREE:
    fill = {"POSITIVE": "g", "NEUTRAL": "b", "NEGATIVE": "r"}[c]
    frac = recall_frac[c]
    w = max(frac * 100, 3.0)
    RECALL_HTML += (f'<div class="recall-row">'
                    f'<div class="rr-top"><span>{c} &nbsp;<span style="color:var(--muted)">({conf[c][c]}/{actual_counts[c]} correct)</span></span>'
                    f'<b>{rec[c]}%</b></div>'
                    f'<div class="rr-track"><div class="rr-fill {fill}" style="width:{w:.1f}%"></div>'
                    f'<span class="rr-pct">{rec[c]}%</span></div></div>')

# --- Step2 vs Step6 comparison (context only) ---
step2_acc = json.loads((ROOT / "results" / "step2_results.json").read_text(encoding="utf-8"))[
    "metrics"]["overall_accuracy_pct"]
COMPARE_HTML = f"""
<div class="compare">
  <div class="cmp"><div class="cmp-tag">Step 2 · binary (2 classes)</div><div class="cmp-num">{step2_acc}%</div>
    <div class="cmp-sub">98 / 100 correct</div><div class="cmp-note">unbalanced — sample was 93% POSITIVE</div></div>
  <div class="cmp"><div class="cmp-tag">Step 6 · balanced 3-class</div><div class="cmp-num">{accuracy}%</div>
    <div class="cmp-sub">{correct} / {total} correct</div><div class="cmp-note">balanced 50 / 50 / 50</div></div>
</div>
<ul style="list-style:none;display:grid;gap:8px;margin-top:14px;font-size:13.5px;color:var(--muted)">
  <li>These two percentages are <b style="color:var(--text)">NOT directly comparable</b>.</li>
  <li>• The class distributions differ (Step 2 was 93% POSITIVE; Step 6 is balanced 50/50/50).</li>
  <li>• The task changed from <b>2 classes</b> to <b>3 classes</b> (NEUTRAL added).</li>
  <li>• The drop from {step2_acc}% to {accuracy}% is a product of these changes, not simply the
      model <span class="warn">"getting worse."</span></li>
</ul>
"""

# --- Compact emotion comparison (secondary) ---
EC = json.loads((ROOT / "results" / "step6_emotion_comparison.json").read_text(encoding="utf-8"))
llm_d, nrc_d = EC["llm_emotion_distribution"], EC["nrc_emotion_distribution"]
agree_pct = EC["llm_emotion_equals_nrc_pct"]
llm_max = max(llm_d.values()) or 1
nrc_max = max(nrc_d.values()) or 1
def _emolist(d, cmax, hue):
    out = ""
    for e in ("anger", "anticipation", "disgust", "fear", "joy", "sadness", "surprise", "trust"):
        v = d.get(e, 0)
        w = max(v / cmax * 100, 0)
        out += (f'<div class="emo-pair"><span>{e}</span>'
                f'<div class="th" style="width:{w:.0f}%;background:{hue}"></div>'
                f'<b>{v}</b></div>')
    return out
EMO_HTML = f"""
<div class="emo-2col">
  <div class="emo-box"><h4>LLM emotion distribution</h4>{_emolist(llm_d, llm_max, "var(--accent)")}</div>
  <div class="emo-box"><h4>NRC emotion distribution</h4>{_emolist(nrc_d, nrc_max, "var(--correct)")}</div>
</div>
<div class="emo-agree">LLM and the NRC word list agree on <b>{agree_pct}%</b> of the 150 reviews. Neither method is
  treated as ground truth here — this is an agreement comparison between two different approaches.</div>
"""


HTML_DOC = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Amazon Gift Cards — Balanced Three-Class Sentiment · Step 6</title>
<style>{CSS}</style></head><body><div class="wrap">

<header>
  <div class="kicker">MBAX 6418 · Assignment 1</div>
  <h1>Amazon Gift Cards — Balanced Three-Class Sentiment</h1>
  <div class="sub">A balanced 150-review sample (50 POSITIVE / 50 NEUTRAL / 50 NEGATIVE, seed&#8202;6418) scored by the three-class classifier.</div>
  <div class="meta">model <code>cyankiwi/Qwen3.6-35B-A3B-AWQ-4bit</code> · endpoint <code>http://dobolyi.com:9001/v1</code> · temperature <code>0.0</code> · source <code>results/step6_metrics.json</code></div>
</header>

<section>
  <h2>Headline results</h2>
  <div class="sec-desc">Balanced three-class run on 150 reviews. Figures are read directly from the saved Step 6 output.</div>
  <div class="stats">
    <div class="stat"><div class="label">Total reviews</div><div class="value">{total}</div><div class="note">balanced sample</div></div>
    <div class="stat"><div class="label">Overall accuracy</div><div class="value teal">{accuracy}%</div><div class="note">macro recall {macro}%</div></div>
    <div class="stat"><div class="label">Correct</div><div class="value green">{correct}</div><div class="note">of {total}</div></div>
    <div class="stat"><div class="label">Mismatches</div><div class="value rose">{mismatch_count}</div><div class="note">shown below</div></div>
    <div class="stat"><div class="label">Actual POSITIVE</div><div class="value green">{pos}</div><div class="note">rating 4–5</div></div>
    <div class="stat"><div class="label">Actual NEUTRAL</div><div class="value blu">{neu}</div><div class="note">rating 3</div></div>
    <div class="stat"><div class="label">Actual NEGATIVE</div><div class="value red">{neg}</div><div class="note">rating 1–2</div></div>
  </div>
</section>

<section>
  <h2>Class balance &amp; correctness</h2>
  <div class="sec-desc">The sample is deliberately balanced, so no class dominates.</div>
  <div class="two-col">
    <div class="chartbox">
      <h3>Actual class split (balanced)</h3>
      <div class="cap">Equal thirds by design — the three-class evaluation is not skewed by imbalance.</div>
      <div class="bar">
        <div class="seg pos" style="width:33.33%">POSITIVE {pos}</div>
        <div class="seg neu" style="width:33.33%">NEUTRAL {neu}</div>
        <div class="seg neg" style="width:33.34%">NEGATIVE {neg}</div>
      </div>
      <div class="legend">
        <span><i style="background:var(--positive)"></i>POSITIVE ({pos})</span>
        <span><i style="background:var(--neutral)"></i>NEUTRAL ({neu})</span>
        <span><i style="background:var(--negative)"></i>NEGATIVE ({neg})</span>
      </div>
    </div>
    <div class="chartbox">
      <h3>Correct vs incorrect</h3>
      <div class="cap">Overall predictions</div>
      <div class="donut-wrap">
        <div class="donut" style="background:conic-gradient(var(--correct) 0 {accuracy}%, var(--incorrect) {accuracy}% 100%)"><div class="inner"><b>{accuracy}%</b><small>accuracy</small></div></div>
        <div class="legend" style="flex-direction:column;gap:10px">
          <span><i style="background:var(--correct)"></i>Correct {correct}</span>
          <span><i style="background:var(--incorrect)"></i>Mismatched {mismatch_count}</span>
        </div>
      </div>
    </div>
  </div>
</section>

<section>
  <h2>Star-rating distribution</h2>
  <div class="sec-desc">Counts for each star rating in the 150-review sample. The sample is balanced by
    <b>sentiment class</b> (50/50/50), <b>not</b> by individual star rating.</div>
  <div class="chartbox"><div class="rating-wrap">{STAR_HTML}</div>
    <div class="sec-desc" style="margin-top:16px;margin-bottom:0">Total = <b>{star_total}</b> reviews
      ({star_counts[1]} × 1★, {star_counts[2]} × 2★, {star_counts[3]} × 3★, {star_counts[4]} × 4★, {star_counts[5]} × 5★).</div></div>
</section>

<section>
  <h2>Confusion matrix</h2>
  <div class="sec-desc">Rows = actual class; columns = predicted class.</div>
  <div class="cmat">
    <table class="matrix">
      <thead><tr><th></th><th>Predicted POSITIVE</th><th>Predicted NEUTRAL</th><th>Predicted NEGATIVE</th></tr></thead>
      <tbody>{MATRIX_ROWS}</tbody>
    </table>
    <div class="chartbox" style="flex:1;min-width:280px">
      <h3>Where the {neu} NEUTRAL reviews went</h3>
      <ul style="list-style:none;display:grid;gap:9px;font-size:13.5px;color:var(--muted)">
        <li><b style="color:var(--positive)">{neut_split['POSITIVE']}</b> → predicted POSITIVE</li>
        <li><b style="color:var(--neutral)">{neut_split['NEUTRAL']}</b> → predicted NEUTRAL</li>
        <li><b style="color:var(--negative)">{neut_split['NEGATIVE']}</b> → predicted NEGATIVE</li>
      </ul>
    </div>
  </div>
</section>

<section>
  <h2>Prediction patterns</h2>
  <div class="two-col">
    <div class="chartbox">
      <h3>Actual vs predicted class counts</h3>
      <div class="cap">Ground-truth (actual) versus what the model predicted, per class.</div>
      {AP_HTML}
      <div class="ap-legend"><span><i style="display:inline-block;width:11px;height:11px;background:var(--positive);border-radius:3px"></i>&nbsp;Actual</span>
        <span><i style="display:inline-block;width:11px;height:11px;background:var(--accent);border-radius:3px"></i>&nbsp;Predicted</span></div>
    </div>
    <div class="chartbox">
      <h3>Correctly classified per class (recall)</h3>
      <div class="cap">How often each actual class was classified correctly. NEUTRAL is clearly the weak class.</div>
      {RECALL_HTML}
    </div>
  </div>
</section>

<section>
  <h2>How each class performed</h2>
  <div class="sec-desc">Recall (of actual class, classified right) and precision (of a prediction, was it right).</div>
  <div class="perf-grid">{PERF_HTML}</div>
</section>

<section>
  <h2>Primary-emotion comparison (secondary)</h2>
  <div class="sec-desc">Two independent emotion methods on the same 150 reviews — an agreement comparison, not an accuracy test.</div>
  <div class="chartbox">{EMO_HTML}</div>
</section>

<section>
  <h2>How to read this</h2>
  <div class="context">
    <ul>
      <li>This is a <b>balanced</b> 150-review sample: <b>{pos} POSITIVE / {neu} NEUTRAL / {neg} NEGATIVE</b> (seed 6418).</li>
      <li>An always-one-class classifier would score about <b class="hl">33%</b> here, so {accuracy}% is not directly comparable to the earlier 98% binary number — both the sample distribution and the classification task changed (three classes vs two).</li>
      <li>Watch NEUTRAL: because it is defined by absence of a clear lean, it is the class the model most often (<b>{neut_split['POSITIVE'] + neut_split['NEGATIVE']} of {neu}</b>) failed to recognize.</li>
    </ul>
    {COMPARE_HTML}
  </div>
</section>

<section>
  <h2>Mismatches ({mismatch_count})</h2>
  <div class="sec-desc">First {min(mismatch_count,12)} mismatches shown; use the review table filter (Result = Mismatched) to see all.</div>
  <div class="mcards">{MCARDS}</div>
</section>

<section>
  <h2>All {total} reviews</h2>
  <div class="sec-desc">Every balanced review. Filter to explore; pink rows are mismatches.</div>
  <div class="filter-bar">
    <div class="fil-group"><span class="fil-label">Result</span><div class="fbtns" data-group="result"><button class="fbtn active" data-v="all">All</button><button class="fbtn" data-v="correct">Correct</button><button class="fbtn" data-v="mismatched">Mismatched</button></div></div>
    <div class="fil-group"><span class="fil-label">Actual</span><div class="fbtns" data-group="actual"><button class="fbtn active" data-v="all">All</button>{actual_filter}</div></div>
    <div class="fil-group"><span class="fil-label">Predicted</span><div class="fbtns" data-group="pred"><button class="fbtn active" data-v="all">All</button>{pred_filter}</div></div>
    <div class="fil-group"><span class="fil-label">Rating</span><div class="fbtns" data-group="rating"><button class="fbtn active" data-v="all">All</button>{ratings}</div></div>
    <div class="live-count" id="liveCount">Showing <b>{total}</b> of {total} reviews</div>
  </div>
  <div class="table-wrap">
    <table class="reviews">
      <thead><tr><th>Row</th><th>Rating</th><th>Title</th><th>Review text</th><th>Actual</th><th>Predicted</th><th>Match</th></tr></thead>
      <tbody>{TABLE_HTML}</tbody>
    </table>
  </div>
</section>

<footer>Generated from results/step6_metrics.json + results/step6_llm.jsonl · model cyankiwi/Qwen3.6-35B-A3B-AWQ-4bit · sample seed 6418 · data: Amazon Reviews '23 (McAuley Lab), Gift Cards.</footer>

<script>{JS_SCRIPT}</script>
</div></body></html>
"""

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(HTML_DOC, encoding="utf-8")
print(f"Wrote {OUT} ({OUT.stat().st_size:,} bytes)")
print("Headline:", total, accuracy, correct, mismatch_count, pos, neu, neg,
      "| conf POS:", conf["POSITIVE"], "| neutral split:", neut_split)
