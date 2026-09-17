#!/usr/bin/env python3
"""Step 3: generate a polished, self-contained HTML dashboard from the SAVED
Step 2 results (results/step2_results.json + results/step2_raw_100.jsonl).

No classifications are rerun and the prompt/model are untouched. Every visible
number is derived from the saved results at build time (in Python), then baked
into a dependency-free static HTML file -- nothing is recomputed by JavaScript,
so the dashboard can never drift from the saved metrics.

Output: dashboard/dashboard.html  (single self-contained file, works offline).
"""

from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = json.loads((ROOT / "results" / "step2_results.json").read_text(encoding="utf-8"))
RAW = [json.loads(l) for l in
       (ROOT / "results" / "step2_raw_100.jsonl").read_text(encoding="utf-8").splitlines()
       if l.strip()]
OUT = ROOT / "dashboard" / "dashboard.html"

M = RESULTS["metrics"]
MD = RESULTS["metadata"]


def esc(s) -> str:
    return html.escape(str(s) if s is not None else "")


# ---- Derived values (computed in Python from the saved metrics). ----
total = M["total_reviews"]
accuracy = M["overall_accuracy_pct"]
correct = M["matched_count"]
mismatch = M["mismatch_count"]
pos = M["actual_positive_count"]
neg = M["actual_negative_count"]
pos_pct = M["actual_positive_pct"]
neg_pct = M["actual_negative_pct"]
cm = M["confusion_matrix"]
tp, fn = cm["actual_POS_pred_POS"], cm["actual_POS_pred_NEG"]
fp, tn = cm["actual_NEG_pred_POS"], cm["actual_NEG_pred_NEG"]
perf = M["class_performance"]
pr, nr = perf["POSITIVE_recall_pct"], perf["NEGATIVE_recall_pct"]
pp, np_ = perf["POSITIVE_precision_pct"], perf["NEGATIVE_precision_pct"]


def cm_shade(count: int, label: str) -> str:
    if label == "ok":
        return f"background:rgba(52,211,153,{0.10 + 0.50*(count/92):.2f})"
    return f"background:rgba(248,113,113,{0.10 + 0.40*(count/max(count,1)):.2f})"


# ---- Review table rows (all 100), mismatch rows highlighted. ----
mismatch_rows = {m["row"] for m in RESULTS["mismatches"]}
table_rows = []
for r in RAW:
    cls = "row-err" if r["row"] in mismatch_rows else ""
    pred = "POSITIVE" if r["prediction"] == "POSITIVE" else "NEGATIVE"
    exp = "POSITIVE" if r["expected"] == "POSITIVE" else "NEGATIVE"
    rating = r["rating"]
    rating_int = int(round(rating)) if isinstance(rating, (int, float)) else ""
    match_flag = "1" if r["matched"] else "0"
    stars = "★" * rating_int if isinstance(rating_int, int) and rating_int else "—"
    text_short = (r["text"] or "[no body]").strip()
    text_short = (text_short[:150] + "…") if len(text_short) > 150 else text_short
    table_rows.append(f"""
    <tr class="{cls}" data-match="{match_flag}" data-actual="{exp.lower()}"
        data-pred="{pred.lower()}" data-rating="{rating_int}">
      <td class="c">{r['row']}</td>
      <td class="c"><span class="stars" title="rating {esc(rating)}">{esc(stars)}&nbsp;{esc(rating)}</span></td>
      <td class="t">{esc(r['title'])}</td>
      <td class="t" title="{esc(r['text'] or '')}">{esc(text_short)}</td>
      <td class="c"><span class="chip {exp.lower()}">{exp}</span></td>
      <td class="c"><span class="chip {pred.lower()}">{pred}</span></td>
      <td class="c">{'<span class="dot ok">✓</span>' if r['matched'] else '<span class="dot bad">✗</span>'}</td>
    </tr>""")
TABLE_HTML = "".join(table_rows)

# ---- Mismatch spotlight cards. ----
mismatch_cards = []
for m_ in RESULTS["mismatches"]:
    text_short = (m_.get("text") or "[no body]").strip()
    text_short = (text_short[:220] + "…") if len(text_short) > 220 else text_short
    mismatch_cards.append(f"""
    <div class="mcard">
      <div class="mcard-top"><span class="mcard-row">Row {m_.get('row')}</span><span class="mcard-rating">rating {esc(m_.get('rating'))}</span></div>
      <div class="mcard-title">{esc(m_.get('title'))}</div>
      <div class="mcard-text">{esc(text_short)}</div>
      <div class="mcard-pred">
        <span class="chip {(m_.get('expected') or '').lower()}">expected {esc(m_.get('expected'))}</span>
        <span class="arrow">→</span>
        <span class="chip {(m_.get('predicted') or '').lower()}">predicted {esc(m_.get('predicted'))}</span>
      </div>
    </div>""")
MISMATCH_CARDS = "".join(mismatch_cards)


CSS = r"""
:root{
  --bg:#0d1017; --panel:#151a24; --panel-2:#1b2130; --line:#262e3f;
  --text:#e9ecf3; --muted:#98a2b8; --faint:#6b7689;
  --positive:#34d399; --positive-soft:rgba(52,211,153,.14);
  --negative:#fb7185; --negative-soft:rgba(251,113,133,.14);
  --correct:#2dd4bf; --incorrect:#fb7185;
  --accent:#a78bfa; --warn:#fbbf24;
}
*{box-sizing:border-box;margin:0;padding:0}
html{-webkit-text-size-adjust:100%}
body{
  font-family:"Segoe UI",system-ui,-apple-system,Roboto,Helvetica,Arial,sans-serif;
  background:var(--bg); color:var(--text); line-height:1.5; margin:0;
  -webkit-font-smoothing:antialiased;
}
.wrap{max-width:1180px;margin:0 auto;padding:40px 28px 72px}
header{border-bottom:1px solid var(--line);padding-bottom:22px;margin-bottom:30px}
.kicker{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--faint);margin-bottom:8px}
h1{font-size:30px;font-weight:650;letter-spacing:-.01em}
.sub{color:var(--muted);font-size:14px;margin-top:8px}
.meta{color:var(--faint);font-size:12px;margin-top:12px}
.meta code{background:var(--panel-2);padding:1px 5px;border-radius:4px;color:var(--accent)}
section{margin-bottom:44px}
h2{font-size:19px;font-weight:600;margin-bottom:6px}
.sec-desc{color:var(--muted);font-size:13.5px;margin-bottom:18px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px}
.stat .label{font-size:12px;color:var(--muted);letter-spacing:.02em}
.stat .value{font-size:30px;font-weight:700;margin-top:6px;letter-spacing:-.01em}
.stat .note{font-size:12px;color:var(--faint);margin-top:2px}
.value.teal{color:var(--correct)}.value.rose{color:var(--incorrect)}
.value.green{color:var(--positive)}.value.purple{color:var(--accent)}
.two-col{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.chartbox{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:20px 20px 22px}
.chartbox h3{font-size:14px;font-weight:600;margin-bottom:4px}
.chartbox .cap{font-size:12.5px;color:var(--muted);margin-bottom:14px}
.bar{display:flex;height:30px;border-radius:8px;overflow:hidden;border:1px solid var(--line)}
.bar .seg{display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:600;min-width:0}
.bar .seg.pos{background:var(--positive)}
.bar .seg.neg{background:var(--negative)}
.bar .seg.ok{background:var(--correct)}
.bar .seg.no{background:var(--incorrect)}
.legend{display:flex;gap:18px;margin-top:12px;flex-wrap:wrap}
.legend span{font-size:12.5px;color:var(--muted);display:flex;align-items:center;gap:7px}
.legend i{width:11px;height:11px;border-radius:3px;display:inline-block}
.donut-wrap{display:flex;align-items:center;gap:24px}
.donut{width:132px;height:132px;border-radius:50%;
  display:grid;place-items:center;flex:none}
.donut .inner{width:84px;height:84px;border-radius:50%;background:var(--panel);
  display:grid;place-items:center;text-align:center}
.donut .inner b{font-size:18px;display:block;line-height:1.1}
.donut .inner small{font-size:11px;color:var(--muted)}
.matrix{width:100%;border-collapse:collapse;max-width:520px;border:1px solid var(--line);border-radius:12px;overflow:hidden}
.matrix th,.matrix td{padding:16px 14px;text-align:center;font-size:13px}
.matrix thead th{color:var(--muted);font-weight:600;background:var(--panel-2);font-size:12px;letter-spacing:.04em}
.matrix .rowhead{text-align:left;font-weight:600;background:var(--panel-2);white-space:nowrap}
.matrix td.cell{font-size:22px;font-weight:700;border:1px solid var(--line)}
.matrix td .sub{display:block;font-size:11px;color:var(--faint);font-weight:500;margin-top:2px}
.cmat{display:flex;gap:20px;align-items:flex-start;flex-wrap:wrap}
.perf-grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.perf{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:18px 20px}
.perf .cls{font-weight:650;font-size:15px}
.perf .row{display:flex;justify-content:space-between;margin:12px 0 4px;font-size:13px;color:var(--muted)}
.perf .track{height:10px;border-radius:6px;background:var(--panel-2);overflow:hidden}
.perf .fill{height:100%;border-radius:6px}
.fill.g{background:var(--positive)}.fill.r{background:var(--negative)}
.context{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--accent);
  border-radius:10px;padding:18px 20px;font-size:14px}
.context ul{list-style:none;display:grid;gap:8px}
.context li{color:var(--muted)}
.context b{color:var(--text);font-weight:600}
.context .hl{color:var(--warn)}
.mcards{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.mcard{background:var(--negative-soft);border:1px solid rgba(251,113,133,.35);border-radius:12px;padding:16px}
.mcard-top{display:flex;justify-content:space-between;font-size:12px;color:var(--incorrect);margin-bottom:6px}
.mcard-row{font-weight:700}
.mcard-title{font-weight:650;font-size:14px}
.mcard-text{font-size:13px;color:var(--muted);margin:8px 0 12px}
.mcard-pred{display:flex;align-items:center;gap:8px}
.arrow{color:var(--muted)}
.chip{font-size:11.5px;font-weight:650;padding:3px 9px;border-radius:20px;display:inline-block;letter-spacing:.02em}
.chip.positive{color:var(--positive);background:var(--positive-soft)}
.chip.negative{color:var(--negative);background:var(--negative-soft)}
.dot{display:inline-block;width:20px;height:20px;border-radius:50%;line-height:20px;font-size:11px;font-weight:700;text-align:center}
.dot.ok{background:var(--positive-soft);color:var(--positive)}
.dot.bad{background:var(--negative-soft);color:var(--negative)}
.stars{color:var(--warn);letter-spacing:1px}
.table-wrap{overflow-x:auto;border:1px solid var(--line);border-radius:12px}
table.reviews{width:100%;border-collapse:collapse;font-size:13px;min-width:840px}
table.reviews th{position:sticky;top:0;background:var(--panel-2);text-align:left;padding:11px 12px;
  font-size:11px;letter-spacing:.05em;color:var(--muted);text-transform:uppercase;border-bottom:1px solid var(--line)}
table.reviews td{padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top}
table.reviews td.c{text-align:center;white-space:nowrap}
table.reviews tr:hover td{background:rgba(167,139,250,.04)}
table.reviews tr.row-err td{background:rgba(251,113,133,.10)}
table.reviews tr.row-err:hover td{background:rgba(251,113,133,.16)}
footer{color:var(--faint);font-size:12px;border-top:1px solid var(--line);padding-top:18px}
.filter-bar{display:flex;flex-wrap:wrap;gap:16px;align-items:flex-end;margin-bottom:14px}
.fil-group{display:flex;flex-direction:column;gap:6px}
.fil-label{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:var(--faint)}
.fbtns{display:flex;background:var(--panel-2);border:1px solid var(--line);border-radius:10px;padding:3px;gap:2px}
.fbtn{background:transparent;border:0;color:var(--muted);font-family:inherit;font-size:12.5px;font-weight:600;padding:6px 12px;border-radius:8px;cursor:pointer;transition:background .12s,color .12s}
.fbtn:hover{color:var(--text)}
.fbtn.active{background:var(--accent);color:#12141c}
tr.hidden-row{display:none}
.live-count{margin-left:auto;font-size:13px;font-weight:600;color:var(--text);background:var(--panel-2);border:1px solid var(--line);border-radius:20px;padding:8px 14px;white-space:nowrap}
.live-count b{color:var(--accent)}
@media (max-width:820px){
  .two-col,.perf-grid,.mcards{grid-template-columns:1fr}
  .wrap{padding:24px 16px 56px}
  h1{font-size:24px}
}
"""


JS_SCRIPT = r"""
(function(){
  var rows = Array.prototype.slice.call(document.querySelectorAll('table.reviews tbody tr'));
  var countEl = document.getElementById('liveCount');
  var total = rows.length;
  var state = {result:'all', actual:'all', pred:'all', rating:'all'};
  var groups = document.querySelectorAll('.fbtns');
  function apply(){
    var visible = 0, i, tr, m, ok;
    for (i=0;i<rows.length;i++){
      tr = rows[i];
      m = tr.getAttribute('data-match')==='1' ? 'correct' : 'mismatched';
      ok = (state.result==='all' || m===state.result)
        && (state.actual==='all' || tr.getAttribute('data-actual')===state.actual)
        && (state.pred==='all' || tr.getAttribute('data-pred')===state.pred)
        && (state.rating==='all' || tr.getAttribute('data-rating')===state.rating);
      if (ok){ tr.classList.remove('hidden-row'); visible++; }
      else { tr.classList.add('hidden-row'); }
    }
    countEl.innerHTML = 'Showing <b>' + visible + '</b> of ' + total + ' reviews';
  }
  var g,b,grp,btns,btn;
  for (g=0; g<groups.length; g++){
    grp = groups[g]; btns = grp.querySelectorAll('.fbtn');
    (function(grp){
      for (b=0; b<btns.length; b++){
        (function(btn){
          btn.addEventListener('click', function(){
            var sibs = grp.querySelectorAll('.fbtn'), x;
            for (x=0;x<sibs.length;x++) sibs[x].classList.remove('active');
            btn.classList.add('active');
            state[grp.getAttribute('data-group')] = btn.getAttribute('data-v');
            apply();
          });
        })(btns[b]);
      }
    })(grp);
  }
  apply();
})();
"""


HTML_DOC = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Amazon Gift Cards — Binary Sentiment · Step 2</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">

<header>
  <div class="kicker">MBAX 6418 · Assignment 1</div>
  <h1>Amazon Gift Cards — Binary Sentiment Classification</h1>
  <div class="sub">First 100 reviews scored by the Step 1 classifier and checked against the star-rating ground truth.</div>
  <div class="meta">
    model <code>{esc(MD['model'])}</code> · endpoint <code>{esc(MD['api_base_url'])}</code> · temperature <code>{esc(MD['temperature'])}</code> ·
    prompt <code>sentiment_prompt.txt</code> <code>sha256 {esc(MD['prompt_sha256'][:12])}…</code> ·
    source <code>results/step2_results.json</code>
  </div>
</header>

<!-- 1. Headline -->
<section>
  <h2>Headline results</h2>
  <div class="sec-desc">The full 100-review run at a glance. Every figure below comes from the saved Step&nbsp;2 output.</div>
  <div class="stats">
    <div class="stat"><div class="label">Total reviews</div><div class="value">{total}</div><div class="note">first 100, file order</div></div>
    <div class="stat"><div class="label">Overall accuracy</div><div class="value teal">{accuracy}%</div><div class="note">agreement with rating</div></div>
    <div class="stat"><div class="label">Correct</div><div class="value green">{correct}</div><div class="note">of {total}</div></div>
    <div class="stat"><div class="label">Mismatches</div><div class="value rose">{mismatch}</div><div class="note">shown below</div></div>
    <div class="stat"><div class="label">Actual POSITIVE</div><div class="value purple">{pos}<span style="font-size:15px"> ({pos_pct}%)</span></div><div class="note">rating ≥ 4</div></div>
    <div class="stat"><div class="label">Actual NEGATIVE</div><div class="value purple">{neg}<span style="font-size:15px"> ({neg_pct}%)</span></div><div class="note">rating &lt; 4</div></div>
  </div>
</section>

<!-- 2. Imbalance + 3. correct vs incorrect -->
<section>
  <h2>Class imbalance &amp; correctness</h2>
  <div class="sec-desc">The sample is heavily skewed toward positive reviews — which matters when you read the accuracy.</div>
  <div class="two-col">
    <div class="chartbox">
      <h3>Actual class split</h3>
      <div class="cap">Ground-truth classes derived from the ratings of the 100 reviews.</div>
      <div class="bar">
        <div class="seg pos" style="width:{pos_pct}%" title="POSITIVE {pos} · {pos_pct}%">POSITIVE {pos} · {pos_pct}%</div>
        <div class="seg neg" style="width:{neg_pct}%" title="NEGATIVE {neg} · {neg_pct}%">{neg} · {neg_pct}%</div>
      </div>
      <div class="legend">
        <span><i style="background:var(--positive)"></i>POSITIVE ({pos})</span>
        <span><i style="background:var(--negative)"></i>NEGATIVE ({neg})</span>
      </div>
    </div>
    <div class="chartbox">
      <h3>Correct vs incorrect</h3>
      <div class="cap">How the model's {total} predictions compared to the rating ground truth.</div>
      <div class="donut-wrap">
        <div class="donut" style="background:conic-gradient(var(--correct) 0 {correct}%, var(--incorrect) {correct}% 100%)"><div class="inner"><b>{accuracy}%</b><small>accuracy</small></div></div>
        <div class="legend" style="flex-direction:column;gap:10px">
          <span><i style="background:var(--correct)"></i>Correct {correct}</span>
          <span><i style="background:var(--incorrect)"></i>Mismatched {mismatch}</span>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- 4. Confusion matrix -->
<section>
  <h2>Confusion matrix</h2>
  <div class="sec-desc">Rows are the actual (rating-derived) class; columns are what the model predicted. <b style="color:var(--text)">{tp}&nbsp;/&nbsp;{fn}&nbsp;/&nbsp;{fp}&nbsp;/&nbsp;{tn}</b></div>
  <div class="cmat">
  <table class="matrix">
    <thead>
      <tr><th class="rowhead" colspan="3" style="text-align:left;font-size:11px;letter-spacing:.05em">&#8592; ACTUAL CLASS &nbsp;·&nbsp; &#8593; PREDICTED CLASS</th></tr>
      <tr><th></th><th>Predicted POSITIVE</th><th>Predicted NEGATIVE</th></tr>
    </thead>
    <tbody>
      <tr>
        <th class="rowhead">Actual POSITIVE ({pos})</th>
        <td class="cell" style="{cm_shade(tp,'ok')}">{tp}<span class="sub">correct</span></td>
        <td class="cell" style="{cm_shade(fn,'err')}">{fn}<span class="sub">false negative</span></td>
      </tr>
      <tr>
        <th class="rowhead">Actual NEGATIVE ({neg})</th>
        <td class="cell" style="{cm_shade(fp,'err')}">{fp}<span class="sub">false positive</span></td>
        <td class="cell" style="{cm_shade(tn,'ok')}">{tn}<span class="sub">correct</span></td>
      </tr>
    </tbody>
  </table>
  <div class="chartbox" style="flex:1;min-width:280px">
    <h3>Reading the matrix</h3>
    <div class="cap">Green cells are correct on the diagonal; pink cells are the two error types.</div>
    <ul style="list-style:none;display:grid;gap:10px;font-size:13.5px;color:var(--muted)">
      <li><b style="color:var(--positive)">{tp} of {pos} POSITIVE</b> reviews correctly classified.</li>
      <li><b style="color:var(--positive)">{tn} of {neg} NEGATIVE</b> reviews correctly classified.</li>
      <li><b style="color:var(--incorrect)">{fn} POSITIVE</b> was called NEGATIVE; <b style="color:var(--incorrect)">{fp} NEGATIVE</b> was called POSITIVE.</li>
    </ul>
  </div>
  </div>
</section>

<!-- 5. Class-specific performance -->
<section>
  <h2>How each class performed</h2>
  <div class="sec-desc">Recall = how often reviews of that actual class were classified correctly. Precision = how often a prediction of that class was right.</div>
  <div class="perf-grid">
    <div class="perf">
      <div class="cls" style="color:var(--positive)">POSITIVE &nbsp;<span style="font-size:12px;color:var(--muted)">{tp}/{pos} correct</span></div>
      <div class="row"><span>Recall</span><b>{pr}%</b></div>
      <div class="track"><div class="fill g" style="width:{pr}%"></div></div>
      <div class="row"><span>Precision</span><b>{pp}%</b></div>
      <div class="track"><div class="fill g" style="width:{pp}%"></div></div>
    </div>
    <div class="perf">
      <div class="cls" style="color:var(--negative)">NEGATIVE &nbsp;<span style="font-size:12px;color:var(--muted)">{tn}/{neg} correct</span></div>
      <div class="row"><span>Recall</span><b>{nr}%</b></div>
      <div class="track"><div class="fill r" style="width:{nr}%"></div></div>
      <div class="row"><span>Precision</span><b>{np_}%</b></div>
      <div class="track"><div class="fill r" style="width:{np_}%"></div></div>
    </div>
  </div>
</section>

<!-- Context -->
<section>
  <h2>How to read this</h2>
  <div class="context">
    <ul>
      <li>The sample contains <b>{pos} POSITIVE</b> and <b>{neg} NEGATIVE</b> reviews.</li>
      <li>An <b>always-POSITIVE baseline</b> would achieve <b class="hl">{pos}% accuracy</b> on this particular sample alone.</li>
      <li>The model achieved <b>{accuracy}%</b> — only <b>{correct - pos} more</b> correct than that trivial baseline.</li>
      <li>So the high overall number says more about the <b>{pos}/{neg}</b> imbalance than about strength on negative reviews. With only {neg} negative reviews in {total}, negative-sentiment reliability is not well measured here.</li>
    </ul>
  </div>
</section>

<!-- Mismatch spotlight -->
<section>
  <h2>Mismatches ({mismatch})</h2>
  <div class="sec-desc">The only reviews where the model disagreed with the rating ground truth.</div>
  <div class="mcards">{MISMATCH_CARDS}</div>
</section>

<!-- Review table -->
<section>
  <h2>All {total} reviews</h2>
  <div class="sec-desc">Every scored review. Filter to explore; rows highlighted pink are the {mismatch} mismatches. Hover a text cell to read the full body.</div>

  <div class="filter-bar">
    <div class="fil-group"><span class="fil-label">Result</span>
      <div class="fbtns" data-group="result">
        <button class="fbtn active" data-v="all">All</button>
        <button class="fbtn" data-v="correct">Correct</button>
        <button class="fbtn" data-v="mismatched">Mismatched</button>
      </div>
    </div>
    <div class="fil-group"><span class="fil-label">Actual</span>
      <div class="fbtns" data-group="actual">
        <button class="fbtn active" data-v="all">All</button>
        <button class="fbtn" data-v="positive">Positive</button>
        <button class="fbtn" data-v="negative">Negative</button>
      </div>
    </div>
    <div class="fil-group"><span class="fil-label">Predicted</span>
      <div class="fbtns" data-group="pred">
        <button class="fbtn active" data-v="all">All</button>
        <button class="fbtn" data-v="positive">Positive</button>
        <button class="fbtn" data-v="negative">Negative</button>
      </div>
    </div>
    <div class="fil-group"><span class="fil-label">Rating</span>
      <div class="fbtns" data-group="rating">
        <button class="fbtn active" data-v="all">All</button>
        <button class="fbtn" data-v="1">1</button>
        <button class="fbtn" data-v="2">2</button>
        <button class="fbtn" data-v="3">3</button>
        <button class="fbtn" data-v="4">4</button>
        <button class="fbtn" data-v="5">5</button>
      </div>
    </div>
    <div class="live-count" id="liveCount">Showing <b>{total}</b> of {total} reviews</div>
  </div>

  <div class="table-wrap">
    <table class="reviews">
      <thead><tr><th>Row</th><th>Rating</th><th>Title</th><th>Review text</th><th>Expected</th><th>Predicted</th><th>Match</th></tr></thead>
      <tbody>{TABLE_HTML}</tbody>
    </table>
  </div>
</section>

<footer>
  Generated from results/step2_results.json and results/step2_raw_100.jsonl · model {esc(MD['model'])} ·
  prompt sha256 {esc(MD['prompt_sha256'])} · brand: Amazon Reviews '23 (McAuley Lab, UC San Diego), Gift Cards category.
</footer>

<script>{JS_SCRIPT}</script>
</div>
</body>
</html>
"""

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(HTML_DOC, encoding="utf-8")
print(f"Wrote {OUT} ({OUT.stat().st_size:,} bytes)")
print("Embedded headline figures:", total, correct, mismatch, pos, neg, accuracy, "| conf:", tp, fn, fp, tn)
