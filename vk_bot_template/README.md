# VK Bot Template

Template includes:

- custom and inline keyboards;
- user info retrieval;
- media attachment parsing (`photo`, `doc`);
- AI responses using Hugging Face Router (OpenAI-compatible API).

## Quick start

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Create `.env` from `env.example` and set tokens.

3. Run bot:

```bash
python bot.py
```

## Message scenarios

- `start` / `menu`: open custom keyboard.
- `help`: show command help.
- `user info`: show basic profile data.
- `media status`: show attachment counters from incoming message.
- `ask ai <question>`: direct call to AI.
- Any other text: AI fallback response.

## Notes

- If `HF_API_TOKEN`/`HF_TOKEN` is missing, bot returns a safe fallback message instead of crashing.
- You can switch model through `HF_MODEL`.
- If API returns `410 Gone`, the selected model is unavailable for HF Router; set another `HF_MODEL`.
