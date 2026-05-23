import json
from .base import CSVImporter, HoldingDTO, TransactionDTO
from datetime import date


class GenericClaudeImporter(CSVImporter):
    """Claude-powered fallback parser for unknown CSV formats."""

    async def parse(self, content: bytes, filename: str) -> list[HoldingDTO]:
        from anthropic import AsyncAnthropic
        from config import settings

        preview = content[:3000].decode("utf-8", errors="replace")
        client = AsyncAnthropic(api_key=settings.anthropic_api_key)

        prompt = f"""You are a financial data parser. Extract holdings from this file content.

File: {filename}
Content preview:
{preview}

Return a JSON array where each item has:
- instrument_type: "mutual_fund" | "stock" | "fixed_deposit" | "ppf" | "nps"
- display_name: string (fund/stock name)
- asset_class: "equity" | "debt" | "gold" | "cash"
- invested_amount: integer (INR paise — multiply rupees by 100)
- current_value: integer (INR paise)
- metadata: object with relevant fields (units, nav, symbol, quantity, etc.)

Return ONLY a valid JSON array, no explanation."""

        try:
            msg = await client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = msg.content[0].text.strip()
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            items = json.loads(raw.strip())
        except Exception:
            return []

        holdings = []
        for item in items:
            try:
                holdings.append(HoldingDTO(
                    instrument_type=item.get("instrument_type", "stock"),
                    display_name=item.get("display_name", "Unknown"),
                    asset_class=item.get("asset_class", "equity"),
                    invested_amount=int(item.get("invested_amount", 0)),
                    current_value=int(item.get("current_value", 0)),
                    metadata=item.get("metadata", {}),
                    confidence_score=0.7,
                    warnings=["Parsed by Claude AI — please review before importing"],
                ))
            except (KeyError, TypeError, ValueError):
                continue

        return holdings
