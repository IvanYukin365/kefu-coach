# -*- coding: utf-8 -*-
"""
服务规范 / 监管红线规则库（合规红队引擎）
====================================================================
规则来源声明：
  规则内容不在此文件硬编码，统一由 core/redlines.json 提供，
  可在应用「④ 红线规则配置」页面直接编辑，无需改动代码。
  默认规则对齐运营商客服通用服务规范与监管要求（资费解释口径、
  携号转网服务规范、增值业务订购确认、申诉渠道告知等）。
  各省公司口径存在差异，正式落地时需替换为省公司现行质检标准版本。
====================================================================
"""

import re

from . import rules_config

_CFG = rules_config.load()

RED_LINES = rules_config.active(_CFG.get("red_lines", []))
YELLOW_LINES = [dict(r, pattern=rules_config.pattern_of(r))
                for r in _CFG.get("yellow_lines", []) if r.get("enabled", True)]
MUST_DO = [(m["name"], rules_config.pattern_of(m))
           for m in _CFG.get("must_do", [])]
ACCURACY_KEYS = _CFG.get("accuracy_keys", {})


def reload():
    """配置页保存后调用：重新加载规则，立即生效（无需重启）"""
    global _CFG, RED_LINES, YELLOW_LINES, MUST_DO, ACCURACY_KEYS
    _CFG = rules_config.load()
    RED_LINES = rules_config.active(_CFG.get("red_lines", []))
    YELLOW_LINES = [dict(r, pattern=rules_config.pattern_of(r))
                    for r in _CFG.get("yellow_lines", []) if r.get("enabled", True)]
    MUST_DO = [(m["name"], rules_config.pattern_of(m))
               for m in _CFG.get("must_do", [])]
    ACCURACY_KEYS = _CFG.get("accuracy_keys", {})

# ── 中文数字归一化 ────────────────────────────────────────────────
# 坐席真打字时可能写「我给您退四十」，归一化后再匹配，避免漏检。
# 只用于规则匹配，不改动任何展示文本。
_CN_DIGITS = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
              "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_CN_UNITS = {"十": 10, "百": 100, "千": 1000, "万": 10000}
_CN_NUM_RE = re.compile(r"[零一二两三四五六七八九十百千万]{1,8}")


def _cn_to_int(s: str) -> int:
    total, section, number = 0, 0, 0
    for ch in s:
        if ch in _CN_DIGITS:
            number = _CN_DIGITS[ch]
        elif ch in _CN_UNITS:
            unit = _CN_UNITS[ch]
            if unit == 10000:
                total += (section + (number or 1)) * unit
                section, number = 0, 0
            else:
                section += (number or 1) * unit
                number = 0
    return total + section + number


def normalize_numbers(text: str) -> str:
    """中文数字 → 阿拉伯数字（如「三百」→「300」），便于规则匹配。"""

    def repl(m):
        s = m.group()
        # 单个数字字（如「一下」「一定」「第一」里的「一」）不转，避免误伤
        if len(s) == 1 and s not in _CN_UNITS:
            return s
        val = _cn_to_int(s)
        return str(val) if val else s

    return _CN_NUM_RE.sub(repl, text)


def hit(pattern: str, text: str) -> bool:
    return re.search(pattern, text) is not None


def scan_message(text: str):
    """对单条客服话术做实时红线扫描"""
    norm = normalize_numbers(text)
    flags = []
    for r in RED_LINES:
        if hit(r["pattern"], norm):
            flags.append({"level": "red", "rule": r})
    for r in YELLOW_LINES:
        if r.get("scope") == "conversation":
            continue
        if r.get("reverse"):
            continue
        if hit(r["pattern"], norm):
            flags.append({"level": "yellow", "rule": r})
    return flags


def scan_conversation(all_cs_text: str, persona_id: str):
    """对整通对话做黄线与必备动作扫描"""
    norm = normalize_numbers(all_cs_text)
    yellows, missing = [], []
    for r in YELLOW_LINES:
        # 场景适用性：部分告知义务只属于特定业务（如合约期只对营销/套餐变更场景成立），
        # 若不做范围限定，故障报修、账单争议等场景会被误判「未说明合约期」而扣分。
        scope_pids = r.get("personas")
        if scope_pids and persona_id not in scope_pids:
            continue
        if r.get("reverse") and not hit(r["pattern"], norm):
            yellows.append(r)
        elif (not r.get("reverse")) and hit(r["pattern"], norm):
            yellows.append(r)
    for name, pat in MUST_DO:
        if not hit(pat, norm):
            missing.append(name)
    keys = ACCURACY_KEYS.get(persona_id, [])
    covered = [k for k in keys if k in all_cs_text]
    return yellows, missing, covered, keys
