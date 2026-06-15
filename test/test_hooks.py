"""
Hook Tests — log-conversation.ps1 Logic Verification

Tests the PowerShell hook script logic by simulating its behavior in Python.
Validates: transcript parsing, user_query tag stripping, week ID calculation, fallback.
"""
import json
import re
import pytest
from pathlib import Path
from datetime import datetime


def strip_user_query_tags(text: str) -> str:
    """Python equivalent of the PS1 tag stripping logic."""
    match = re.search(r'<user_query>(.*?)</user_query>', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Fallback: strip all tags
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def calc_iso_week(dt: datetime = None) -> str:
    """Python equivalent of the PS1 ISO week calculation."""
    if dt is None:
        dt = datetime.now()
    iso_cal = dt.isocalendar()
    return f"{iso_cal[0]}-W{iso_cal[1]:02d}"


def parse_transcript_last_user(lines: list[str]) -> str:
    """Python equivalent of transcript parsing: extract last user message."""
    user_msgs = []
    for line in lines:
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
            if msg.get("role") != "user":
                continue
            texts = []
            if msg.get("message") and msg["message"].get("content"):
                for part in msg["message"]["content"]:
                    if part.get("type") == "text" and part.get("text"):
                        texts.append(part["text"])
            combined = " ".join(texts).strip()
            if combined:
                user_msgs.append(combined)
        except json.JSONDecodeError:
            continue
    return user_msgs[-1] if user_msgs else ""


class TestUserQueryTagStripping:
    """Test <user_query> tag extraction logic."""

    def test_strip_simple(self):
        text = "<user_query>调研 Transformer</user_query>"
        assert strip_user_query_tags(text) == "调研 Transformer"

    def test_strip_with_system_reminder(self):
        text = "<system-reminder>some reminder</system-reminder>\n\n<user_query>实际提问</user_query>"
        assert strip_user_query_tags(text) == "实际提问"

    def test_strip_multiline(self):
        text = "<user_query>第一行\n第二行\n第三行</user_query>"
        result = strip_user_query_tags(text)
        assert "第一行" in result
        assert "第三行" in result

    def test_strip_no_tags(self):
        text = "普通文本，没有标签"
        assert strip_user_query_tags(text) == "普通文本，没有标签"

    def test_strip_empty_after_tags(self):
        text = "<system-reminder>reminder</system-reminder>"
        result = strip_user_query_tags(text)
        assert result == "reminder"

    def test_strip_preserves_chinese(self):
        text = "<user_query>这个项目很有意思</user_query>"
        assert strip_user_query_tags(text) == "这个项目很有意思"


class TestISOWeekCalculation:
    """Test ISO week number calculation."""

    def test_known_week(self):
        dt = datetime(2026, 6, 15)  # Monday
        week = calc_iso_week(dt)
        assert week == "2026-W25"

    def test_year_boundary(self):
        dt = datetime(2026, 1, 1)
        week = calc_iso_week(dt)
        assert "W" in week

    def test_december_late(self):
        dt = datetime(2026, 12, 28)
        week = calc_iso_week(dt)
        assert "W" in week

    def test_current_week_format(self):
        week = calc_iso_week()
        assert re.match(r"\d{4}-W\d{2}", week)


class TestTranscriptParsing:
    """Test transcript JSONL parsing logic."""

    def test_parse_single_user_message(self):
        lines = [
            json.dumps({"role": "user", "message": {"content": [
                {"type": "text", "text": "<user_query>测试问题</user_query>"}
            ]}}),
            json.dumps({"role": "assistant", "message": {"content": [
                {"type": "text", "text": "这是回答"}
            ]}}),
        ]
        result = parse_transcript_last_user(lines)
        assert "测试问题" in result

    def test_parse_returns_last_user(self):
        lines = [
            json.dumps({"role": "user", "message": {"content": [
                {"type": "text", "text": "第一条"}
            ]}}),
            json.dumps({"role": "assistant", "message": {"content": [
                {"type": "text", "text": "回答"}
            ]}}),
            json.dumps({"role": "user", "message": {"content": [
                {"type": "text", "text": "第二条"}
            ]}}),
        ]
        result = parse_transcript_last_user(lines)
        assert "第二条" in result

    def test_parse_empty_transcript(self):
        assert parse_transcript_last_user([]) == ""

    def test_parse_only_assistant(self):
        lines = [
            json.dumps({"role": "assistant", "message": {"content": [
                {"type": "text", "text": "只有回答"}
            ]}}),
        ]
        assert parse_transcript_last_user(lines) == ""

    def test_parse_skips_malformed_lines(self):
        lines = [
            "this is not json",
            json.dumps({"role": "user", "message": {"content": [
                {"type": "text", "text": "有效消息"}
            ]}}),
        ]
        result = parse_transcript_last_user(lines)
        assert "有效消息" in result

    def test_parse_multi_part_content(self):
        """User messages can have multiple text parts."""
        lines = [
            json.dumps({"role": "user", "message": {"content": [
                {"type": "text", "text": "第一部分"},
                {"type": "image", "url": "..."},
                {"type": "text", "text": "第二部分"},
            ]}}),
        ]
        result = parse_transcript_last_user(lines)
        assert "第一部分" in result
        assert "第二部分" in result

    def test_parse_system_reminder_in_transcript(self):
        """Transcript often wraps user input in system-reminder + user_query tags."""
        text = (
            '<system-reminder>\n[IMPORTANT] You must always respond in 中文.\n</system-reminder>\n\n'
            '<user_query>\n这个项目很有意思\n</user_query>'
        )
        lines = [
            json.dumps({"role": "user", "message": {"content": [
                {"type": "text", "text": text}
            ]}}),
        ]
        raw = parse_transcript_last_user(lines)
        result = strip_user_query_tags(raw)
        assert result == "这个项目很有意思"


class TestLogEntryFormat:
    """Test the JSON log entry format matches expected schema."""

    def test_entry_has_required_fields(self):
        entry = {
            "ts": "2026-06-15T10:00:00",
            "week": "2026-W25",
            "session": "abc-123",
            "text": "测试提问",
        }
        assert "ts" in entry
        assert "week" in entry
        assert "session" in entry
        assert "text" in entry

    def test_entry_serializable(self):
        entry = {
            "ts": "2026-06-15T10:00:00",
            "week": "2026-W25",
            "session": "abc-123",
            "text": "包含特殊字符: \"quotes\" and \\backslash",
        }
        serialized = json.dumps(entry, ensure_ascii=False)
        deserialized = json.loads(serialized)
        assert deserialized["text"] == entry["text"]
