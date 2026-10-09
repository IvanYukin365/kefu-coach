# -*- coding: utf-8 -*-
"""冒烟测试公共辅助：先过口令门，再跑真正的用例。

口令门启用后，AppTest 看到的第一个页面是登录页，直接点主界面控件会
IndexError。所有交互测试都应在 at.run() 之后调一次 ensure_login()。
"""
from pathlib import Path

SECRETS = Path(".streamlit/secrets.toml")


def password_from_toml() -> str:
    """从 secrets.toml 读出当前口令（测试用，正式代码走 core.auth）"""
    if not SECRETS.exists():
        return ""
    for line in SECRETS.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s.startswith("APP_PASSWORD =") and "在这里填" not in line:
            return s.split("=", 1)[1].strip().strip('"')
    return ""


def ensure_login(at):
    """若口令门拦在前面，就用配置里的口令登录一次。未启用则原样返回。"""
    if not any("访问口令" in str(t.label) for t in at.text_input):
        return at                      # 未启用口令门，已直接进主界面
    pw = password_from_toml()
    if not pw:
        raise AssertionError("口令门拦住了测试，但 secrets.toml 里读不到口令")
    at.text_input[0].set_value(pw).run()
    for b in at.button:
        if "进入系统" in b.label:
            b.click().run()
            break
    if at.exception:
        raise AssertionError(f"登录后异常: {at.exception}")
    return at
