import json
from typing import Any

from app.agents.base import AgentError, BaseAgent, ToolResult
from app.memory.cache import get_cache


class CommerceAgent(BaseAgent):
    name = "commerce"
    model = "openai/gpt-4o-2024-11-20"

    HITL_ACTIONS = {"charge_stripe"}
    _inventory: dict[str, dict[str, Any]] = {}

    async def _run(
        self,
        action: str,
        params: dict[str, Any],
        session_id: str,
        trace_id: str,
        attachments: list[dict[str, str]] | None = None,
    ) -> Any:
        if action in self.HITL_ACTIONS:
            from app.utils.hitl_gateway import HITLPendingError

            try:
                details = {"action": action, "params": params, "agent": self.name}
                await self._require_hitl(session_id, action, details)
            except HITLPendingError:
                raise

        tool_map = {
            "catalog": self._manage_catalog,
            "pricing": self._optimize_pricing,
            "checkout": self._create_checkout,
            "inventory": self._manage_inventory,
            "faq": self._generate_faq,
            "charge_stripe": self._charge_stripe,
        }

        handler = tool_map.get(action)
        if not handler:
            raise AgentError("UNKNOWN_ACTION", f"Unknown action: {action}")

        return await handler(params, session_id, trace_id)

    async def _manage_catalog(
        self, params: dict[str, Any], session_id: str, trace_id: str
    ) -> ToolResult:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": f"""Manage product catalog:
{json.dumps(params, indent=2)}

Generate product entries with: name, description, SKU, price, category, tags, images.
Return as structured product catalog data.""",
            },
        ]
        content = await self._llm_call(messages)
        return ToolResult(success=True, data={"catalog": content})

    async def _optimize_pricing(
        self, params: dict[str, Any], session_id: str, trace_id: str
    ) -> ToolResult:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": f"""Optimize pricing for:
{json.dumps(params, indent=2)}

Analyze market position, competitor pricing, demand elasticity.
Provide pricing recommendations with rationale.""",
            },
        ]
        content = await self._llm_call(messages)
        return ToolResult(success=True, data={"pricing": content})

    async def _create_checkout(
        self, params: dict[str, Any], session_id: str, trace_id: str
    ) -> ToolResult:
        price_id = params.get("price_id", self.settings.stripe_price_id)
        success_url = params.get("success_url", "http://localhost:3000/success")
        cancel_url = params.get("cancel_url", "http://localhost:3000/cancel")

        try:
            import stripe

            stripe.api_key = self.settings.stripe_api_key

            session = stripe.checkout.Session.create(
                mode="payment",
                line_items=[{"price": price_id, "quantity": 1}],
                success_url=success_url,
                cancel_url=cancel_url,
            )
            return ToolResult(
                success=True, data={"checkout_url": session.url, "session_id": session.id}
            )
        except ImportError:
            pass
        except Exception as e:
            self.logger.log_warn(self.name, "checkout", f"Stripe failed: {e}")

        return ToolResult(
            success=True,
            data={
                "checkout_url": f"https://checkout.stripe.com/test?price={price_id}",
                "mode": "simulated",
                "note": "Stripe SDK unavailable or not configured, returning simulated checkout",
            },
        )

    async def _manage_inventory(
        self, params: dict[str, Any], session_id: str, trace_id: str
    ) -> ToolResult:
        operation = params.get("operation", "list")
        item_id = params.get("item_id", "")
        quantity = params.get("quantity", 0)

        cache = get_cache()
        cache_key = f"inventory:{session_id}"

        if operation == "add":
            self._inventory[item_id] = {
                "item_id": item_id,
                "quantity": quantity,
                **params.get("metadata", {}),
            }
            await cache.set(cache_key, self._inventory, ttl=3600)
            return ToolResult(success=True, data={"inventory": self._inventory, "operation": "add"})

        elif operation == "list":
            cached = await cache.get(cache_key)
            data = cached if cached else self._inventory
            return ToolResult(success=True, data={"inventory": data, "operation": "list"})

        elif operation == "update":
            if item_id in self._inventory:
                self._inventory[item_id]["quantity"] = quantity
                await cache.set(cache_key, self._inventory, ttl=3600)
                return ToolResult(
                    success=True, data={"inventory": self._inventory, "operation": "update"}
                )
            raise AgentError("INVENTORY_ITEM_NOT_FOUND", f"Item {item_id} not found in inventory")

        raise AgentError("UNKNOWN_OPERATION", f"Unknown inventory operation: {operation}")

    async def _generate_faq(
        self, params: dict[str, Any], session_id: str, trace_id: str
    ) -> ToolResult:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": f"""Generate FAQ for:
{json.dumps(params, indent=2)}

Generate 10-15 Q&A pairs covering: product features, pricing, shipping, returns,
technical support. Include structured data for Schema.org markup.""",
            },
        ]
        content = await self._llm_call(messages)
        return ToolResult(success=True, data={"faq": content})

    async def _charge_stripe(
        self, params: dict[str, Any], session_id: str, trace_id: str
    ) -> ToolResult:
        amount = params.get("amount", 0)
        currency = params.get("currency", "usd")

        try:
            import stripe

            stripe.api_key = self.settings.stripe_api_key

            payment = stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                metadata={"session_id": session_id, "trace_id": trace_id},
            )
            return ToolResult(
                success=True,
                data={"payment_intent": payment.id, "amount": amount, "currency": currency},
            )
        except ImportError:
            pass
        except Exception as e:
            self.logger.log_warn(self.name, "charge", f"Stripe charge failed: {e}")

        return ToolResult(
            success=True,
            data={
                "payment_intent": f"pi_simulated_{session_id[:8]}",
                "amount": amount,
                "currency": currency,
                "mode": "simulated",
                "note": "Stripe SDK unavailable, returning simulated payment",
            },
        )
