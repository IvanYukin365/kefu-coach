# -*- coding: utf-8 -*-
"""
大模型接入层
====================================================================
兼容 OpenAI Chat Completions 协议，可直接对接：
  · 中国移动 MoMA 模型服务平台 / 九天大模型
  · DeepSeek、通义千问、智谱 GLM、火山方舟等
  · 任意自建 OpenAI 兼容网关

未配置密钥时自动降级为「离线演示模式」——客户回复走内置脚本，
评分走确定性规则引擎，保证现场演示 100% 可用。

配置方式（**不在界面上填，避免泄露给访客**）：
  · Streamlit Cloud：App → Settings → Secrets
  · 本地 / Docker：.streamlit/secrets.toml 或环境变量

    LLM_API_KEY  = "sk-xxxxxxxx"
    LLM_BASE_URL = "https://api.deepseek.com/v1"   # 可选
    LLM_MODEL    = "deepseek-chat"                 # 可选
====================================================================
"""

import os

_DEFAULT = {
    "LLM_API_KEY": "",
    "LLM_BASE_URL": "https://api.deepseek.com/v1",
    "LLM_MODEL": "deepseek-chat",
}


def _env(name: str) -> str:
    """读取配置：Secrets（secrets.toml / 云端面板）> 环境变量 > 默认值。

    注意：Streamlit Cloud 的 Secrets **不会**自动写入 os.environ，
    仅读 os.environ 会导致云端部署时永远处于离线演示模式。
    """
    try:
        import streamlit as st
        v = st.secrets.get(name, None)                   # type: ignore[union-attr]
        if v:
            return str(v).strip()
    except Exception:
        pass
    return os.environ.get(name, _DEFAULT.get(name, "")).strip()


def get_config():
    return {
        "api_key": _env("LLM_API_KEY"),
        "base_url": _env("LLM_BASE_URL"),
        "model": _env("LLM_MODEL"),
    }


def online() -> bool:
    return bool(get_config()["api_key"])


def chat(messages, temperature=0.7, max_tokens=400, timeout=30):
    """返回 str；失败返回 None，调用方需自行降级。"""
    cfg = get_config()
    if not cfg["api_key"]:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"], timeout=timeout)
        resp = client.chat.completions.create(
            model=cfg["model"], messages=messages,
            temperature=temperature, max_tokens=max_tokens,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception:
        return None
