# 原始输出样例（paper1.pdf：单摆 + 抛体运动）

这是 Day3 实际测试跑出来的真实输出内容（关系部分是从工具界面原样复制的，未做修改）。
之所以没有直接导出JSON重新贴一份，是为了不再重新调用一次AI浪费API额度——这份就是
第一次运行的真实结果。

## 涉及的概念节点（Nodes）

| 概念 | Level |
|---|---|
| Nonlinear pendulum dynamics | L3 |
| Large angle isochronism failure | L3 |
| Air resistance effects | L3 |
| High-speed trajectory deviation | L3 |
| Small angle approximation | L2 |
| Simple harmonic motion | L2 |
| Ideal projectile model | L2 |
| Motion decomposition | L2 |
| Harmonic period formula | L1 |
| Equation linearization | L1 |
| Constant velocity motion | L1 |
| Free fall motion | L1 |

## 关系（Relations，节选，共16条）

```
[1] L3 Nonlinear pendulum dynamics → reduced-to → L2 Small angle approximation  (9/10)
[2] L2 Small angle approximation → enables → L2 Simple harmonic motion          (10/10)
[7] L3 Large angle isochronism failure → related-to → L3 Nonlinear pendulum dynamics (9/10)
[8] L3 Large angle isochronism failure → conflicts → L2 Small angle approximation (8/10)
[10] L3 High-speed trajectory deviation → causes → L3 Air resistance effects    (9/10)  ⚠️ 方向错误，见day3_manual_review.md
[12] L2 Motion decomposition → is-part-of → L1 Constant velocity motion         (10/10) ⚠️ 关系类型选错，见day3_manual_review.md
```

完整16条关系列表 + 逐条explanation，见对话记录 / [day3_manual_review.md](day3_manual_review.md) 的核查结果。

## 结构对照

跟 [environment.md](environment.md) 里描述的JSON结构基本一致，实际字段是
`source` / `target` / `relation` / `confidence` / `explanation`，节点带 `level` 字段。
