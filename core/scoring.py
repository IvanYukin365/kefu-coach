# -*- coding: utf-8 -*-
"""评分引擎：确定性评分（离线可用）+ 可选大模型语义增强"""

from . import rules

WEIGHTS = {
    "规范合规": 30,
    "业务准确": 25,
    "服务流程": 20,
    "沟通技巧": 15,
    "问题解决": 10,
}


def score(messages, persona, position_cfg):
    """
    messages: [{"role": "cs"|"customer", "content": str}]
    返回 dict: dims / total / red_hits / yellows / missing / gate / suggestions
    """
    cs_msgs = [m for m in messages if m["role"] == "cs"]
    cs_text = "\n".join(m["content"] for m in cs_msgs)
    n = max(len(cs_msgs), 1)

    # 1) 规范合规（红线一票否决制）
    red_hits = []
    for m in cs_msgs:
        for f in rules.scan_message(m["content"]):
            if f["level"] == "red":
                red_hits.append({"turn": m.get("turn"), "text": m["content"], "rule": f["rule"]})
    yellows, missing, covered, keys = rules.scan_conversation(cs_text, persona["id"])

    if red_hits:
        compliance = 0.0
    else:
        compliance = 100.0 - len(yellows) * 12.0
        compliance = max(compliance, 40.0)

    # 2) 业务准确
    if keys:
        accuracy = 55.0 + 45.0 * (len(covered) / len(keys))
    else:
        accuracy = 75.0
    if red_hits:
        accuracy -= 15.0
    accuracy = max(0.0, min(100.0, accuracy))

    # 3) 服务流程
    process = 100.0 - len(missing) * 20.0
    process = max(0.0, process)

    # 4) 沟通技巧
    avg_len = sum(len(m["content"]) for m in cs_msgs) / n
    skill = 70.0
    if avg_len < 12:
        skill -= 15          # 答复过短、敷衍
    elif 20 <= avg_len <= 120:
        skill += 15          # 表达充分且不啰嗦
    else:
        skill -= 5           # 过长，通话效率低
    if any(r["rule"]["id"] == "RL04" for r in red_hits):
        skill -= 30
    if n >= 3:
        skill += 10
    skill = max(0.0, min(100.0, skill))

    # 5) 问题解决
    resolution = 50.0 + len(covered) * 8.0
    if len(missing) == 0:
        resolution += 20
    resolution = max(0.0, min(100.0, resolution))

    dims = {
        "规范合规": round(compliance, 1),
        "业务准确": round(accuracy, 1),
        "服务流程": round(process, 1),
        "沟通技巧": round(skill, 1),
        "问题解决": round(resolution, 1),
    }
    total = round(sum(dims[k] * w for k, w in WEIGHTS.items()) / 100.0, 1)

    gate_total, gate_comp = position_cfg["gate_total"], position_cfg["gate_compliance"]
    passed = (not red_hits) and total >= gate_total and dims["规范合规"] >= gate_comp

    return {
        "dims": dims,
        "total": total,
        "red_hits": red_hits,
        "yellows": yellows,
        "missing": missing,
        "covered": covered,
        "keys": keys,
        "gate": {"total": gate_total, "compliance": gate_comp},
        "passed": passed,
        "turns": len(cs_msgs),
    }


def build_suggestions(result, persona):
    """教练智能体的确定性输出（离线可用）"""
    tips = []

    for rh in result["red_hits"][:3]:
        tips.append({
            "type": "红线整改",
            "level": "red",
            "title": f"【{rh['rule']['name']}】第 {rh['turn']} 轮：{rh['text'][:40]}",
            "why": rh["rule"]["why"],
            "fix": rh["rule"]["fix"],
        })

    for y in result["yellows"][:4]:
        tips.append({
            "type": "规范补齐",
            "level": "yellow",
            "title": f"【{y['name']}】{y['why']}",
            "why": "本通对话未覆盖该要点。",
            "fix": y["fix"],
        })

    for m in result["missing"][:5]:
        tips.append({
            "type": "流程缺失",
            "level": "yellow",
            "title": f"缺少关键动作：{m}",
            "why": "服务流程完整性扣分。",
            "fix": f"在相应环节补上「{m}」的标准话术。",
        })

    missing_keys = [k for k in result["keys"] if k not in result["covered"]]
    if missing_keys:
        tips.append({
            "type": "业务要点",
            "level": "yellow",
            "title": "未讲清的业务关键点：" + "、".join(missing_keys),
            "why": f"该场景（{persona['name']}）要求客服主动讲清以上要点。",
            "fix": "把这些要点组织成一句完整解释，避免用户二次来电追问。",
        })

    if not tips:
        tips.append({
            "type": "通过",
            "level": "green",
            "title": "本通对话未检出红线与流程缺失",
            "why": "话术达到上岗认证标准。",
            "fix": "建议进入更高难度场景（情绪升级 / 多诉求并发）继续演练。",
        })
    return tips
