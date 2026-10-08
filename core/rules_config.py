# -*- coding: utf-8 -*-
"""
红线 / 黄线规则的可配置化存储
====================================================================
设计目的：
  规则不再硬编码在代码里，而是落在 core/redlines.json 上。
  各省公司服务规范口径不同，落地时只需替换这份 JSON（或在
  「④ 红线规则配置」页面上直接改），无需改动任何 Python 代码。

两种匹配模式（照顾非技术使用者）：
  keyword —— 写关键词，一行一个，系统自动转义并拼成「或」关系
  regex   —— 直接写正则表达式，用于「确定性承诺 + 具体金额」这类
             必须靠结构识别的规则（如 RL02 越权承诺）
====================================================================
"""

import json
import re
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "redlines.json"

# ── 内置默认规则（首次运行会落盘成 redlines.json）─────────────────
DEFAULT_RULES = {
    "version": "1.0",
    "source_note": (
        "以下规则对齐运营商客服通用服务规范与监管要求（资费解释口径、携号转网服务规范、"
        "增值业务订购确认、申诉渠道告知等）。各省公司口径存在差异，正式落地时需替换为"
        "省公司现行质检标准版本，并在此处标注标准编号与生效日期。"
    ),
    "red_lines": [
        {
            "id": "RL01", "name": "推诿 / 甩锅", "mode": "keyword",
            "words": ["系统自动", "系统就是这么", "改不了", "退不了", "办不了", "处理不了",
                      "没办法", "规定就是这样", "我管不了", "不归我管", "不归我们管",
                      "爱办不办", "只能这样", "你自己"],
            "regex": "", "enabled": True, "personas": [],
            "why": "未正面回应用户诉求，属于典型推诿话术，直接触发服务投诉升级。",
            "fix": "先承接诉求，再说明可做什么：「您的情况我可以帮您处理，我先为您核实一下……」",
        },
        {
            "id": "RL02", "name": "越权承诺退费 / 赔付", "mode": "regex",
            "words": [],
            # 关键在「确定性承诺 + 具体金额」：正常流程性表述（如「为您提交减免申请，
            # 金额由专人核定」）不应误伤，所以必须用正则做结构识别。
            "regex": (r"(我保证退|肯定能退|肯定能批|一定能批|我给您退\s*\d+|赔您\s*\d+|我承诺"
                      r"|一定给您退|全部退还"
                      r"|(我给您|我帮您|我为您)[^。！？]{0,10}(退|退还|减免|赔付|赔偿)\s*\d+(\.\d+)?"
                      r"|(肯定|一定|保证|绝对|没问题|包您)[^。！？]{0,12}(能退|能批|退给您|赔给您|给您退))"),
            "enabled": True, "personas": [],
            "why": "退费与赔付金额需按权限审批，坐席擅自承诺会造成无法兑现的二次投诉。",
            "fix": "改为流程性承诺：「我会为您提交退费申请，审核通过后 X 个工作日到账，结果以短信通知为准。」",
        },
        {
            "id": "RL03", "name": "携号转网阻挠 / 误导", "mode": "regex",
            "words": [],
            "regex": r"(必须(本人)?到(营业)?厅|没法线上办|不能线上办|转出去(就)?(收不到|用不了)|携转(以)?后会(变差|有问题)|不建议您转)",
            "enabled": True, "personas": [],
            "why": "违反携号转网服务规范，属于监管明令禁止的阻挠行为，可引发监管处罚。",
            "fix": "如实告知并主动提供方式：「您符合携出条件，发送短信 XXX 到 10086 即可查询，我这就把办理途径发给您。」",
        },
        {
            "id": "RL04", "name": "否定 / 对抗用户", "mode": "keyword",
            "words": ["不可能", "绝对没有", "你记错了", "您理解错了", "这是您的问题",
                      "这是您自己的问题", "您搞错了", "怪谁", "怪您自己", "您自己点的",
                      "您自己造成的", "您自己弄的", "您自己订的", "是您自己点的",
                      "是您自己造成的", "您记性"],
            "regex": "", "enabled": True, "personas": [],
            "why": "与用户形成对抗，是情绪升级的直接导火索。",
            "fix": "用事实替代否定：「我帮您查了一下，这笔费用产生的时间是……可能是当时点到了链接，我们来看看怎么取消。」",
        },
        {
            "id": "RL05", "name": "隐瞒 / 拒绝告知申诉渠道", "mode": "keyword",
            "words": ["不能投诉", "投诉也没用", "没有投诉渠道", "投诉没意义",
                      "投诉也没有意义", "您投诉不了"],
            "regex": "", "enabled": True, "personas": [],
            "why": "用户享有申诉权，隐瞒申诉渠道属于严重违规。",
            "fix": "必须主动告知：「如果您对处理结果有异议，可以通过 10080 或工信部申诉平台反映，我把渠道发给您。」",
        },
        {
            "id": "RL06", "name": "营销夸大 / 资费误导", "mode": "keyword",
            "words": ["永久免费", "终身免费", "永远不收费", "没有任何费用", "不限速",
                      "无限流量", "一定跑满", "绝对够用", "不会收费", "不会收您费"],
            "regex": "", "enabled": True, "personas": [],
            "why": "违反「明白办、放心用」要求，隐瞒优惠期与恢复价会形成批量投诉。",
            "fix": "全量告知：「首年是优惠价 0.00 元，第二年恢复标准资费 30.00 元/月；合约 24 个月，提前解约按 30.00 元/月计违约金。」",
        },
    ],
    "yellow_lines": [
        {
            "id": "YL01", "name": "未说明合约期 / 违约金", "mode": "keyword",
            "words": ["合约", "协议", "绑定"], "regex": "",
            "enabled": True, "reverse": True, "scope": "conversation",
            # 仅在确实涉及合约义务的场景生效；不限定会让故障报修、账单争议被误判
            "personas": ["upsell_fttr", "downgrade_penalty", "portability"],
            "why": "涉及合约的业务必须先说明期限与解约成本，否则后续必然产生争议。",
            "fix": "补充一句：「这个方案有 24 个月合约期，提前解约按每月 30.00 元计违约金。」",
        },
        {
            "id": "YL02", "name": "未说明生效 / 到期恢复价", "mode": "keyword",
            "words": ["生效", "次月", "到期", "恢复原价", "恢复标准资费", "优惠期"], "regex": "",
            "enabled": True, "reverse": True, "scope": "conversation",
            "personas": ["upsell_fttr", "downgrade_penalty", "bill_dispute",
                         "elder_misorder", "portability"],
            "why": "优惠到期恢复原价未告知，是「被扣费」类投诉的第一大成因。",
            "fix": "补充一句：「优惠期 12 个月，到期后恢复标准资费 30.00 元/月，届时会提前短信提醒您。」",
        },
        {
            "id": "YL03", "name": "未做身份核验", "mode": "keyword",
            "words": ["请问您的手机号", "请问您的号码", "请问机主", "请问手机号", "请问号码",
                      "为您核对", "帮您核实一下", "帮您查询一下", "麻烦您提供", "验证一下"],
            "regex": "", "enabled": True, "reverse": True, "scope": "conversation",
            "personas": [],
            "why": "未核验身份即提供账单 / 办理业务，存在信息泄露风险，属流程硬伤。",
            "fix": "开口先核验：「为了您的信息安全，麻烦您提供一下本机号码的后四位。」",
        },
        {
            "id": "YL04", "name": "缺乏共情 / 安抚", "mode": "keyword",
            "words": ["理解", "抱歉", "给您带来不便", "体会", "明白您", "您别着急",
                      "不好意思"],
            "regex": "", "enabled": True, "reverse": True, "scope": "conversation",
            "personas": [],
            "why": "情绪型来电未先共情，会直接推高升级率。",
            "fix": "先承接情绪再说事：「耽误您这么久，换作是我也会着急，我马上为您处理。」",
        },
        {
            "id": "YL05", "name": "未复述确认需求", "mode": "keyword",
            "words": ["您的意思是", "我理解您", "确认一下", "您是说",
                      "跟您核对一下诉求", "跟您核对一下需求"],
            "regex": "", "enabled": True, "reverse": True, "scope": "conversation",
            "personas": [],
            "why": "未复述确认易导致处理方向跑偏，形成反复来电。",
            "fix": "加一句复述：「我理解您的诉求是……对吗？我按这个方向为您处理。」",
        },
        {
            "id": "YL06", "name": "未给出明确时限 / 闭环", "mode": "keyword",
            "words": ["24小时", "48小时", "一个工作日", "今天", "明天", "为您登记",
                      "为您派单", "为您提交", "为您处理", "工单", "回访"],
            "regex": "", "enabled": True, "reverse": True, "scope": "conversation",
            "personas": [],
            "why": "没有时限与闭环的答复，用户只能再次来电催办。",
            "fix": "明确承诺：「我为您登记工单，24 小时内装维上门，明天下午 5 点前会有专人回访您。」",
        },
        {
            "id": "YL07", "name": "未告知工单号 / 结束语缺失", "mode": "keyword",
            "words": ["工单号", "受理编号", "感谢", "还有其他", "祝您", "麻烦您给个评价"],
            "regex": "", "enabled": True, "reverse": True, "scope": "conversation",
            "personas": [],
            "why": "缺少工单号与结束语，用户无法追踪进度，也不符合话务收尾规范。",
            "fix": "收尾：「本次工单号是 XXXX，您可以凭这个号查询进度。还有其他需要帮助的吗？」",
        },
    ],
    "must_do": [
        {"name": "身份核验", "mode": "keyword",
         "words": ["请问您的手机号", "请问您的号码", "请问机主", "请问手机号", "请问号码",
                   "为您核对", "帮您核实一下", "帮您查询一下", "麻烦您提供"], "regex": ""},
        {"name": "情绪共情", "mode": "keyword",
         "words": ["理解", "抱歉", "给您带来不便", "明白您", "您别着急", "不好意思"], "regex": ""},
        {"name": "需求复述", "mode": "keyword",
         "words": ["您的意思是", "我理解您", "确认一下", "您是说"], "regex": ""},
        {"name": "方案与时限", "mode": "keyword",
         "words": ["为您登记", "为您派单", "为您提交", "为您处理", "24小时", "48小时",
                   "一个工作日", "工单", "今天", "明天"], "regex": ""},
        {"name": "闭环收尾", "mode": "keyword",
         "words": ["工单号", "受理编号", "感谢", "还有其他", "祝您"], "regex": ""},
    ],
    "accuracy_keys": {
        "bill_dispute": ["套餐外流量", "彩铃", "账单明细", "退费", "取消"],
        "broadband_outage": ["派单", "上门", "24小时", "回访", "工单", "光猫", "线路"],
        "downgrade_penalty": ["合约期", "违约金", "每月", "申诉", "10080", "工信部"],
        "portability": ["短信", "查询", "携出", "符合条件", "线上"],
        "upsell_fttr": ["合约", "到期", "恢复", "速率", "违约金", "资费"],
        "elder_misorder": ["退订", "取消", "短信", "确认", "退费", "不会"],
    },
}


# ── 读写 ──────────────────────────────────────────────────────────
def load():
    """读取配置文件；缺失或损坏时回落到内置默认并落盘。"""
    if CONFIG_PATH.exists():
        try:
            cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(cfg, dict) and "red_lines" in cfg:
                return cfg
        except Exception:
            pass
    save(DEFAULT_RULES)
    return json.loads(json.dumps(DEFAULT_RULES))  # 深拷贝，避免被调用方改脏


def save(cfg):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def reset():
    save(DEFAULT_RULES)
    return json.loads(json.dumps(DEFAULT_RULES))


# ── 匹配式编译 ────────────────────────────────────────────────────
def words_to_regex(words):
    """关键词列表 → 正则（自动转义，避免用户输入 . * ( ) 等特殊字符出错）"""
    ws = [w.strip() for w in (words or []) if w and w.strip()]
    if not ws:
        return r"(?!x)x"  # 永不匹配，等价于该规则暂时失效
    return "(" + "|".join(re.escape(w) for w in ws) + ")"


def pattern_of(rule):
    """统一出口：无论 keyword 还是 regex 模式，都返回一个可直接 re.search 的正则"""
    if rule.get("mode") == "regex":
        return (rule.get("regex") or "").strip() or r"(?!x)x"
    return words_to_regex(rule.get("words"))


def active(rules):
    """过滤启用项，并挂上编译后的 pattern"""
    out = []
    for r in rules:
        if not r.get("enabled", True):
            continue
        item = dict(r)
        item["pattern"] = pattern_of(r)
        out.append(item)
    return out


def new_id(prefix, existing):
    """生成下一个不重复的 ID（如 RL07）"""
    nums = []
    for r in existing:
        m = re.match(re.escape(prefix) + r"(\d+)$", str(r.get("id", "")))
        if m:
            nums.append(int(m.group(1)))
    return f"{prefix}{max(nums) + 1:02d}" if nums else f"{prefix}01"
