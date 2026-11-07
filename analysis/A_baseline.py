"""A baseline descriptive statistics, paired contrasts and rho-FE OLS.

Inference: resample entire seed blocks, each containing all rho x E x B.
Only NumPy/pandas are needed. No independent-row standard errors are used.
"""
from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.validate_outputs import validate
from src.market import ROOT
from src.provenance import digest, environment, now, source_hashes, write_json

OUTCOMES = ("rmst_T", "welfare_T")
LABELS = {"rmst_T": "截断崩溃时间（步）", "welfare_T": "累计交易净剩余"}


def markdown_table(frame):
    def fmt(v):
        if pd.isna(v):
            return ""
        if isinstance(v, (float, np.floating)):
            return f"{0.0 if abs(v) < 0.0005 else v:.3f}"
        return str(v)
    return "\n".join(["| " + " | ".join(map(str, frame.columns)) + " |",
                      "| " + " | ".join("---" for _ in frame.columns) + " |"] +
                     ["| " + " | ".join(fmt(v) for v in row) + " |"
                      for row in frame.itertuples(index=False, name=None)])


def block_weights(n_seeds, reps, rng_seed):
    rng = np.random.default_rng(rng_seed)
    indices = rng.integers(0, n_seeds, size=(reps, n_seeds))
    return np.array([np.bincount(x, minlength=n_seeds) for x in indices], dtype=float)


def interval(estimate, boot):
    low, high = np.quantile(boot, [0.025, 0.975])
    return {"estimate": float(estimate), "bootstrap_se": float(np.std(boot, ddof=1)),
            "ci_low": float(low), "ci_high": float(high)}


def design_matrix(frame):
    levels = sorted(frame.rho.unique())
    X = np.column_stack([np.ones(len(frame)), frame.E, frame.B, frame.E*frame.B] +
                        [(frame.rho == rho).astype(float) for rho in levels[1:]])
    return X, ["intercept", "E", "B", "E:B"] + [f"rho[{r:.2f}]" for r in levels[1:]]


def fit_ols(frame, outcome, weights):
    X, names = design_matrix(frame)
    y = frame[outcome].to_numpy(float)
    beta, _, rank, _ = np.linalg.lstsq(X, y, rcond=None)
    if rank != X.shape[1]:
        raise ValueError("Rank-deficient OLS design")
    seeds = sorted(frame.seed.unique())
    # Every seed has exactly one full factorial block. Resampling whole blocks
    # leaves X'X fixed, so OLS is linear in the resampled block X'y sums.
    per_seed_xty = np.array([X[frame.seed.to_numpy() == s].T @ y[frame.seed.to_numpy() == s]
                             for s in seeds])
    xtx_inv = np.linalg.inv(X.T @ X)
    boot = (weights @ per_seed_xty) @ xtx_inv
    rows = []
    for i, name in enumerate(names):
        rows.append({"outcome": outcome, "term": name, **interval(beta[i], boot[:, i])})
    for name, positions in (("E|B=1", (1, 3)), ("B|E=1", (2, 3))):
        rows.append({"outcome": outcome, "term": name,
                     **interval(beta[list(positions)].sum(), boot[:, positions].sum(axis=1))})
    return pd.DataFrame(rows), {"rank": int(rank), "n_parameters": int(X.shape[1]),
                               "n_rows": len(frame), "rho_reference": float(frame.rho.min()),
                               "max_abs_X_residual_moment": float(np.max(np.abs(X.T @ (y-X@beta))))}


def paired_contrasts(cube):
    # cube order: seed, rho, E, B.
    return {
        "E|B=0": cube[:, :, 1, 0]-cube[:, :, 0, 0],
        "E|B=1": cube[:, :, 1, 1]-cube[:, :, 0, 1],
        "B|E=0": cube[:, :, 0, 1]-cube[:, :, 0, 0],
        "B|E=1": cube[:, :, 1, 1]-cube[:, :, 1, 0],
        "E:B": cube[:, :, 1, 1]-cube[:, :, 0, 1]-cube[:, :, 1, 0]+cube[:, :, 0, 0],
    }


def label_feasibility(runs):
    rows = []
    groups = [("pooled", runs)] + [(f"rho={rho:.2f},E={E},B={B}", g)
                                     for (rho, E, B), g in runs.groupby(["rho", "E", "B"])]
    for label, g in groups:
        for t0, horizon in itertools.product((1, 2, 3, 5, 10), (5, 10, 20)):
            prevalent = (g.collapse_event == 1) & (g.collapse_time <= t0)
            risk = g.loc[~prevalent]
            observable = risk.loc[risk["T"] >= t0+horizon]
            positive = ((observable.collapse_event == 1) &
                        (observable.collapse_time <= t0+horizon)).sum()
            rows.append({"group": label, "t0": t0, "horizon": horizon,
                         "n_runs": len(g), "n_prevalent_excluded": int(prevalent.sum()),
                         "n_at_risk": len(risk), "n_unknown_window": len(risk)-len(observable),
                         "n_positive": int(positive), "n_negative": int(len(observable)-positive),
                         "positive_rate": float(positive/len(observable)) if len(observable) else None})
    return pd.DataFrame(rows)


def analyze(data, out, report_path=None):
    runs, steps, meta = validate(data)
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    config = meta["config"]
    seeds, rhos = sorted(runs.seed.unique()), sorted(runs.rho.unique())
    if set(runs.E) != {0, 1} or set(runs.B) != {0, 1}:
        raise ValueError("Need all four institutions")
    weights = block_weights(len(seeds), config["bootstrap_reps"], config["bootstrap_seed"])
    index = pd.MultiIndex.from_product([seeds, rhos, [0, 1], [0, 1]], names=["seed", "rho", "E", "B"])
    ordered = runs.set_index(["seed", "rho", "E", "B"]).loc[index].reset_index()
    means, paired, ols_frames, table = [], [], [], []
    ols_diagnostics = {}
    for outcome in OUTCOMES:
        cube = ordered[outcome].to_numpy(float).reshape(len(seeds), len(rhos), 2, 2)
        # Full covariance across outputs and groups uses the same bootstrap draws.
        for rho_index, rho_label in [(None, "pooled")] + list(enumerate(rhos)):
            selected = cube if rho_index is None else cube[:, rho_index:rho_index+1]
            for E, B in itertools.product((0, 1), repeat=2):
                values = selected[:, :, E, B]
                seed_means = values.mean(axis=1)
                sample = runs.loc[(runs.E == E) & (runs.B == B)]
                if rho_index is not None:
                    sample = sample.loc[sample.rho == rho_label]
                row = {"outcome": outcome, "rho": rho_label, "E": E, "B": B,
                       **interval(values.mean(), weights @ seed_means / len(seeds)),
                       "sample_sd": float(values.std(ddof=1)), "n_runs": values.size,
                       "n_seed_blocks": len(seeds), "n_events": int(sample.collapse_event.sum()),
                       "collapse_rate": float(sample.collapse_event.mean())}
                means.append(row)
                if rho_index is None:
                    table.append({"outcome": outcome, "section": "institution_mean", "term": f"E={E},B={B}", **row})
            for name, differences in paired_contrasts(selected).items():
                seed_mean = differences.mean(axis=1)
                paired.append({"outcome": outcome, "rho": rho_label, "contrast": name,
                               **interval(differences.mean(), weights @ seed_mean / len(seeds)),
                               "paired_sd": float(differences.std(ddof=1)),
                               "n_pairs": differences.size, "n_seed_blocks": len(seeds)})
        ols, diagnostics = fit_ols(ordered, outcome, weights)
        ols_frames.append(ols); ols_diagnostics[outcome] = diagnostics
        contrasts = paired_contrasts(cube)
        for term, comparison in (("E", "E|B=0"), ("B", "B|E=0"), ("E:B", "E:B"),
                                 ("E|B=1", "E|B=1"), ("B|E=1", "B|E=1")):
            row = ols.loc[ols.term == term].iloc[0].to_dict()
            target = contrasts[comparison].mean()
            if not np.isclose(row["estimate"], target, atol=1e-8):
                raise AssertionError("OLS and balanced paired contrast disagree")
            table.append({"outcome": outcome, "section": "rho_FE_OLS", **row,
                          "n_runs": len(runs), "n_seed_blocks": len(seeds)})
    means, paired, ols, table = pd.DataFrame(means), pd.DataFrame(paired), pd.concat(ols_frames), pd.DataFrame(table)
    means.to_csv(out / "institution_means.csv", index=False)
    paired.to_csv(out / "paired_effects.csv", index=False)
    ols.to_csv(out / "OLS_full.csv", index=False)
    table.to_csv(out / "Table1_baseline.csv", index=False)
    table_text = ["# Table 1：A组基准制度结果", "", f"模型：{meta['model_version']}；T={config['T']}；运行数={len(runs)}；seed区组数={len(seeds)}。", ""]
    for outcome in OUTCOMES:
        table_text += [f"## {LABELS[outcome]}", "", f"四制度均值（{len(rhos)}个rho等权）：", "",
                       markdown_table(means.loc[(means.outcome == outcome) & (means.rho == "pooled"),
                                              ["E", "B", "estimate", "sample_sd", "bootstrap_se", "ci_low", "ci_high", "collapse_rate"]]), "",
                       "rho固定效应OLS及线性组合：", "",
                       markdown_table(table.loc[(table.outcome == outcome) & (table.section == "rho_FE_OLS"),
                                              ["term", "estimate", "bootstrap_se", "ci_low", "ci_high"]]), ""]
    table_text += ["注：E=声誉驱逐，B=破产退出。E系数为B=0时驱逐效应，E|B=1=beta_E+beta_EB；E:B为制度交互（差中之差）。",
                   f"95%区间为{config['bootstrap_reps']}次整seed区组bootstrap百分位区间，bootstrap seed={config['bootstrap_seed']}。每次携带所有rho与四制度。",
                   "sample_sd是轨迹结果的描述标准差；bootstrap_se是区组重采样估计标准误。未使用独立行标准误或显著性星号。",
                   "rmst_T是min(tau,T)，终点仍未崩溃者右删失；welfare_T是固定T的累计交易净剩余，不是活跃财富。", ""]
    (out / "Table1_baseline.md").write_text("\n".join(table_text), encoding="utf-8")
    # Labels are checked only; no prediction model or t0 is selected here.
    labels = label_feasibility(runs)
    labels.to_csv(out / "ML_label_feasibility.csv", index=False)
    events = runs.loc[runs.collapse_event == 1, "collapse_time"]
    timing = {"n_events": len(events), "n_censored": int((runs.collapse_event == 0).sum()),
              "event_time_quantiles": {str(q): float(events.quantile(q)) for q in (0, .1, .25, .5, .75, .9, 1)} if len(events) else {}}
    write_json(out / "event_timing.json", timing)
    inference = {"generated_at": now(), "model_version": meta["model_version"],
                 "input_metadata_sha256": digest(Path(data) / "metadata.json"),
                 "input_sha256": meta["output_sha256"], "config_sha256": meta["config_sha256"],
                 "source_sha256": source_hashes(), "environment": environment(),
                 "bootstrap_reps": config["bootstrap_reps"], "bootstrap_seed": config["bootstrap_seed"],
                 "resampling_unit": "seed across all rho x E x B", "ols_diagnostics": ols_diagnostics}
    write_json(out / "analysis_metadata.json", inference)
    report = report_path or (out / "A_BASELINE_REPORT.md" if meta["smoke"] else ROOT / "docs/A_BASELINE_REPORT.md")
    write_report(Path(report), means, paired, labels, timing, meta)
    print("Analysis saved:", out)
    print(means.loc[means.rho == "pooled", ["outcome", "E", "B", "estimate", "ci_low", "ci_high"]].to_string(index=False))
    print(paired.loc[paired.rho == "pooled", ["outcome", "contrast", "estimate", "ci_low", "ci_high"]].to_string(index=False))
    return means, paired, ols


def write_report(path, means, paired, labels, timing, meta):
    config = meta["config"]
    text = ["# A组基准结果报告", "", f"生成时间：{now()}。模型版本：`{meta['model_version']}`。",
            "", "## 设计与口径", "",
            f"本轮{'为小样本验证' if meta['smoke'] else '完成正式基准'}，共{meta['actual_runs']}次运行，N={config['N']}、a=p=q=3、c=0、T={config['T']}。",
            "E为驱逐，B为破产。保持原件贪心匹配、同步结算、步末转化和退出。按负责人选择A保留状态及退出财富原始负值。",
            "诚实交易基础崩溃定义为活跃H不超过初始H的10%；主存续结果为min(tau,T)，未发生者按T右删失。福利在崩溃后继续累计到固定T，等于4*总HH−2*总CC。", "",
            "## 四制度与配对结果", ""]
    for outcome in OUTCOMES:
        text += [f"### {LABELS[outcome]}", "",
                 markdown_table(means.loc[(means.outcome == outcome) & (means.rho == "pooled"),
                                        ["E", "B", "estimate", "ci_low", "ci_high", "collapse_rate"]]), "",
                 markdown_table(paired.loc[(paired.outcome == outcome) & (paired.rho == "pooled"),
                                         ["contrast", "estimate", "ci_low", "ci_high"]]), ""]
        effects = paired.loc[(paired.outcome == outcome) & (paired.rho == "pooled")].set_index("contrast")
        directions = []
        for label in ("E|B=0", "E|B=1"):
            row = effects.loc[label]
            conclusion = "95%区间全为正" if row.ci_low > 0 else ("95%区间全为负" if row.ci_high < 0 else "95%区间含零")
            directions.append(f"{label}的平均效应为{row.estimate:.3f}（{conclusion}）")
        interaction = effects.loc["E:B"]
        text += ["；".join(directions) + f"。制度交互为{interaction.estimate:.3f}，表示两种破产设定下驱逐效应之差，不能把它单独当作驱逐的总效应。", ""]
    text += ["## rho分组与解释边界", ""]
    for outcome in OUTCOMES:
        part = means.loc[(means.outcome == outcome) & (means.rho != "pooled")]
        pivot = part.pivot(index="rho", columns=["E", "B"], values="estimate")
        pivot.columns = [f"E={E},B={B}" for E, B in pivot.columns]
        text += [LABELS[outcome] + "的分组均值：", "", markdown_table(pivot.reset_index()), ""]
    honest = means.loc[(means.outcome == "rmst_T") & (means.rho != "pooled")]
    low = honest.loc[(honest.rho.isin([.05, .1])) & (honest.E == 1)]
    if len(low) and np.allclose(low.estimate, config["T"]):
        text += ["在本样本的rho=0.05、0.10下，开启驱逐的轨迹均存续至观察终点；这只是T内未崩溃，不能称为永久稳定。跨rho平均改善不代表高骗子比例下同样有效，应结合上表读取各组差异。", ""]
    # State only the average zero effect here; row-level equality is separately audited.
    if all(abs(paired.loc[(paired.outcome == "rmst_T") & (paired.rho == "pooled") &
                         (paired.contrast == label), "estimate"].iloc[0]) < 1e-10
           for label in ("B|E=0", "B|E=1")):
        text += ["本轮破产开关对平均截断崩溃时间的配对效应为零，但对净剩余的效应不同；因此不能用存续指标的零效应概括全部制度结果，也不能把本轮零效应推广到其他参数。", ""]
    text += ["制度效应均由同rho、同seed的配对差异计算，不将四制度视为独立样本。完整平衡设计下，rho固定效应OLS的E、B、交互与条件效应等于相应平均配对差异，脚本已核验。",
             f"表中95%区间采用{config['bootstrap_reps']}次整seed区组重采样（seed={config['bootstrap_seed']}）；每次同时带入所有rho与制度。区间若含零，就不能据此判定该方向的平均制度效应稳定；不报告独立行显著性星号。",
             "基准中未转化H的累计受害次数m≤2，财富至少为10−2m≥6；准确举报又不驱逐H。因此H_active=H0−converted_total已在全样本逐步校验，诚实基础崩溃直接反映转化扩散。破产主要通过改变后续配对间接影响它，也可能通过减少崩溃后的CC交易改善福利。后一解释需结合后续机制分析，不能仅凭总效应确证。",
             "E=0仍保留私人拉黑和举报记录，只有公共驱逐关闭；B=0允许负财富者继续交易。以上是固定模型与网格下的平均效应，不证明各rho或每条轨迹方向一致，也不外推到现实平台。模型没有误举报、执法成本、重入，H→C不可逆；q固定为3，本轮不识别最优阈值或完整阈值响应。", "",
             "## 事件与后续预测任务", "",
             f"崩溃事件{timing['n_events']}次，右删失{timing['n_censored']}次；仅事件样本的时间分位数为{timing['event_time_quantiles']}。不能把删失的T当成实际崩溃时间。",
             "候选窗口只作可行性检查，不据此宣布已完成预测任务。t0时已崩溃的轨迹必须排除；不使用未来交易、未来退出或未来身份作为特征。当前H_active是仿真器全知变量，不能直接声称平台可观测。", "",
             markdown_table(labels.loc[(labels.group == "pooled") & (labels.horizon == 20),
                                      ["t0", "horizon", "n_prevalent_excluded", "n_at_risk", "n_positive", "n_negative", "positive_rate"]]), "",
             "候选t0=2、h=20的总体类别比例不能代替按配置检查：", ""]
    cells = labels.loc[(labels.group != "pooled") & (labels.t0 == 2) & (labels.horizon == 20)]
    single = int(((cells.n_positive == 0) | (cells.n_negative == 0)).sum())
    text += [f"本样本{len(cells)}个配置格中有{single}格在该窗口仅出现一个类别。后续预测必须与仅用配置的简单基准比较，检验早期状态是否增加预测信息；不能把重复seed视为{meta['actual_runs']}种独立配置，也不能只凭汇总AUC宣称模型学到了动态风险。", "",
             "按完整seed区组切分训练/验证/测试，可避免同一seed的其他制度或rho轨迹跨侧泄漏；配置外推需要另设测试。正式训练前仍须核对各制度/各rho类别分布、可观测特征及风险集选择。未训练算法。", "",
             "## 可复现来源", "",
             "参数与seed列表见configs/baseline.json；数据与模型哈希见data/processed/metadata.json；完整性校验见validation.json；所有系数与区间见outputs/tables/Table1_baseline.csv及analysis_metadata.json。小样本输出位于独立smoke目录。", ""]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(text), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=ROOT / "data/processed")
    parser.add_argument("--out", type=Path, default=ROOT / "outputs/tables")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    analyze(args.data, args.out, args.report)
