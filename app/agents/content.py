import json
import os
import tempfile
from typing import Any

import httpx

from app.agents.base import AgentError, BaseAgent, ToolResult
from app.utils.hitl_gateway import HITLPendingError


class ContentAgent(BaseAgent):
    name = "content"
    model = "openai/gpt-4o-2024-11-20"

    HITL_ACTIONS = {"publish"}

    async def _run(
        self, action: str, params: dict[str, Any], session_id: str, trace_id: str
    ) -> Any:
        if action in self.HITL_ACTIONS:
            try:
                details = {"action": action, "params": params, "agent": self.name}
                await self._require_hitl(session_id, action, details)
            except HITLPendingError:
                raise

        tool_map = {
            "write": self._write_content,
            "image": self._generate_image,
            "calendar": self._create_calendar,
            "publish": self._publish_cms,
        }

        handler = tool_map.get(action)
        if not handler:
            raise AgentError("UNKNOWN_ACTION", f"Unknown action: {action}")

        return await handler(params, session_id, trace_id)

    async def _write_content(
        self, params: dict[str, Any], session_id: str, trace_id: str
    ) -> ToolResult:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": f"""Write SEO-optimized content for:
{json.dumps(params, indent=2)}

Generate full article with: H1/H2/H3 structure, meta description, keyword integration,
readability score target > 60. Return as structured markdown.""",
            },
        ]
        content = await self._llm_call(messages)
        return ToolResult(success=True, data={"content": content})

    async def _generate_image(
        self, params: dict[str, Any], session_id: str, trace_id: str
    ) -> ToolResult:
        prompt = params.get("prompt", params.get("description", "Generate an image"))
        try:
            import replicate

            if self.settings.replicate_api_token:
                client: Any = replicate.Client(api_token=self.settings.replicate_api_token)
                output = client.run(
                    "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",
                    input={"prompt": prompt},
                )
                image_url = str(output[0]) if isinstance(output, list) else str(output)
                return ToolResult(success=True, data={"image_url": image_url, "prompt": prompt})
        except ImportError:
            pass
        except Exception as e:
            self.logger.log_warn(
                self.name, "image_gen", f"Replicate unavailable, using LLM description: {e}"
            )

        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": f"""Describe the image to generate for:
{prompt}

Provide detailed image description including composition, colors, style, and mood.
Note: Image generation API is in fallback mode, returning prompt only.""",
            },
        ]
        content = await self._llm_call(messages)
        return ToolResult(
            success=True,
            data={"image_description": content, "prompt": prompt, "mode": "description_only"},
        )

    async def _create_calendar(
        self, params: dict[str, Any], session_id: str, trace_id: str
    ) -> ToolResult:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": f"""Create editorial calendar for:
{json.dumps(params, indent=2)}

Generate a 4-week calendar with topics, publish dates, content types, keywords,
and distribution channels. Return as structured data.""",
            },
        ]
        content = await self._llm_call(messages)
        return ToolResult(success=True, data={"calendar": content})

    async def _publish_cms(
        self, params: dict[str, Any], session_id: str, trace_id: str
    ) -> ToolResult:
        cms_type = params.get("cms", "strapi")
        if cms_type == "strapi":
            try:
                async with httpx.AsyncClient(base_url="http://strapi:1337", timeout=30) as client:
                    payload = {
                        "data": {
                            "title": params.get("title", "Untitled"),
                            "content": params.get("content", ""),
                            "status": "published",
                        }
                    }
                    resp = await client.post("/api/articles", json=payload)
                    if resp.status_code in (200, 201):
                        return ToolResult(
                            success=True,
                            data={"cms": "strapi", "id": resp.json().get("data", {}).get("id")},
                        )
            except Exception as e:
                self.logger.log_warn(self.name, "cms_publish", f"Strapi unavailable: {e}")

        content = params.get("content", "")
        tmp_dir = os.path.join(tempfile.gettempdir(), "agentos_content")
        os.makedirs(tmp_dir, exist_ok=True)
        path = os.path.join(tmp_dir, f"{params.get('title', 'content').replace(' ', '_')}.md")
        with open(path, "w") as f:
            f.write(content)
        return ToolResult(
            success=True,
            data={
                "cms": "markdown_file",
                "path": path,
                "note": "Strapi unavailable, content saved as Markdown",
            },
        )
