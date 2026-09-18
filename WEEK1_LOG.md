# 第1周日志：注册GitHub并熟悉原始HLG工具

## Day1（09-12）GitHub账号 + 公开仓库
- 注册GitHub，完善Bio（"High school student exploring code & AI"，特意写得宽泛，不绑死在物理方向上，因为以后不一定继续走物理）
- 建立个人README仓库
- 建立项目公开仓库 `hlg-physics`
- 装了 `gh` CLI，用浏览器登录做git身份验证（比手动配token简单）
- 学会 `git init / add / commit / push`，独立做完一次commit+push练习
- 概念：搞清楚了 clone（远程→本地）和 commit+push（本地→远程）是相反方向的两件事；
  commit只在本地生效，push之后GitHub上才会真的更新

## Day2（09-14）验证环境
- 发现Python环境、依赖、API Key其实早就装好了，不用重新搭建
- 实际跑通工具时报错：`st.experimental_rerun()` 在新版streamlit(1.50.0)里已经删除，
  改名叫 `st.rerun()` —— 学到一课：**库升级后旧API失效是常见坑**，看报错最后一行的
  函数/属性名，去查是不是改名了
- 修复4处调用，commit + push

## Day3（09-14）首次真实测试 + 人工核查
- 写了8段物理解释文本（单摆、抛体、牛顿第二定律等），每段刻意包含假设条件、机制、
  结论、失效条件，转成PDF（工具只接受PDF，一次2-5个文件）
- 学到一课：数学/物理文本天然不贴合这个工具原本的L1/L2/L3分类（研究问题/数学建模/
  技术方案是CS论文的叙事结构），这正是Week3要改造工具的原因
- 人工核查单摆+抛体运动那篇的16条关系，发现：
  - 2处真错误：一处因果方向反了（AI自己的explanation都跟relation矛盾），
    一处不只是方向错、而是**关系类型本身选错**（"方法→产生的结果"被硬套成
    "整体-部件"关系is-part-of）——这两条错误都拿了9-10/10的满分confidence
  - 1处遗漏：原文"速度快**或形状不规则**"两个并列原因，AI只抓了一个
  - 核心结论：**confidence高只代表"这是原文里的内容"，不代表关系的方向/类型判断对了**
- 画了HLG工作流程图（对照真实代码逻辑：PDF提取→AI提取节点→AI找关系→可选推理→
  跨论文分析→可视化）

## Day4（09-18）整理与验收
- 补齐 README.md、environment.md、sample_output.md、本日志
- 对照第1周验收标准自查（见下）

## 第1周验收自查

| 要求 | 完成情况 |
|---|---|
| 建立公开仓库 | ✅ `hlg-physics` |
| README.md初稿 | ✅ |
| environment.md | ✅ |
| 原始输出样例 | ✅ sample_output.md |
| 第1周日志 | ✅ 本文件 |
| 能独立完成clone/运行/修改/commit/push | ✅ Day1自己独立完成一次commit+push；概念都能解释 |
| 能口头解释HLG工作流程 | ✅ 见hlg_workflow.md + 对话中的复述 |

第1周完成。下一步：Day6开始第2周——确定两个核心物理模型和一个可选模型，写清楚项目的问题定位。
