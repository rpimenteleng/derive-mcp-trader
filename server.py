"""
Derive MCP Trading Server

Exposes Derive.xyz trading capabilities as MCP tools that can be
called by AI agents (e.g., Claude via Claude Desktop).
"""

import json
import logging
from decimal import Decimal
from typing import Optional

from mcp.server.fastmcp import FastMCP

from credentials import get_credentials
from derive_client import DeriveClient, OrderParams

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Create MCP server
mcp = FastMCP(
    "derive-trader",
    instructions=(
        "MCP server for trading on Derive.xyz (options, perps, spot). "
        "Use get_instruments and get_ticker to discover available markets. "
        "Use get_positions, get_open_orders, and get_balance to check account state. "
        "Use place_order to trade and cancel_order / cancel_all_orders to manage orders. "
        "⚠️ This server places REAL trades with REAL money. Always confirm with the user before placing or cancelling orders."
    ),
)

# ---------------------------------------------------------------------------
# Client singleton — initialized on first tool call
# ---------------------------------------------------------------------------
_client: Optional[DeriveClient] = None


def _get_client() -> DeriveClient:
    """Get or create the authenticated DeriveClient."""
    global _client
    if _client is None:
        creds = get_credentials()
        _client = DeriveClient(
            session_key=creds["session_key"],
            wallet_address=creds["wallet_address"],
            subaccount_id=creds["subaccount_id"],
            network=creds["network"],
        )
    return _client


# ===========================================================================
# Public tools (no auth required)
# ===========================================================================


@mcp.tool()
def get_instruments(currency: str = "ETH", kind: str = "option") -> str:
    """
    List available trading instruments on Derive.

    Args:
        currency: Base currency — "ETH" or "BTC"
        kind: Instrument type — "option", "perp", or "spot"

    Returns:
        JSON list of instruments with names and metadata.
    """
    client = _get_client()
    instruments = client.get_instruments(currency, kind)
    if not instruments:
        return f"No {currency} {kind} instruments found."

    # Return a concise summary
    names = [i.get("instrument_name", "N/A") for i in instruments]
    return json.dumps({
        "count": len(names),
        "currency": currency,
        "kind": kind,
        "instruments": names,
    }, indent=2)


@mcp.tool()
def get_ticker(instrument_name: str) -> str:
    """
    Get current price and market data for a specific instrument.

    Args:
        instrument_name: The instrument name, e.g. "ETH-20260130-3000-C" or "ETH-PERP"

    Returns:
        JSON with bid, ask, mark price, volume, open interest, etc.
    """
    client = _get_client()
    ticker = client.get_ticker(instrument_name)
    if not ticker:
        return f"Could not fetch ticker for {instrument_name}."
    return json.dumps(ticker, indent=2, default=str)


@mcp.tool()
def get_orderbook(instrument_name: str, depth: int = 10) -> str:
    """
    Get the order book (bids and asks) for an instrument.

    Args:
        instrument_name: The instrument name
        depth: Number of price levels to return (default 10)

    Returns:
        JSON with bids and asks arrays.
    """
    client = _get_client()
    book = client.get_orderbook(instrument_name, depth)
    if not book:
        return f"Could not fetch order book for {instrument_name}."
    return json.dumps(book, indent=2, default=str)


# ===========================================================================
# Private tools (auth required)
# ===========================================================================


@mcp.tool()
def get_positions() -> str:
    """
    Show all open positions for the authenticated account.

    Returns:
        JSON list of positions with instrument, side, size, average price, and P&L.
    """
    client = _get_client()
    positions = client.get_positions()
    if not positions:
        return "No open positions."

    result = []
    for p in positions:
        result.append({
            "instrument": p.instrument_name,
            "side": p.side,
            "amount": str(p.amount),
            "average_price": str(p.average_price),
            "unrealized_pnl": str(p.unrealized_pnl),
            "realized_pnl": str(p.realized_pnl),
        })
    return json.dumps(result, indent=2)


@mcp.tool()
def get_open_orders() -> str:
    """
    Show all open (pending) orders for the authenticated account.

    Returns:
        JSON list of open orders with instrument, direction, amount, price, and status.
    """
    client = _get_client()
    orders = client.get_open_orders()
    if not orders:
        return "No open orders."
    return json.dumps(orders, indent=2, default=str)


@mcp.tool()
def get_balance() -> str:
    """
    Show account collateral and balance information.

    Returns:
        JSON with collateral details per asset.
    """
    client = _get_client()
    collateral = client.get_collateral()
    if not collateral:
        return "Could not fetch balance."
    return json.dumps(collateral, indent=2, default=str)


@mcp.tool()
def place_order(
    instrument_name: str,
    side: str,
    amount: str,
    limit_price: str,
    order_type: str = "limit",
    time_in_force: str = "gtc",
    reduce_only: bool = False,
    post_only: bool = False,
) -> str:
    """
    Place a buy or sell order on Derive.

    ⚠️ This places a REAL order with REAL money. Confirm with the user first.

    Args:
        instrument_name: Instrument to trade, e.g. "ETH-PERP" or "ETH-20260130-3000-C"
        side: "buy" or "sell"
        amount: Order size as a decimal string, e.g. "0.1"
        limit_price: Limit price as a decimal string, e.g. "3000.00"
        order_type: "limit" (default) or "market"
        time_in_force: "gtc" (good til cancelled), "ioc" (immediate or cancel), "fok" (fill or kill)
        reduce_only: If True, only reduce an existing position
        post_only: If True, order will only be placed as a maker order

    Returns:
        JSON with order confirmation or error details.
    """
    if side not in ("buy", "sell"):
        return f"Invalid side '{side}'. Must be 'buy' or 'sell'."

    client = _get_client()
    params = OrderParams(
        instrument_name=instrument_name,
        side=side,
        amount=Decimal(amount),
        limit_price=Decimal(limit_price),
        order_type=order_type,
        time_in_force=time_in_force,
        reduce_only=reduce_only,
        post_only=post_only,
    )

    result = client.place_order(params)
    if "error" in result:
        return json.dumps({"status": "failed", "error": result["error"]}, indent=2, default=str)
    return json.dumps({"status": "success", "order": result}, indent=2, default=str)


@mcp.tool()
def cancel_order(order_id: str) -> str:
    """
    Cancel a specific open order by its ID.

    Args:
        order_id: The order ID to cancel (get this from get_open_orders).

    Returns:
        Confirmation message.
    """
    client = _get_client()
    if client.cancel_order(order_id):
        return json.dumps({"status": "success", "message": f"Order {order_id} cancelled."})
    return json.dumps({"status": "failed", "message": f"Failed to cancel order {order_id}."})


@mcp.tool()
def cancel_all_orders(instrument_name: Optional[str] = None) -> str:
    """
    Cancel all open orders, optionally filtered to a specific instrument.

    Args:
        instrument_name: If provided, only cancel orders for this instrument.

    Returns:
        Number of orders cancelled.
    """
    client = _get_client()
    count = client.cancel_all_orders(instrument_name)
    return json.dumps({"status": "success", "cancelled": count})


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    mcp.run()
