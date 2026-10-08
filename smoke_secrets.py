# -*- coding: utf-8 -*-
"""验证 Secrets / 环境变量 / 界面覆盖 三者的优先级与「清空可回离线」。

模拟 Streamlit Cloud 环境：依赖项目根目录下的 .streamlit/secrets.toml
（该文件已被 .gitignore 排除，不会进代码库）。
"""
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

SECRETS = Path(".streamlit/secrets.toml")


def _text(at):
    """收集侧栏 + 主区所有可见文本（st.success / st.caption 不在 markdown 里）"""
    parts = [m.value for m in at.markdown]
    parts += [s.value for s in at.success]
    parts += [s.value for s in at.sidebar.success] if at.sidebar else []
    parts += [c.value for c in at.caption]
    return " ".join(str(p) for p in parts)


def main():
    if not SECRETS.exists():
        print("跳过：未找到 .streamlit/secrets.toml（无法模拟云端 Secrets）")
        return 0

    at = AppTest.from_file("app.py", default_timeout=120)
    at.run()
    if at.exception:
        raise AssertionError(f"应用启动异常: {at.exception}")

    # [1] Secrets 生效：应处于在线模式
    body = _text(at)
    if "在线大模型模式" not in body:
        raise AssertionError("Secrets 已配置但侧栏未显示「在线大模型模式」")
    print("[1] Secrets 生效 → 在线大模型模式 OK")

    # [2] 输入框初始值来自 Secrets
    key_box = at.text_input(key="cfg_api_key")
    if not key_box.value:
        raise AssertionError("API Key 输入框未回填 Secrets 的值")
    print(f"[2] 输入框回填 Secrets OK（{key_box.value[:6]}***）")

    # [3] 用户在界面上清空 Key → 应回到离线（曾经会因为 widget 无 key 而清不掉）
    key_box.set_value("").run()
    body = _text(at)
    if "在线大模型模式" in body:
        raise AssertionError("清空 API Key 后仍处于在线模式（界面覆盖未生效）")
    print("[3] 清空 Key 可回到离线模式 OK")

    # [4] 填入自定义模型名 → 覆盖 Secrets，且不被弹回
    at.text_input(key="cfg_api_key").set_value("sk-mine-000").run()
    at.text_input(key="cfg_model").set_value("我的私有模型").run()
    body = _text(at)
    if "在线大模型模式" not in body:
        raise AssertionError("填入自定义 Key 后未进入在线模式")
    if "我的私有模型" not in body:
        raise AssertionError("自定义模型名未反映到侧栏提示（界面覆盖被 Secrets 盖掉）")
    print("[4] 界面覆盖优先于 Secrets OK")

    print("\n全部通过 ✅ Secrets 优先级正确，界面可随时覆盖并回退")
    return 0


if __name__ == "__main__":
    sys.exit(main())
