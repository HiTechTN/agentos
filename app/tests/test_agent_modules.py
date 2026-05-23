import builtins
import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.base import ToolResult
from app.agents.content import ContentAgent
from app.agents.dev import DevAgent
from app.agents.marketing import MarketingAgent
from app.utils.hitl_gateway import HITLPendingError

# =====================================================================
# MarketingAgent
# =====================================================================


@pytest.fixture
def marketing_agent(mock_llm_client: Any, mock_hitl_gateway: Any) -> MarketingAgent:
    return MarketingAgent()


class TestMarketingAgentRun:
    @pytest.mark.asyncio
    async def test_execute_hitl_create_campaign_hitl_called_then_unknown(
        self, marketing_agent: MarketingAgent
    ) -> None:
        result = await marketing_agent.execute(
            {"action": "create_campaign", "params": {"name": "test"}},
            session_id="s1",
            trace_id="t1",
        )
        assert result["success"] is False
        assert result["error"]["code"] == "UNKNOWN_ACTION"
        marketing_agent._hitl.request_approval.assert_awaited_once_with(  # type: ignore[attr-defined]
            session_id="s1",
            agent_name="marketing",
            action="create_campaign",
            details={"action": "create_campaign", "params": {"name": "test"}, "agent": "marketing"},
        )

    @pytest.mark.asyncio
    async def test_execute_hitl_send_campaign_pending_raises(
        self, marketing_agent: MarketingAgent
    ) -> None:
        marketing_agent._hitl.request_approval = AsyncMock(  # type: ignore[method-assign]
            side_effect=HITLPendingError("aid-55", "send_campaign")
        )
        with pytest.raises(HITLPendingError):
            await marketing_agent.execute(
                {"action": "send_campaign", "params": {}},
                session_id="s1",
                trace_id="t1",
            )

    @pytest.mark.asyncio
    async def test_execute_hitl_create_campaign_pending_raises(
        self, marketing_agent: MarketingAgent
    ) -> None:
        marketing_agent._hitl.request_approval = AsyncMock(  # type: ignore[method-assign]
            side_effect=HITLPendingError("aid-56", "create_campaign")
        )
        with pytest.raises(HITLPendingError):
            await marketing_agent.execute(
                {"action": "create_campaign", "params": {}},
                session_id="s1",
                trace_id="t1",
            )

    @pytest.mark.asyncio
    async def test_execute_non_hitl_action_segment_success(
        self, marketing_agent: MarketingAgent
    ) -> None:
        result = await marketing_agent.execute(
            {"action": "segment", "params": {"criteria": "age > 30"}},
            session_id="s1",
            trace_id="t1",
        )
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_unknown_action_returns_error(
        self, marketing_agent: MarketingAgent
    ) -> None:
        result = await marketing_agent.execute(
            {"action": "bogus", "params": {}},
            session_id="s1",
            trace_id="t1",
        )
        assert result["success"] is False
        assert result["error"]["code"] == "UNKNOWN_ACTION"


class TestMarketingAgentSegment:
    @pytest.mark.asyncio
    async def test_segment_audience_returns_tool_result(
        self, marketing_agent: MarketingAgent
    ) -> None:
        result = await marketing_agent._segment_audience({"criteria": "age > 30"}, "s1", "t1")
        assert isinstance(result, ToolResult)
        assert result.success is True
        assert "segments" in result.data


class TestMarketingAgentEmail:
    @pytest.mark.asyncio
    async def test_email_campaign_send_true_smtp_success(
        self, marketing_agent: MarketingAgent
    ) -> None:
        with patch("smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server
            result = await marketing_agent._email_campaign(
                {"send": True, "to": "user@test.com", "subject": "Hello", "body": "Content"},
                "s1",
                "t1",
            )
        assert result.success is True
        assert result.data["email_sent"] is True

    @pytest.mark.asyncio
    async def test_email_campaign_send_true_smtp_failure_falls_to_draft(
        self, marketing_agent: MarketingAgent
    ) -> None:
        with patch("smtplib.SMTP", side_effect=Exception("SMTP unreachable")):
            result = await marketing_agent._email_campaign(
                {"send": True, "to": "user@test.com", "subject": "Hi", "body": "Msg"},
                "s1",
                "t1",
            )
        assert result.success is True
        assert result.data["mode"] == "draft"

    @pytest.mark.asyncio
    async def test_email_campaign_no_send_returns_draft(
        self, marketing_agent: MarketingAgent
    ) -> None:
        result = await marketing_agent._email_campaign({"subject": "Test"}, "s1", "t1")
        assert result.success is True
        assert result.data["mode"] == "draft"

    @pytest.mark.asyncio
    async def test_email_campaign_send_false_returns_draft(
        self, marketing_agent: MarketingAgent
    ) -> None:
        result = await marketing_agent._email_campaign({"send": False}, "s1", "t1")
        assert result.success is True
        assert result.data["mode"] == "draft"


class TestMarketingAgentAds:
    @pytest.mark.asyncio
    async def test_ads_campaign_meta_configured(self, marketing_agent: MarketingAgent) -> None:
        with patch.dict(os.environ, {"META_ADS_ACCESS_TOKEN": "meta-token"}):
            result = await marketing_agent._ads_campaign(
                {"provider": "meta", "budget": 100},
                "s1",
                "t1",
            )
        assert result.success is True
        assert result.data["ads_platform"] == "meta"

    @pytest.mark.asyncio
    async def test_ads_campaign_google_configured(self, marketing_agent: MarketingAgent) -> None:
        with patch.dict(os.environ, {"GOOGLE_ADS_CLIENT_ID": "google-id"}):
            result = await marketing_agent._ads_campaign(
                {"provider": "google", "budget": 200},
                "s1",
                "t1",
            )
        assert result.success is True
        assert result.data["ads_platform"] == "google"

    @pytest.mark.asyncio
    async def test_ads_campaign_no_keys_stub_mode(self, marketing_agent: MarketingAgent) -> None:
        result = await marketing_agent._ads_campaign({"provider": "meta"}, "s1", "t1")
        assert result.success is True
        assert result.data["mode"] == "stub"

    @pytest.mark.asyncio
    async def test_ads_campaign_provider_not_matching_key_falls_to_stub(
        self, marketing_agent: MarketingAgent
    ) -> None:
        with patch.dict(os.environ, {"META_ADS_ACCESS_TOKEN": "meta-token"}):
            result = await marketing_agent._ads_campaign(
                {"provider": "google"},
                "s1",
                "t1",
            )
        assert result.success is True
        assert result.data["mode"] == "stub"


class TestMarketingAgentReport:
    @pytest.mark.asyncio
    async def test_generate_report_returns_tool_result(
        self, marketing_agent: MarketingAgent
    ) -> None:
        result = await marketing_agent._generate_report({"period": "Q1 2026"}, "s1", "t1")
        assert isinstance(result, ToolResult)
        assert result.success is True
        assert "report" in result.data


# =====================================================================
# ContentAgent
# =====================================================================


@pytest.fixture
def content_agent(mock_llm_client: Any, mock_hitl_gateway: Any) -> ContentAgent:
    return ContentAgent()


class TestContentAgentRun:
    @pytest.mark.asyncio
    async def test_execute_hitl_publish_approved(self, content_agent: ContentAgent) -> None:
        with patch("httpx.AsyncClient"):
            result = await content_agent.execute(
                {"action": "publish", "params": {"title": "Post", "content": "Body"}},
                session_id="s1",
                trace_id="t1",
            )
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_hitl_publish_pending_raises(self, content_agent: ContentAgent) -> None:
        content_agent._hitl.request_approval = AsyncMock(  # type: ignore[method-assign]
            side_effect=HITLPendingError("aid-33", "publish")
        )
        with pytest.raises(HITLPendingError):
            await content_agent.execute(
                {"action": "publish", "params": {}},
                session_id="s1",
                trace_id="t1",
            )

    @pytest.mark.asyncio
    async def test_execute_unknown_action_returns_error(self, content_agent: ContentAgent) -> None:
        result = await content_agent.execute(
            {"action": "nonexistent", "params": {}},
            session_id="s1",
            trace_id="t1",
        )
        assert result["success"] is False
        assert result["error"]["code"] == "UNKNOWN_ACTION"


class TestContentAgentWrite:
    @pytest.mark.asyncio
    async def test_write_content_returns_tool_result(self, content_agent: ContentAgent) -> None:
        result = await content_agent._write_content({"topic": "AI"}, "s1", "t1")
        assert isinstance(result, ToolResult)
        assert result.success is True
        assert "content" in result.data


class TestContentAgentImage:
    @pytest.mark.asyncio
    async def test_generate_image_replicate_success(self, content_agent: ContentAgent) -> None:
        content_agent.settings.replicate_api_token = "test-token"
        mock_client = MagicMock()
        mock_client.run.return_value = ["https://replicate.delivery/image.png"]
        with patch("replicate.Client", return_value=mock_client):
            result = await content_agent._generate_image({"prompt": "A cat"}, "s1", "t1")
        assert result.success is True
        assert result.data["image_url"] == "https://replicate.delivery/image.png"

    @pytest.mark.asyncio
    async def test_generate_image_replicate_returns_single_string(
        self, content_agent: ContentAgent
    ) -> None:
        content_agent.settings.replicate_api_token = "test-token"
        mock_client = MagicMock()
        mock_client.run.return_value = "https://replicate.delivery/single.png"
        with patch("replicate.Client", return_value=mock_client):
            result = await content_agent._generate_image({"prompt": "A dog"}, "s1", "t1")
        assert result.success is True
        assert result.data["image_url"] == "https://replicate.delivery/single.png"

    @pytest.mark.asyncio
    async def test_generate_image_replicate_exception_fallback(
        self, content_agent: ContentAgent
    ) -> None:
        content_agent.settings.replicate_api_token = "test-token"
        mock_client = MagicMock()
        mock_client.run.side_effect = Exception("Replicate API error")
        with patch("replicate.Client", return_value=mock_client):
            result = await content_agent._generate_image({"prompt": "test"}, "s1", "t1")
        assert result.success is True
        assert result.data["mode"] == "description_only"

    @pytest.mark.asyncio
    async def test_generate_image_no_token_fallback(self, content_agent: ContentAgent) -> None:
        content_agent.settings.replicate_api_token = ""
        result = await content_agent._generate_image({"description": "A landscape"}, "s1", "t1")
        assert result.success is True
        assert result.data["mode"] == "description_only"
        assert result.data["prompt"] == "A landscape"

    @pytest.mark.asyncio
    async def test_generate_image_default_prompt(self, content_agent: ContentAgent) -> None:
        content_agent.settings.replicate_api_token = ""
        result = await content_agent._generate_image({}, "s1", "t1")
        assert result.success is True
        assert result.data["prompt"] == "Generate an image"

    @pytest.mark.asyncio
    async def test_generate_image_import_error_fallback(self, content_agent: ContentAgent) -> None:
        content_agent.settings.replicate_api_token = "test-token"
        original_import = builtins.__import__

        def _block_replicate(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "replicate":
                raise ImportError(f"No module named '{name}'")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=_block_replicate):
            result = await content_agent._generate_image({"prompt": "blocked"}, "s1", "t1")
        assert result.success is True
        assert result.data["mode"] == "description_only"


class TestContentAgentCalendar:
    @pytest.mark.asyncio
    async def test_create_calendar_returns_tool_result(self, content_agent: ContentAgent) -> None:
        result = await content_agent._create_calendar({"month": "June"}, "s1", "t1")
        assert isinstance(result, ToolResult)
        assert result.success is True
        assert "calendar" in result.data


class TestContentAgentPublish:
    @pytest.mark.asyncio
    async def test_publish_cms_strapi_success(self, content_agent: ContentAgent) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"data": {"id": 42}}
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__.return_value = mock_client
        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await content_agent._publish_cms(
                {"title": "Article", "content": "# Hello"},
                "s1",
                "t1",
            )
        assert result.success is True
        assert result.data["cms"] == "strapi"
        assert result.data["id"] == 42

    @pytest.mark.asyncio
    async def test_publish_cms_strapi_non_200_falls_to_file(
        self, content_agent: ContentAgent
    ) -> None:
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__.return_value = mock_client
        with (
            patch("httpx.AsyncClient", return_value=mock_client),
            patch("builtins.open", MagicMock()),
            patch("os.makedirs"),
        ):
            result = await content_agent._publish_cms(
                {"title": "Article", "content": "Body"},
                "s1",
                "t1",
            )
        assert result.success is True
        assert result.data["cms"] == "markdown_file"

    @pytest.mark.asyncio
    async def test_publish_cms_strapi_exception_falls_to_file(
        self, content_agent: ContentAgent
    ) -> None:
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=Exception("Strapi unreachable"))
        mock_client.__aenter__.return_value = mock_client
        with (
            patch("httpx.AsyncClient", return_value=mock_client),
            patch("builtins.open", MagicMock()),
            patch("os.makedirs"),
        ):
            result = await content_agent._publish_cms(
                {"title": "Fallback", "content": "Saved as file"},
                "s1",
                "t1",
            )
        assert result.success is True
        assert result.data["cms"] == "markdown_file"

    @pytest.mark.asyncio
    async def test_publish_cms_non_strapi_cms_type_falls_to_file(
        self, content_agent: ContentAgent
    ) -> None:
        with patch("builtins.open", MagicMock()), patch("os.makedirs"):
            result = await content_agent._publish_cms(
                {"cms": "wordpress", "title": "WP Post", "content": "WP content"},
                "s1",
                "t1",
            )
        assert result.success is True
        assert result.data["cms"] == "markdown_file"

    @pytest.mark.asyncio
    async def test_publish_cms_uses_default_title_when_missing(
        self, content_agent: ContentAgent
    ) -> None:
        with patch("builtins.open", MagicMock()), patch("os.makedirs"):
            result = await content_agent._publish_cms(
                {"content": "Just content", "cms": "custom"},
                "s1",
                "t1",
            )
        assert result.success is True
        assert "content.md" in result.data["path"] or "content" in result.data["path"]


# =====================================================================
# DevAgent
# =====================================================================


@pytest.fixture
def dev_agent(mock_llm_client: Any, mock_hitl_gateway: Any) -> DevAgent:
    return DevAgent()


class TestDevAgentRun:
    @pytest.mark.asyncio
    async def test_execute_hitl_deploy_approved(self, dev_agent: DevAgent) -> None:
        result = await dev_agent.execute(
            {"action": "deploy", "params": {"target": "production"}},
            session_id="s1",
            trace_id="t1",
        )
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_hitl_deploy_pending_raises(self, dev_agent: DevAgent) -> None:
        dev_agent._hitl.request_approval = AsyncMock(  # type: ignore[method-assign]
            side_effect=HITLPendingError("aid-77", "deploy")
        )
        with pytest.raises(HITLPendingError):
            await dev_agent.execute(
                {"action": "deploy", "params": {}},
                session_id="s1",
                trace_id="t1",
            )

    @pytest.mark.asyncio
    async def test_execute_unknown_action_returns_error(self, dev_agent: DevAgent) -> None:
        result = await dev_agent.execute(
            {"action": "nonexistent", "params": {}},
            session_id="s1",
            trace_id="t1",
        )
        assert result["success"] is False
        assert result["error"]["code"] == "UNKNOWN_ACTION"


class TestDevAgentScaffold:
    @pytest.mark.asyncio
    async def test_scaffold_returns_tool_result(self, dev_agent: DevAgent) -> None:
        result = await dev_agent._scaffold({"prompt": "Create a FastAPI app"}, "s1", "t1")
        assert isinstance(result, ToolResult)
        assert result.success is True
        assert "plan" in result.data

    @pytest.mark.asyncio
    async def test_scaffold_uses_default_prompt(self, dev_agent: DevAgent) -> None:
        result = await dev_agent._scaffold({}, "s1", "t1")
        assert isinstance(result, ToolResult)
        assert result.success is True


class TestDevAgentTests:
    @pytest.mark.asyncio
    async def test_run_tests_returns_tool_result(self, dev_agent: DevAgent) -> None:
        result = await dev_agent._run_tests({"framework": "pytest", "module": "utils"}, "s1", "t1")
        assert isinstance(result, ToolResult)
        assert result.success is True
        assert "tests" in result.data

    @pytest.mark.asyncio
    async def test_run_tests_uses_default_framework(self, dev_agent: DevAgent) -> None:
        result = await dev_agent._run_tests({}, "s1", "t1")
        assert isinstance(result, ToolResult)
        assert result.success is True
        assert "tests" in result.data


class TestDevAgentLint:
    @pytest.mark.asyncio
    async def test_run_lint_returns_tool_result(self, dev_agent: DevAgent) -> None:
        result = await dev_agent._run_lint({"path": "src/"}, "s1", "t1")
        assert isinstance(result, ToolResult)
        assert result.success is True
        assert "lint_report" in result.data


class TestDevAgentDeploy:
    @pytest.mark.asyncio
    async def test_deploy_returns_tool_result(self, dev_agent: DevAgent) -> None:
        result = await dev_agent._deploy({"target": "staging"}, "s1", "t1")
        assert isinstance(result, ToolResult)
        assert result.success is True
        assert "deployment" in result.data

    @pytest.mark.asyncio
    async def test_deploy_uses_default_target(self, dev_agent: DevAgent) -> None:
        result = await dev_agent._deploy({}, "s1", "t1")
        assert isinstance(result, ToolResult)
        assert result.success is True
        assert result.data["target"] == "staging"


class TestDevAgentAnalyze:
    @pytest.mark.asyncio
    async def test_analyze_returns_tool_result(self, dev_agent: DevAgent) -> None:
        result = await dev_agent._analyze({"code": "print('hello')"}, "s1", "t1")
        assert isinstance(result, ToolResult)
        assert result.success is True
        assert "analysis" in result.data
