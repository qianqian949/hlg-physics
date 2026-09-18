# 环境说明

## 依赖

| 库 | 版本要求 | 实际安装版本 | 用途 |
|---|---|---|---|
| streamlit | >=1.40,<2 | 1.50.0 | 网页界面 |
| openai | >=1.0,<4 | 2.48.0 | 调用智谱AI(GLM)的接口（OpenAI兼容格式） |
| httpx | >=0.24,<1 | 0.28.1 | HTTP请求 |
| networkx | >=3.0,<4 | 3.2.1 | 图结构处理 |
| pyvis | >=0.3.2,<1 | 0.3.2 | 网络图可视化 |
| python-dotenv | >=1.0,<2 | 1.2.1 | 读取.env里的API Key |
| PyMuPDF (fitz) | >=1.22,<2 | 1.26.5 | 解析PDF文本 |

完整列表见 [requirements.txt](requirements.txt)。

**Python版本**：README_MAC.md建议3.11/3.12，实际项目用的是venv里的 **3.9.6**，目前跑起来没问题。

## 首次搭建步骤

```bash
cd multi-paper-HLG-generator-mac
chmod +x setup.sh run.sh "Start Mac.command"
./setup.sh          # 创建venv、装依赖、生成.env
```

然后打开 `.env`，填入智谱AI的Key（[开通地址](https://open.bigmodel.cn/usercenter/apikeys)）：

```
ZHIPU_API_KEY=你的密钥
```

## 日常启动

```bash
./run.sh
```

或双击 `Start Mac.command`。浏览器访问 `http://localhost:8650`。

## Git / GitHub 相关

- 用 `gh auth login`（浏览器登录）做身份验证，比手动配置token简单
- `.gitignore` 已经排除 `venv/`、`.env`、`__pycache__/`、`.DS_Store`，密钥不会被提交

## 输入格式

- 界面"Upload Papers"标签，一次上传 **2-5个PDF文件**
- 只接受PDF，不支持txt/word/markdown——如果测试材料是纯文字，需要先转成PDF（我们用Python的PyMuPDF库写了个脚本自动转换，不需要装Word/WPS）

## 输出格式（核心JSON结构）

每篇论文的分析结果（`hlg_data`）大致长这样：

```json
{
  "Nodes": [
    {"node": "概念名", "level": "L1/L2/L3"}
  ],
  "Relations": [
    {
      "source": "概念A",
      "target": "概念B",
      "relation": "关系类型（如causes/solved-by/is-part-of）",
      "confidence": 1-10,
      "explanation": "为什么这么判断"
    }
  ],
  "overall_confidence": 1-10,
  "InferredNodes": [],      // 可选：AI补充的、原文没出现的相关概念
  "InferredRelations": []
}
```

多篇论文之间还会额外生成 `cross_paper` 结果，包含跨论文的关系和综合评分。

真实样例见 [sample_output.md](sample_output.md)（用单摆物理文本的实际输出整理的）。

## 已知问题记录

- 装的streamlit是最新版(1.50.0)，但代码里用了旧API `st.experimental_rerun()`，新版本已删除该方法，改名为 `st.rerun()`。已在 `utils.py` 和 `modes/multi_paper.py` 里修复（4处）。
