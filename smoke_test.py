# -*- coding: utf-8 -*-
"""交互冒烟测试：用 Streamlit AppTest 模拟真实点击流程"""
import sys
from streamlit.testing.v1 import AppTest

at = AppTest.from_file("app.py", default_timeout=120)
at.run()
assert not at.exception, f"初始加载异常: {at.exception}"
print("[1] 初始加载 OK")

# 选携号转网画像 + 开始对练
at.selectbox[1].select("portability").run()
assert not at.exception, f"切换画像异常: {at.exception}"
print("[2] 切换画像 OK")

btn = [b for b in at.button if "开始对练" in b.label][0]
btn.click().run()
assert not at.exception, f"开始对练异常: {at.exception}"
print("[3] 客户开口 OK")

# 第 1 轮：故意说推诿红线话术
at.chat_input[0].set_value("这个我们管不了，规定就是这样，改不了。").run()
assert not at.exception, f"第1轮异常: {at.exception}"
print("[4] 第1轮(红线) OK")

# 第 2 轮：规范话术
at.chat_input[0].set_value(
    "非常抱歉给您带来不便，麻烦您提供一下号码后四位，我为您核对一下。"
    "您符合携出条件，发送短信查询即可，我这就把办理途径发给您。我为您登记工单，"
    "24小时内回复，工单号是20260929。").run()
assert not at.exception, f"第2轮异常: {at.exception}"
print("[5] 第2轮(规范) OK")

# 结束对练 -> 应自动跳到评分报告
end = [b for b in at.button if "结束对练" in b.label]
if end:
    end[0].click().run()
    assert not at.exception, f"结束对练异常: {at.exception}"
    print("[6] 结束对练并自动跳转 OK")

print("[7] 当前页面 nav =", at.session_state.nav)
assert at.session_state.nav == "② 评分报告", "未自动跳转到评分报告"
print("[8] 评分报告渲染 OK")

# 手动切回对练台 / 规则库
at.radio[0].set_value("③ 画像与规则库").run()
assert not at.exception, f"切到规则库异常: {at.exception}"
print("[9] 画像与规则库 OK")

at.radio[0].set_value("① 对练台").run()
assert not at.exception, f"切回对练台异常: {at.exception}"
print("[10] 返回对练台 OK")

print("\n全部通过 ✅ 无 StreamlitWidgetAlreadyInstantiatedError")
