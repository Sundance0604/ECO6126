# 变量说明与组员复用

## 主键与参数

`data/processed/run_level.csv`每个配置×seed×制度一行。`run_id`由模型版本与参数哈希确定；相同模型相同配置重跑具有相同ID，不使用随机UUID。模型改变后版本和ID改变，便于关联与去重。`step_level.csv`主键为(run_id,t)，参数通过run_id作多对一合并，不按文件行号拼接。均为UTF-8 CSV。

| 字段 | 定义 |
|---|---|
| model_version | 原件、适配层、指标代码SHA-256组合指纹 |
| seed | 仿真初始随机种子；跨rho与制度复用的完整区组编号 |
| N,H0,C0,rho | 总人数、初始H、初始C、初始骗子比例 |
| E,B | 驱逐、破产退出开关（0/1） |
| a,p,q | 每轮配对上限、累计受损转化阈值、累计举报驱逐阈值 |
| c,w_init,T | 自然消耗、初始财富、固定观察期 |
| g_HH,g_HP_H,g_HP_P,g_PP | 原件支付参数；本基准为2,-2,2,-1 |

## run_level结果

E=0仍保留私人黑名单及举报累计，只有公共驱逐关闭；B=0允许负财富主体继续交易。基准参数下H_active=H0−converted_total（未转化H不会破产，也不会被准确举报驱逐），所以诚实基础崩溃直接衡量转化扩散。

| 字段 | 定义 |
|---|---|
| collapse_event | T内是否出现10*H_active≤H0，包括恰在T发生 |
| right_censored | 1−collapse_event；无事件时表示仅知tau>T |
| collapse_time | 有事件为首次步末时间，否则为T；不可脱离event使用 |
| rmst_T | min(tau,T)，逐次轨迹截断崩溃时间；其均值为限制平均存续时间估计 |
| welfare_T | 固定T内累计交易净剩余，等于4*total_HH−2*total_CC |
| total_HH,total_HC,total_CC,total_trades | T内各类交易累计数；每条无向边仅记一次 |
| converted_total | 累计H→C转化人数，含随后退出者 |
| bankrupt_total,evicted_total,both_total | 破产、驱逐及两标签交集人数 |
| exited_total | 实际退出总人数=破产+驱逐−交集（当前c=0） |
| no_trade_steps | t=1..T中零交易步数，含吸收状态补齐的步数 |
| simulated_steps,padded_steps | 原模型实际推进步数与到T的吸收状态补齐数 |
| H_active_T,C_active_T,N_active_T | T时市场活跃人口 |
| W_all_T | 所有主体状态财富总和，包含退出者及负财富 |
| W_active_T | T时活跃者状态财富总和，不能当作累计交易剩余 |
| W_evict_exit_raw_T,W_bankrupt_exit_raw_T | 对应标签主体的首次退出财富快照总额，包含负值；两项可能包含同一人，不能相加当总退出财富 |

## step_level状态与本轮交易

`t=0`是初态；`t=1..T`是第t轮结束。该行的n_HH/n_HC/n_CC/surplus_t属于状态t−1→t的交易，H_active/C_active属于转化、退出之后的状态。

| 字段 | 定义 |
|---|---|
| H_active,C_active,N_active | 步末活跃H、C、总人数；原件P_active更名为C_active |
| N_alive | 原件alive标签数量；被驱逐但尚未死亡者可能仍alive，不能代替市场人口 |
| n_edges,n_HH,n_HC,n_CC | 该轮交易数；HC合并原HP与PH，CC对应原PP |
| surplus_t,cumulative_welfare | 本轮及累计净交易剩余；t=0为0 |
| W_all,W_active | 所有主体、活跃主体状态财富总和 |
| W_evict_current | 驱逐标签主体当前w总额；替代含混的W_evict_frozen命名 |
| W_evict_exit_raw,W_bankrupt_exit_raw | 退出时原始财富快照的标签内总额 |
| labelled_exited_total | 原件bankrupt或evict标签并集人数；c>0关闭破产时可能小于真实退出人数 |
| exited_total | (~active).sum()，实际累计退出人数 |
| converted_total,bankrupt_total,evicted_total,both_total | 步末累计数，不是本轮流量；用相邻差分取得本轮新增数 |
| death_total,death_trade_total,death_consumption_total | 原件生存标签统计；“trade”仅指本轮交易过，不能解释为死亡的因果原因 |
| absorbed_padding | 1表示c=0无active吸收状态补齐；状态不变，交易与本轮剩余为0 |

## 可选边事件

`python -m scripts.run_baseline --edges --out data/with_edges`生成`edge_level.csv.gz`。默认正式结果不生成大体积边事件，smoke输出保留事件用于时间核验。事件主键(run_id,t,i,j)，i<j。

事件`t=t_end=t_start+1`，theta_i/theta_j为步初身份（0=H,1=C），type沿用原件HH/HP/PH/PP，delta_w_i/delta_w_j为各端交易收益，不含财富退出记账。用t_start关联步初状态，用t_end关联步末状态；不能将步末状态当作本轮事前预测特征。

## 分析输出与组员接口

`institution_means.csv`：按rho及pooled的制度均值、样本标准差、区组bootstrap标准误/95%区间、事件率。pooled对五个rho等权。

`paired_effects.csv`：E|B=0、E|B=1、B|E=0、B|E=1、E:B配对差异；E:B=[Y11−Y01]−[Y10−Y00]，下标顺序为E,B。`OLS_full.csv`含截距、rho虚拟变量及条件效应；`Table1_baseline.csv/.md`展示四制度均值和主要OLS制度系数。区间为5,000次整seed区组bootstrap，seed=20261107，不使用独立行标准误。

`event_timing.json`只统计已发生事件的时间分位数，并单列删失数量。`ML_label_feasibility.csv`对候选t0、h检查风险集、阳性/阴性及提前崩溃排除数量，不是训练集或预测成果。未来预测必须只用预测时点可见信息，H_active等仿真器隐藏身份统计不能未经说明当平台可观测特征。

- B组：直接使用run_level中的collapse_time、collapse_event、rmst_T；N_alive不是本研究的生存终点。
- C/D组：复用模拟器、配置格式和结果函数；阈值或rho扩展应使用新配置和独立输出目录，不能覆盖基准。
- E组：先用step_level本轮交易与累计转化差分；需要个体链路时重跑可选边事件。完整个体状态历史默认不持久保存，避免不必要数据量。
- F组：使用welfare_T及HH/HC/CC分解；HC本基准净剩余为0，破产者负财富不另行归零。

metadata记录配置、完整seed列表、模型/源文件/输出哈希、环境与时间。合并不同模型版本前先核对这些信息。不要手工修改CSV后继续沿用原metadata，也不要把不同制度同seed视为独立样本。
