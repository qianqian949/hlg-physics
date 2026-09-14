# Day 3 人工核查记录（单摆 + 抛体运动，paper1.pdf）

## 正确的关系
- [1] Nonlinear pendulum dynamics → reduced-to → Small angle approximation (9/10) ✅
- [2] Small angle approximation → enables → Simple harmonic motion (10/10) ✅
- [7] Large angle isochronism failure → related-to → Nonlinear pendulum dynamics (9/10) ✅
- [8] Large angle isochronism failure → conflicts → Small angle approximation (8/10) ✅ 成功捕捉到"失效条件"
- [9] Air resistance effects → conflicts → Ideal projectile model (9/10) ✅
- [14][15] Constant/Free fall motion → implements → Ideal projectile model (9/10) ✅

## 发现的错误

### 错误1：因果方向反了
- 关系：`[10] High-speed trajectory deviation → causes → Air resistance effects` (9/10)
- 问题：AI自己写的explanation说的是"速度快→空气阻力变得不可忽略→轨迹偏离"，
  正确方向应该是 空气阻力 causes 轨迹偏离，relation标注的方向和它自己的explanation矛盾
- 结论：confidence高不代表逻辑方向对

### 错误2：is-part-of 方向反了
- 关系：`[12] Motion decomposition → is-part-of → Constant velocity motion` (10/10)
- 关系：`[13] Motion decomposition → is-part-of → Free fall motion` (10/10)
- 问题：按relation定义is-part-of应该是"小部件属于大系统"，
  正确应为 Constant velocity motion → is-part-of → Motion decomposition（分解是大概念，匀速运动是其中一部分）
- 结论：两条方向都反了，且都是满分/接近满分

## 发现的遗漏（Recall miss）
- 原文："物体速度很快**或者形状不规则**（比如羽毛球、乒乓球）"
- AI只提取了"速度快"这一个诱因，"形状不规则"完全没有被提取为节点或关系

## 冗余现象（非错误，但值得记录）
- [3]/[4]、[5]/[6] 都是同一对概念的正反两个方向关系（xx solved-by yy / yy implements xx），
  内容重复，只是换了个方向表达 —— 不算错，但会让关系列表看起来比实际信息量更"膨胀"

## 结论（喂给Week3改造）
1. 高confidence不等于关系方向正确——需要额外检查relation方向逻辑，不能只看分数
2. 原文里的"并列原因"（如"速度快或形状不规则"）容易被AI只抓一个，漏掉另一个
3. 当前L1/L2/L3分类是为CS论文设计的，套到物理文本上，"假设条件"（如摆角<5度）、
   "失效条件"这类物理特有的概念被迫塞进L2/L3，命名也比较别扭（比如"Harmonic period formula"
   这种AI自己编的技术名词，原文其实没有直接提到"公式"这个词）
