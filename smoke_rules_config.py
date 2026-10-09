# -*- coding: utf-8 -*-
"""
红线规则配置页（④）的交互冒烟测试
覆盖：导航 → 试匹配命中 → 改词表后实时生效 → 保存落盘 → 恢复默认
运行：python smoke_rules_config.py
"""
import json
from pathlib import Path
import shutil

from streamlit.testing.v1 import AppTest
from smoke_helper import ensure_login

CFG = Path("core/redlines.json")
BACKUP = Path("core/_redlines_backup.json")


def pick(widgets, suffix):
    """按 key 后缀定位控件（key 带版本号前缀 v0_/v1_，不能直接写死）"""
    for w in widgets:
        if getattr(w, "key", "") and w.key.endswith(suffix):
            return w
    raise AssertionError(f"未找到控件 *{suffix}")


def click_btn(at, label):
    for b in at.button:
        if label in b.label:
            b.click().run()
            return True
    raise AssertionError(f"未找到按钮「{label}」")


def main():
    if CFG.exists():
        shutil.copy(CFG, BACKUP)

    ok = True
    try:
        at = AppTest.from_file("app.py", default_timeout=120)
        at.run()
        ensure_login(at)          # 口令门启用时先登录
        if at.exception:
            raise AssertionError(f"初始加载异常: {at.exception}")

        # [1] 导航到配置页
        at.radio[0].set_value("④ 红线规则配置").run()
        if at.exception:
            raise AssertionError(f"配置页渲染异常: {at.exception}")
        print("[1] 配置页渲染 OK")

        # [2] 试匹配：违规话术应命中红线
        pick(at.text_area, "probe_text").set_value(
            "这个我们管不了，规定就是这样，系统自动扣的。").run()
        body = " ".join(m.value for m in at.markdown)
        if "命中红线" not in body:
            raise AssertionError("违规话术未命中红线")
        if "推诿" not in body:
            raise AssertionError("未命中 RL01 推诿甩锅")
        print("[2] 试匹配命中红线 OK")

        # [3] 试匹配：规范话术不应命中
        pick(at.text_area, "probe_text").set_value(
            "非常抱歉给您带来不便，我为您登记工单，24小时内回复，工单号是20260929。").run()
        body = " ".join(m.value for m in at.markdown)
        if "命中红线" in body:
            raise AssertionError("规范话术被误判为红线")
        print("[3] 规范话术零误判 OK")

        # [4] 改词表：给 RL01 加一个新词，不保存也应立刻影响试匹配
        pick(at.radio, "rl_mode_RL01").set_value("keyword").run()
        pick(at.text_area, "rl_w_RL01").set_value("管不了\n我懒得管").run()
        pick(at.text_area, "probe_text").set_value("我懒得管这件事。").run()
        body = " ".join(m.value for m in at.markdown)
        if "命中红线" not in body:
            raise AssertionError("新增关键词未在保存前生效")
        print("[4] 改词表即时生效（未落盘）OK")

        # [5] 保存落盘
        click_btn(at, "保存并生效")
        if not CFG.exists():
            raise AssertionError("保存后 redlines.json 不存在")
        data = json.loads(CFG.read_text(encoding="utf-8"))
        rl01 = next(r for r in data["red_lines"] if r["id"] == "RL01")
        if "我懒得管" not in rl01["words"]:
            raise AssertionError(f"保存内容不含新词: {rl01['words']}")
        print("[5] 保存落盘 OK")

        # [6] 保存后规则引擎确实生效（重新导入模块验证）
        import importlib
        import core.rules as rules
        importlib.reload(rules)
        red01 = next(r for r in rules.RED_LINES if r["id"] == "RL01")
        if not rules.hit(red01["pattern"], "我懒得管这件事。"):
            raise AssertionError("reload 后新词未进入规则引擎")
        if not rules.hit(red01["pattern"], "这个我们管不了"):
            raise AssertionError("reload 后原词丢失")
        print("[6] 规则引擎热生效 OK")

        # [7] 恢复默认：配置文件应回到内置默认
        at2 = AppTest.from_file("app.py", default_timeout=120)
        at2.run()
        ensure_login(at2)         # 新会话，同样要先过口令门
        at2.radio[0].set_value("④ 红线规则配置").run()
        click_btn(at2, "恢复默认")
        data = json.loads(CFG.read_text(encoding="utf-8"))
        rl01 = next(r for r in data["red_lines"] if r["id"] == "RL01")
        if "我懒得管" in rl01["words"]:
            raise AssertionError("恢复默认未清掉自定义词")
        print("[7] 恢复默认（配置文件）OK")

        # [8] 恢复默认：界面上的输入框也必须回到默认值
        #     带 key 的 widget 会保留用户输入状态，若不强制重建会显示旧值
        shown = pick(at2.text_area, "rl_w_RL01").value
        if "我懒得管" in shown:
            raise AssertionError(f"恢复默认后界面仍显示旧词: {shown!r}")
        if "规定就是这样" not in shown:
            raise AssertionError(f"恢复默认后界面未回到默认词表: {shown!r}")
        print("[8] 恢复默认（界面同步刷新）OK")

    except AssertionError as e:
        print(f"❌ {e}")
        ok = False
    finally:
        if BACKUP.exists():
            shutil.copy(BACKUP, CFG)
            BACKUP.unlink()

    print("\n全部通过 ✅ 红线规则可配置、可即时生效、可恢复" if ok else "\n测试失败 ❌")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
