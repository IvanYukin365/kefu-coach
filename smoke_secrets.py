# -*- coding: utf-8 -*-
"""验证：口令门拦得住 / 口令校验正确 / 大模型走 secrets.toml / 前端无密钥输入框。

依赖项目根目录的 .streamlit/secrets.toml（已被 .gitignore 排除）。
涉及"改配置"的场景在子进程里跑，并用 try/finally 保证配置还原。
"""
import os
import subprocess
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

SECRETS = Path(".streamlit/secrets.toml")


def _all_text(at):
    parts = [m.value for m in at.markdown]
    parts += [s.value for s in at.success] + [s.value for s in at.error]
    parts += [w.value for w in at.warning] + [i.value for i in at.info]
    parts += [c.value for c in at.caption]
    return " ".join(str(p) for p in parts)


def _run_child(code: str, label: str):
    # 清掉继承来的 APP_PASSWORD*：主进程跑过 AppTest 后，Streamlit 会把 secrets
    # 注入 os.environ，子进程若不清理就会读到父进程的旧口令，测不出真实行为。
    env = {k: v for k, v in os.environ.items() if k not in ("APP_PASSWORD",
                                                            "APP_PASSWORD_HINT")}
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, env=env,
                       text=True, encoding="utf-8", errors="ignore")
    if r.returncode != 0:
        tail = (r.stdout or "")[-800:] + (r.stderr or "")[-800:]
        raise AssertionError(f"[{label}] 子进程失败:\n{tail}")
    print(f"    {label}: " + (r.stdout or "").strip().splitlines()[-1])


def main():
    if not SECRETS.exists():
        print("跳过：未找到 .streamlit/secrets.toml")
        return 0

    pw = None
    for line in SECRETS.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("APP_PASSWORD =") and "在这里填" not in line:
            pw = line.split("=", 1)[1].strip().strip('"')
    if not pw:
        print("跳过：secrets.toml 未配置 APP_PASSWORD")
        return 0

    at = AppTest.from_file("app.py", default_timeout=120)
    at.run()
    if at.exception:
        raise AssertionError(f"应用启动异常: {at.exception}")

    # [1] 未登录 → 只有登录页，看不到主界面内容
    body = _all_text(at)
    if "访问口令" not in body:
        raise AssertionError("未显示登录页（口令门未生效）")
    if "陪练控制台" in body:
        raise AssertionError("未登录却看到了侧栏，口令门形同虚设")
    print("[1] 未登录被拦截 → 仅显示登录页 OK")

    # [2] 错误口令 → 仍在登录页
    at.text_input[0].set_value("wrong-password").run()
    for b in at.button:
        if "进入系统" in b.label:
            b.click().run()
            break
    body = _all_text(at)
    if "口令不正确" not in body:
        raise AssertionError("错误口令未报错")
    if "陪练控制台" in body:
        raise AssertionError("错误口令竟然放行了")
    print("[2] 错误口令被拒绝 OK")

    # [3] 正确口令 → 进入主界面
    at.text_input[0].set_value(pw).run()
    for b in at.button:
        if "进入系统" in b.label:
            b.click().run()
            break
    body = _all_text(at)
    if "陪练控制台" not in body:
        raise AssertionError("正确口令未进入主界面")
    print("[3] 正确口令放行 OK")

    # [4] 主界面不应再有大模型输入框（已在服务端配置，不该出现在前端）
    labels = [t.label for t in at.text_input]
    bad = [l for l in labels if l in ("API Key", "Base URL（OpenAI 兼容）", "模型名")]
    if bad:
        raise AssertionError(f"前端仍存在大模型输入框: {bad}")
    print(f"[4] 前端已无密钥输入框 OK（剩余 {len(labels)} 个输入框，均为业务输入）")

    orig = SECRETS.read_text(encoding="utf-8")

    # [5] 子进程：去掉口令 → 直接放行
    try:
        SECRETS.write_text(
            "\n".join(l for l in orig.splitlines()
                      if not l.strip().startswith("APP_PASSWORD")),
            encoding="utf-8")
        _run_child(CHILD_NO_PASSWORD, "未配置口令时直接放行")
    finally:
        SECRETS.write_text(orig, encoding="utf-8")

    # [6] 子进程：填入 API Key → 侧栏显示在线大模型模式
    try:
        SECRETS.write_text(
            orig.replace('LLM_API_KEY = ""', 'LLM_API_KEY = "sk-child-test-000"'),
            encoding="utf-8")
        _run_child(CHILD_ONLINE, "toml 中的 API Key 生效")
    finally:
        SECRETS.write_text(orig, encoding="utf-8")

    print("\n全部通过 ✅ 口令门 + 服务端密钥配置均正常")
    return 0


CHILD_NO_PASSWORD = r'''
import pathlib, sys
sys.path.insert(0, ".")
import streamlit as st
from core import auth
print("  [diag] cwd=%s 文件=%s" % (pathlib.Path.cwd().name,
                                   pathlib.Path(".streamlit/secrets.toml").exists()))
print("  [diag] secrets keys=%s" % list(st.secrets.keys()))
print("  [diag] auth.enabled()=%s" % auth.enabled())
from streamlit.testing.v1 import AppTest
at = AppTest.from_file("app.py", default_timeout=120); at.run()
assert not at.exception, at.exception
txt = " ".join(m.value for m in at.markdown) + " ".join(c.value for c in at.caption)
assert "访问口令" not in txt, "未配置口令却仍要求登录"
assert "陪练控制台" in txt, "未配置口令时未直接进入主界面"
print("OK 无口令直接放行")
'''

CHILD_ONLINE = r'''
import pathlib
from streamlit.testing.v1 import AppTest
at = AppTest.from_file("app.py", default_timeout=120); at.run()
pw = None
for line in pathlib.Path(".streamlit/secrets.toml").read_text(encoding="utf-8").splitlines():
    if line.strip().startswith("APP_PASSWORD ="):
        pw = line.split("=", 1)[1].strip().strip('"')
at.text_input[0].set_value(pw).run()
for b in at.button:
    if "进入系统" in b.label:
        b.click().run(); break
parts = [m.value for m in at.markdown] + [s.value for s in at.success] + [c.value for c in at.caption]
txt = " ".join(str(p) for p in parts)
assert "陪练控制台" in txt, "登录后未进入主界面"
assert "在线大模型模式" in txt, "toml 中已填 API Key，侧栏却未显示在线模式"
print("OK toml 密钥生效（在线大模型模式）")
'''

if __name__ == "__main__":
    sys.exit(main())
