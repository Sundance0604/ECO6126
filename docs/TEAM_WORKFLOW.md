# 六人协作：数据、接口与后续步骤

仓库：<https://github.com/Sundance0604/ECO6126>。本文件是后续工作入口；当前A基准已经完成，B–F只提供可执行的数据接口和研究约定，不伪装成已完成的分析。

## 先获取和核验

```bash
git clone git@github.com:Sundance0604/ECO6126.git
cd ECO6126
python -m venv .venv
# Windows: .venv\Scripts\activate；macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
python -B -m unittest discover -s tests -v
python -B -m scripts.validate_outputs --data data/processed
```

正式`run_level.csv`、`step_level.csv`和metadata均随仓库提供，不必先重跑2,000次。完整复现应使用独立目录：

```bash
python -B -m scripts.run_baseline --out data/reproduction --workers 4
python -B -m analysis.A_baseline --data data/reproduction --out outputs/reproduction --report outputs/reproduction/report.md
```

当前基准模型指纹`v1.5-A-raw-4d85097a0e80`。原始Python、PDF、公式图片、冻结配置、seed列表、生成/提取/验证脚本和正式数据一并提交。`.gitattributes`禁止自动转换换行，确保跨系统checkout仍能通过源代码与数据哈希核验。

## 统一程序接口

```python
from src.data_access import (
    load_experiment, select_runs, survival_inputs,
    paired_inputs, step_flows, welfare_components,
)

data = load_experiment("data/processed", with_steps=True)
runs = select_runs(data, rho=[0.10, 0.30], B=1)
survival = survival_inputs(runs)       # duration/event：保留右删失
effects = paired_inputs(runs, "rmst_T", treatment="E")
flows = step_flows(data)              # 累计人数 → 本轮新增人数
components = welfare_components(runs) # HH/HC/CC支付分解，逐行核对总和
```

读取器默认核对已读取CSV的SHA-256、模型版本与主键；完整经济/时序校验使用`validate_outputs`。`paired_inputs`按同seed及所有其他模型参数配对，缺对照或重复行会报错，不自动丢样本。不确定性继续按整个seed区组处理；匹配表本身不是标准误计算器。

事件时间统一：step的t是步末，包含该轮交易；预测时点t只能使用当时及过去信息。边事件t_start→t_end=t_start+1，t=t_end。累计转化人数不是本轮转化流量，使用`converted_step`等差分字段。

## 分工与可执行入口

| 成员 | 起点与提取命令 | 待成员完成的分析 | 交付约定 |
|---|---|---|---|
| A | 已提交正式基准与Table1 | 已完成2×2、配对差异、rho FE OLS | 保持outputs/tables与基准数据冻结 |
| B | `python -m scripts.prepare_member --member B` | KM、RMST差异，Cox作为补充并检查比例风险及离散时间/大量并列事件 | analysis/B_survival.py，outputs/B/figures/Figure1.*，报告 |
| C | 下述阈值plan，完成后`prepare_member --member C --data .../manifest.json` | 阈值虚拟变量/响应图，不预设存在内点最优 | analysis/C_thresholds.py，outputs/C/figures/Figure2.*，阈值表与报告 |
| D | `python -m scripts.prepare_member --member D` | 先复用已有五个rho的制度异质性；扩展rho才需另跑 | analysis/D_heterogeneity.py，outputs/D/figures/Figure3.*，交互表与报告 |
| E | `python -m scripts.prepare_member --member E` | HC交易、H→C转化、HH合作的制度效应；后处理结果不冒称因果中介 | analysis/E_mechanisms.py，outputs/E/tables/Table2.*，报告 |
| F | `python -m scripts.prepare_member --member F` | 固定T福利比较、支付分解和经确认的稳健性设计 | analysis/F_welfare.py，outputs/F/figures、tables及报告 |

默认提取结果放在`outputs/<成员>/inputs`，拒绝覆盖非空目录；用`--out`另定目录。B的duration必须和event一起使用；D若加入rho固定效应，不再重复加入与之共线的rho主效应；E不要用alive代替active；F扰动支付后不能再硬套4HH−2CC，应按支付参数分解。

随仓库还提供`examples/member_inputs`的小样本提取结果及来源metadata，便于对照字段。它们明确为smoke示例，不能替代2,000次正式数据；C示例为q=1、2的接口验证，不是正式阈值结论。

## C/F扩展实验接口

阈值模板仅作示例：固定E=1、B=1，8个q×5rho×100seed=4,000次；B=1是模板条件，不是替全组冻结的新决策，可由C组修改common.B后评审。F模板是8个单因素场景，共16,000次，含基准、N/a/p/T与支付扰动示例。两个模板默认只预览：

```bash
python -m scripts.run_extensions --plan configs/experiments/C_thresholds.json
python -m scripts.run_extensions --plan configs/experiments/F_robustness.json
# 只执行最多两个配置格、前两个rho和前两个seed，用于验证接口：
python -m scripts.run_extensions --plan configs/experiments/C_thresholds.json --smoke --execute --out data/extensions/C_smoke
# 设计确定后，成员自行执行完整阈值设计：
python -m scripts.run_extensions --plan configs/experiments/C_thresholds.json --execute --workers 4 --out data/extensions/C
python -m scripts.prepare_member --member C --data data/extensions/C/manifest.json
```

每格复用相同模拟器、指标与run/step schema，分别保存config、metadata和数据；manifest记录完整集合与各批metadata哈希。`load_experiment(".../manifest.json")`可合并完整集合；不完整、重复run或metadata被改写会拒绝。不要把C的q=3格与A中同一格再拼一次，run_id会相同，不能双计。

扩展仍固定c=0和已批准的原始负财富记账。无转化等新机制不在这个接口偷偷加入，先写模型决策。各成员新依赖应单独记录确切版本，不把未使用的大型包加入共同基础环境。

## Git分支与交付检查

从最新main建立个人分支，例如`codex/B-survival`、`codex/C-thresholds`，提交代码、配置、结果与来源说明后发PR。不要直接编辑正式CSV或覆盖A输出；不能只提交截图或Excel手算结果。B–F完整模块文件名是交付约定，当前尚未编造空分析脚本。

每份报告至少写明：Git提交、model_version、配置/seed及数据metadata哈希、指标定义、删失处理、推断区组、执行命令、实际产物和局限。参数扩展须保持配对seed；对多个结果/阈值的统计比较应说明多重比较口径。不同T的截断时间和累计福利不能未经说明混合比较。

ML另立任务：现有候选t0=2、h=20在本样本20格中18格单类别。先检验早期可观察状态相对配置基准的增量预测价值，再选窗口与算法；按完整seed区组切分，未见配置的外推另评估。本轮未训练模型。
