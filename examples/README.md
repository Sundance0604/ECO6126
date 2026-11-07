# 接口提取示例（smoke数据，不是正式B–F分析）

`member_inputs/B,D,E,F`来自`data/smoke`的24次运行；`member_inputs/C`来自`data/extensions/C_smoke/manifest.json`的8次阈值接口验证。各目录的inputs_metadata.json记录来源、文件哈希及行数。

重新提取到新目录：

```bash
python -m scripts.prepare_member --member B --data data/smoke --out outputs/example_B_new
python -m scripts.prepare_member --member E --data data/smoke --out outputs/example_E_new
```

正式研究直接读取随仓库提交的`data/processed`，或省略`--data`使用默认正式数据。完整步骤见`docs/TEAM_WORKFLOW.md`。提取输出不包含拟合模型、因果结论或显著性结果。
