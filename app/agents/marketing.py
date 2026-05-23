import json
import os
from typing import Any

from app.agents.base import AgentError, BaseAgent, ToolResult


class MarketingAgent(BaseAgent):
    name = "marketing"
    model = "anthropic/claude-sonnet-20241022"

    HITL_ACTIONS = {"create_campaign", "send_campaign"}

    async def _run(
        self, action: str, params: dict[str, Any], session_id: str, trace_id: str
    ) -> Any:
        if action in self.HITL_ACTIONS:
            from app.utils.hitl_gateway import HITLPendingError

            try:
                details = {"action": action, "params": params, "agent": self.name}
                await self._require_hitl(session_id, action, details)
            except HITLPendingError:
                raise

        tool_map = {
            "segment": self._segment_audience,
            "email": self._email_campaign,
            "ads": self._ads_campaign,
            "report": self._generate_report,
        }

        handler = tool_map.get(action)
        if not handler:
            raise AgentError("UNKNOWN_ACTION", f"Unknown action: {action}")

        return await handler(params, session_id, trace_id)

    async def _segment_audience(
        self, params: dict[str, Any], session_id: str, trace_id: str
    ) -> ToolResult:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": f"""Segment the audience based on:
{json.dumps(params, indent=2)}

Provide segments with: name, criteria, estimated size, engagement level,
and recommended approach for each segment.""",
            },
        ]
        content = await self._llm_call(messages)
        return ToolResult(success=True, data={"segments": content})

    async def _email_campaign(
        self, params: dict[str, Any], session_id: str, trace_id: str
    ) -> ToolResult:
        smtp_host = os.getenv("SMTP_HOST", "mailhog")
        smtp_port = int(os.getenv("SMTP_PORT", "1025"))

        if params.get("send") is True:
            try:
                import smtplib
                from email.mime.text import MIMEText

                msg = MIMEText(params.get("body", ""))
                msg["Subject"] = params.get("subject", "Campaign")
                msg["From"] = "agentos@localhost"
                msg["To"] = params.get("to", "test@localhost")

                with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
                    server.send_message(msg)

                return ToolResult(success=True, data={"email_sent": True, "to": params.get("to")})
            except Exception as e:
                self.logger.log_warn(self.name, "email", f"SMTP failed: {e}")

        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": f"""Create email campaign content for:
{json.dumps(params, indent=2)}

Generate: subject line (A/B variants), body HTML, preview text, CTA, UTM parameters.""",
            },
        ]
        content = await self._llm_call(messages)
        return ToolResult(success=True, data={"email_campaign": content, "mode": "draft"})

    async def _ads_campaign(
        self, params: dict[str, Any], session_id: str, trace_id: str
    ) -> ToolResult:
        has_meta_key = bool(os.getenv("META_ADS_ACCESS_TOKEN"))
        has_google_key = bool(os.getenv("GOOGLE_ADS_CLIENT_ID"))

        if has_meta_key and params.get("provider") == "meta":
            return ToolResult(
                success=True,
                data={"ads_platform": "meta", "status": "configured", "params": params},
            )

        if has_google_key and params.get("provider") == "google":
            return ToolResult(
                success=True,
                data={"ads_platform": "google", "status": "configured", "params": params},
            )

        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": f"""Create ad campaign plan for:
{json.dumps(params, indent=2)}

Generate: ad copy variants, target audience, budget allocation, schedule,
KPIs and tracking setup. (Running in stub mode - no real ads API keys configured)""",
            },
        ]
        content = await self._llm_call(messages)
        return ToolResult(
            success=True,
            data={
                "ads_plan": content,
                "mode": "stub",
                "note": "No ads API keys configured, running in simulation mode",
            },
        )

    async def _generate_report(
        self, params: dict[str, Any], session_id: str, trace_id: str
    ) -> ToolResult:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": f"""Generate marketing performance report for:
{json.dumps(params, indent=2)}

Include: KPIs, channel performance, ROI analysis, recommendations,
and next steps. Format as structured report.""",
            },
        ]
        content = await self._llm_call(messages)
        return ToolResult(success=True, data={"report": content})
