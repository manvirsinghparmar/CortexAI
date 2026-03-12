from models.user_context import UserContext
from orchestrator.prompt_analyzer import PromptAnalyzer


def test_detect_code_and_logs():
    analyzer = PromptAnalyzer()
    prompt = "```python\nprint('hi')\n```\nTraceback (most recent call last):\nException: boom"
    features = analyzer.analyze(prompt, context=None)
    assert features.has_code is True
    assert features.has_logs_stacktrace is True


def test_follow_up_detection():
    analyzer = PromptAnalyzer()
    context = UserContext(conversation_history=[{"role": "user", "content": "Explain X"}])
    features = analyzer.analyze("continue", context=context)
    assert features.is_follow_up is True


def test_detail_follow_up_detection_with_context():
    analyzer = PromptAnalyzer()
    context = UserContext(
        conversation_history=[
            {"role": "user", "content": "Who is war between Iran and Israel going on?"},
            {"role": "assistant", "content": "Detailed answer with sources."},
        ]
    )
    features = analyzer.analyze("can you be a bit more detailed on it?", context=context)
    assert features.has_analysis is True
    assert features.is_follow_up is True


def test_strict_constraints_detection():
    analyzer = PromptAnalyzer()
    features = analyzer.analyze("Give exactly 3 bullets and no extra text.", context=None)
    assert features.has_strict_constraints is True


def test_quality_intent_detection():
    analyzer = PromptAnalyzer()
    features = analyzer.analyze("Need best quality production code with deep reasoning.", context=None)
    assert features.needs_accuracy is True
