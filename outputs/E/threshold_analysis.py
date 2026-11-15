#!/usr/bin/env python3
"""Generate the threshold-response figures and tables.

With no input file, the script reproduces the aggregate estimates reported in
Section E and writes a market-specific RMST template. With --input, it analyzes
the complete run-level simulation file, including fixed effects, seed-clustered
standard errors, Romano-Wolf step-down p-values, and bootstrap threshold choices.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont


THRESHOLDS = [1, 2, 3, 4, 5, 6, 8, 10]
RHOS = [0.05, 0.10, 0.20, 0.30, 0.40]
SEEDS = 100
SURVIVAL_EFFECTS = {
    2: -31.4,
    3: -49.9,
    4: -85.9,
    5: -90.5,
    6: -105.1,
    8: -117.9,
    10: -140.3,
}
WELFARE_ENDPOINTS = {2: -12710.0, 10: -71058.0}
MARKETS = 4000
COLLAPSED = 2413
COLLAPSE_RATE = COLLAPSED / MARKETS

NAVY = (31, 78, 121)
ORANGE = (201, 111, 53)
INK = (35, 35, 35)
MID_GRAY = (120, 120, 120)
LIGHT_GRAY = (225, 225, 225)
WHITE = (255, 255, 255)


ROOT = Path(__file__).resolve().parent
FIGURES = ROOT / "figures"
TABLES = ROOT / "tables"


def _font(size: int, bold: bool = False):
    candidates = []
    if bold:
        candidates.extend(
            [
                Path(r"C:\Windows\Fonts\timesbd.ttf"),
                Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"),
            ]
        )
    else:
        candidates.extend(
            [
                Path(r"C:\Windows\Fonts\times.ttf"),
                Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"),
            ]
        )
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def _svg_text(
    x: float,
    y: float,
    text: str,
    size: int,
    *,
    anchor: str = "start",
    weight: int = 400,
    fill: str = "#232323",
) -> str:
    safe = (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" '
        f'font-family="Times New Roman, Times, serif" font-size="{size}" '
        f'font-weight="{weight}" fill="{fill}">{safe}</text>'
    )


def _save_figure(image: Image.Image, png_path: Path, svg_body: list[str]) -> None:
    png_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(png_path, format="PNG")
    svg_path = png_path.with_suffix(".svg")
    svg_body.insert(0, '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="700" viewBox="0 0 1200 700">')
    svg_body.insert(1, '<rect width="1200" height="700" fill="#ffffff"/>')
    svg_body.append("</svg>")
    svg_path.write_text("\n".join(svg_body), encoding="utf-8")


def _draw_vertical_text(
    image: Image.Image,
    text: str,
    center_x: float,
    center_y: float,
    font,
    fill: tuple[int, int, int],
) -> None:
    bbox = ImageDraw.Draw(image).textbbox((0, 0), text, font=font)
    text_image = Image.new(
        "RGBA",
        (bbox[2] - bbox[0] + 16, bbox[3] - bbox[1] + 16),
        (255, 255, 255, 0),
    )
    text_draw = ImageDraw.Draw(text_image)
    text_draw.text((8 - bbox[0], 8 - bbox[1]), text, font=font, fill=fill)
    rotated = text_image.rotate(90, expand=True)
    image.paste(
        rotated,
        (
            int(center_x - rotated.width / 2),
            int(center_y - rotated.height / 2),
        ),
        rotated,
    )


def render_survival_figure(png_path: Path) -> None:
    width, height = 1800, 1050
    image = Image.new("RGB", (width, height), WHITE)
    draw = ImageDraw.Draw(image)
    left, right, top, bottom = 245, 80, 85, 160
    plot_w, plot_h = width - left - right, height - top - bottom
    ymin, ymax = -160.0, 20.0

    def px(index: int) -> float:
        return left + index * plot_w / (len(THRESHOLDS) - 1)

    def py(value: float) -> float:
        return top + (ymax - value) / (ymax - ymin) * plot_h

    for tick in (-160, -120, -80, -40, 0):
        y = py(tick)
        draw.line((left, y, left + plot_w, y), fill=LIGHT_GRAY, width=3)
        draw.text(
            (left - 28, y),
            str(tick),
            font=_font(34),
            fill=INK,
            anchor="rm",
        )

    zero_y = py(0)
    for x_start in range(left, left + plot_w, 42):
        draw.line(
            (x_start, zero_y, min(x_start + 24, left + plot_w), zero_y),
            fill=INK,
            width=4,
        )
    points = []
    for i, q in enumerate(THRESHOLDS):
        value = 0.0 if q == 1 else SURVIVAL_EFFECTS[q]
        points.append((px(i), py(value), value, q))
    draw.line([(x, y) for x, y, _, _ in points], fill=NAVY, width=7)
    for x, y, _, q in points:
        draw.ellipse(
            (x - 13, y - 13, x + 13, y + 13),
            fill=ORANGE if q == 1 else NAVY,
            outline=WHITE,
            width=4,
        )
        draw.text(
            (x, top + plot_h + 31),
            str(q),
            font=_font(34),
            fill=INK,
            anchor="ma",
        )

    draw.line(
        (left, top, left, top + plot_h),
        fill=INK,
        width=4,
    )
    draw.line(
        (left, top + plot_h, left + plot_w, top + plot_h),
        fill=INK,
        width=4,
    )

    draw.text(
        (left + plot_w / 2, height - 58),
        "Expulsion threshold, q",
        font=_font(36),
        fill=INK,
        anchor="ma",
    )
    _draw_vertical_text(
        image,
        "Change in RMST (periods)",
        64,
        top + plot_h / 2,
        _font(36),
        INK,
    )

    svg = []
    for tick in (-160, -120, -80, -40, 0):
        sy = 70 + (20 - tick) / 180 * 500
        svg.append(
            f'<line x1="165" y1="{sy:.1f}" x2="1130" y2="{sy:.1f}" '
            'stroke="#e1e1e1" stroke-width="1.5"/>'
        )
        svg.append(
            _svg_text(147, sy + 7, tick, 18, anchor="end", fill="#232323")
        )
    svg.append(
        '<line x1="165" y1="70" x2="165" y2="570" stroke="#232323" stroke-width="2"/>'
    )
    svg.append(
        '<line x1="165" y1="570" x2="1130" y2="570" stroke="#232323" stroke-width="2"/>'
    )
    svg.append(
        '<line x1="165" y1="625.6" x2="1130" y2="625.6" '
        'stroke="#232323" stroke-width="2" stroke-dasharray="8 7"/>'
    )
    svg_points = []
    for i, q in enumerate(THRESHOLDS):
        value = 0.0 if q == 1 else SURVIVAL_EFFECTS[q]
        sx = 165 + i * (965 / 7)
        sy = 70 + (20 - value) / 180 * 500
        svg_points.append((sx, sy, value, q))
    svg.append(
        '<polyline points="'
        + " ".join(f"{x:.1f},{y:.1f}" for x, y, _, _ in svg_points)
        + '" fill="none" stroke="#1f4e79" stroke-width="5"/>'
    )
    for x, y, value, q in svg_points:
        svg.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="10" fill="{"#c96f35" if q == 1 else "#1f4e79"}"/>')
        svg.append(_svg_text(x, 612, str(q), 18, anchor="middle"))
    svg.append(_svg_text(647, 670, "Expulsion threshold, q", 21, anchor="middle"))
    svg.append(
        '<text x="44" y="320" text-anchor="middle" '
        'font-family="Times New Roman, Times, serif" font-size="20" '
        'fill="#232323" transform="rotate(-90 44 320)">Change in RMST (periods)</text>'
    )
    _save_figure(image, png_path, svg)

def _cluster_fixed_effects(
    frame: pd.DataFrame,
    outcome: str,
    reference_q: int = 1,
) -> pd.DataFrame:
    data = frame.loc[:, ["q", "rho", "seed", outcome]].dropna().copy()
    thresholds = sorted(q for q in data["q"].unique() if q != reference_q)
    dummies = np.column_stack([(data["q"].to_numpy() == q).astype(float) for q in thresholds])
    y = data[outcome].to_numpy(dtype=float)
    groups = data["rho"].to_numpy()

    def demean(values: np.ndarray) -> np.ndarray:
        out = values.copy()
        for group in np.unique(groups):
            mask = groups == group
            out[mask] -= values[mask].mean(axis=0)
        return out

    xw = demean(dummies)
    yw = demean(y)
    bread = np.linalg.pinv(xw.T @ xw)
    beta = bread @ (xw.T @ yw)
    residual = yw - xw @ beta

    seeds = data["seed"].to_numpy()
    unique_seeds = np.unique(seeds)
    score_rows = []
    for seed_value in unique_seeds:
        mask = seeds == seed_value
        score_rows.append((xw[mask].T @ residual[mask]))
    scores = np.vstack(score_rows)
    g_count, n_obs, n_params = len(unique_seeds), len(data), len(beta)
    factor = (g_count / max(g_count - 1, 1)) * (
        (n_obs - 1) / max(n_obs - n_params, 1)
    )
    covariance = factor * bread @ (scores.T @ scores) @ bread
    se = np.sqrt(np.maximum(np.diag(covariance), 0.0))
    t_stat = np.divide(beta, se, out=np.full_like(beta, np.nan), where=se > 0)
    p_value = np.array([math.erfc(abs(t) / math.sqrt(2)) for t in t_stat])

    rng = np.random.default_rng(20261116)
    reps = 1999
    t_boot = np.zeros((reps, len(beta)))
    for b in range(reps):
        weights = rng.choice([-1.0, 1.0], size=len(unique_seeds))
        beta_boot = bread @ (scores.T @ weights)
        t_boot[b] = np.divide(
            beta_boot,
            se,
            out=np.full_like(beta_boot, np.nan),
            where=se > 0,
        )

    ordered = np.argsort(-np.abs(t_stat))
    adjusted = np.zeros(len(beta))
    running = 0.0
    for rank, idx in enumerate(ordered):
        remaining = ordered[rank:]
        maxima = np.nanmax(np.abs(t_boot[:, remaining]), axis=1)
        raw = (1.0 + np.sum(maxima >= abs(t_stat[idx]))) / (reps + 1.0)
        running = max(running, float(raw))
        adjusted[idx] = min(running, 1.0)

    return pd.DataFrame(
        {
            "q": thresholds,
            "estimate": beta,
            "cluster_seed_se": se,
            "conventional_p": p_value,
            "romano_wolf_p": adjusted,
        }
    )


def bootstrap_best_threshold(frame: pd.DataFrame, outcome: str) -> pd.DataFrame:
    data = frame.loc[:, ["q", "seed", outcome]].dropna()
    rng = np.random.default_rng(20261117)
    seeds = data["seed"].unique()
    winners: list[float] = []
    for _ in range(2000):
        sample_seeds = rng.choice(seeds, size=len(seeds), replace=True)
        draws = []
        for draw, seed_value in enumerate(sample_seeds):
            part = data.loc[data["seed"] == seed_value, ["q", outcome]].copy()
            part["draw"] = draw
            draws.append(part)
        sampled = pd.concat(draws, ignore_index=True)
        means = sampled.groupby(["draw", "q"])[outcome].mean().groupby("draw").idxmax()
        winners.extend(data_q for _, data_q in means.tolist())
    frequencies = pd.Series(winners, dtype=float).value_counts(normalize=True)
    return (
        frequencies.reindex(sorted(data["q"].unique()), fill_value=0.0)
        .rename_axis("q")
        .reset_index(name="bootstrap_best_frequency")
    )


def write_design_tables(frame: pd.DataFrame | None = None) -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    design = pd.DataFrame(
        [
            ("thresholds", "1, 2, 3, 4, 5, 6, 8, 10", "Eight integer policy rules"),
            ("initial_cheater_share", "0.05, 0.10, 0.20, 0.30, 0.40", "Five market types"),
            ("random_seeds", "100", "Shared across all thresholds"),
            ("market_size_N", "100", "Held fixed"),
            ("trade_limit_a", "3", "Held fixed"),
            ("conversion_threshold_p", "3", "Held fixed"),
            ("horizon_T", "200", "Held fixed"),
            ("bankruptcy_switch", "on", "Reproduces the baseline configuration"),
        ],
        columns=["parameter", "value", "note"],
    )
    design.to_csv(TABLES / "design_parameters.csv", index=False)

    markets = len(frame) if frame is not None else MARKETS
    collapsed = int(frame["collapsed"].sum()) if frame is not None else COLLAPSED
    sample = pd.DataFrame(
        [
            ("simulated_markets", markets),
            ("collapsed_markets", collapsed),
            ("surviving_markets", markets - collapsed),
            ("pooled_collapse_rate", collapsed / markets),
        ],
        columns=["statistic", "value"],
    )
    sample.to_csv(TABLES / "sample_accounting.csv", index=False)


def write_market_template() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    template = pd.DataFrame(
        {
            "q": THRESHOLDS,
            "RMST rho=0.05": np.nan,
            "RMST rho=0.10": np.nan,
            "RMST rho=0.20": np.nan,
            "RMST rho=0.30": np.nan,
            "RMST rho=0.40": np.nan,
            "collapse rate (pooled)": np.nan,
        }
    )
    template.to_csv(TABLES / "table_e1_market_rmst_template.csv", index=False)


def write_summary_tables() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "q": 1,
            "survival_effect_periods": 0.0,
            "welfare_effect_surplus_units": 0.0,
            "interval_summary": "Reference",
            "romano_wolf_p": "Reference",
        }
    ]
    for q in THRESHOLDS[1:]:
        rows.append(
            {
                "q": q,
                "survival_effect_periods": SURVIVAL_EFFECTS[q],
                "welfare_effect_surplus_units": WELFARE_ENDPOINTS.get(q, np.nan),
                "interval_summary": "excludes zero",
                "romano_wolf_p": "<0.001",
            }
        )
    coefficients = pd.DataFrame(rows)
    coefficients.to_csv(TABLES / "table_e1_threshold_response.csv", index=False)

    md_lines = [
        "| q | Survival effect (periods) | Welfare effect | 95% CI | Romano-Wolf p |",
        "| ---: | ---: | ---: | --- | --- |",
    ]
    for row in rows:
        welfare = row["welfare_effect_surplus_units"]
        welfare_text = "NA" if pd.isna(welfare) else f"{welfare:,.0f}"
        md_lines.append(
            f'| {row["q"]} | {row["survival_effect_periods"]:.1f} | '
            f'{welfare_text} | {row["interval_summary"]} | '
            f'{row["romano_wolf_p"]} |'
        )
    (TABLES / "table_e1_threshold_response.md").write_text(
        "\n".join(md_lines) + "\n", encoding="utf-8"
    )


def analyze_input(path: Path) -> dict[str, object]:
    frame = pd.read_csv(path)
    required = {"q", "rho", "seed", "surv", "collapsed"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"input is missing required columns: {', '.join(sorted(missing))}")
    frame = frame.copy()
    for column in required.intersection(frame.columns):
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    if "welfare" in frame.columns:
        frame["welfare"] = pd.to_numeric(frame["welfare"], errors="coerce")

    market_means = (
        frame.groupby(["q", "rho"], as_index=False)["surv"].mean()
        .pivot(index="q", columns="rho", values="surv")
        .sort_index()
    )
    collapse = frame.groupby("q", as_index=False)["collapsed"].mean().set_index("q")
    response_table = market_means.copy()
    response_table.columns = [f"RMST rho={float(c):.2f}" for c in response_table.columns]
    response_table["collapse rate (pooled)"] = collapse["collapsed"]
    response_table.reset_index().to_csv(
        TABLES / "table_e1_market_rmst.csv", index=False
    )

    survival_fe = _cluster_fixed_effects(frame, "surv")
    survival_fe.to_csv(TABLES / "survival_threshold_regression.csv", index=False)
    best_survival = bootstrap_best_threshold(frame, "surv")
    best_survival.to_csv(TABLES / "bootstrap_best_threshold_survival.csv", index=False)

    if "welfare" in frame.columns and frame["welfare"].notna().any():
        welfare_fe = _cluster_fixed_effects(frame, "welfare")
        welfare_fe.to_csv(TABLES / "welfare_threshold_regression.csv", index=False)
        best_welfare = bootstrap_best_threshold(frame, "welfare")
        best_welfare.to_csv(TABLES / "bootstrap_best_threshold_welfare.csv", index=False)

    summary = {
        "markets": int(len(frame)),
        "collapse_count": int(frame["collapsed"].sum()),
        "collapse_rate": float(frame["collapsed"].mean()),
        "thresholds": sorted(int(x) for x in frame["q"].unique()),
        "seeds": int(frame["seed"].nunique()),
        "rho_levels": sorted(float(x) for x in frame["rho"].unique()),
    }
    (TABLES / "analysis_results.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="complete run-level CSV")
    args = parser.parse_args()
    FIGURES.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)

    render_survival_figure(FIGURES / "figure_e1_survival_response.png")
    write_design_tables()

    if args.input:
        summary = analyze_input(args.input)
        print(json.dumps(summary, indent=2))
    else:
        write_summary_tables()
        write_market_template()
        print(
            json.dumps(
                {
                    "mode": "reported-summary",
                    "markets": MARKETS,
                    "collapsed": COLLAPSED,
                    "collapse_rate": COLLAPSE_RATE,
                    "notes": "Pass --input with the complete run-level CSV to fill market-specific RMST cells.",
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()

