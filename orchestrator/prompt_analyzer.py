import re
from typing import Any

from models.user_context import UserContext
from orchestrator.routing_types import PromptFeatures


class PromptAnalyzer:
    def analyze(self, prompt: str, context: UserContext | None) -> PromptFeatures:
        text = prompt or ""
        words = self._tokenize_words(text)
        word_count = len(words)
        char_count = len(text)
        token_estimate = self._estimate_tokens(word_count, char_count)

        has_code = self._detect_code(text)
        has_logs = self._detect_logs(text)

        has_math = self._contains_phrase(
            text,
            [
                "calculate",
                "compute",
                "derive",
                "equation",
                "integral",
                "derivative",
                "probability",
                "statistics",
                "math",
            ],
        ) or bool(re.search(r"\d+\s*[\+\-\*/=]\s*\d+", text))

        has_analysis = self._contains_phrase(
            text,
            [
                "analyze",
                "analysis",
                "compare",
                "evaluate",
                "tradeoff",
                "multi-step",
                "multi step",
                "step-by-step",
                "step by step",
                "proof",
                "derive",
                "plan",
                "architecture",
            ],
        )

        has_creative = self._contains_phrase(
            text, ["poem", "story", "creative", "imagine", "metaphor", "character"]
        )

        has_factual = self._contains_phrase(
            text,
            [
                "what is",
                "what are",
                "how many",
                "how much",
                "price",
                "rate",
                "percentage",
                "percent",
                "latest",
                "recent",
                "today",
                "current",
            ],
        )

        strict_format = self._contains_phrase(
            text,
            [
                "json only",
                "respond in json",
                "no extra text",
                "exactly",
                "follow template",
                "strict format",
                "return only",
            ],
        )

        has_strict_constraints = bool(
            re.search(
                r"\bexactly\s+\d+\s+(bullets|bullet|items|steps|lines)\b", text, re.I
            )
        ) or self._contains_phrase(
            text,
            [
                "no extra text",
                "follow template exactly",
                "must follow the template",
                "output only",
                "long structured output",
            ],
        )

        context_tokens, context_messages = self._estimate_context_tokens(context)

        is_follow_up = False
        if context_messages > 0:
            is_follow_up = self._contains_phrase(
                text,
                ["continue", "refine this", "try again", "go on", "keep going"],
            ) and word_count <= 6

        needs_latest_info = self._contains_phrase(
            text,
            [
                "latest",
                "recent",
                "today",
                "this week",
                "this month",
                "this year",
                "current",
                "up to date",
            ],
        )

        needs_accuracy = self._contains_phrase(
            text,
            [
                "accurate",
                "precise",
                "exact",
                "verify",
                "fact check",
                "cite",
                "best quality",
                "deep reasoning",
                "production code",
                "step-by-step proof",
                "step by step proof",
            ],
        )

        intent = self._derive_intent(text, has_code, has_analysis)

        return PromptFeatures(
            word_count=word_count,
            char_count=char_count,
            token_estimate=token_estimate,
            has_code=has_code,
            has_math=has_math,
            has_analysis=has_analysis,
            has_creative=has_creative,
            has_factual=has_factual,
            strict_format=strict_format,
            has_logs_stacktrace=has_logs,
            context_token_estimate=context_tokens,
            context_messages=context_messages,
            is_follow_up=is_follow_up,
            needs_latest_info=needs_latest_info,
            needs_accuracy=needs_accuracy,
            intent=intent,
            has_strict_constraints=has_strict_constraints,
        )

    def _tokenize_words(self, text: str) -> list[str]:
        return re.findall(r"\b[\w'-]+\b", text)

    def _contains_phrase(self, text: str, patterns: list[str]) -> bool:
        for pattern in patterns:
            escaped = re.escape(pattern)
            if re.search(rf"\b{escaped}\b", text, re.I):
                return True
        return False

    def _detect_code(self, text: str) -> bool:
        if "```" in text:
            return True
        if re.search(r"\b(def|class|import|function|const|let|var)\b", text):
            return True
        if re.search(r"\{[\s\S]*\}", text) and ":" in text:
            return True

        symbol_count = sum(1 for ch in text if ch in "{}[]();:=<>")
        return len(text) > 0 and (symbol_count / max(len(text), 1)) > 0.08

    def _detect_logs(self, text: str) -> bool:
        patterns = [
            r"\btraceback\b",
            r"\bexception\b",
            r"\berror\b",
            r"\bwarn\b",
            r"\bfatal\b",
            r"\bat\s+\S+:\d+\b",
        ]
        return any(re.search(p, text, re.I) for p in patterns)

    def _estimate_tokens(self, words: int, chars: int) -> int:
        if words == 0 and chars == 0:
            return 0
        return max(int(words * 1.3), int(chars / 4))

    def _estimate_context_tokens(self, context: UserContext | None) -> tuple[int, int]:
        if not context or not context.conversation_history:
            return 0, 0

        total_tokens = 0
        for msg in context.conversation_history:
            content = msg.get("content", "")
            words = len(self._tokenize_words(content))
            total_tokens += self._estimate_tokens(words, len(content))

        return total_tokens, len(context.conversation_history)

    def _derive_intent(self, text: str, has_code: bool, has_analysis: bool) -> str:
        if self._contains_phrase(text, ["production code", "implementation plan", "test strategy"]):
            return "analysis"
        if self._contains_phrase(text, ["rewrite", "rephrase", "paraphrase"]):
            return "rewrite"
        if self._contains_phrase(text, ["summarize", "summary", "tl;dr"]):
            return "summarize"
        if self._contains_phrase(text, ["bullet", "bullets", "bullet points", "list"]):
            return "bullets"
        if self._contains_phrase(text, ["brainstorm", "ideas", "ideate"]):
            return "brainstorm"
        if has_code or self._contains_phrase(text, ["code", "implement", "bug", "stack trace"]):
            return "code"
        if has_analysis:
            return "analysis"
        return "general"
