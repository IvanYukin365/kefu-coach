# -*- coding: utf-8 -*-
"""多智能体：客户扮演 Agent / 合规红队 Agent / 裁判 Agent / 教练 Agent"""

from . import llm

# ────────────────────────────────────────────────────────────────
# Agent 1：客户扮演智能体
# ────────────────────────────────────────────────────────────────
CUSTOMER_SYSTEM = """你是中国移动客服上岗认证系统中的「客户扮演智能体」，负责与受训坐席进行真实感对练。

# 你的角色
{user}

# 场景背景（对你可见，对客服隐藏）
{brief}

# 只有你才知道的真相
{hidden_truth}
重要：绝不能主动说出这段真相，只能等客服查询核实后，你才逐步承认。

# 情绪与强度
当前情绪：{emotion}；难度等级：{level}（1=温和，3=激烈，会要求找领导、索要赔偿）

# 本次场景的合规陷阱（你要在这些点上施压，但不要明说）
{traps}

# 硬性规则
1. 只输出客户的**一句口语化中文**，像真人打电话，1-3 句，不超过 60 字。
2. 绝不自曝 AI 身份，绝不替客服解决问题，绝不提供客服话术。
3. 情绪随轮次推进：客服专业 → 逐步缓和并给正向反馈；客服推诿 → 情绪升级。
4. 客服问到关键信息时，你要给出可被查询的具体信息（如号码后四位、订购时间）。
5. 轮次达到 {max_turns} 轮左右才收尾：问题已解决 → 自然收尾并表示认可；未解决 → 表达不满并要求升级。
   在此之前不要提前结束对话，每一轮都要提出新的追问或新的质疑点，保持对话推进。
6. 只输出客户说的话，不要任何旁白、括号说明或格式标记。"""

CUSTOMER_FEWSHOT = [
    {"role": "user", "content": "您好，很高兴为您服务，请问有什么可以帮您？"},
    {"role": "assistant", "content": "（示例）"},
]


def customer_reply(persona, level, history, max_turns=10):
    """返回 (文本, 是否来自大模型)"""
    if llm.online():
        sys = CUSTOMER_SYSTEM.format(
            user=persona["user"], brief=persona["brief"],
            hidden_truth=persona["hidden_truth"], emotion=persona["emotion"],
            level=level, traps="；".join(persona["traps"]), max_turns=max_turns,
        )
        msgs = [{"role": "system", "content": sys}]
        for h in history:
            msgs.append({"role": "user" if h["role"] == "cs" else "assistant",
                         "content": h["content"]})
        out = llm.chat(msgs, temperature=0.85, max_tokens=200)
        if out:
            return out, True

    # 离线演示模式：脚本化回复
    seq = persona["scripted"]
    idx = sum(1 for h in history if h["role"] == "customer")
    if idx < len(seq):
        return seq[idx], False
    # 脚本用完后的通用追问池（保证 15 轮上限内离线模式也不会原地重复）
    tail = ["还有一件事我得问清楚，这个处理到底要几个工作日？",
            "那我怎么知道你们有没有真的在处理？会不会又拖着？",
            "行，那你把工单号再跟我说一遍，我记一下。",
            "要是到时候没办好，我找谁？还是打这个电话吗？",
            "你说的这些，能不能发条短信给我？我怕后面忘了。",
            "我还有一个问题，这个会不会影响我下个月的费用？",
            "你说得倒好听，上次也是这么说的，结果呢？",
            "好吧，那我再信你们一次，希望这次能真的解决。",
            "那我等你消息，要是再出问题我还会再打过来的。",
            "行，我了解了，谢谢。"]
    return tail[min(idx - len(seq), len(tail) - 1)], False


# ────────────────────────────────────────────────────────────────
# Agent 2：合规红队智能体（实时监督，不参与对话）
# ────────────────────────────────────────────────────────────────
REDLINE_SYSTEM = """你是「合规红队智能体」。你的职责不是参与对话，而是实时监督客服话术是否触碰监管红线与服务禁语。
对每句客服话术，只输出 JSON：{"level":"red|yellow|none","rule":"规则名","reason":"20字内说明"}
判定标准：推诿甩锅、越权承诺退费赔付、携号转网阻挠误导、否定对抗用户、隐瞒申诉渠道、营销夸大资费误导 —— 均为 red。"""


# ────────────────────────────────────────────────────────────────
# Agent 3：裁判智能体
# ────────────────────────────────────────────────────────────────
JUDGE_SYSTEM = """你是「服务合规裁判智能体」。依据运营商客服服务规范与监管要求，对整通对话中【客服】的表现评分。
只输出 JSON，不要任何解释文字：
{"规范合规":0-100,"业务准确":0-100,"服务流程":0-100,"沟通技巧":0-100,"问题解决":0-100,
 "红线":[{"轮次":1,"问题":"...","违反":"..."}],"总评":"60字内"}
评分口径：规范合规考察红线与禁语；业务准确考察资费与规则解释是否正确；服务流程考察身份核验/共情/复述/时限/收尾；
沟通技巧考察情绪应对与表达；问题解决考察是否给出可执行方案。"""


def judge(transcript, persona):
    if not llm.online():
        return None
    msgs = [
        {"role": "system", "content": JUDGE_SYSTEM},
        {"role": "user", "content": f"场景：{persona['name']}（{persona['brief']}）\n\n对话记录：\n{transcript}\n\n请评分。"},
    ]
    return llm.chat(msgs, temperature=0.2, max_tokens=500)


# ────────────────────────────────────────────────────────────────
# Agent 4：教练智能体
# ────────────────────────────────────────────────────────────────
COACH_SYSTEM = """你是「教练智能体」，面向中国移动一线客服做话术辅导。
基于评分结果与违规点，输出：
1) 三条改进建议（每条：问题 → 原因 → 怎么改）
2) 一段可直接照读的示范话术（针对本场景，80-150 字，口语化）
3) 一句鼓励
用中文，结构清晰，不要空话套话。"""


def coach(transcript, persona, result):
    if not llm.online():
        return None
    brief = f"场景：{persona['name']}；得分：{result['total']}；" \
            f"红线：{[r['rule']['name'] for r in result['red_hits']] or '无'}；" \
            f"流程缺失：{result['missing'] or '无'}"
    msgs = [
        {"role": "system", "content": COACH_SYSTEM},
        {"role": "user", "content": f"{brief}\n\n对话记录：\n{transcript}\n\n请给出辅导。"},
    ]
    return llm.chat(msgs, temperature=0.6, max_tokens=600)
