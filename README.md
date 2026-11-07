# ECO6126 封闭市场制度实验

六人协作入口：[分工、数据提取和扩展实验步骤](docs/TEAM_WORKFLOW.md)。正式数据与生成/提取代码均在本仓库，可直接使用，也可独立重跑。

研究声誉驱逐对**诚实交易基础崩溃时间**与**固定观察期累计交易净剩余**的影响。原v1.5 Python、两张公式图和计划书均保留；不修改配对、支付、转化或退出规则。

## 决策与范围

基准N=100，rho=0.05/0.10/0.20/0.30/0.40，a=p=q=3，w_init=10，c=0，T=200。驱逐E、破产B各0/1，每格seed=0..99，共2,000次。2026-11-07负责人选择财富方案A：状态财富与首次退出记录均保留负值，不归零。计划书与公式修订文字见[审计记录](docs/MODEL_AUDIT.md)。

不预设最优惩罚阈值。关闭转化、参数稳健性、Cox、其他成员完整模块、ML训练均不在首轮。候选预测窗口只做事件/标签可行性检查。

## 从零运行

使用Python 3.12；本轮实际环境的精确版本记录在data/processed/metadata.json。只需NumPy、pandas；测试使用标准库unittest，不需安装pytest、statsmodels或大型框架。

在本目录执行：

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -B -m unittest discover -s tests -v
.venv\Scripts\python -B -m scripts.run_baseline --smoke --edges
.venv\Scripts\python -B -m analysis.A_baseline --data data/smoke --out outputs/smoke
.venv\Scripts\python -B -m scripts.run_baseline --workers 4
.venv\Scripts\python -B -m analysis.A_baseline
```

使用已有Python环境时可直接以`python`替代`.venv\Scripts\python`。`--workers 4`仅并行不同运行，序列内仍使用原算法；默认1进程。串行与并行输出一致的测试已包含。原始运行器不以诚实基础崩溃为停止条件，福利继续累计到T。

默认禁止覆盖已有run_level.csv；重新运行时使用独立目录，例如：

```powershell
python -B -m scripts.run_baseline --out data/reproduction --workers 4
python -B -m analysis.A_baseline --data data/reproduction --out outputs/reproduction --report outputs/reproduction/report.md
```

只有明确要替换同目录结果时才添加`--overwrite`。`--config configs/baseline.json`可显式指定配置。首轮运行使用该配置文件，无个人绝对路径。

## 交付位置

| 文件 | 用途 |
|---|---|
| docs/MODEL_AUDIT.md | 原件对照、决策、冲突和最小输出修正 |
| docs/RESEARCH_PROTOCOL.md | 运行前固定的设计、指标与推断方法 |
| docs/DATA_DICTIONARY.md | 每个字段、时间约定与B–F组复用接口 |
| docs/A_BASELINE_REPORT.md | 正式实验结果与局限 |
| docs/VALIDATION_LOG.md | 实际执行命令、测试、失败修复与验收记录 |
| src/market.py | 继承原件的轻量记录适配层 |
| src/metrics.py | 唯一的崩溃、截断时间与福利定义 |
| scripts/run_baseline.py | smoke/正式实验与来源追踪 |
| scripts/validate_outputs.py | 实验网格、哈希、时序、财富及聚合核验 |
| analysis/A_baseline.py | 均值、配对效应、rho固定效应OLS与区组bootstrap |
| data/processed/run_level.csv | 2,000条运行结果 |
| data/processed/step_level.csv | 402,000条初态与步末记录 |
| data/processed/metadata.json | 模型版本、配置、种子、环境和哈希 |
| data/processed/validation.json | 正式数据完整性校验 |
| outputs/tables/Table1_baseline.md | 可直接阅读的Table 1 |
| outputs/tables/Table1_baseline.csv | 可复用的表格数值 |

不确定性按整个seed区组重采样（携带全部rho与四制度），不是按2,000行独立抽样。OLS包含rho虚拟变量、E、B及交互；E系数是B=0时效应，E+交互是B=1时效应。rmst_T均值是限制平均存续时间；右删失的T不能解释为实际崩溃时间。福利不是W_active。

## GitHub协作

本目录是独立仓库，远程为`git@github.com:Sundance0604/ECO6126.git`。提交内容包括原始参考材料、代码、配置、审计/变量说明、正式run/step数据、metadata、表格及小样本提取示例。完整边事件gzip为可选大文件，默认gitignore，可用`--edges`重建；小体积smoke边事件作为校验示例随仓库保留。不要提交.venv与缓存。

共同模拟器或指标有实质改动时先写决策记录并生成新模型版本；各组员用自己的配置/输出目录，不能覆盖本轮基准。本仓库与本机父课程仓库独立，不包含其他课程文件或其Git历史。上游原有LICENSE保留。

## 组员数据接口

```bash
python -m scripts.prepare_member --member B
python -m scripts.prepare_member --member D
python -m scripts.prepare_member --member E
python -m scripts.prepare_member --member F
python -m scripts.run_extensions --plan configs/experiments/C_thresholds.json
```

`prepare_member`提取正式数据，输出到成员自己的`outputs/<成员>/inputs`并记录来源哈希。最后一条仅预览阈值配置，完整执行需显式`--execute`。C/F扩展模板及smoke验证不等于其他成员的完整分析。通用Python API见`src/data_access.py`；完整操作步骤见协作文档。
