# -*- coding: utf-8 -*-
"""
客服上岗认证 · 合规红队陪练智能体
亚信 1024 黑客松大赛 · 创意赛道 · 赛道A（智能体）
"""

import re
import time
import datetime

import streamlit as st

from core import llm, agents, scoring, rules, rules_config, auth
from core.personas import PERSONAS, PERSONA_MAP, POSITIONS

st.set_page_config(
    page_title="客服上岗认证 · 合规红队陪练智能体",
    page_icon="🎧",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 样式 ──────────────────────────────────────────────────────────
CSS = """
<style>
:root{ --brand:#0A6EBD; --brand-d:#08538F; --ink:#0F1720; --sub:#5B6B7C;
       --line:#E3E9F0; --bg:#F5F8FB; --red:#C62828; --amber:#E08700; --green:#1B8A4B; }
.block-container{ padding-top:1.4rem; padding-bottom:3rem; max-width:1360px; }
.hd{ background:linear-gradient(120deg,#0A6EBD 0%,#0E8AD6 60%,#12A5E8 100%);
     border-radius:16px; padding:22px 26px; color:#fff; margin-bottom:18px;
     box-shadow:0 8px 24px rgba(10,110,189,.22); }
.hd h1{ margin:0; font-size:24px; font-weight:700; letter-spacing:.5px; }
.hd p{ margin:8px 0 0; font-size:13.5px; opacity:.92; line-height:1.7; }
.chip{ display:inline-block; background:rgba(255,255,255,.18); border:1px solid rgba(255,255,255,.35);
       border-radius:999px; padding:3px 12px; font-size:12px; margin-right:8px; margin-top:10px; }
.card{ background:#fff; border:1px solid var(--line); border-radius:14px; padding:16px 18px;
       margin-bottom:14px; box-shadow:0 2px 10px rgba(16,42,67,.05); }
.card h4{ margin:0 0 10px; font-size:15px; color:var(--ink); }
.muted{ color:var(--sub); font-size:12.5px; line-height:1.75; }
.kv{ font-size:13px; color:#33475B; line-height:1.9; }
.alert-red{ background:#FDECEC; border-left:4px solid var(--red); border-radius:8px;
            padding:11px 14px; margin:8px 0; font-size:13px; color:#7A1C1C; }
.alert-amber{ background:#FFF6E5; border-left:4px solid var(--amber); border-radius:8px;
              padding:11px 14px; margin:8px 0; font-size:13px; color:#7A4E00; }
.alert-green{ background:#EAF7EF; border-left:4px solid var(--green); border-radius:8px;
              padding:11px 14px; margin:8px 0; font-size:13px; color:#14603A; }
.monitor{ background:#fff; border:1px solid var(--line); border-radius:14px; padding:14px 16px; }
.monitor .ttl{ font-size:13px; font-weight:700; color:var(--ink); margin-bottom:10px;
               display:flex; align-items:center; gap:6px; }
.dot{ width:9px; height:9px; border-radius:50%; display:inline-block; }
.score-ring{ text-align:center; padding:10px 0 4px; }
.score-num{ font-size:52px; font-weight:800; line-height:1; letter-spacing:-1px; }
.badge{ display:inline-block; border-radius:999px; padding:5px 16px; font-size:13px;
        font-weight:700; letter-spacing:.5px; }
.tag{ display:inline-block; background:#EEF4FA; color:#0A6EBD; border-radius:6px;
      padding:2px 8px; font-size:11.5px; margin:2px 4px 2px 0; }
.role-hint{ background:#F7FAFD; border:1px dashed #C8D8E8; border-radius:10px;
            padding:12px 14px; font-size:12.5px; color:#3C5670; line-height:1.85; }
hr.slim{ border:none; border-top:1px solid var(--line); margin:14px 0; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ── 访问口令门 ────────────────────────────────────────────────────
# 公网部署后默认任何人可访问，这里先拦一道。
# 未配置 APP_PASSWORD 时不启用，本地开发直接放行。
if not auth.passed():
    auth.render_gate()
    st.stop()


# ── 会话状态 ──────────────────────────────────────────────────────
def reset():
    st.session_state.messages = []
    st.session_state.turn = 0
    st.session_state.result = None
    st.session_state.finished = False


if "messages" not in st.session_state:
    reset()

PAGES = ["① 对练台", "② 评分报告", "③ 画像与规则库", "④ 红线规则配置"]
if "nav" not in st.session_state:
    st.session_state.nav = PAGES[0]


# ── 侧栏 ──────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🎧 陪练控制台")

    position = st.selectbox("受训岗位", list(POSITIONS.keys()))
    pos_cfg = POSITIONS[position]

    persona_id = st.selectbox(
        "客户画像（来自工单复盘）",
        list(PERSONA_MAP.keys()),
        format_func=lambda k: f"{PERSONA_MAP[k]['name']}｜{PERSONA_MAP[k]['tag']}",
    )
    persona = PERSONA_MAP[persona_id]

    level = st.slider("情绪强度", 1, 3, 2,
                      help="1 温和 / 2 急躁 / 3 激烈（会要求找领导、索要赔偿）")

    max_turns = st.select_slider("对练轮次上限", options=[5, 8, 10, 12, 15], value=10,
                                 help="到上限自动结束并评分；也可随时点「结束对练并评分」")

    if st.button("🔄 重新开始一局", width="stretch"):
        reset()
        st.rerun()

    st.markdown("---")
    # 注意：这里不能用 key="nav"，否则后续无法用代码切换页面
    # （会触发 StreamlitWidgetAlreadyInstantiatedError）
    _sel = st.radio("导航", PAGES, index=PAGES.index(st.session_state.nav))
    st.session_state.nav = _sel

    st.markdown("---")
    if llm.online():
        st.success("在线大模型模式")
        st.caption(f"模型：{llm.get_config()['model']}　（密钥由服务端配置）")
    else:
        st.info("离线演示模式")
        st.caption("无需密钥，100% 可演示")

    if auth.enabled() and st.button("🔒 退出登录", width="stretch"):
        auth.logout()
        st.rerun()

st.markdown(
    f"""<div class="hd">
      <h1>客服上岗认证 · 合规红队陪练智能体</h1>
      <p>用「客户扮演 + 合规红队 + 裁判 + 教练」四智能体协同，把客服上岗培训从
      <b>师傅带、凭感觉</b> 变成 <b>可演练、可评分、可拦截红线</b> 的认证闸门。</p>
      <span class="chip">赛道A · 多智能体</span>
      <span class="chip">上岗认证闸门</span>
      <span class="chip">合规红队拦截</span>
      <span class="chip">行业：中国移动</span>
    </div>""",
    unsafe_allow_html=True,
)

# ── ④ 红线规则配置 ───────────────────────────────────────────────
PID_LABEL = {p["id"]: p["name"] for p in PERSONAS}


def _parse_words(text):
    """词表输入框解析：支持换行 / 逗号 / 分号分隔"""
    return [w.strip() for w in re.split(r"[\n,，;；]+", text or "") if w.strip()]


def _k(name):
    """
    给配置页的 widget key 加版本号前缀。
    带 key 的 widget 会保留用户输入状态，恢复默认 / 导入配置后
    旧状态会覆盖新值 —— 递增版本号可强制 widget 重建，读取新的 default。
    """
    return f"v{st.session_state.get('rcfg_ver', 0)}_{name}"


def _match_preview(cfg, text):
    """用「当前正在编辑的配置」试匹配一句话（不落盘也能测）"""
    norm = rules.normalize_numbers(text or "")
    red_hit, yel_hit = [], []
    for r in cfg.get("red_lines", []):
        if r.get("enabled", True) and re.search(rules_config.pattern_of(r), norm):
            red_hit.append(f"{r['id']} {r['name']}")
    for r in cfg.get("yellow_lines", []):
        if not r.get("enabled", True) or r.get("reverse"):
            continue
        if re.search(rules_config.pattern_of(r), norm):
            yel_hit.append(f"{r['id']} {r['name']}")
    return red_hit, yel_hit


def _rule_card(rule, kind):
    """渲染单条规则的编辑卡片，并把编辑结果写回 rule（原地修改）"""
    rid = rule.get("id", "")
    enabled = rule.get("enabled", True)
    label = f"{rid} {rule.get('name','')}" + ("" if enabled else "　🚫 已停用")
    with st.expander(label, expanded=False):
        a, b = st.columns([4, 1])
        with a:
            rule["name"] = st.text_input("规则名称", rule.get("name", ""),
                                         key=_k(f"{kind}_name_{rid}"))
        with b:
            rule["enabled"] = st.checkbox("启用", enabled, key=_k(f"{kind}_on_{rid}"))

        rule["mode"] = st.radio(
            "匹配方式", ["keyword", "regex"], index=0 if rule.get("mode") == "keyword" else 1,
            format_func=lambda x: "关键词（推荐，一行一个）" if x == "keyword" else "正则表达式（高级）",
            horizontal=True, key=_k(f"{kind}_mode_{rid}"))

        if rule["mode"] == "keyword":
            raw = st.text_area(
                "触发词", "\n".join(rule.get("words") or []), height=110,
                key=_k(f"{kind}_w_{rid}"),
                help="一行一个，也可以用逗号分隔。命中任意一个即触发。会自动转义特殊字符，不用管正则语法。")
            rule["words"] = _parse_words(raw)
            st.caption(f"已识别 {len(rule['words'])} 个词")
        else:
            rule["regex"] = st.text_input(
                "正则表达式", rule.get("regex", ""), key=_k(f"{kind}_rx_{rid}"),
                help="用于「确定性承诺 + 具体金额」这类必须靠结构识别的规则。用 | 表示「或」。")
            if rule.get("regex", "").strip():
                try:
                    re.compile(rule["regex"])
                except re.error as e:
                    st.error(f"正则语法有误：{e}")

        rule["why"] = st.text_area("为什么算违规", rule.get("why", ""), height=68,
                                   key=_k(f"{kind}_why_{rid}"))
        rule["fix"] = st.text_area("正确话术示例", rule.get("fix", ""), height=68,
                                   key=_k(f"{kind}_fix_{rid}"))

        if kind == "yl":
            c1, c2 = st.columns(2)
            with c1:
                rule["reverse"] = st.checkbox(
                    "反向判定（整通对话里**没**说到才扣分）", rule.get("reverse", False),
                    key=_k(f"{kind}_rev_{rid}"))
            with c2:
                rule["scope"] = st.selectbox(
                    "判定范围", ["conversation", "message"],
                    index=0 if rule.get("scope", "conversation") == "conversation" else 1,
                    format_func=lambda x: "整通对话汇总判定" if x == "conversation" else "单条消息即时判定",
                    key=_k(f"{kind}_sc_{rid}"))
            pids = [p for p in rule.get("personas") or [] if p in PID_LABEL]
            rule["personas"] = st.multiselect(
                "生效场景（不选 = 全部场景）", options=list(PID_LABEL.keys()), default=pids,
                format_func=lambda x: PID_LABEL.get(x, x), key=_k(f"{kind}_ps_{rid}"),
                help="像「合约期」这类告知义务只在特定业务成立，不限定会让故障报修、账单争议被误判。")

        if st.button("🗑 删除这条规则", key=_k(f"{kind}_del_{rid}"), width="stretch"):
            return "delete"
    return None


def _render_rules_config():
    import json as _json
    if "rcfg_ver" not in st.session_state:
        st.session_state.rcfg_ver = 0
    if "rcfg" not in st.session_state:
        st.session_state.rcfg = rules_config.load()
    cfg = st.session_state.rcfg

    st.markdown(
        "<div class='card'><h4>⚙️ 红线规则配置</h4>"
        "<div class='muted'>规则内容存放在 <code>core/redlines.json</code>，"
        "改完点「保存并生效」立即作用于评分，<b>不需要改代码、不需要重启</b>。<br>"
        "各省公司服务规范口径不同，落地时把这里的词表替换成省公司现行质检标准即可。</div></div>",
        unsafe_allow_html=True)

    # ── 实时试匹配（改完立刻验证，这是配置页最常用的一步）──
    st.markdown("<div class='card'><h4>🔍 试一试：这句话会被判违规吗？</h4>"
                "<div class='muted'>输入一句客服话术，立刻看它命中哪些规则。"
                "用的是你<b>当前正在编辑</b>的配置，保存前也能测。</div></div>",
                unsafe_allow_html=True)
    probe = st.text_area("客服话术", placeholder="例如：这个我们管不了，规定就是这样，系统自动扣的。",
                         height=70, key="probe_text", label_visibility="collapsed")
    if probe.strip():
        r_hit, y_hit = _match_preview(cfg, probe)
        if r_hit:
            st.markdown("<div class='alert-red'><b>命中红线（一票否决）</b><br>"
                        + "<br>".join("· " + x for x in r_hit) + "</div>",
                        unsafe_allow_html=True)
        if y_hit:
            st.markdown("<div class='alert-amber'><b>命中风险提示项（扣分）</b><br>"
                        + "<br>".join("· " + x for x in y_hit) + "</div>",
                        unsafe_allow_html=True)
        if not r_hit and not y_hit:
            st.markdown("<div class='alert-green'>未命中任何规则。</div>",
                        unsafe_allow_html=True)
        st.caption(f"匹配时已做中文数字归一化：「{rules.normalize_numbers(probe)}」")

    st.markdown("<hr class='slim'>", unsafe_allow_html=True)

    t_red, t_yel, t_must, t_acc = st.tabs(
        ["🚫 红线（一票否决）", "⚠️ 风险提示项（扣分）", "✅ 必备动作", "🎯 画像关键要点"])

    with t_red:
        st.caption(f"共 {len(cfg['red_lines'])} 条。红线命中即判定「规范合规」为 0 分，认证不通过。")
        for r in list(cfg["red_lines"]):
            if _rule_card(r, "rl") == "delete":
                cfg["red_lines"] = [x for x in cfg["red_lines"] if x.get("id") != r.get("id")]
                st.rerun()
        if st.button("➕ 新增红线", key="add_rl", width="stretch"):
            nid = rules_config.new_id("RL", cfg["red_lines"])
            cfg["red_lines"].append({
                "id": nid, "name": "新增红线", "mode": "keyword", "words": [], "regex": "",
                "enabled": True, "personas": [], "why": "", "fix": ""})
            st.rerun()

    with t_yel:
        st.caption(f"共 {len(cfg['yellow_lines'])} 条。多数为「反向判定」：整通对话里没做到才扣分。")
        for r in list(cfg["yellow_lines"]):
            if _rule_card(r, "yl") == "delete":
                cfg["yellow_lines"] = [x for x in cfg["yellow_lines"] if x.get("id") != r.get("id")]
                st.rerun()
        if st.button("➕ 新增风险提示项", key="add_yl", width="stretch"):
            nid = rules_config.new_id("YL", cfg["yellow_lines"])
            cfg["yellow_lines"].append({
                "id": nid, "name": "新增提示项", "mode": "keyword", "words": [], "regex": "",
                "enabled": True, "reverse": True, "scope": "conversation",
                "personas": [], "why": "", "fix": ""})
            st.rerun()

    with t_must:
        st.caption("必备动作命中即加分，构成「流程完整性」维度。")
        for i, m in enumerate(cfg["must_do"]):
            with st.expander(f"{m['name']}", expanded=False):
                m["name"] = st.text_input("动作名称", m["name"], key=_k(f"md_name_{i}"))
                m["mode"] = st.radio(
                    "匹配方式", ["keyword", "regex"],
                    index=0 if m.get("mode") == "keyword" else 1,
                    format_func=lambda x: "关键词" if x == "keyword" else "正则表达式",
                    horizontal=True, key=_k(f"md_mode_{i}"))
                if m["mode"] == "keyword":
                    m["words"] = _parse_words(st.text_area(
                        "触发词", "\n".join(m.get("words") or []), height=100,
                        key=_k(f"md_w_{i}")))
                else:
                    m["regex"] = st.text_input("正则表达式", m.get("regex", ""), key=_k(f"md_rx_{i}"))
                if st.button("🗑 删除", key=_k(f"md_del_{i}"), width="stretch"):
                    cfg["must_do"].pop(i)
                    st.rerun()
        if st.button("➕ 新增必备动作", key="add_md", width="stretch"):
            cfg["must_do"].append({"name": "新动作", "mode": "keyword", "words": [], "regex": ""})
            st.rerun()

    with t_acc:
        st.caption("每个画像「必须说到的业务关键点」，用于「业务准确性」维度计分。")
        for pid in list(cfg["accuracy_keys"].keys()):
            with st.expander(PID_LABEL.get(pid, pid), expanded=False):
                cfg["accuracy_keys"][pid] = _parse_words(st.text_area(
                    "关键要点（一行一个）", "\n".join(cfg["accuracy_keys"][pid]),
                    height=110, key=_k(f"ak_{pid}")))

    # ── 保存 / 导入导出 ──
    st.markdown("<hr class='slim'>", unsafe_allow_html=True)
    s1, s2, s3 = st.columns([2, 1, 1])
    with s1:
        if st.button("💾 保存并生效", type="primary", width="stretch"):
            rules_config.save(cfg)
            rules.reload()
            st.session_state.pop("rcfg", None)
            st.session_state.rcfg_ver += 1   # 重建 widget，确保 UI 与文件一致
            st.success("已保存到 core/redlines.json 并立即生效。")
            st.rerun()
    with s2:
        st.download_button(
            "⬇ 导出 JSON", _json.dumps(cfg, ensure_ascii=False, indent=2),
            file_name="redlines.json", mime="application/json", width="stretch",
            help="部署在 Streamlit Cloud 时，云端文件系统不持久，建议导出留存。")
    with s3:
        if st.button("↩ 恢复默认", width="stretch"):
            st.session_state.rcfg = rules_config.reset()
            st.session_state.rcfg_ver += 1   # 强制 widget 重建，否则旧输入会覆盖默认值
            rules.reload()
            st.success("已恢复为内置默认规则。")
            st.rerun()

    up = st.file_uploader("⬆ 导入 JSON（替换当前配置）", type=["json"])
    if up is not None:
        try:
            loaded = _json.loads(up.read().decode("utf-8"))
            if isinstance(loaded, dict) and "red_lines" in loaded:
                st.session_state.rcfg = loaded
                st.session_state.rcfg_ver += 1
                st.success("导入成功，点「保存并生效」使其生效。")
                st.rerun()
            else:
                st.error("文件格式不对：缺少 red_lines 字段。")
        except Exception as e:
            st.error(f"解析失败：{e}")

    cfg["source_note"] = st.text_area(
        "规则来源声明（会写进配置，供评审追溯）", cfg.get("source_note", ""), height=90,
        key="src_note")


page = st.session_state.nav


# ══════════════════════════ ① 对练台 ═════════════════════════════
if page == "① 对练台":
    left, right = st.columns([1.55, 1], gap="large")

    with left:
        st.markdown(
            f"""<div class="role-hint">
            <b>本局客户：</b>{persona['user']}<br>
            <b>场景：</b>{persona['brief']}<br>
            <b>监管关注点：</b>{persona['regulatory']}<br>
            <b>你要躲开的坑：</b>{'；'.join(persona['traps'])}
            </div><br>""",
            unsafe_allow_html=True,
        )

        box = st.container(height=430, border=False)
        with box:
            if not st.session_state.messages:
                st.caption("点击下方输入框开始。系统会先以客户身份开口，你扮演客服接招。")
            for m in st.session_state.messages:
                if m["role"] == "customer":
                    with st.chat_message("user", avatar="🙋"):
                        st.markdown(f"**客户：** {m['content']}")
                else:
                    with st.chat_message("assistant", avatar="🎧"):
                        st.markdown(f"**客服（你）：** {m['content']}")
                        for f in m.get("flags", []):
                            if f["level"] == "red":
                                st.markdown(
                                    f"<div class='alert-red'>🚩 红线｜<b>{f['rule']['name']}</b><br>"
                                    f"{f['rule']['why']}<br><i>改法：{f['rule']['fix']}</i></div>",
                                    unsafe_allow_html=True,
                                )

        if st.session_state.finished:
            st.button("📊 查看评分报告", type="primary", width="stretch",
                      on_click=lambda: st.session_state.update(nav="② 评分报告"))
        else:
            prompt = st.chat_input("输入你的客服话术（回车发送）…")
            if prompt:
                flags = rules.scan_message(prompt)
                st.session_state.turn += 1
                st.session_state.messages.append(
                    {"role": "cs", "content": prompt, "turn": st.session_state.turn, "flags": flags}
                )
                with st.spinner("客户正在回应…"):
                    time.sleep(0.35)
                    reply, _ = agents.customer_reply(persona, level, st.session_state.messages,
                                                     max_turns=max_turns)
                st.session_state.messages.append({"role": "customer", "content": reply})
                if st.session_state.turn >= max_turns:
                    st.session_state.finished = True
                    st.session_state.result = scoring.score(st.session_state.messages, persona, pos_cfg)
                    st.session_state.nav = "② 评分报告"
                st.rerun()

            if st.session_state.messages:
                if st.button("⏹ 结束对练并评分", width="stretch"):
                    st.session_state.finished = True
                    st.session_state.result = scoring.score(st.session_state.messages, persona, pos_cfg)
                    st.session_state.nav = "② 评分报告"
                    st.rerun()
            else:
                if st.button("▶️ 客户来电，开始对练", type="primary", width="stretch"):
                    st.session_state.messages.append({"role": "customer", "content": persona["opening"]})
                    st.rerun()

    with right:
        st.markdown('<div class="monitor"><div class="ttl">🛡️ 合规红队 · 实时监测</div>',
                    unsafe_allow_html=True)
        reds = [f for m in st.session_state.messages for f in m.get("flags", []) if f["level"] == "red"]
        if not st.session_state.messages:
            st.markdown("<div class='alert-green'>待机中 · 未检出违规</div>", unsafe_allow_html=True)
        elif reds:
            st.markdown(
                f"<div class='alert-red'><b>⛔ 已命中 {len(reds)} 条红线</b><br>"
                f"按认证规则，红线命中即<b>一票否决</b>，本局不得通过上岗认证。</div>",
                unsafe_allow_html=True,
            )
            for f in reds:
                st.markdown(f"<div class='alert-red'><b>{f['rule']['id']} {f['rule']['name']}</b><br>"
                            f"{f['rule']['why']}</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='alert-green'>✅ 本局暂未触碰监管红线</div>", unsafe_allow_html=True)

        st.markdown("<hr class='slim'>", unsafe_allow_html=True)
        st.markdown("**流程完整性检查**", unsafe_allow_html=True)
        cs_text = "\n".join(m["content"] for m in st.session_state.messages if m["role"] == "cs")
        for name, pat in rules.MUST_DO:
            ok = rules.hit(pat, cs_text)
            color = "#1B8A4B" if ok else "#94A3B8"
            icon = "✔" if ok else "○"
            st.markdown(f"<span style='color:{color};font-size:12.5px'>{icon} {name}</span>",
                        unsafe_allow_html=True)
        st.markdown("<hr class='slim'>", unsafe_allow_html=True)
        st.markdown(
            f"<div class='muted'>对话轮次：{st.session_state.turn} / {max_turns} ｜ "
            f"岗位：{position}<br>认证线：总分 ≥ {pos_cfg['gate_total']} 且 规范合规 ≥ "
            f"{pos_cfg['gate_compliance']}（红线一票否决）</div></div>",
            unsafe_allow_html=True,
        )

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            f"""<div class="card"><h4>🎭 客户画像卡</h4>
            <div class="kv"><b>{persona['name']}</b><br>
            <span class="tag">{persona['tag']}</span><br><br>
            <b>情绪：</b>{persona['emotion']}<br>
            <b>隐藏真相（客服需查证后才知道）：</b>{persona['hidden_truth']}<br>
            <b>必须做到：</b>{'、'.join(persona['must_do'])}</div></div>""",
            unsafe_allow_html=True,
        )


# ══════════════════════════ ② 评分报告 ═══════════════════════════
elif page == "② 评分报告":
    if not st.session_state.messages:
        st.warning("还没有对练记录，请先去「① 对练台」跑一局。")
        st.stop()

    result = st.session_state.result or scoring.score(st.session_state.messages, persona, pos_cfg)
    tips = scoring.build_suggestions(result, persona)
    dims, total = result["dims"], result["total"]
    passed = result["passed"]

    a, b = st.columns([1, 1.25], gap="large")

    with a:
        color = "#1B8A4B" if passed else "#C62828"
        word = "通过上岗认证" if passed else "未通过 · 需补练"
        st.markdown(
            f"""<div class="card"><div class="score-ring">
            <div class="score-num" style="color:{color}">{total}</div>
            <div style="color:#5B6B7C;font-size:12.5px;margin-top:6px">综合得分 / 100</div>
            <div style="margin-top:12px">
              <span class="badge" style="background:{'#EAF7EF' if passed else '#FDECEC'};color:{color}">{word}</span>
            </div>
            <div class="muted" style="margin-top:10px">
              认证线：总分 ≥ {result['gate']['total']} ｜ 规范合规 ≥ {result['gate']['compliance']}
              ｜ 红线一票否决（当前命中 {len(result['red_hits'])} 条）
            </div></div></div>""",
            unsafe_allow_html=True,
        )

        try:
            import plotly.graph_objects as go
            keys = list(dims.keys())
            fig = go.Figure(data=go.Scatterpolar(
                r=[dims[k] for k in keys] + [dims[keys[0]]],
                theta=keys + [keys[0]], fill="toself",
                line=dict(color="#0A6EBD", width=2),
                fillcolor="rgba(10,110,189,.18)",
            ))
            fig.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 100],
                                           tickfont=dict(size=9), gridcolor="#E3E9F0"),
                           bgcolor="#FFFFFF"),
                showlegend=False, height=340,
                margin=dict(l=30, r=30, t=24, b=24),
            )
            st.plotly_chart(fig, width="stretch")
        except Exception:
            st.bar_chart(dims)

        st.markdown("<div class='card'><h4>五维得分与权重</h4>", unsafe_allow_html=True)
        for k, w in scoring.WEIGHTS.items():
            v = dims[k]
            st.markdown(
                f"<div style='font-size:12.5px;margin:5px 0'>{k} "
                f"<span style='color:#94A3B8'>（权重 {w}）</span> "
                f"<b style='float:right'>{v}</b></div>", unsafe_allow_html=True)
            st.progress(int(v) / 100)
        st.markdown("</div>", unsafe_allow_html=True)

    with b:
        st.markdown("<div class='card'><h4>🚩 红线命中（一票否决项）</h4>", unsafe_allow_html=True)
        if result["red_hits"]:
            for rh in result["red_hits"]:
                st.markdown(
                    f"<div class='alert-red'><b>第 {rh['turn']} 轮 · {rh['rule']['name']}</b><br>"
                    f"<span style='opacity:.8'>你的原话：</span>{rh['text']}<br>"
                    f"<b>为什么是红线：</b>{rh['rule']['why']}<br>"
                    f"<b>怎么改：</b>{rh['rule']['fix']}</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='alert-green'>本通对话未检出监管红线与服务禁语。</div>",
                        unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='card'><h4>🎓 教练智能体 · 改进建议</h4>", unsafe_allow_html=True)
        if llm.online():
            transcript = "\n".join(
                f"{'客服' if m['role']=='cs' else '客户'}：{m['content']}"
                for m in st.session_state.messages)
            with st.spinner("教练智能体生成辅导中…"):
                out = agents.coach(transcript, persona, result)
            if out:
                st.markdown(out)
            else:
                for t in tips:
                    cls = {"red": "alert-red", "yellow": "alert-amber", "green": "alert-green"}[t["level"]]
                    st.markdown(f"<div class='{cls}'><b>{t['type']}｜{t['title']}</b><br>{t['fix']}</div>",
                                unsafe_allow_html=True)
        else:
            for t in tips:
                cls = {"red": "alert-red", "yellow": "alert-amber", "green": "alert-green"}[t["level"]]
                st.markdown(f"<div class='{cls}'><b>{t['type']}｜{t['title']}</b><br>"
                            f"<span style='opacity:.75'>{t['why']}</span><br>"
                            f"<b>改法：</b>{t['fix']}</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        with st.expander("📜 查看完整对话记录"):
            for m in st.session_state.messages:
                who = "客户" if m["role"] == "customer" else "客服（你）"
                st.markdown(f"**{who}：** {m['content']}")
        st.download_button(
            "⬇️ 导出本局记录与评分（.txt）",
            data=("\n".join(f"{'客服' if m['role']=='cs' else '客户'}：{m['content']}"
                            for m in st.session_state.messages)
                  + f"\n\n【评分】{dims}\n【总分】{total}\n【认证】{'通过' if passed else '未通过'}\n"
                    f"【生成时间】{datetime.datetime.now():%Y-%m-%d %H:%M}"),
            file_name=f"陪练记录_{persona['id']}_{datetime.datetime.now():%m%d%H%M}.txt",
            mime="text/plain", width="stretch",
        )


# ═══════════════════════ ③ 画像与规则库 ══════════════════════════
elif page == "③ 画像与规则库":
    c1, c2 = st.columns([1, 1], gap="large")
    with c1:
        st.markdown("<div class='card'><h4>🗂️ 客户画像库（真数据来源）</h4>"
                    "<div class='muted'>6 类画像均来自 10086 呼入投诉高频场景的工单复盘。"
                    "正式上线前需由业务方用脱敏后的真实通话转写替换，并标注样本量与时间窗。</div></div>",
                    unsafe_allow_html=True)
        for p in PERSONAS:
            with st.expander(f"{p['name']}　·　{p['tag']}"):
                st.markdown(
                    f"<div class='kv'><b>用户：</b>{p['user']}<br>"
                    f"<b>场景：</b>{p['brief']}<br>"
                    f"<b>隐藏真相：</b>{p['hidden_truth']}<br>"
                    f"<b>情绪：</b>{p['emotion']}<br>"
                    f"<b>监管关注点：</b>{p['regulatory']}<br>"
                    f"<b>陷阱：</b>{'；'.join(p['traps'])}<br>"
                    f"<b>必须做到：</b>{'、'.join(p['must_do'])}</div>",
                    unsafe_allow_html=True)

    with c2:
        st.markdown("<div class='card'><h4>⚖️ 监管红线（命中即一票否决）</h4></div>",
                    unsafe_allow_html=True)
        for r in rules.RED_LINES:
            st.markdown(f"<div class='alert-red'><b>{r['id']} {r['name']}</b><br>{r['why']}<br>"
                        f"<i>改法：{r['fix']}</i></div>", unsafe_allow_html=True)
        st.markdown("<br><div class='card'><h4>⚠️ 风险提示项（扣分）</h4></div>",
                    unsafe_allow_html=True)
        for r in rules.YELLOW_LINES:
            st.markdown(f"<div class='alert-amber'><b>{r['id']} {r['name']}</b><br>{r['why']}<br>"
                        f"<i>改法：{r['fix']}</i></div>", unsafe_allow_html=True)


# ═══════════════════════ ④ 红线规则配置 ══════════════════════════
elif page == "④ 红线规则配置":
    _render_rules_config()
