# Vision Analysis Skill — AgentOS

Analyze images and videos using vision-capable LLMs via OpenRouter.

## Available Vision Models

| Model | Context | Best For |
|-------|---------|----------|
| `google/gemini-2.0-flash:free` | 1M tokens | Fast, general-purpose |
| `google/gemini-2.0-pro:free` | 2M tokens | Complex analysis |
| `qwen/qwen-2.5-vl-72b-instruct:free` | 128K tokens | Screenshots, UI, OCR |

## CLI Usage

```bash
# Analyze a single screenshot
python3 .agents/skills/vision-analysis/vision.py path/to/screenshot.png "Describe the error shown"

# OCR — extract text from image
python3 .agents/skills/vision-analysis/vision.py path/to/screenshot.png --ocr

# Analyze a frame from video at timestamp
python3 .agents/skills/vision-analysis/vision.py path/to/video.mp4 --frame 00:01:30 "What is displayed?"
```

## API Usage (via AgentOS)

```python
from app.utils.api_clients import LLMClient
from app.utils.llm_router import WorkType

client = LLMClient()
response = await client.chat(
    model="qwen/qwen-2.5-vl-72b-instruct:free",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "What's in this screenshot?"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
            ]
        }
    ]
)
```

## Requirements

- `OPENROUTER_API_KEY` set in `.env`
- For video: `ffmpeg` installed
