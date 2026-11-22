"""Generate the six figures quoted in Section 7, as monochrome SVG."""
import sys, os, csv, json
from collections import defaultdict
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from svgplot import compose

OUT = r"C:\Users\86187\WorkBuddy\2026-11-22-21-56-35\outputs"
DATA = os.path.join(OUT, "data")
FIG = os.path.join(OUT, "figures")
os.makedirs(FIG, exist_ok=True)


def read_csv(path):
    with open(path, "r", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def num(r, k, d=0.0):
    try:
        return float(r[k])
    except (KeyError, TypeError, ValueError):
        return d


RUNS = read_csv(os.path.join(DATA, "run_level.csv"))
TS = read_csv(os.path.join(DATA, "timeseries.csv"))
A = json.load(open(os.path.join(DATA, "analysis.json"), encoding="utf-8"))
KN = A["key_numbers"]
MAIN = [r for r in RUNS if r["sample"] == "main"]
C_SUB = [r for r in RUNS if r["sample"] == "c_robust"]
AGG = [r for r in TS if r["run_id"] == "AGG"]
CASE = [r for r in TS if r["run_id"] != "AGG"]


def by(rows, xkey, ykey, filt=lambda r: True):
    d = defaultdict(list)
    for r in rows:
        if filt(r):
            d[num(r, xkey)].append(num(r, ykey))
    xs = sorted(d)
    return xs, [float(np.mean(d[x])) for x in xs]


def ts_by(rows, ykey, E, tmax=200):
    pts = [(num(r, "t"), num(r, ykey)) for r in rows
           if num(r, "E") == E and num(r, "t") <= tmax]
    pts.sort()
    return [p[0] for p in pts], [p[1] for p in pts]


def save(name, svg):
    with open(os.path.join(FIG, name + ".svg"), "w", encoding="utf-8") as f:
        f.write(svg)
    print("wrote", name + ".svg", len(svg), "chars")


# ---------------------------- Figure 7.1 ----------------------------
p = []
for key, title, ylab in [
    ("fraud_count", "(a) Fraudulent trades", "H-C trades per run"),
    ("conversion_share", "(b) Conversion share", "Share of initial honest"),
    ("cooperation_count", "(c) Cooperative trades", "H-H trades per run"),
]:
    x0, y0 = by(MAIN, "rho", key, lambda r: num(r, "E") == 0)
    x1, y1 = by(MAIN, "rho", key, lambda r: num(r, "E") == 1)
    p.append(dict(title=title, xlabel="Initial cheater share rho", ylabel=ylab,
                  xlim=(0.04, 0.41), xticks=[0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40],
                  zero_base=True,
                  series=[dict(x=x0, y=y0, label="E = 0"),
                          dict(x=x1, y=y1, label="E = 1")]))
save("fig7_1_mechanism_by_rho", compose(p, cols=3, pw=340, ph=270))


# ---------------------------- Figure 7.2 ----------------------------
p = []
for key, title, ylab in [
    ("active_h", "(a) Active honest agents", "Agents"),
    ("edges", "(b) Trade edges per step", "Edges"),
    ("cum_conv", "(c) Cumulative conversions", "Agents"),
]:
    x0, y0 = ts_by(AGG, key, 0, tmax=60)
    x1, y1 = ts_by(AGG, key, 1, tmax=60)
    p.append(dict(title=title, xlabel="Step t (horizon T = 200)", ylabel=ylab,
                  xlim=(1, 60), xticks=[1, 10, 20, 30, 40, 50, 60],
                  zero_base=True,
                  series=[dict(x=x0, y=y0, label="E = 0"),
                          dict(x=x1, y=y1, label="E = 1")]))
save("fig7_2_market_dynamics", compose(p, cols=3, pw=340, ph=270))


# ---------------------------- Figure 7.3 ----------------------------
p = []
for E in (0, 1):
    rows = [r for r in CASE if num(r, "E") == E and num(r, "t") <= 30]
    rows.sort(key=lambda r: num(r, "t"))
    hh, hc, cc = [], [], []
    last = [0.33, 0.33, 0.34]
    for r in rows:
        e = num(r, "edges")
        if e > 0:
            last = [num(r, "hh") / e, num(r, "hc") / e, num(r, "cc") / e]
        hh.append(last[0]); hc.append(last[1]); cc.append(last[2])
    xs = [num(r, "t") for r in rows]
    p.append(dict(title="(a) E = 0" if E == 0 else "(b) E = 1",
                  xlabel="Step t", ylabel="Share of trades", type="stacked",
                  xlim=(1, 30), xticks=[1, 5, 10, 15, 20, 25, 30],
                  ylim=(0, 1.0), yticks=[0, 0.25, 0.5, 0.75, 1.0],
                  series=[dict(x=xs, y=hh, label="H-H"),
                          dict(x=xs, y=hc, label="H-C"),
                          dict(x=xs, y=cc, label="C-C")]))
save("fig7_3_trade_composition", compose(p, cols=2, pw=370, ph=280))


# ---------------------------- Figure 7.4 ----------------------------
x0, y0 = ts_by(AGG, "wt_cum", 0, tmax=200)
x1, y1 = ts_by(AGG, "wt_cum", 1, tmax=200)
hh0 = float(np.mean([num(r, "wt_hh") for r in MAIN if num(r, "E") == 0]))
hh1 = float(np.mean([num(r, "wt_hh") for r in MAIN if num(r, "E") == 1]))
cc0 = float(np.mean([num(r, "wt_cc") for r in MAIN if num(r, "E") == 0]))
cc1 = float(np.mean([num(r, "wt_cc") for r in MAIN if num(r, "E") == 1]))
pa = dict(title="(a) Cumulative social net benefit", xlabel="Step t",
          ylabel="Cumulative net benefit", xlim=(1, 200), xticks=[1, 40, 80, 120, 160, 200],
          series=[dict(x=x0, y=y0, label="E = 0"),
                  dict(x=x1, y=y1, label="E = 1")])
pb = dict(title="(b) Decomposition by trade type", xlabel="Treatment",
          ylabel="Contribution to net benefit", type="bar",
          xlim=(-0.5, 1.5), xticks=[0, 1], xticklabels={0: "E = 0", 1: "E = 1"},
          groups=["E = 0", "E = 1"],
          series=[dict(y=[hh0, hh1], label="H-H (positive)"),
                  dict(y=[cc0, cc1], label="C-C (negative)")])
save("fig7_4_welfare", compose([pa, pb], cols=2, pw=370, ph=285))


# ---------------------------- Figure 7.5 ----------------------------
spec = A["regressions"]["collapse"]
b0, b1 = spec[0]["beta_E"], spec[1]["beta_E"]
ci0, ci1 = spec[0]["ci_E"], spec[1]["ci_E"]
lo = min(ci0[0], ci1[0], 0.0)
hi = max(ci0[1], ci1[1], 0.0)
pad = (hi - lo) * 0.12
pa = dict(title="(a) Treatment coefficient in the collapse equation",
          xlabel="Coefficient on E (survival steps)", ylabel="Specification",
          type="coef", xlim=(lo - pad, hi + pad),
          ylim=(0.5, 2.5), yticks=[1, 2],
          yticklabels={1: "With controls", 2: "Baseline"},
          series=[dict(x=[b0, b1], y=[2, 1], lo=[ci0[0], ci1[0]],
                       hi=[ci0[1], ci1[1]], label="E")])

rng = np.random.default_rng(7)
pb_series = []
for E in (0, 1):
    sub = [r for r in MAIN if num(r, "E") == E]
    pick = rng.choice(len(sub), size=min(260, len(sub)), replace=False)
    xs = [num(sub[i], "fraud_count") for i in pick]
    ys = [num(sub[i], "survival_steps") for i in pick]
    X = np.column_stack([np.ones(len(xs)), np.array(xs)])
    beta = np.linalg.lstsq(X, np.array(ys), rcond=None)[0]
    xlo, xhi = min(xs), max(xs)
    ylo = max(0.0, min(200.0, beta[0] + beta[1] * xlo))
    yhi = max(0.0, min(200.0, beta[0] + beta[1] * xhi))
    pb_series.append(dict(x=xs, y=ys, label="E = %d" % E,
                          fit=[(xlo, ylo), (xhi, yhi)]))
allx = [v for s in pb_series for v in s["x"]]
pb = dict(title="(b) Survival and realised fraud", xlabel="Fraudulent trades",
          ylabel="Restricted survival steps", type="scatter",
          xlim=(0, max(allx) * 1.02),
          series=pb_series)
save("fig7_5_bad_control", compose([pa, pb], cols=2, pw=370, ph=285))


# ---------------------------- Figure 7.6 ----------------------------
cs = [0.0, 0.10, 0.30]
def cmean(c, E, key):
    v = [num(r, key) for r in C_SUB if num(r, "c") == c and num(r, "E") == E]
    return float(np.mean(v)) if v else 0.0

p1 = dict(title="(a) Welfare under a survival cost", xlabel="Per-step cost c",
          ylabel="Welfare", xlim=(-0.01, 0.31), xticks=[0, 0.1, 0.2, 0.3],
          series=[
              dict(x=cs, y=[cmean(c, 0, "wt_realised") for c in cs], label="Welfare, E = 0"),
              dict(x=cs, y=[cmean(c, 1, "wt_realised") for c in cs], label="Welfare, E = 1"),
              dict(x=cs, y=[cmean(c, 0, "resource_adjusted_wt") for c in cs], label="Adjusted, E = 0"),
              dict(x=cs, y=[cmean(c, 1, "resource_adjusted_wt") for c in cs], label="Adjusted, E = 1"),
          ])
p2 = dict(title="(b) Trade deaths and cost deaths", xlabel="Per-step cost c",
          ylabel="Agents", type="bar", xlim=(-0.5, 2.5),
          xticks=[0, 1, 2], xticklabels={0: "c = 0", 1: "c = 0.10", 2: "c = 0.30"},
          groups=["c = 0", "c = 0.10", "c = 0.30"],
          series=[
              dict(y=[cmean(c, 0, "trade_death") for c in cs], label="Trade, E = 0"),
              dict(y=[cmean(c, 0, "cost_death") for c in cs], label="Cost, E = 0"),
              dict(y=[cmean(c, 1, "trade_death") for c in cs], label="Trade, E = 1"),
              dict(y=[cmean(c, 1, "cost_death") for c in cs], label="Cost, E = 1"),
          ])
p3 = dict(title="(c) Survival and market exit", xlabel="Per-step cost c",
          ylabel="Agents", xlim=(-0.01, 0.31), xticks=[0, 0.1, 0.2, 0.3],
          zero_base=True,
          series=[
              dict(x=cs, y=[cmean(c, 0, "alive_final") for c in cs], label="Alive, E = 0"),
              dict(x=cs, y=[cmean(c, 1, "alive_final") for c in cs], label="Alive, E = 1"),
              dict(x=cs, y=[cmean(c, 0, "cum_death") for c in cs], label="Deaths, E = 0"),
              dict(x=cs, y=[cmean(c, 1, "cum_death") for c in cs], label="Deaths, E = 1"),
          ])
save("fig7_6_survival_cost", compose([p1, p2, p3], cols=3, pw=340, ph=275))


# ---------------------------- figure index ----------------------------
names = ["fig7_1_mechanism_by_rho", "fig7_2_market_dynamics",
         "fig7_3_trade_composition", "fig7_4_welfare",
         "fig7_5_bad_control", "fig7_6_survival_cost"]
html = ['<!DOCTYPE html><html><head><meta charset="utf-8"><title>Figures - Section 7</title>',
        '<style>body{font-family:Helvetica,Arial,sans-serif;margin:24px;color:#111;background:#fff}',
        'figure{margin:0 0 34px}figcaption{font-size:12px;margin:8px 0 6px}',
        'svg{border:1px solid #ddd;max-width:100%;height:auto}</style></head><body>',
        '<h1 style="font-weight:normal;font-size:20px">Section 7 - Figures</h1>']
caps = {
    "fig7_1_mechanism_by_rho": "Figure 7.1. Mechanism outcomes across the initial cheater share, averaged over p and seeds.",
    "fig7_2_market_dynamics": "Figure 7.2. Market dynamics under each institution, averaged over two rho cells and 30 seeds.",
    "fig7_3_trade_composition": "Figure 7.3. Trade composition in a representative run (rho = 0.10, p = 3, seed = 0).",
    "fig7_4_welfare": "Figure 7.4. Cumulative social net benefit and its decomposition by transaction type.",
    "fig7_5_bad_control": "Figure 7.5. Post-treatment bias diagnostic: coefficient attenuation and mechanical correlation.",
    "fig7_6_survival_cost": "Figure 7.6. Survival cost, resource-adjusted welfare, and the exit/death decomposition.",
}
for n in names:
    svg = open(os.path.join(FIG, n + ".svg"), encoding="utf-8").read()
    html.append("<figure><figcaption>%s</figcaption>%s</figure>" % (caps[n], svg))
html.append("</body></html>")
with open(os.path.join(FIG, "figures_index.html"), "w", encoding="utf-8") as f:
    f.write("\n".join(html))
print("wrote figures_index.html")
