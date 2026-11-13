# Member D：市场异质性与机器学习

本节研究：开启破产机制（B=1）且驱逐阈值 q=3 时，开启公共驱逐机制能延长多少市场存续时间，以及这一效应如何随初始欺诈者比例 ρ 和诚实交易者转化阈值 p 变化。

采用任务 A 的提交 `d30d156a1343a8261e83ff000e9fb13fe050445d`（模型 `v1.5-A-raw-4d85097a0e80`）的原始模拟器、记录适配层和基准配置。共同设定为 N=100、a=3、初始财富 10、自然消耗 c=0、观察期 200 步和 A 的交易收益。D 数据中的 `surv` 与 A 的 `rmst_T` 对应：活跃诚实交易者人数首次降至初始值的 10% 或以下的步数；观察期内未触及阈值则按 200 计，不能解释为该步崩溃。

D 扩展了 ρ（0.05–0.40，间隔 0.01）和 p（2、3、4），对每个配置和种子分别模拟开启及关闭驱逐，共 17,280 次。同一个种子下两次运行的存续时间之差是效应估计的基础。训练、验证和测试分别使用种子 1–48、49–64、65–80；另留出七档 ρ，比较模型对未见配置的预测。误差的 bootstrap 按测试种子重采样，固定训练好的模型，不反映训练不确定性。临界区域是估计效应越过预设步数的区间；特征重要性衡量置换特征后预测误差的变化。

- [Figure 3](figures/Figure3.pdf) 和 [Table 3](tables/Table3.csv) 分别展示估计效应和样本外模型比较。
- [论文正文 Word](report/Market_Heterogeneity.docx) · [PDF](report/Market_Heterogeneity.pdf)
- [设计与划分](design.json) · [来源、软件版本和 SHA-256](reproducibility.json)
- [D 扩展数据](../../data/extensions/D/ml_dense_rho_p.csv) 是模型输入；[A 对照数据](../../data/extensions/D/task_a_reference.csv) 只用于核验 800 条重叠运行。A 原始数据及基准产物保持不变。

从仓库根目录运行（建议 Python 3.12）：

```bash
python -m pip install -r analysis/requirements-D.txt
python -B -m analysis.D_verify
python -B -m analysis.D_heterogeneity --analyze
```

最后一条根据已提交的 D 数据重建分析结果。若要重跑模拟，改用 `python -B -m analysis.D_heterogeneity --force --workers 8`，会更新 D 的数据及分析产物。模拟在首次崩溃或受限存续时间已可确定时停止。
