# -*- coding: utf-8 -*-
"""
访问口令（简易认证门）
====================================================================
Streamlit 本身**不提供任何访问控制**，部署到公网后默认是任何人可访问。
本模块在应用最前面插一道口令门，把演示范围收回到「拿到口令的人」。

配置（.streamlit/secrets.toml，**该文件已被 .gitignore 排除**）：

    APP_PASSWORD      = "你的口令"        # 不配置则不启用，本地直接放行
    APP_PASSWORD_HINT = "口令提示语"       # 可选，显示在登录页

云端：App → Settings → Secrets 里填同样的键。

安全边界（说清楚，不要过度承诺）：
  这是**演示级**访问控制，能挡住随手点进来的陌生人，
  不是企业级身份认证——没有账号体系、没有审计、口令是明文配置。
  要接真实身份体系，应改为对接企业 SSO / OAuth。
====================================================================
"""

import hmac
import os
import time

import streamlit as st

_FAIL_LIMIT = 5        # 连续失败次数上限
_LOCK_SECONDS = 60     # 触发后锁定时长


def _read(key: str) -> str:
    try:
        v = st.secrets.get(key, None)                    # type: ignore[union-attr]
        if v:
            return str(v).strip()
    except Exception:
        pass
    return os.environ.get(key, "").strip()


def password() -> str:
    return _read("APP_PASSWORD")


def hint() -> str:
    return _read("APP_PASSWORD_HINT")


def enabled() -> bool:
    """是否启用了口令门（未配置口令 = 不启用）"""
    return bool(password())


def passed() -> bool:
    """当前会话是否已通过"""
    if not enabled():
        return True
    return bool(st.session_state.get("_auth_ok", False))


def verify(pwd: str) -> bool:
    """恒定时间比较，避免时序侧信道"""
    expect = password()
    if not expect:
        return True
    return hmac.compare_digest((pwd or "").strip(), expect)


def logout():
    st.session_state.pop("_auth_ok", None)
    st.session_state.pop("_auth_fail", None)
    st.session_state.pop("_auth_lock_until", None)


def _remaining_lock() -> float:
    return max(0.0, float(st.session_state.get("_auth_lock_until", 0)) - time.time())


def render_gate():
    """渲染登录页。校验通过会自动 rerun，调用方在其后 st.stop() 即可。"""
    # 顶部留白，让登录卡片落在视觉中心，而不是贴着页面顶端
    st.markdown("<div style='height:7vh'></div>", unsafe_allow_html=True)
    _l, center, _r = st.columns([1, 1.6, 1])
    with center:
        st.markdown(
            "<div class='hd'>"
            "<h1>🎧 客服上岗认证 · 合规红队陪练智能体</h1>"
            "<p>本系统为内部演示环境，请输入访问口令。</p>"
            "<span class='chip'>亚信 1024 黑客松 · 创意赛道</span>"
            "</div>",
            unsafe_allow_html=True,
        )
        st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

        lock = _remaining_lock()
        fails = int(st.session_state.get("_auth_fail", 0))
        disabled = lock > 0

        with st.form("auth_form"):
            pwd = st.text_input("访问口令", type="password",
                                placeholder="请输入访问口令",
                                disabled=disabled)
            submitted = st.form_submit_button("进入系统", width="stretch",
                                              disabled=disabled)

        if disabled:
            st.error(f"尝试次数过多，请 {int(lock)} 秒后再试。")
        elif fails:
            st.warning(f"口令不正确，已失败 {fails} 次（上限 {_FAIL_LIMIT} 次）。")

        _h = hint()
        if _h:
            st.caption(f"提示：{_h}")

        if submitted and not disabled:
            if verify(pwd):
                st.session_state["_auth_ok"] = True
                st.session_state.pop("_auth_fail", None)
                st.session_state.pop("_auth_lock_until", None)
                st.rerun()
            else:
                n = fails + 1
                st.session_state["_auth_fail"] = n
                if n >= _FAIL_LIMIT:
                    st.session_state["_auth_lock_until"] = time.time() + _LOCK_SECONDS
                    st.session_state["_auth_fail"] = 0
                st.rerun()

        st.markdown(
            "<div class='muted' style='margin-top:18px'>"
            "未收到口令？请联系项目负责人。离线演示模式无需密钥，"
            "进入后仍可完整走通对练与评分流程。</div>",
            unsafe_allow_html=True,
        )
