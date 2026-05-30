#!/usr/bin/env python3
"""Analyze images (screenshots, photos) using vision-capable models via OpenRouter."""

import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import httpx

API_BASE = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "google/gemini-2.0-flash:free"
OCR_MODEL = "qwen/qwen-2.5-vl-72b-instruct:free"


def get_api_key() -> str:
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        sys.exit("Error: OPENROUTER_API_KEY not set. Add it to agentos/.env")
    return key


def encode_image(path: str) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def extract_video_frame(video_path: str, timestamp: str = "00:00:05") -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.close()
    result = subprocess.run(
        ["ffmpeg", "-ss", timestamp, "-i", video_path, "-vframes", "1", tmp.name],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        sys.exit(f"ffmpeg error: {result.stderr}")
    return tmp.name


def analyze(image_path: str, prompt: str, model: str) -> dict:
    api_key = get_api_key()
    b64 = encode_image(image_path)

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{b64}"},
                    },
                ],
            }
        ],
    }

    resp = httpx.post(
        f"{API_BASE}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


def main():
    parser = argparse.ArgumentParser(description="Analyze images with vision LLM")
    parser.add_argument("file", help="Path to image or video file")
    parser.add_argument("prompt", nargs="?", default="Describe what you see in detail",
                        help="Question about the image")
    parser.add_argument("--ocr", action="store_true",
                        help="Extract text from image (OCR mode)")
    parser.add_argument("--model", default=DEFAULT_MODEL,
                        help=f"Vision model (default: {DEFAULT_MODEL})")
    parser.add_argument("--frame", default="00:00:05",
                        help="Video timestamp to capture (default: 00:00:05)")

    args = parser.parse_args()

    path = args.file
    if not os.path.exists(path):
        sys.exit(f"File not found: {path}")

    ext = Path(path).suffix.lower()
    is_video = ext in (".mp4", ".mov", ".avi", ".mkv", ".webm")

    if is_video:
        print(f"Extracting frame at {args.frame}...")
        path = extract_video_frame(path, args.frame)
        print(f"Extracted to {path}")

    if args.ocr:
        prompt = "Extract all text from this image. Return only the extracted text, no commentary."
        model = OCR_MODEL
    else:
        prompt = args.prompt
        model = args.model

    print(f"Analyzing with {model}...")
    result = analyze(path, prompt, model)

    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
    model_used = result.get("model", model)

    print(f"\n{'='*60}")
    print(f"Model: {model_used}")
    print(f"{'='*60}")
    print(content)

    if is_video:
        os.unlink(path)


if __name__ == "__main__":
    main()
