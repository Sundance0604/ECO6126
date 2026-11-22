"""Agent-based simulation of a closed trading market with reputation punishment.

Implements the environment supplied by the user:
  N = H + C agents, discrete time t = 1..T, initial wealth w0,
  at most a distinct counterparties per agent per step, at most one trade
  per pair per step, blacklists, synchronous (step-end) identity changes,
  H->C conversion at m >= p, bankruptcy at w <= 0, eviction at r >= q,
  and an optional per-step survival cost c.

Outputs run-level outcomes, aggregated time series, one representative
transaction ledger, and one representative individual-level final state.
"""
import sys, os, csv, json
from collections import defaultdict
sys.stdout.reconfigure(encoding='utf-8')
import numpy as np

OUT = r"C:\Users\86187\WorkBuddy\2026-11-22-21-56-35\outputs"
DATA = os.path.join(OUT, "data")
os.makedirs(DATA, exist_ok=True)

# ----------------------------- calibration -----------------------------
N = 200                 # market size
W0 = 20.0               # initial wealth of every agent
G_HH = 1.5              # one-sided payoff in H-H trade (2 g_HH = +3)
G_CC = -2.0             # one-sided payoff in C-C trade (2 g_CC = -4)
X = 5.0                 # H-C wealth transfer (pure transfer, sum = 0)
Q = 3                   # reports needed for eviction
T = 200                 # fixed observation window
COLLAPSE_FRAC = 0.10    # collapse when active H <= 10% of H0

RHO_GRID = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40]
P_GRID = [2, 3, 4]
A_MAIN = 3
E_GRID = [0, 1]
SEEDS_MAIN = 30
A_ROBUST = [2, 4]
C_ROBUST = [0.0, 0.10, 0.30]
RHO_SUB = [0.10, 0.25]
SEEDS_SUB = 20

PARAMS = dict(
    N=N, w0=W0, g_HH=G_HH, g_CC=G_CC, x=X, q=Q, T=T,
    collapse_frac=COLLAPSE_FRAC, a_main=A_MAIN,
    rho_grid=RHO_GRID, p_grid=P_GRID, e_grid=E_GRID,
    seeds_main=SEEDS_MAIN, a_robust=A_ROBUST, c_robust=C_ROBUST,
    rho_sub=RHO_SUB, seeds_sub=SEEDS_SUB,
)


def run_one(rho, p, a, E, c, seed, sample,
            need_ts=False, need_ledger=False, need_indiv=False):
    rng = np.random.default_rng(seed)
    C0 = int(round(rho * N))
    H0 = N - C0

    typ = np.zeros(N, dtype=np.int8)          # 0 = honest, 1 = cheater
    init_perm = rng.permutation(N)
    typ[init_perm[:C0]] = 1
    w = np.full(N, W0, dtype=np.float64)
    m = np.zeros(N, dtype=np.int32)           # cumulative victimisation
    r = np.zeros(N, dtype=np.int32)           # cumulative reports
    active = np.ones(N, dtype=bool)
    blacklist = [set() for _ in range(N)]
    n_black_by = np.zeros(N, dtype=np.int32)
    bankrupt = np.zeros(N, dtype=bool)
    evicted = np.zeros(N, dtype=bool)
    both = np.zeros(N, dtype=bool)
    death_cause = np.full(N, -1, dtype=np.int8)   # -1 alive, 0 trade death, 1 cost death
    exit_wealth = np.full(N, -1.0)
    exit_time = np.full(N, -1, dtype=np.int32)
    death_time = np.full(N, -1, dtype=np.int32)
    conv_time = np.full(N, -1, dtype=np.int32)
    converted = np.zeros(N, dtype=bool)
    alive = np.ones(N, dtype=bool)

    hh = cc = hc = 0                    # cumulative trade counts by type
    wt_real = 0.0                       # realised social net benefit
    wt_theory = 0.0                     # theoretical g_i + g_j (no truncation)
    gap_trade = 0.0                     # truncation gap on C-C losses
    c_real = 0.0                        # realised survival cost paid
    gap_cost = 0.0
    cum_edges = 0
    cum_conv = cum_bank = cum_evict = cum_both = cum_exit = 0
    cum_death = cum_trade_death = cum_cost_death = 0
    evicted_wealth = 0.0
    collapse_time = -1
    collapse_event = 0

    ts, ledger = [], []

    for t in range(1, T + 1):
        active_idx = np.flatnonzero(active)
        n_active = len(active_idx)
        h_active = int(np.count_nonzero((typ == 0) & active))
        c_active = n_active - h_active

        if collapse_time < 0 and h_active <= COLLAPSE_FRAC * H0:
            collapse_time, collapse_event = t, 1

        edges_t = hh_t = hc_t = cc_t = 0
        wt_t = 0.0
        if n_active >= 2:
            partner_count = np.zeros(N, dtype=np.int16)
            traded = set()
            pending = defaultdict(set)
            for _round in range(a):
                perm = rng.permutation(active_idx)
                L = len(perm)
                for k in range(0, L - 1, 2):
                    i = int(perm[k]); j = int(perm[k + 1])
                    if i == j:
                        continue
                    if partner_count[i] >= a or partner_count[j] >= a:
                        continue
                    key = (i, j) if i < j else (j, i)
                    if key in traded:
                        continue
                    if j in blacklist[i] or i in blacklist[j]:
                        continue
                    traded.add(key)
                    partner_count[i] += 1
                    partner_count[j] += 1

                    ti, tj = int(typ[i]), int(typ[j])   # step-start identities
                    if ti == 0 and tj == 0:
                        gi = gj = G_HH
                        dwi, dwj = gi, gj
                        hh += 1; hh_t += 1
                        wt_theory += 2 * G_HH
                        ttype = "HH"
                    elif ti == 1 and tj == 1:
                        gi = gj = G_CC
                        pay_i, pay_j = min(-G_CC, w[i]), min(-G_CC, w[j])
                        gap_trade += (-G_CC - pay_i) + (-G_CC - pay_j)
                        dwi, dwj = -pay_i, -pay_j
                        cc += 1; cc_t += 1
                        wt_theory += 2 * G_CC
                        pending[i].add(j); pending[j].add(i)
                        ttype = "CC"
                    else:
                        if ti == 0:
                            h, ch = i, j
                            tr = min(X, w[i])
                            dwi, dwj = -tr, tr
                            m[i] += 1; r[j] += 1
                            pending[i].add(j)
                        else:
                            h, ch = j, i
                            tr = min(X, w[j])
                            dwi, dwj = tr, -tr
                            m[j] += 1; r[i] += 1
                            pending[j].add(i)
                        hc += 1; hc_t += 1
                        gi, gj = -X, X
                        wt_theory += 0.0
                        ttype = "HC"
                    w[i] += dwi
                    w[j] += dwj
                    wt_real += dwi + dwj
                    wt_t += dwi + dwj
                    edges_t += 1
                    if need_ledger:
                        ledger.append(dict(
                            t=t, i=i, j=j, type=ttype,
                            g_i=round(gi, 6), g_j=round(gj, 6),
                            dw_i=round(dwi, 6), dw_j=round(dwj, 6),
                            S_theory=round(gi + gj, 6),
                            S_realised=round(dwi + dwj, 6)))

            # blacklist updates become effective at step end (synchronous)
            for i0, s in pending.items():
                for j0 in s:
                    if j0 not in blacklist[i0]:
                        blacklist[i0].add(j0)
                        n_black_by[j0] += 1

        cum_edges += edges_t

        # ---------------- step-end synchronous settlement ----------------
        step_active = active_idx.copy()
        for i0 in step_active:
            i0 = int(i0)
            bcond, cause = False, -1
            if w[i0] <= 0.0:                     # wealth exhausted by trading
                w[i0] = 0.0
                bcond, cause = True, 0
            elif c > 0.0:                        # per-step survival cost
                pay = min(c, w[i0])
                w[i0] -= pay
                c_real += pay
                gap_cost += (c - pay)
                if w[i0] <= 0.0:
                    w[i0] = 0.0
                    bcond, cause = True, 1
            econd = bool(E == 1 and r[i0] >= Q)
            if bcond:
                bankrupt[i0] = True
                death_cause[i0] = cause
                death_time[i0] = t
                alive[i0] = False
                cum_bank += 1
                cum_death += 1
                if cause == 0:
                    cum_trade_death += 1
                else:
                    cum_cost_death += 1
            if econd:
                evicted[i0] = True
                cum_evict += 1
                evicted_wealth += w[i0]          # retained wealth at exit
            if bcond and econd:
                both[i0] = True
                cum_both += 1
            if bcond or econd:
                active[i0] = False
                exit_wealth[i0] = w[i0]          # first-exit wealth snapshot
                exit_time[i0] = t
                cum_exit += 1

        # identity changes only at step end; this step settled as honest
        for i0 in step_active:
            i0 = int(i0)
            if active[i0] and typ[i0] == 0 and m[i0] >= p:
                typ[i0] = 1
                converted[i0] = True
                conv_time[i0] = t
                cum_conv += 1

        # ---------------- step-level record ----------------
        n_active_end = int(active.sum())
        rec = dict(
            t=t,
            n_active=n_active_end,
            active_h=int(np.count_nonzero((typ == 0) & active)),
            active_c=int(np.count_nonzero((typ == 1) & active)),
            active_wealth=round(float(w[active].sum()), 4),
            edges=edges_t,
            hh=hh_t, hc=hc_t, cc=cc_t,
            wt_step=round(wt_t, 4), wt_cum=round(wt_real, 4),
            cum_conv=cum_conv, cum_exit=cum_exit,
            cum_death=cum_death, trade_death=cum_trade_death,
            cost_death=cum_cost_death,
            alive=int(alive.sum()),
            cum_bank=cum_bank, cum_evict=cum_evict, cum_both=cum_both,
            evicted_wealth=round(evicted_wealth, 4),
        )
        if need_ts:
            ts.append(rec)

    final_wealth = float(w.sum())
    survival_steps = min(collapse_time, T) if collapse_event else T
    end_active_wealth = float(w[active].sum())

    row = dict(
        run_id=f"{sample}_rho{rho:.2f}_p{p}_a{a}_E{E}_c{c:.2f}_s{seed}",
        sample=sample, rho=rho, p=p, a=a, E=E, c=c, seed=seed,
        config_id=f"rho{rho:.2f}_p{p}_a{a}",
        paired_block_id=f"rho{rho:.2f}_p{p}_a{a}_s{seed}",
        H0=H0, C0=C0,
        collapse_time=collapse_time if collapse_event else T,
        collapse_event=collapse_event,
        survival_steps=survival_steps,
        fraud_count=hc,
        conversion_share=round(cum_conv / H0, 6) if H0 > 0 else 0.0,
        converted_H=cum_conv,
        cooperation_count=hh,
        cooperation_volume=round(2 * G_HH * hh, 4),   # traded surplus value in H-H
        collusion_count=cc,
        total_edges=cum_edges,
        wt_theory=round(wt_theory, 4),
        wt_realised=round(wt_real, 4),
        wt_hh=round(2 * G_HH * hh, 4),
        wt_cc=round(2 * G_CC * cc, 4),
        wt_hc=0.0,
        truncation_gap=round(wt_theory - wt_real, 4),
        cost_realised=round(c_real, 4),
        cost_gap=round(gap_cost, 4),
        resource_adjusted_wt=round(wt_real - c_real, 4),
        end_wealth_total=round(final_wealth, 4),
        accounting_gap=round(final_wealth - (N * W0 + wt_real - c_real), 6),
        end_active_wealth=round(end_active_wealth, 4),
        active_final=int(active.sum()),
        active_h_final=int(np.count_nonzero((typ == 0) & active)),
        active_c_final=int(np.count_nonzero((typ == 1) & active)),
        evicted_wealth=round(evicted_wealth, 4),
        cum_bankrupt=cum_bank, cum_evicted=cum_evict, cum_both=cum_both,
        cum_exit=cum_exit, cum_death=cum_death,
        trade_death=cum_trade_death, cost_death=cum_cost_death,
        alive_final=int(alive.sum()),
        edges_last=edges_t,
        mean_edges=round(cum_edges / T, 4),
        blacklist_links=int(sum(len(s) for s in blacklist)),
        mean_blacklist=round(float(np.mean([len(s) for s in blacklist])), 4),
        mean_blacklisted_by=round(float(n_black_by.mean()), 4),
        mean_wealth=round(float(w.mean()), 4),
    )

    indiv = None
    if need_indiv:
        indiv = []
        for i0 in range(N):
            indiv.append(dict(
                run_id=row["run_id"], E=E, agent=i0,
                final_type="H" if typ[i0] == 0 else "C",
                wealth=round(float(w[i0]), 4),
                victimisations=int(m[i0]), reports=int(r[i0]),
                blacklisted=int(len(blacklist[i0])),
                blacklisted_by=int(n_black_by[i0]),
                active=int(bool(active[i0])),
                bankrupt=int(bool(bankrupt[i0])),
                evicted=int(bool(evicted[i0])),
                both=int(bool(both[i0])),
                alive=int(bool(alive[i0])),
                exit_wealth=round(float(exit_wealth[i0]), 4),
                exit_time=int(exit_time[i0]),
                death_time=int(death_time[i0]),
                death_cause=int(death_cause[i0]),
                converted=int(bool(converted[i0])),
                conversion_time=int(conv_time[i0]),
            ))
    return row, ts, ledger, indiv


def write_csv(path, rows):
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)


def main():
    run_rows, ts_rows, ledger_rows, indiv_rows = [], [], [], []
    agg = defaultdict(lambda: defaultdict(float))
    agg_n = defaultdict(int)
    ts_fields = ["n_active", "active_h", "active_c", "active_wealth", "edges",
                 "hh", "hc", "cc", "wt_step", "wt_cum", "cum_conv", "cum_exit",
                 "cum_death", "trade_death", "cost_death", "alive",
                 "cum_bank", "cum_evict", "cum_both", "evicted_wealth"]

    jobs = []
    for rho in RHO_GRID:
        for p in P_GRID:
            for E in E_GRID:
                for seed in range(SEEDS_MAIN):
                    jobs.append((rho, p, A_MAIN, E, 0.0, seed, "main"))
    for rho in RHO_SUB:
        for a in A_ROBUST:
            for E in E_GRID:
                for seed in range(SEEDS_SUB):
                    jobs.append((rho, 3, a, E, 0.0, seed, "a_robust"))
    for rho in RHO_SUB:
        for c in C_ROBUST:
            for E in E_GRID:
                for seed in range(SEEDS_SUB):
                    jobs.append((rho, 3, A_MAIN, E, c, seed, "c_robust"))

    print("total runs:", len(jobs), flush=True)
    for idx, (rho, p, a, E, c, seed, sample) in enumerate(jobs):
        is_case = (sample == "main" and rho == 0.10 and p == 3 and seed == 0)
        row, ts, ledger, indiv = run_one(
            rho, p, a, E, c, seed, sample,
            need_ts=is_case, need_ledger=is_case, need_indiv=is_case)
        run_rows.append(row)
        if is_case:
            for rec in ts:
                ts_rows.append(dict(run_id=row["run_id"], E=E, n_runs=1, **rec))
            ledger_rows.extend([dict(run_id=row["run_id"], E=E, **x) for x in ledger])
            indiv_rows.extend(indiv)
        if (idx + 1) % 200 == 0:
            print("  done", idx + 1, "/", len(jobs), flush=True)

    # aggregated time series: separate pass over a smaller representative grid
    # (rho in {0.10, 0.25}, p=3, seeds 0..29, main calibration)
    print("building aggregated time series ...", flush=True)
    for rho in [0.10, 0.25]:
        for p in [3]:
            for E in E_GRID:
                for seed in range(SEEDS_MAIN):
                    row, ts, _, _ = run_one(rho, p, A_MAIN, E, 0.0, seed, "ts",
                                           need_ts=True)
                    for rec in ts:
                        key = (E, rec["t"])
                        agg_n[key] += 1
                        for f in ts_fields:
                            agg[key][f] += rec[f]
    for (E, t), d in sorted(agg.items(), key=lambda kv: (kv[0][0], kv[0][1])):
        n = agg_n[(E, t)]
        rec = dict(run_id="AGG", E=E, t=t, n_runs=n)
        for f in ts_fields:
            rec[f] = round(d[f] / n, 4)
        ts_rows.append(rec)

    write_csv(os.path.join(DATA, "run_level.csv"), run_rows)
    write_csv(os.path.join(DATA, "timeseries.csv"), ts_rows)
    write_csv(os.path.join(DATA, "event_ledger_baseline.csv"), ledger_rows)
    write_csv(os.path.join(DATA, "individual_final_baseline.csv"), indiv_rows)
    with open(os.path.join(DATA, "params.json"), "w", encoding="utf-8") as f:
        json.dump(PARAMS, f, indent=2)

    print("run_level rows:", len(run_rows))
    print("timeseries rows:", len(ts_rows))
    print("ledger rows:", len(ledger_rows))
    print("individual rows:", len(indiv_rows))
    # sanity checks
    main = [r for r in run_rows if r["sample"] == "main"]
    print("max |accounting_gap|:", max(abs(r["accounting_gap"]) for r in main))
    for E in E_GRID:
        sub = [r for r in main if r["E"] == E]
        print("E=%d  n=%d  surv=%.2f  fraud=%.1f  conv=%.3f  coop=%.1f  WT=%.1f  endwealth=%.1f" % (
            E, len(sub), np.mean([r["survival_steps"] for r in sub]),
            np.mean([r["fraud_count"] for r in sub]),
            np.mean([r["conversion_share"] for r in sub]),
            np.mean([r["cooperation_count"] for r in sub]),
            np.mean([r["wt_realised"] for r in sub]),
            np.mean([r["end_wealth_total"] for r in sub])))


if __name__ == "__main__":
    main()
