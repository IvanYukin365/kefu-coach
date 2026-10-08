# -*- coding: utf-8 -*-
"""
30 秒演示视频自动生成流水线
--------------------------------------------------
1) edge-tts 生成中文配音（按分镜分段）
2) Playwright 驱动真实 Streamlit 应用，按配音时长录制操作过程
3) ffmpeg 合成：录屏 + 配音 + 烧录中文字幕 -> 1920x1080 MP4

用法：
    python video/make_video.py            # 全流程
    python video/make_video.py --tts-only # 只生成配音
"""
import argparse
import asyncio
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

VIDEO_DIR = Path(__file__).resolve().parent
ROOT = VIDEO_DIR.parent
WORK = VIDEO_DIR / "build"
WORK.mkdir(parents=True, exist_ok=True)

APP_URL = os.environ.get("APP_URL", "http://localhost:8630")
VOICE = os.environ.get("TTS_VOICE", "zh-CN-XiaoxiaoNeural")
RATE = os.environ.get("TTS_RATE", "+22%")

FFMPEG = r"C:\Users\AI\AppData\Roaming\Python\Python312\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
if not os.path.exists(FFMPEG):
    import imageio_ffmpeg
    FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

FONT = r"C:/Windows/Fonts/msyhbd.ttc"
if not os.path.exists(FONT):
    FONT = r"C:/Windows/Fonts/simhei.ttf"

# ── 台词（对练话术，故意先错后对）──────────────────────────────
BAD_LINE = "这个我们管不了，规定就是这样，改不了。你还是别转了，转出去收不到验证码的。"
GOOD_LINE = (
    "非常抱歉给您带来不便，我理解您的想法。您的意思是想把现在这个号码转到其他运营商，对吗？"
    "携号转网可以正常办理：请先发送短信 CXXZ#姓名#证件号码 到 10086 查询是否符合携出条件；"
    "如您的合约尚未到期，需先办理解约。查询通过后，您本人携带有效证件到携入方营业厅即可办理，"
    "也支持线上申请。转出后部分第三方平台的验证码可能会受影响，建议您提前解绑。"
    "麻烦您提供一下号码后四位，我为您核对套餐情况并登记工单，24小时内回复，工单号是 20260929。"
    "感谢您的来电，请问还有其他需要吗？"
)

# ── 分镜：配音 + 操作 + 该段最短时长补偿 ────────────────────────
SEGMENTS = [
    {"key": "home", "narr": "一零零八六客服新人，上岗前怎么练？", "act": None, "gap": 0.4},
    {"key": "setup", "narr": "真实客户由 AI 扮演，会追问、会挖坑，还会要找你领导。", "act": "setup", "gap": 0.5},
    {"key": "bad", "narr": "推诿甩锅、越权承诺、携转阻挠、隐瞒申诉渠道——"
                           "六条监管红线实时拦截，命中即一票否决。", "act": "bad", "gap": 0.5},
    {"key": "good", "narr": "重开一局，改说规范话术，合规面板立刻转绿。", "act": "good", "gap": 1.6},
    {"key": "report", "narr": "五个维度自动打分，教练智能体给出改进话术。红线不过，不能上岗。",
     "act": "report", "gap": 1.1},
]


def log(msg):
    print(msg, flush=True)


# ══════════════════ 1. 配音 ══════════════════════════════════
async def _tts(text, path):
    import edge_tts
    comm = edge_tts.Communicate(text, VOICE, rate=RATE)
    await comm.save(str(path))


def gen_audio():
    log("[1/4] 生成中文配音 …")
    for i, seg in enumerate(SEGMENTS):
        mp3 = WORK / f"narr_{i}.mp3"
        if not mp3.exists() or mp3.stat().st_size < 1000:
            asyncio.run(_tts(seg["narr"], mp3))
        seg["dur"] = probe_duration(mp3)
        log(f"      {seg['key']:7s} {seg['dur']:.2f}s  {seg['narr'][:22]}…")
    return True


def probe_duration(path):
    out = subprocess.run([FFMPEG, "-hide_banner", "-i", str(path)],
                         capture_output=True, text=True, errors="ignore").stderr
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", out)
    if not m:
        raise RuntimeError(f"无法解析时长: {path}")
    h, mnt, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
    return h * 3600 + mnt * 60 + s


# ══════════════════ 2. 录屏 ══════════════════════════════════
OPENING_MARK = "我问一下"          # 携转画像的客户开场白
RED_MARK = "已命中"                 # 红队面板：已命中 N 条红线
GREEN_MARK = "本局暂未触碰监管红线"   # 红队面板：转绿
REPORT_MARK = "综合得分"            # 评分报告已渲染


def _wait(page, text, timeout=25000):
    """等某个可视状态出现，比固定 sleep 稳得多"""
    page.wait_for_selector(f"text={text}", timeout=timeout)


def record():
    from playwright.sync_api import sync_playwright

    log("[2/4] 启动浏览器并录制操作过程 …")
    rec_dir = WORK / "rec"
    if rec_dir.exists():
        shutil.rmtree(rec_dir)
    rec_dir.mkdir(parents=True)

    timeline = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        ctx = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            device_scale_factor=1,
            locale="zh-CN",
            record_video_dir=str(rec_dir),
            record_video_size={"width": 1920, "height": 1080},
        )
        page = ctx.new_page()
        t_page = time.monotonic()
        page.goto(APP_URL, wait_until="networkidle")
        page.wait_for_selector('[data-testid="stChatInput"]', timeout=60000)
        page.wait_for_timeout(2500)          # 等骨架屏彻底稳定
        wall = {"t0": time.monotonic()}
        lead = wall["t0"] - t_page
        log(f"      应用加载 {lead:.1f}s（成片里裁掉）")

        marks = []

        def seg_start(i):
            marks.append({"i": i, "t": time.monotonic() - wall["t0"]})

        def hold(i):
            """补时到「配音时长 + gap」，保证每段画面停留够"""
            target = SEGMENTS[i]["dur"] + SEGMENTS[i]["gap"]
            elapsed = time.monotonic() - wall["t0"] - marks[-1]["t"]
            if elapsed < target:
                page.wait_for_timeout(int((target - elapsed) * 1000))

        # ── S0 首页 ──
        seg_start(0)
        hold(0)

        # ── S1 选画像 + 开始对练 ──
        seg_start(1)
        sb = page.locator('[data-testid="stSelectbox"]').nth(1)
        sb.scroll_into_view_if_needed()
        sb.locator("input").click()
        page.wait_for_timeout(500)
        page.get_by_role("option").filter(has_text="携号转网咨询型").first.click()
        page.wait_for_function(
            """() => {
                 const s = document.querySelectorAll('[data-testid="stSelectbox"]');
                 return s[1] && s[1].querySelector('input').value.includes('携号转网');
               }""", timeout=15000)
        page.wait_for_timeout(1300)          # 等 rerun 把 DOM 换完
        page.get_by_role("button", name="客户来电，开始对练").click()
        _wait(page, OPENING_MARK)
        page.wait_for_timeout(700)
        hold(1)

        # ── S2 故意说红线话术 ──
        seg_start(2)
        _type_and_send(page, BAD_LINE)
        _wait(page, RED_MARK)
        page.wait_for_timeout(400)
        hold(2)

        # ── S3 重开一局 + 规范话术 ──
        seg_start(3)
        page.get_by_role("button", name="重新开始一局").click()
        page.wait_for_timeout(1000)
        page.get_by_role("button", name="客户来电，开始对练").click()
        _wait(page, OPENING_MARK)
        page.wait_for_timeout(400)
        _type_and_send(page, GOOD_LINE, delay=10, head=16)
        try:
            _wait(page, "非常抱歉给您带来不便", timeout=8000)   # 规范话术已上屏
        except Exception:
            log("      ! 规范话术上屏确认超时，继续")
        page.wait_for_timeout(1500)                          # 等客户接话
        _wait(page, GREEN_MARK, timeout=8000)
        page.wait_for_timeout(700)
        hold(3)

        # ── S4 结束并查看评分报告 ──
        seg_start(4)
        page.get_by_role("button", name="结束对练并评分").click()
        _wait(page, REPORT_MARK)
        page.wait_for_timeout(700)
        hold(4)

        page.wait_for_timeout(400)
        video_path = page.video.path()
        page.close()
        ctx.close()
        browser.close()

    for m in marks:
        timeline.append({"i": m["i"], "t": round(m["t"], 2)})
        log(f"      段{m['i']} 起点 {m['t']:.2f}s")
    return video_path, timeline, lead


def _type_and_send(page, text, delay=22, head=0):
    """逐字敲前 head 个字符（有真实打字感），其余一次性插入，避免长句拖慢节奏"""
    box = page.locator('[data-testid="stChatInput"]').locator("textarea")
    box.click()
    if head and len(text) > head:
        box.press_sequentially(text[:head], delay=delay)
        page.keyboard.insert_text(text[head:])
    else:
        box.press_sequentially(text, delay=delay)
    page.wait_for_timeout(300)
    page.keyboard.press("Enter")


# ══════════════════ 3. 音轨 & 字幕 ═══════════════════════════
def build_audio(total):
    log("[3/4] 合成配音音轨 …")
    out = WORK / "narration.m4a"
    parts, labels = [], []
    args = [FFMPEG, "-hide_banner", "-y",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
    for i, seg in enumerate(SEGMENTS):
        args += ["-i", str(WORK / f"narr_{i}.mp3")]
    fc = []
    for i, seg in enumerate(SEGMENTS):
        ms = int(round(seg["start"] * 1000))
        fc.append(f"[{i+1}:a]aresample=44100,aformat=channel_layouts=stereo,"
                  f"adelay={ms}|{ms}[a{i}]")
        labels.append(f"[a{i}]")
    fc.append(f"[0:a]{''.join(labels)}amix=inputs={len(SEGMENTS)+1}:"
              f"normalize=0:duration=first,apad,volume=1.0[aout]")
    args += ["-filter_complex", ";".join(fc), "-map", "[aout]",
             "-t", f"{total:.2f}", "-ar", "44100", "-ac", "2",
             "-c:a", "aac", "-b:a", "192k", str(out)]
    subprocess.run(args, capture_output=True, text=True, errors="ignore", check=True)
    return out


def build_video(video_in, audio_in, total, lead=0.0):
    log("[4/4] 合成最终视频（录屏 + 配音 + 字幕）…")
    out = VIDEO_DIR / "演示视频_30s.mp4"
    # 滤镜链里带盘符的路径无法转义冒号，统一复制到工作目录后用相对路径
    local_font = WORK / Path(FONT).name
    if not local_font.exists():
        shutil.copy2(FONT, local_font)
    # 录屏下方留出 64px 字幕带，避免字幕压住聊天输入框 / 按钮
    band = 64
    chain = ["crop=1920:1016:0:0", "setsar=1",
             "pad=1920:1080:0:0:0x0B1220",
             "fps=30", "format=yuv420p"]
    for i, seg in enumerate(SEGMENTS):
        tf = WORK / f"sub_{i}.txt"
        tf.write_text(seg["narr"], encoding="utf-8")
        # 字幕铺到下一段开始（末段铺到片尾），避免段落之间出现无字幕空档
        s = seg["start"]
        nxt = SEGMENTS[i + 1]["start"] if i + 1 < len(SEGMENTS) else total + 0.5
        e = max(seg["start"] + seg["dur"] + 0.25, nxt - 0.08)
        chain.append(
            f"drawtext=fontfile={local_font.name}:textfile={tf.name}"
            f":fontsize=34:fontcolor=white:shadowcolor=black@0.85:shadowx=2:shadowy=2"
            f":x=(w-tw)/2:y=1016+({band}-th)/2"
            f":enable='between(t,{s:.2f},{e:.2f})'"
        )
    vf = ",".join(chain)
    args = [FFMPEG, "-hide_banner", "-y"]
    if lead > 0:
        args += ["-ss", f"{lead:.2f}"]
    args += ["-i", str(video_in), "-i", str(audio_in),
            "-vf", vf, "-map", "0:v", "-map", "1:a",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
            "-t", f"{total:.2f}", "-movflags", "+faststart", str(out)]
    r = subprocess.run(args, capture_output=True, text=True, errors="ignore",
                       cwd=str(WORK))
    if r.returncode != 0:
        log(r.stderr[-2500:])
        raise RuntimeError("ffmpeg 合成失败")
    return out


# ══════════════════ main ════════════════════════════════════
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tts-only", action="store_true")
    a = ap.parse_args()

    gen_audio()
    if a.tts_only:
        return

    video_in, timeline, lead = record()
    for m in timeline:
        SEGMENTS[m["i"]]["start"] = m["t"]

    vdur = probe_duration(video_in) - lead
    total = min(vdur, SEGMENTS[-1]["start"] + SEGMENTS[-1]["dur"] + SEGMENTS[-1]["gap"])
    log(f"      录屏时长 {vdur:.2f}s（已裁掉开头 {lead:.2f}s），成片时长 {total:.2f}s")

    audio = build_audio(total + 0.6)
    final = build_video(video_in, audio, total, lead)
    log(f"\n✅ 完成：{final}")
    log(f"   尺寸 1920x1080 ｜ 时长 {total:.1f}s ｜ 配音 {VOICE}")


if __name__ == "__main__":
    main()
