#!/usr/bin/env python3
"""把 WorkBuddy 会话 JSONL 导出为可读的 Markdown 对话记录。"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path


def clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit] + "\n...(截断)"


def fmt_ts(raw) -> str:
    if isinstance(raw, (int, float)):
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(raw / 1000))
    if isinstance(raw, str) and raw:
        return raw[:19].replace("T", " ")
    return ""


def from_content(content) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts = []
    for b in content:
        if not isinstance(b, dict):
            continue
        bt = b.get("type")
        if bt in ("text", "input_text", "output_text"):
            parts.append(b.get("text", ""))
        elif bt == "tool_use":
            args = json.dumps(b.get("input", {}), ensure_ascii=False)
            parts.append(f"**[调用工具 `{b.get('name','tool')}`]**\n\n```json\n{clip(args,500)}\n```")
        elif b.get("type") == "tool_result":
            c = b.get("content", "")
            if isinstance(c, list):
                c = "\n".join(x.get("text", "") for x in c if isinstance(x, dict))
            parts.append(f"**[工具返回]**\n\n```\n{clip(str(c),1500)}\n```")
    return "\n\n".join(p for p in parts if p)


NOISE = (
    "system-reminder",
    "identity_context",
    "product_identity",
    "current-expert",
    "connector-status",
    "memory_and_skills_reminder",
    "additional-data",
    "user_references",
    "craft_mode",
    "project_context",
    "user_info",
    "expert_selection",
    "attached_files",
)

# 公开仓库不应暴露本机用户名与绝对路径，统一替换为占位前缀。
# 用环境变量读取当前用户名，脚本本身不写死任何具体用户名。
_CURRENT_USER = os.environ.get("USERNAME") or os.environ.get("USER") or ""


def _build_replacements() -> tuple:
    """构造各种路径写法的替换规则，避免正则转义歧义。"""
    if not _CURRENT_USER:
        return ()
    u = _CURRENT_USER
    return (
        ("C:\\Users\\" + u, "<USER_HOME>"),
        ("C:/Users/" + u, "<USER_HOME>"),
        ("c/Users/" + u, "<USER_DIR>"),
        ("/c/Users/" + u, "<USER_HOME>"),
        ("c-Users-" + u, "<USER_DIR>"),
    )


_HOME_REPLACEMENTS = _build_replacements()


def sanitize(text: str) -> str:
    """移除本机用户名与路径，避免公开仓库泄露个人信息。"""
    for src, dst in _HOME_REPLACEMENTS:
        text = text.replace(src, dst)
    # 兜底：清除被工具输出截断后残留的用户名片段（如 ...c/Users/han）
    if _CURRENT_USER:
        text = re.sub(re.escape(_CURRENT_USER) + r"[A-Za-z0-9_\\/.-]*", "<USER_HOME>", text)
    return text


def strip_noise(body: str) -> str:
    """移除内部注入的系统提示词标签，只保留用户真实输入与助手输出。"""
    lines = body.split("\n")
    kept: list[str] = []
    skipping = False
    for ln in lines:
        if any(m in ln for m in NOISE):
            skipping = True
            continue
        if skipping:
            if ln.startswith("</") or not ln.strip():
                skipping = False
            continue
        kept.append(ln)
    return "\n".join(kept).strip()


def main() -> int:
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    out: list[str] = [
        "# WorkBuddy 开发对话记录",
        "",
        "本文件为麦门点单诸葛亮项目的真实开发对话记录，由WorkBuddy 会话存储直接导出。",
        "",
    ]
    role_cn = {"user": "用户", "assistant": "WorkBuddy"}
    n = 0
    calls = 0
    with src.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = d.get("type")
            ts = fmt_ts(d.get("timestamp"))

            if t == "message":
                role = d.get("role")
                if role not in role_cn:
                    continue
                body = from_content(d.get("content"))
                if role == "user":
                    body = strip_noise(body)
                body = body.strip()
                if not body:
                    continue
                n += 1
                out.append(f"## 对话 {n} · {role_cn[role]}　`{ts}`")
                out.append("")
                out.append(sanitize(body))
                out.append("")

            elif t == "function_call":
                calls += 1
                args = d.get("arguments", "")
                if not isinstance(args, str):
                    args = json.dumps(args, ensure_ascii=False)
                out.append(f"### 工具调用 {calls} · `{d.get('name','tool')}`　`{ts}`")
                out.append("")
                out.append(f"```json\n{clip(sanitize(args), 500)}\n```")
                out.append("")

            elif t == "function_call_result":
                o = d.get("output", "")
                if not isinstance(o, str):
                    o = json.dumps(o, ensure_ascii=False)
                out.append(f"#### 工具返回 · `{ts}`")
                out.append("")
                out.append(f"```\n{clip(sanitize(o), 900)}\n```")
                out.append("")

    dst.write_text("\n".join(out), encoding="utf-8")
    print(f"导出 {n} 条消息、{calls} 次工具调用 -> {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
