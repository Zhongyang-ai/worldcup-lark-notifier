from __future__ import annotations

import json
import logging
import time
from urllib.request import Request, urlopen

LOG = logging.getLogger("worldcup_bot")


class DeepSeekPredictor:
    URL = "https://api.deepseek.com/chat/completions"

    def __init__(self, api_key: str, model: str, timeout: int = 45):
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def predict(self, contexts: list[dict]) -> tuple[str, dict]:
        if not contexts:
            return "", {}
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self._system_prompt()},
                {
                    "role": "user",
                    "content": "请分析以下比赛。输入数据为 JSON：\n" + json.dumps(contexts, ensure_ascii=False),
                },
            ],
            "thinking": {"type": "enabled"},
            "reasoning_effort": "high",
            "response_format": {"type": "json_object"},
            "max_tokens": 6000,
            "temperature": 0.2,
            "stream": False,
        }
        result = self._post_with_retry(payload)
        content = result["choices"][0]["message"].get("content") or ""
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            LOG.warning("DeepSeek returned no valid JSON; retrying with medium reasoning")
            payload["reasoning_effort"] = "medium"
            payload["thinking"] = {"type": "enabled"}
            payload["max_tokens"] = 6000
            result = self._post_with_retry(payload)
            content = result["choices"][0]["message"].get("content") or ""
            if not content:
                raise RuntimeError("DeepSeek returned empty final content")
            parsed = json.loads(content)
        usage = result.get("usage", {})
        return self._format(parsed), usage

    def _post_with_retry(self, payload: dict) -> dict:
        body = json.dumps(payload).encode()
        last_error = None
        for attempt in range(2):
            try:
                request = Request(
                    self.URL,
                    data=body,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    method="POST",
                )
                with urlopen(request, timeout=self.timeout) as response:
                    return json.load(response)
            except Exception as exc:
                last_error = exc
                if attempt == 0:
                    time.sleep(2)
        raise RuntimeError(f"DeepSeek request failed: {last_error}")

    @staticmethod
    def _system_prompt() -> str:
        return """你是严谨的足球赛前分析师。只使用用户提供的事实，不得假装知道未提供的实时伤停、首发、排名或内部消息。
综合考虑：胜平负市场赔率及开盘到当前变化、让球与大小球、赛事记录、近期新闻、明确列出的伤停、交锋、场地和主客身份。
市场赔率是重要基线，但不要机械照抄；概率必须合计100。信息不足时降低confidence并明确说明。
不要给出下注指令或保证盈利。请输出合法JSON对象：
{"predictions":[{"match_id":"...","home":"...","away":"...","home_win":40,"draw":30,"away_win":30,"predicted_score":"1-1","over_under_view":"偏大/偏小/中性","btts_view":"是/否/中性","confidence":"低/中/高","key_factors":["最多3条简短依据"],"risks":["最多2条不确定性"]}]}
不得输出JSON之外的文字。"""

    @staticmethod
    def _format(parsed: dict) -> str:
        blocks = ["🤖 DeepSeek AI 赛前分析"]
        for item in parsed.get("predictions", []):
            factors = "；".join(str(value) for value in item.get("key_factors", [])[:3]) or "数据有限"
            risks = "；".join(str(value) for value in item.get("risks", [])[:2]) or "无额外信息"
            blocks.append(
                "\n{home} vs {away}\n"
                "胜平负：{home_win}% / {draw}% / {away_win}%\n"
                "预测比分：{score}｜大小球：{ou}｜双方进球：{btts}\n"
                "信心：{confidence}\n"
                "依据：{factors}\n"
                "风险：{risks}".format(
                    home=item.get("home", "主队"),
                    away=item.get("away", "客队"),
                    home_win=item.get("home_win", "?"),
                    draw=item.get("draw", "?"),
                    away_win=item.get("away_win", "?"),
                    score=item.get("predicted_score", "未知"),
                    ou=item.get("over_under_view", "中性"),
                    btts=item.get("btts_view", "中性"),
                    confidence=item.get("confidence", "低"),
                    factors=factors,
                    risks=risks,
                )
            )
        blocks.append("\n仅供参考，不构成投注建议。")
        return "\n".join(blocks)
