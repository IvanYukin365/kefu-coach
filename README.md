# 客服上岗认证 · 合规红队陪练智能体

亚信 1024 黑客松大赛 · 创意赛道 · **赛道 A（AI Agent / 多智能体）** · 行业：中国移动

---

## 一、这是什么

一个给中国移动一线客服（10086 呼入 / 营业厅 / 政企客户经理）用的**上岗前对练与认证系统**：

- **客户扮演智能体** —— 模拟真实投诉客户，情绪可升级，会挖坑、会追问、会要求找领导
- **合规红队智能体** —— 在对话过程中实时扫描客服话术，命中监管红线立即报警
- **裁判智能体** —— 通话结束后按五维标准打分
- **教练智能体** —— 针对违规点给改进建议 + 一段可直接照读的示范话术

核心不是"培训"，而是**上岗闸门**：红线命中即一票否决，通不过就不能上机接用户。

---

## 二、本地运行

先进入项目目录，再装依赖：

```powershell
cd C:\Users\AI\WorkBuddy\2026-09-29-08-54-20\kefu-coach
pip install -r requirements.txt
```

然后启动 —— **三种写法任选，推荐第一种**：

```powershell
# ① 最省事：双击 run.bat（自动探测可用环境，不受任何 venv 影响）
.\run.bat

# ② 指定系统 Python（最稳）
C:\Python312\python.exe -m streamlit run app.py

# ③ 常规写法 —— 但前提是当前 python 里装了 streamlit
python -m streamlit run app.py
```

浏览器会自动打开 `http://localhost:8501`。

> **为什么直接敲 `streamlit run app.py` 会报错？**
> 两个坑，都可能踩到：
> 1. `streamlit.exe` 装在用户级目录 `C:\Users\AI\AppData\Roaming\Python\Python312\Scripts\`，
>    该目录**不在系统 PATH** 上 → 报"无法识别 streamlit"。
> 2. 当前终端激活了别的虚拟环境（如 `ai-infra\.venv`），`python` 指向的是那个环境，
>    里面没装 streamlit → 报 "No module named streamlit"。
>
> **两者都跟你在哪个目录无关。** 用 `run.bat` 或完整路径 `C:\Python312\python.exe`
> 可以绕开全部问题。想在当前 venv 里用，就先装依赖：
> ```powershell
> pip install -r requirements.txt
> ```

> **不需要配 API Key 也能完整演示。** 未配置时自动进入「离线演示模式」：
> 客户回复走内置脚本（6 类画像 × 5 轮高质量话术），评分走确定性规则引擎。
> 现场演示 / 答辩录像时绝不会因为网络或额度问题翻车。

---

## 三、接大模型（可选，效果更好）

侧栏 → 🔌 大模型接入，填三项即可（兼容 OpenAI Chat Completions 协议）：

| 平台 | Base URL 示例 | 模型名 |
|---|---|---|
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| 中国移动 MoMA / 九天 | 按平台给你的网关地址 | 平台模型名 |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| 智谱 GLM | `https://open.bigmodel.cn/api/paas/v4` | `glm-4` |
| 火山方舟 | `https://ark.cn-beijing.volces.com/api/v3` | 你的接入点 ID |

也可以用环境变量：`LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`。

---

## 四、部署到 Streamlit Community Cloud

**完整步骤见 [`部署指南.md`](部署指南.md)**（含 git 命令、Secrets 配置、
验收清单、三个真实会踩的坑，以及 Hugging Face / Docker 两个备选方案）。

最简流程：

1. 本地 git 仓库已初始化并提交好，只需加远端推上去：

   ```powershell
   git remote add origin https://github.com/<你的用户名>/kefu-coach.git
   git branch -M main
   git push -u origin main
   ```

2. 打开 [share.streamlit.io](https://share.streamlit.io) → New app
3. **Main file path 填 `app.py`**（不是 `kefu-coach/app.py`），Branch 填 `main`
4. Deploy，等 1–2 分钟拿到公网链接 —— 这就是说明书里要填的 **Demo 访问链接**

**想用大模型又不想把 Key 写进代码**：App 设置 → Secrets 里填

```toml
LLM_API_KEY = "sk-xxxxxx"
LLM_BASE_URL = "https://api.deepseek.com/v1"
LLM_MODEL = "deepseek-chat"
```

Secrets 不进代码库。注意云端容器重启会丢本地改动，**在 ④ 配置页改完红线记得
「导出 JSON」→ 覆盖 `core/redlines.json` → `git push`**。

---

## 五、目录结构

```
kefu-coach/
├── app.py                 Streamlit 主程序（对练台 / 评分报告 / 规则库 / 红线配置）
├── requirements.txt
├── .streamlit/config.toml 主题配色
├── redlines.json          规则配置导出件（云端部署时用它做版本管理）
├── 红线规则说明.md         规则是怎么定的、怎么改、有哪些坑
├── 对话测试场景集.md        6 场景 × 10 轮自测台词
└── core/
    ├── redlines.json      ← 规则库本体，可在应用「④ 红线规则配置」页编辑
    ├── rules_config.py    规则配置的读写 / 编译（关键词 ↔ 正则）
    ├── personas.py        客户画像库 ← 真数据来源，上线前须替换为真实工单
    ├── rules.py           规则匹配引擎（从 redlines.json 加载，不硬编码）
    ├── agents.py          四智能体 Prompt（客户 / 红队 / 裁判 / 教练）
    ├── scoring.py         五维评分引擎 + 认证闸门判定
    └── llm.py             大模型接入层（OpenAI 兼容，失败自动降级）
```

---

## 六、改红线规则（不用改代码）

应用左侧导航切到「**④ 红线规则配置**」即可可视化编辑：

- **关键词模式**：一行一个词，业务人员就能维护，系统自动转义
- **正则模式**：用于「确定性承诺 + 具体金额」这类必须靠结构识别的规则
- **试一试**：输入一句话立刻看命中哪些规则，改完先验证再保存
- **保存并生效**：写入 `core/redlines.json`，立即作用于评分，无需重启
- **导入 / 导出 JSON**：跨环境迁移配置

详细设计逻辑与避坑指南见 [红线规则说明.md](红线规则说明.md)。

> ⚠️ **Streamlit Cloud 部署注意**：云端文件系统不持久，容器重启会丢失页面上的改动。
> 在页面上改完请**导出 JSON → 提交回 GitHub**，或直接在本地改完再推送。

---

## 七、答辩前必做（重要）

`core/personas.py` 里的 6 类画像目前是**场景原型**，虽然高度贴近真实工单，但评审问到"数据哪来的"必须有据可依。建议赛前找业务同事要：

- 每类场景 **20–30 条**脱敏通话转写（或投诉工单摘要）
- 替换 `brief` / `hidden_truth` / `scripted` 三段
- 在说明书中标注：**样本量、时间窗、来源系统**（如"某省 10086，2026 年 7 月，计费争议类工单 TOP 场景"）

同理，红线规则建议替换为**省公司现行质检标准版本**：在「④ 红线规则配置」页替换词表，并在页面的「规则来源声明」里写明标准编号与生效日期（该字段会随配置保存，供评审追溯）。

这两件事做完，"真数据"这一栏就从"像真的"变成"就是真的"。
