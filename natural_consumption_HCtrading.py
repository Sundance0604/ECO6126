"""
封闭市场互动模型 v1.5  (完整版)
================================================================
v1.5 死亡分类修正（交易死亡优先，消耗死亡兜底）：
- 死亡原因只有两种：交易死亡 / 消耗死亡（模型无其他死亡途径）
- 判定依据：个体本步是否参与至少一笔交易
    * 参与   → 交易死亡
    * 未参与 → 消耗死亡（含被驱逐后的慢性死亡）
- 当步保护：步首扣 c 后 w≤0 仍照常交易，步末才判死

v1.4 基础（自然消耗与死亡解耦）：
- Params.c：每步自然消耗；默认 0，对 RQ1 完全兼容
- 死亡条件：w≤0 且 (c>0 或 enable_bankrupt)
- 被驱逐后死亡：flag_evict 保留，death_cause = 消耗死亡
- 无 active 但有 alive 且 c>0 时，步进仅扣消耗并检查死亡

基础设定（v1.3）：
- 交易边 t 步末迭代双向配对，每人最多 a 个对象，双向加入
- 同步结算（theta_t 快照），当步转化放步末
- m 为“累计交易受损次数”：H-P 老实人 m+1；P-P 双方 m 各+1
- 拉黑/举报：H-P 老实人拉黑并举报骗子；P-P 只互相拉黑不举报
- 退出：flag_bankrupt / flag_evict 两个独立标签，可同时触发
================================================================
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List, Dict
import os
import numpy as np

HONEST = 0
CHEAT = 1
TT_HH, TT_HP, TT_PH, TT_PP = "HH", "HP", "PH", "PP"

# death_cause 取值
DEATH_NONE = -1
DEATH_TRADE = 0
DEATH_CONSUMPTION = 1


# ============================================================
# 参数
# ============================================================
@dataclass
class Params:
    H: int = 70
    C: int = 30
    a: int = 3
    p: int = 3
    q: int = 3
    w_init: float = 10.0
    max_steps: int = 200
    seed: Optional[int] = 42
    g_HH: float = 2.0
    g_HP_H: float = -2.0
    g_HP_P: float = 2.0
    g_PP: float = -1.0
    enable_bankrupt: bool = True
    enable_evict: bool = True
    c: float = 0.0

    @property
    def N(self) -> int:
        return self.H + self.C


# ============================================================
# 模型
# ============================================================
class MarketModel:
    def __init__(self, params: Params):
        self.p = params
        if params.H < 0 or params.C < 0:
            raise ValueError("H、C 必须非负")
        if params.N < 2:
            raise ValueError(f"H + C = {params.N} 太小")
        if params.c < 0:
            raise ValueError("c 必须非负")

        self.rng = np.random.default_rng(params.seed)
        theta0 = np.concatenate([
            np.full(params.H, HONEST, dtype=int),
            np.full(params.C, CHEAT, dtype=int),
        ])
        self.rng.shuffle(theta0)
        self.theta = theta0

        N = params.N
        self.w = np.full(N, float(params.w_init))
        self.m = np.zeros(N, dtype=int)
        self.r = np.zeros(N, dtype=int)
        self.blacklist = [set() for _ in range(N)]

        # 退出市场标签
        self.flag_bankrupt = np.zeros(N, dtype=bool)
        self.flag_evict = np.zeros(N, dtype=bool)
        self.active = np.ones(N, dtype=bool)
        self.exit_w = np.full(N, np.nan)
        self.exit_t = np.full(N, -1, dtype=int)

        # 存活与死亡
        self.alive = np.ones(N, dtype=bool)
        self.death_t = np.full(N, -1, dtype=int)
        self.death_cause = np.full(N, DEATH_NONE, dtype=int)

        self.t = 0
        self.converted_total = 0
        self.edge_history: List[Dict] = []
        self.agg_history: List[Dict] = []
        self.ind_history: List[Dict] = []

        self._record_individuals()
        self._record_aggregate(n_edges=0, by_type={})

    # ---------------- 双向配对 ----------------
    @staticmethod
    def _pool_remove(pool, pos_in_pool, item):
        k = pos_in_pool.pop(item)
        last = pool[-1]
        if k != len(pool) - 1:
            pool[k] = last
            pos_in_pool[last] = k
        pool.pop()

    def _draw_edges(self) -> List[tuple]:
        N = self.p.N
        a = self.p.a
        active = self.active
        bl = self.blacklist

        sets: List[set] = [set() for _ in range(N)]
        remaining = [a if active[i] else 0 for i in range(N)]

        pool = [i for i in range(N) if active[i] and remaining[i] > 0]
        pos_in_pool = {idx: k for k, idx in enumerate(pool)}

        while pool:
            pos = int(self.rng.integers(len(pool)))
            i = pool[pos]

            cands = []
            for j in range(N):
                if j == i or not active[j] or remaining[j] <= 0:
                    continue
                if j in sets[i] or i in sets[j]:
                    continue
                if j in bl[i] or i in bl[j]:
                    continue
                cands.append(j)

            if not cands:
                self._pool_remove(pool, pos_in_pool, i)
                continue

            j = int(self.rng.choice(cands))
            sets[i].add(j)
            sets[j].add(i)
            remaining[i] -= 1
            remaining[j] -= 1

            if remaining[i] <= 0:
                self._pool_remove(pool, pos_in_pool, i)
            if remaining[j] <= 0 and j in pos_in_pool:
                self._pool_remove(pool, pos_in_pool, j)

        edges = []
        for i in range(N):
            for j in sets[i]:
                if i < j:
                    edges.append((i, j))
        return edges

    # ---------------- 单步 ----------------
    def step(self) -> bool:
        if not self.alive.any():
            return False

        # ===== 步首：所有存活个体扣自然消耗（当步保护：本步后续照常）=====
        if self.p.c > 0:
            self.w[self.alive] -= self.p.c

        # ===== 无 active 个体时的特殊分支（被驱逐后的慢性死亡阶段）=====
        if not self.active.any():
            if self.p.c == 0:
                # 无活跃、无消耗：市场已静默，结束
                return False
            traded_this_step = np.zeros(self.p.N, dtype=bool)  # 无交易
            for i in np.where(self.alive)[0]:
                self._check_exit_and_death(int(i), traded_this_step)
            self.t += 1
            self._record_individuals()
            self._record_aggregate(n_edges=0, by_type={})
            return self.alive.any()

        # ===== 正常交易流程 =====
        edges = self._draw_edges()

        traded_this_step = np.zeros(self.p.N, dtype=bool)

        theta_t = self.theta.copy()
        d_w = np.zeros(self.p.N)
        d_m = np.zeros(self.p.N, dtype=int)
        d_r = np.zeros(self.p.N, dtype=int)
        add_bl = [set() for _ in range(self.p.N)]

        edge_records, by_type = [], {TT_HH: 0, TT_HP: 0, TT_PH: 0, TT_PP: 0}
        p = self.p
        for (i, j) in edges:
            traded_this_step[i] = True
            traded_this_step[j] = True

            ti, tj = int(theta_t[i]), int(theta_t[j])
            if ti == HONEST and tj == HONEST:
                dw_i = dw_j = p.g_HH
                tt = TT_HH
            elif ti == HONEST and tj == CHEAT:
                dw_i, dw_j = p.g_HP_H, p.g_HP_P
                d_m[i] += 1
                d_r[j] += 1
                add_bl[i].add(j)
                tt = TT_HP
            elif ti == CHEAT and tj == HONEST:
                dw_i, dw_j = p.g_HP_P, p.g_HP_H
                d_m[j] += 1
                d_r[i] += 1
                add_bl[j].add(i)
                tt = TT_PH
            else:
                dw_i = dw_j = p.g_PP
                d_m[i] += 1
                d_m[j] += 1
                add_bl[i].add(j)
                add_bl[j].add(i)
                tt = TT_PP

            d_w[i] += dw_i
            d_w[j] += dw_j
            by_type[tt] += 1
            edge_records.append({
                't': self.t, 'i': int(i), 'j': int(j),
                'theta_i': ti, 'theta_j': tj, 'type': tt,
                'delta_w_i': dw_i, 'delta_w_j': dw_j,
            })

        # 应用资金/受骗/举报/拉黑（仅 active 个体）
        for i in np.where(self.active)[0]:
            self.w[i] += d_w[i]
        self.m += d_m
        self.r += d_r
        for i in range(p.N):
            if add_bl[i]:
                self.blacklist[i] |= add_bl[i]

        # 步末转化
        for i in np.where(self.active)[0]:
            if self.theta[i] == HONEST and self.m[i] >= p.p:
                self.theta[i] = CHEAT
                self.converted_total += 1

        # ===== 步末退出与死亡检查（覆盖所有存活个体）=====
        for i in np.where(self.alive)[0]:
            self._check_exit_and_death(int(i), traded_this_step)

        self.edge_history.extend(edge_records)
        self.t += 1
        self._record_individuals()
        self._record_aggregate(n_edges=len(edges), by_type=by_type)
        return self.alive.any()

    def _check_exit_and_death(self, i: int, traded_this_step: np.ndarray) -> bool:
        """
        检查个体 i 是否退出市场和/或死亡。
        死亡分类：本步参与交易 → 交易死亡；否则 → 消耗死亡。
        """
        p = self.p
        w = self.w[i]

        can_die = (p.c > 0) or p.enable_bankrupt
        is_dying = self.alive[i] and can_die and w <= 0

        hit_bk = p.enable_bankrupt and self.active[i] and w <= 0
        hit_ev = p.enable_evict and self.active[i] and self.r[i] >= p.q

        if not (is_dying or hit_bk or hit_ev):
            return False

        # 首次退出市场：记录 exit_w / exit_t
        if self.active[i] and (hit_bk or hit_ev or is_dying):
            self.exit_w[i] = float(w)
            self.exit_t[i] = self.t + 1
            self.active[i] = False

        if hit_bk:
            self.flag_bankrupt[i] = True
        if hit_ev:
            self.flag_evict[i] = True

        if is_dying:
            self.alive[i] = False
            self.death_t[i] = self.t + 1
            if traded_this_step[i]:
                self.death_cause[i] = DEATH_TRADE
            else:
                self.death_cause[i] = DEATH_CONSUMPTION

        return True

    # ---------------- 记录 ----------------
    def _record_individuals(self):
        N = self.p.N
        bl_size = np.array([len(self.blacklist[i]) for i in range(N)])
        bl_by = np.zeros(N, dtype=int)
        for i in range(N):
            for j in self.blacklist[i]:
                bl_by[j] += 1
        self.ind_history.append({
            't': self.t,
            'theta': self.theta.copy(),
            'w': self.w.copy(),
            'm': self.m.copy(),
            'r': self.r.copy(),
            'active': self.active.copy(),
            'flag_bankrupt': self.flag_bankrupt.copy(),
            'flag_evict': self.flag_evict.copy(),
            'exit_w': self.exit_w.copy(),
            'exit_t': self.exit_t.copy(),
            'blacklist_size': bl_size,
            'blacklisted_by_size': bl_by,
            'alive': self.alive.copy(),
            'death_t': self.death_t.copy(),
            'death_cause': self.death_cause.copy(),
        })

    def _record_aggregate(self, n_edges: int, by_type: Dict[str, int]):
        act = self.active
        H_alive = int(np.sum(act & (self.theta == HONEST)))
        P_alive = int(np.sum(act & (self.theta == CHEAT)))
        fb = self.flag_bankrupt
        fe = self.flag_evict
        self.agg_history.append({
            't': self.t,
            'N_active': int(act.sum()),
            'H_active': H_alive,
            'P_active': P_alive,
            'W_active': float(np.sum(self.w[act])),
            'W_evict_frozen': float(np.sum(self.w[fe])),
            'converted_total': self.converted_total,
            'bankrupt_total': int(fb.sum()),
            'evicted_total': int(fe.sum()),
            'both_total': int((fb & fe).sum()),
            'exited_total': int((fb | fe).sum()),
            'n_edges': int(n_edges),
            'n_HH': by_type.get(TT_HH, 0),
            'n_HP': by_type.get(TT_HP, 0) + by_type.get(TT_PH, 0),
            'n_PP': by_type.get(TT_PP, 0),
            'N_alive': int(self.alive.sum()),
            'death_total': int((~self.alive).sum()),
            'death_trade_total': int((self.death_cause == DEATH_TRADE).sum()),
            'death_consumption_total': int((self.death_cause == DEATH_CONSUMPTION).sum()),
        })

    # ---------------- 运行 ----------------
    def run(self, verbose_every: Optional[int] = None) -> "MarketModel":
        while self.t < self.p.max_steps:
            if not self.step():
                break
            if verbose_every and self.t % verbose_every == 0:
                h = self.agg_history[-1]
                print(f"t={h['t']:4d}  active={h['N_active']:4d} "
                      f"(H={h['H_active']:4d}, P={h['P_active']:4d})  "
                      f"alive={h['N_alive']:4d}  edges={h['n_edges']:4d}  "
                      f"W_act={h['W_active']:9.1f}  "
                      f"bk={h['bankrupt_total']:3d} ev={h['evicted_total']:3d}  "
                      f"death={h['death_total']:3d} "
                      f"(trade={h['death_trade_total']:3d}, "
                      f"cons={h['death_consumption_total']:3d})")
        return self

    # ---------------- DataFrame ----------------
    def to_aggregate_dataframe(self):
        import pandas as pd
        return pd.DataFrame(self.agg_history)

    def to_individual_dataframe(self):
        """向量化生成 individual 长表：行 = (t, id)，列 = 状态变量。"""
        import pandas as pd
        N = self.p.N
        T = len(self.ind_history)

        cols = ['theta', 'w', 'm', 'r', 'active',
                'flag_bankrupt', 'flag_evict', 'exit_w', 'exit_t',
                'blacklist_size', 'blacklisted_by_size',
                'alive', 'death_t', 'death_cause']
        arrays = {c: np.stack([s[c] for s in self.ind_history]) for c in cols}
        t_index = np.array([s['t'] for s in self.ind_history], dtype=int)

        df = pd.DataFrame({
            't': np.repeat(t_index, N),
            'id': np.tile(np.arange(N), T),
        })
        for c in cols:
            df[c] = arrays[c].reshape(-1)

        fb = df['flag_bankrupt'].values
        fe = df['flag_evict'].values
        label = np.full(len(df), 'none', dtype=object)
        label[fb] = 'bankrupt'
        label[fe] = 'evict'
        label[fb & fe] = 'both'
        df['exit_label'] = label

        return df[['t', 'id', 'theta', 'w', 'm', 'r', 'active',
                   'flag_bankrupt', 'flag_evict', 'exit_label',
                   'exit_w', 'exit_t',
                   'blacklist_size', 'blacklisted_by_size',
                   'alive', 'death_t', 'death_cause']]

    def to_edges_dataframe(self):
        import pandas as pd
        return pd.DataFrame(self.edge_history)


# ============================================================
# 启动器
# ============================================================
def _ask_int(prompt, default):
    s = input(f"{prompt} [默认 {default}]: ").strip()
    return int(s) if s else default


def _ask_float(prompt, default):
    s = input(f"{prompt} [默认 {default}]: ").strip()
    return float(s) if s else default


def _ask_optional_int(prompt, default):
    d = "无" if default is None else str(default)
    s = input(f"{prompt} [默认 {d}]: ").strip()
    return default if not s else int(s)


def _ask_bool(prompt, default: bool) -> bool:
    d = "Y/n" if default else "y/N"
    s = input(f"{prompt} [{d}]: ").strip().lower()
    if not s:
        return default
    return s in ("y", "yes", "1", "true", "是")


def _print_config(params: Params):
    total = params.N
    ratio = params.C / total * 100 if total else 0.0
    print("=" * 64)
    print(" 封闭市场互动模型 v1.5  配置预览")
    print("=" * 64)
    print(f"  老实人 H / 骗子 C    : {params.H} / {params.C}  (N={total}, 骗子占 {ratio:.1f}%)")
    print(f"  初始资金 w_init      : {params.w_init}")
    print(f"  每步自然消耗 c       : {params.c}   （0 表示不启用消耗机制）")
    print(f"  交易能力 a           : {params.a}")
    print(f"  转化阈值 p           : {params.p}")
    print(f"  驱逐阈值 q           : {params.q}")
    print(f"  最大步数 max_steps   : {params.max_steps}")
    print(f"  随机种子 seed        : {params.seed}")
    print(f"  破产退出开关         : {'启用' if params.enable_bankrupt else '关闭'}")
    print(f"  举报驱逐开关         : {'启用' if params.enable_evict else '关闭'}")
    print(f"  （死亡分类：交易死亡 / 消耗死亡；消耗死亡兜底）")
    print(f"  损益                 : H-H={params.g_HH:+g}  "
          f"H-P=({params.g_HP_H:+g},{params.g_HP_P:+g})  P-P={params.g_PP:+g}")
    print("=" * 64)


def make_params(
    H: int, C: int,
    w_init: float = 10.0, a: int = 3, p: int = 3, q: int = 3,
    max_steps: int = 200, seed: Optional[int] = 42,
    enable_bankrupt: bool = True,
    enable_evict: bool = True,
    c: float = 0.0,
    verbose: bool = True,
) -> Params:
    if int(H) < 0 or int(C) < 0:
        raise ValueError(f"H={H}, C={C} 必须非负")
    if int(H) + int(C) < 2:
        raise ValueError(f"H + C = {int(H) + int(C)} 太小，至少为 2")
    if a < 1 or p < 1 or q < 1:
        raise ValueError("a, p, q 必须 ≥ 1")
    if w_init <= 0:
        raise ValueError("w_init 必须 > 0")
    if c < 0:
        raise ValueError("c 必须 ≥ 0")

    params = Params(
        H=int(H), C=int(C),
        w_init=float(w_init), a=int(a), p=int(p), q=int(q),
        max_steps=int(max_steps), seed=seed,
        enable_bankrupt=bool(enable_bankrupt),
        enable_evict=bool(enable_evict),
        c=float(c),
    )
    if verbose:
        _print_config(params)
    return params


def interactive_params() -> Params:
    print("\n>>> 交互式配置：回车采用方括号内默认值\n")
    H = _ask_int("老实人数 H", 70)
    C = _ask_int("骗子数 C", 30)
    print(f"  -> 自动得到 N = H + C = {H + C}\n")
    w_init = _ask_float("初始资金 w_init", 10.0)
    c = _ask_float("每步自然消耗 c（0 表示不启用消耗机制）", 0.0)
    a = _ask_int("交易能力 a", 3)
    p = _ask_int("转化阈值 p", 3)
    q = _ask_int("驱逐阈值 q", 3)
    max_steps = _ask_int("最大步数 max_steps", 200)
    seed = _ask_optional_int("随机种子 seed（留空为 None）", 42)
    enable_bankrupt = _ask_bool("启用破产退出？", True)
    enable_evict = _ask_bool("启用举报驱逐？", True)

    return make_params(
        H=H, C=C, w_init=w_init, c=c, a=a, p=p, q=q,
        max_steps=max_steps, seed=seed,
        enable_bankrupt=enable_bankrupt,
        enable_evict=enable_evict,
        verbose=True,
    )


def launch(interactive: Optional[bool] = None, verbose_every: Optional[int] = None,
           confirm: bool = False, **param_kwargs) -> MarketModel:
    if interactive is None:
        interactive = (len(param_kwargs) == 0)
    params = interactive_params() if interactive else make_params(**param_kwargs)

    if confirm and input("确认启动？(y/N): ").strip().lower() != "y":
        raise RuntimeError("用户取消启动")

    model = MarketModel(params)
    model.run(verbose_every=verbose_every)
    return model


# ============================================================
# 导出与汇总
# ============================================================
def export_results(
    model: MarketModel,
    out_dir: str = "simulation_results",
    prefix: Optional[str] = None,
    fmt: str = "both",
    include_edges: bool = True,
    include_params: bool = True,
) -> List[str]:
    try:
        import pandas as pd
    except ImportError:
        print("[导出] 未安装 pandas，跳过导出。请先 `pip install pandas`")
        return []

    os.makedirs(out_dir, exist_ok=True)
    if prefix is None:
        p = model.p
        flag_b = "BK" if p.enable_bankrupt else "noBK"
        flag_e = "EV" if p.enable_evict else "noEV"
        c_tag = f"c{str(p.c).replace('.', 'p')}"
        prefix = f"H{p.H}_C{p.C}_a{p.a}_p{p.p}_q{p.q}_{flag_b}_{flag_e}_{c_tag}_seed{p.seed}"

    agg = model.to_aggregate_dataframe()
    ind = model.to_individual_dataframe()
    edges = model.to_edges_dataframe() if include_edges else None
    files: List[str] = []

    if fmt in ("csv", "both"):
        f_agg = os.path.join(out_dir, f"{prefix}_aggregate.csv")
        f_ind = os.path.join(out_dir, f"{prefix}_individual.csv")
        agg.to_csv(f_agg, index=False, encoding="utf-8-sig")
        ind.to_csv(f_ind, index=False, encoding="utf-8-sig")
        files += [f_agg, f_ind]
        if edges is not None:
            f_edge = os.path.join(out_dir, f"{prefix}_edges.csv")
            edges.to_csv(f_edge, index=False, encoding="utf-8-sig")
            files.append(f_edge)

    if fmt in ("xlsx", "both"):
        xlsx_path = os.path.join(out_dir, f"{prefix}.xlsx")
        try:
            with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
                agg.to_excel(writer, sheet_name="aggregate", index=False)
                ind.to_excel(writer, sheet_name="individual", index=False)
                if edges is not None:
                    edges.to_excel(writer, sheet_name="edges", index=False)
                if include_params:
                    row = {**vars(model.p), "N": model.p.N}
                    pd.DataFrame([row]).to_excel(
                        writer, sheet_name="params", index=False)
            files.append(xlsx_path)
        except ImportError:
            print("[导出] 未安装 openpyxl，跳过 xlsx。请 `pip install openpyxl` 或改用 fmt='csv'")

    print(f"[导出] 共生成 {len(files)} 个文件：")
    for f in files:
        print("   ", f)
    return files


def export_pivot_views(
    model: MarketModel,
    out_dir: str = "simulation_results",
    variables: Optional[List[str]] = None,
    prefix: Optional[str] = None,
) -> List[str]:
    """可选：把 individual 长表按每个状态变量 pivot 成“时间×个体”矩阵 CSV。"""
    try:
        import pandas as pd
    except ImportError:
        print("[透视导出] 未安装 pandas，跳过。")
        return []

    os.makedirs(out_dir, exist_ok=True)
    if prefix is None:
        p = model.p
        flag_b = "BK" if p.enable_bankrupt else "noBK"
        flag_e = "EV" if p.enable_evict else "noEV"
        c_tag = f"c{str(p.c).replace('.', 'p')}"
        prefix = f"H{p.H}_C{p.C}_a{p.a}_p{p.p}_q{p.q}_{flag_b}_{flag_e}_{c_tag}_seed{p.seed}"

    if variables is None:
        variables = ['theta', 'w', 'm', 'r', 'active', 'alive']

    ind = model.to_individual_dataframe()
    files: List[str] = []
    for var in variables:
        if var not in ind.columns:
            print(f"[透视导出] 变量 {var} 不在 individual 表中，跳过")
            continue
        mat = ind.pivot(index='t', columns='id', values=var)
        f = os.path.join(out_dir, f"{prefix}_pivot_{var}.csv")
        mat.to_csv(f, encoding="utf-8-sig")
        files.append(f)

    print(f"[透视导出] 共生成 {len(files)} 个矩阵文件：")
    for f in files:
        print("   ", f)
    return files


def summarize(model: MarketModel):
    print("\n==== 末态汇总 ====")
    print(f"  模拟步数          = {model.t}")
    print(f"  累计转化          = {model.converted_total}")
    fb = model.flag_bankrupt
    fe = model.flag_evict
    print(f"  破产标签数        = {int(fb.sum())}")
    print(f"  驱逐标签数        = {int(fe.sum())}")
    print(f"  双标签（同时）    = {int((fb & fe).sum())}")
    print(f"  退出总人数        = {int((fb | fe).sum())}")
    act = model.active
    print(f"  活跃人数          = {int(act.sum())}")
    print(f"  活跃资金          = {float(model.w[act].sum()):.2f}")
    if fe.any():
        ex_w = model.exit_w[fe]
        print(f"  驱逐者退出时账面资金总和 = {float(np.nansum(ex_w)):.2f}  "
              f"(均值 {float(np.nanmean(ex_w)):.2f})")
    if fb.any():
        ex_w = model.exit_w[fb]
        print(f"  破产者退出时账面资金总和 = {float(np.nansum(ex_w)):.2f}")
    al = model.alive
    dc = model.death_cause
    print(f"  存活人数          = {int(al.sum())}")
    print(f"  累计死亡          = {int((~al).sum())}")
    print(f"    交易死亡        = {int((dc == DEATH_TRADE).sum())}")
    print(f"    消耗死亡        = {int((dc == DEATH_CONSUMPTION).sum())}")
    ev = fe & (~al)
    if ev.any():
        lag = model.death_t[ev] - model.exit_t[ev]
        print(f"  被驱逐后死亡人数  = {int(ev.sum())}  "
              f"平均多活 {float(np.nanmean(lag)):.2f} 步")
    H_alive = int(np.sum(act & (model.theta == HONEST)))
    P_alive = int(np.sum(act & (model.theta == CHEAT)))
    print(f"  活跃 H / P        = {H_alive} / {P_alive}")
    print(f"  破产开关          = {'启用' if model.p.enable_bankrupt else '关闭'}")
    print(f"  驱逐开关          = {'启用' if model.p.enable_evict else '关闭'}")
    print(f"  自然消耗 c        = {model.p.c}")


# ============================================================
# 主入口
# ============================================================
if __name__ == "__main__":
    BASE = os.path.dirname(os.path.abspath(__file__))
    OUT_DIR = os.path.join(BASE, "simulation_results")

    # RQ1（宏观崩溃）示例：c=0
    # model = launch(
    #     interactive=False, H=70, C=30, w_init=10.0,
    #     a=3, p=3, q=3, c=0.0,
    #     max_steps=200, seed=42,
    #     enable_bankrupt=True, enable_evict=True,
    #     verbose_every=20,
    # )

    # RQ2/RQ3（个体生存）示例：c>0
    # model = launch(
    #     interactive=False, H=70, C=30, w_init=10.0,
    #     a=3, p=3, q=3, c=0.5,
    #     max_steps=500, seed=42,
    #     enable_bankrupt=True, enable_evict=True,
    #     verbose_every=20,
    # )

    model = launch(interactive=True, verbose_every=20)

    summarize(model)
    export_results(model, out_dir=OUT_DIR, fmt="both")