from google import genai
from google.genai import types


class GeminiClient:
    def __init__(self, api_key: str, model_name: str):
        self.client = genai.Client(
            api_key=api_key, http_options=types.HttpOptions(api_version="v1")  # stable v1
        )
        self.model_name = model_name or "gemini-2.5-flash"  # updated default

    def list_models(self) -> list[tuple[str, object]]:
        """Return (model_name, supported_methods) for debugging."""
        out = []
        for m in self.client.models.list():  # Models endpoint :contentReference[oaicite:2]{index=2}
            out.append((m.name, getattr(m, "supported_generation_methods", None)))
        return out
