import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.base import AgentError, ToolResult
from app.agents.commerce import CommerceAgent
from app.utils.hitl_gateway import HITLPendingError


@pytest.fixture
def agent(mock_llm_client: Any, mock_hitl_gateway: Any) -> CommerceAgent:
    CommerceAgent._inventory = {}
    return CommerceAgent()


class TestCommerceAgentRun:
    @pytest.mark.asyncio
    async def test_execute_hitl_charge_stripe_approved(self, agent: CommerceAgent) -> None:
        mock_stripe = MagicMock()
        mock_stripe.PaymentIntent.create.return_value = MagicMock(id="pi_test")
        with patch.dict("sys.modules", {"stripe": mock_stripe}):
            result = await agent.execute(
                {"action": "charge_stripe", "params": {"amount": 2000}},
                session_id="s1",
                trace_id="t1",
            )
        assert result["success"] is True
        assert result["result"].data["payment_intent"] == "pi_test"

    @pytest.mark.asyncio
    async def test_execute_hitl_charge_stripe_pending_raises(self, agent: CommerceAgent) -> None:
        agent._hitl.request_approval = AsyncMock(  # type: ignore[method-assign]
            side_effect=HITLPendingError("aid-99", "charge_stripe")
        )
        with pytest.raises(HITLPendingError):
            await agent.execute(
                {"action": "charge_stripe", "params": {}},
                session_id="s1",
                trace_id="t1",
            )

    @pytest.mark.asyncio
    async def test_execute_unknown_action_returns_error(self, agent: CommerceAgent) -> None:
        result = await agent.execute(
            {"action": "nonexistent", "params": {}},
            session_id="s1",
            trace_id="t1",
        )
        assert result["success"] is False
        assert result["error"]["code"] == "UNKNOWN_ACTION"


class TestCommerceAgentCatalog:
    @pytest.mark.asyncio
    async def test_manage_catalog_returns_tool_result(self, agent: CommerceAgent) -> None:
        result = await agent._manage_catalog({"product": "widget"}, "s1", "t1")
        assert isinstance(result, ToolResult)
        assert result.success is True
        assert result.data["catalog"] == "Mocked LLM response"


class TestCommerceAgentPricing:
    @pytest.mark.asyncio
    async def test_optimize_pricing_returns_tool_result(self, agent: CommerceAgent) -> None:
        result = await agent._optimize_pricing({"product": "gadget"}, "s1", "t1")
        assert isinstance(result, ToolResult)
        assert result.success is True
        assert "pricing" in result.data


class TestCommerceAgentCheckout:
    @pytest.mark.asyncio
    async def test_checkout_stripe_success(self, agent: CommerceAgent) -> None:
        mock_stripe = MagicMock()
        mock_session = MagicMock(url="https://checkout.stripe.com/pay/cs_test", id="cs_test_123")
        mock_stripe.checkout.Session.create.return_value = mock_session
        with patch.dict("sys.modules", {"stripe": mock_stripe}):
            result = await agent._create_checkout({"price_id": "price_123"}, "s1", "t1")
        assert result.success is True
        assert result.data["checkout_url"] == "https://checkout.stripe.com/pay/cs_test"
        assert result.data["session_id"] == "cs_test_123"

    @pytest.mark.asyncio
    async def test_checkout_stripe_exception_fallback(self, agent: CommerceAgent) -> None:
        mock_stripe = MagicMock()
        mock_stripe.checkout.Session.create.side_effect = Exception("Stripe API error")
        with patch.dict("sys.modules", {"stripe": mock_stripe}):
            result = await agent._create_checkout({"price_id": "price_123"}, "s1", "t1")
        assert result.success is True
        assert result.data["mode"] == "simulated"

    @pytest.mark.asyncio
    async def test_checkout_stripe_import_error_fallback(self, agent: CommerceAgent) -> None:
        result = await agent._create_checkout({}, "s1", "t1")
        assert result.success is True
        assert result.data["mode"] == "simulated"

    @pytest.mark.asyncio
    async def test_checkout_uses_defaults_when_params_empty(self, agent: CommerceAgent) -> None:
        mock_stripe = MagicMock()
        mock_session = MagicMock(url="https://checkout.stripe.com/pay/cs_test", id="cs_test_123")
        mock_stripe.checkout.Session.create.return_value = mock_session
        with patch.dict("sys.modules", {"stripe": mock_stripe}):
            result = await agent._create_checkout({}, "s1", "t1")
        assert result.success is True
        _, kwargs = mock_stripe.checkout.Session.create.call_args
        assert kwargs["line_items"][0]["price"] == agent.settings.stripe_price_id
        assert kwargs["success_url"] == "http://localhost:3000/success"
        assert kwargs["cancel_url"] == "http://localhost:3000/cancel"


class TestCommerceAgentInventory:
    @pytest.mark.asyncio
    async def test_inventory_add_operation(self, agent: CommerceAgent) -> None:
        mock_cache = MagicMock()
        mock_cache.set = AsyncMock(return_value=True)
        with patch("app.agents.commerce.get_cache", return_value=mock_cache):
            result = await agent._manage_inventory(
                {
                    "operation": "add",
                    "item_id": "item_1",
                    "quantity": 10,
                    "metadata": {"color": "red"},
                },
                "s1",
                "t1",
            )
        assert result.success is True
        assert result.data["operation"] == "add"
        assert result.data["inventory"]["item_1"]["quantity"] == 10
        assert result.data["inventory"]["item_1"]["color"] == "red"

    @pytest.mark.asyncio
    async def test_inventory_list_operation_no_cache(self, agent: CommerceAgent) -> None:
        mock_cache = MagicMock()
        mock_cache.get = AsyncMock(return_value=None)
        with patch("app.agents.commerce.get_cache", return_value=mock_cache):
            result = await agent._manage_inventory({"operation": "list"}, "s1", "t1")
        assert result.success is True
        assert result.data["operation"] == "list"
        assert result.data["inventory"] == {}

    @pytest.mark.asyncio
    async def test_inventory_list_operation_with_cache(self, agent: CommerceAgent) -> None:
        cached_data = {"item_2": {"item_id": "item_2", "quantity": 5}}
        mock_cache = MagicMock()
        mock_cache.get = AsyncMock(return_value=cached_data)
        with patch("app.agents.commerce.get_cache", return_value=mock_cache):
            result = await agent._manage_inventory({"operation": "list"}, "s1", "t1")
        assert result.success is True
        assert result.data["inventory"] == cached_data

    @pytest.mark.asyncio
    async def test_inventory_update_existing_item(self, agent: CommerceAgent) -> None:
        agent._inventory["item_x"] = {"item_id": "item_x", "quantity": 1}
        mock_cache = MagicMock()
        mock_cache.set = AsyncMock(return_value=True)
        with patch("app.agents.commerce.get_cache", return_value=mock_cache):
            result = await agent._manage_inventory(
                {"operation": "update", "item_id": "item_x", "quantity": 42},
                "s1",
                "t1",
            )
        assert result.success is True
        assert result.data["operation"] == "update"
        assert agent._inventory["item_x"]["quantity"] == 42

    @pytest.mark.asyncio
    async def test_inventory_update_missing_item_raises_error(self, agent: CommerceAgent) -> None:
        with pytest.raises(AgentError) as exc:
            await agent._manage_inventory(
                {"operation": "update", "item_id": "ghost", "quantity": 10},
                "s1",
                "t1",
            )
        assert exc.value.code == "INVENTORY_ITEM_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_inventory_unknown_operation_raises_error(self, agent: CommerceAgent) -> None:
        with pytest.raises(AgentError) as exc:
            await agent._manage_inventory({"operation": "delete"}, "s1", "t1")
        assert exc.value.code == "UNKNOWN_OPERATION"


class TestCommerceAgentFaq:
    @pytest.mark.asyncio
    async def test_generate_faq_returns_tool_result(self, agent: CommerceAgent) -> None:
        result = await agent._generate_faq({"product": "widget"}, "s1", "t1")
        assert isinstance(result, ToolResult)
        assert result.success is True
        assert "faq" in result.data


class TestCommerceAgentCharge:
    @pytest.mark.asyncio
    async def test_charge_stripe_import_error_fallback(self, agent: CommerceAgent) -> None:
        with patch.dict("sys.modules"):
            sys.modules.pop("stripe", None)
            for k in list(sys.modules):
                if k.startswith("stripe."):
                    del sys.modules[k]
            result = await agent._charge_stripe({"amount": 1000}, "s1", "t1")
        assert result.success is True
        assert result.data["mode"] == "simulated"
        assert "pi_simulated" in result.data["payment_intent"]

    @pytest.mark.asyncio
    async def test_charge_stripe_success(self, agent: CommerceAgent) -> None:
        mock_stripe = MagicMock()
        mock_stripe.PaymentIntent.create.return_value = MagicMock(id="pi_test_abc")
        with patch.dict("sys.modules", {"stripe": mock_stripe}):
            result = await agent._charge_stripe({"amount": 5000, "currency": "eur"}, "s1", "t1")
        assert result.success is True
        assert result.data["payment_intent"] == "pi_test_abc"
        assert result.data["amount"] == 5000
        assert result.data["currency"] == "eur"

    @pytest.mark.asyncio
    async def test_charge_stripe_exception_fallback(self, agent: CommerceAgent) -> None:
        mock_stripe = MagicMock()
        mock_stripe.PaymentIntent.create.side_effect = Exception("API error")
        with patch.dict("sys.modules", {"stripe": mock_stripe}):
            result = await agent._charge_stripe({"amount": 1000}, "s1", "t1")
        assert result.success is True
        assert result.data["mode"] == "simulated"
        assert "pi_simulated" in result.data["payment_intent"]

    @pytest.mark.asyncio
    async def test_charge_stripe_uses_default_currency(self, agent: CommerceAgent) -> None:
        mock_stripe = MagicMock()
        mock_stripe.PaymentIntent.create.return_value = MagicMock(id="pi_def")
        with patch.dict("sys.modules", {"stripe": mock_stripe}):
            result = await agent._charge_stripe({"amount": 1000}, "s1", "t1")
        assert result.success is True
        _, kwargs = mock_stripe.PaymentIntent.create.call_args
        assert kwargs["currency"] == "usd"
        assert kwargs["metadata"]["session_id"] == "s1"
        assert kwargs["metadata"]["trace_id"] == "t1"
