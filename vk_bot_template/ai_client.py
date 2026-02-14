from __future__ import annotations

from openai import OpenAI


class HuggingFaceClient:
    def __init__(self, api_token: str, model: str, timeout: int = 30) -> None:
        self.api_token = api_token
        self.model = model
        self.timeout = timeout
        self.client: OpenAI | None = None
        if api_token:
            self.client = OpenAI(
                base_url='https://router.huggingface.co/v1',
                api_key=api_token,
            )

    def generate(self, user_message: str, user_name: str | None = None) -> str:
        question = user_message.strip()
        if not question:
            return 'Напишите вопрос текстом, и я постараюсь помочь.'
        if self.client is None:
            return 'Не удалось получить ответ от ИИ. Проверьте токен HF_API_TOKEN/HF_TOKEN.'

        system_hint = (
            'Ты лаконичный помощник VK-бота. '
            'Отвечай понятно и короткими абзацами на русском языке.'
        )
        user_prompt = f"Пользователь: {user_name or 'Пользователь'}\nВопрос: {question}"
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {'role': 'system', 'content': system_hint},
                {'role': 'user', 'content': user_prompt},
            ],
            temperature=0.7,
            max_tokens=180,
            timeout=self.timeout,
        )

        if not completion.choices:
            return 'Не удалось получить ответ от ИИ.'

        content = completion.choices[0].message.content
        if isinstance(content, str):
            cleaned = content.strip()
            if cleaned:
                normalized = cleaned.lower()
                generic_patterns = (
                    'не могу ответить без дополнительного контекста',
                    'предоставьте больше информации',
                    'уточните ваш запрос',
                )
                if any(pattern in normalized for pattern in generic_patterns):
                    return 'Уточните вопрос чуть подробнее: что именно нужно сделать или объяснить?'
                return cleaned

        return 'Не удалось получить ответ от ИИ.'
