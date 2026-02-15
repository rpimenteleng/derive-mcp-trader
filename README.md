# Derive MCP Trading Server

An MCP (Model Context Protocol) server that exposes [Derive.xyz](https://derive.xyz) trading capabilities as tools for AI agents like Claude.

## ⚠️ Important Warnings

### Real Money
This server places **real trades with real cryptocurrency**. Use at your own risk:
- Start with small amounts
- Test thoroughly before using larger positions
- Never invest more than you can afford to lose

### Geo-Restrictions
**Derive.xyz may block access from certain countries, including Canada.** If you receive 403 Forbidden errors, you may need to use a VPN connected to an allowed region.

## Setup

### 1. Install Dependencies

```bash
cd derive-mcp-trader
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Generate a Session Key

```bash
python generate_session_key.py
```

This prints a private key and address. **Save the private key** — you'll need it in step 4.

### 3. Register the Session Key on Derive

1. Go to [app.derive.xyz](https://app.derive.xyz)
2. Navigate to: **Home → Developers → Session Keys**
3. Register the **address** from step 2 as a new session key
4. Note your **Derive Wallet** address and **Subaccount ID** from the Developers page

### 4. Save Credentials

```bash
python credentials.py
```

This prompts for your session key, wallet address, and subaccount ID via hidden input (not logged in shell history) and saves them to a `.env` file with `600` permissions.

### 5. Run the MCP Server

```bash
source .venv/bin/activate
python server.py
```

## Claude Desktop Configuration

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "derive-trader": {
      "command": "/path/to/derive-mcp-trader/.venv/bin/python",
      "args": ["/path/to/derive-mcp-trader/server.py"]
    }
  }
}
```

Replace `/path/to/derive-mcp-trader` with the actual path to this directory.

## Available MCP Tools

### Market Data (public, no auth)
| Tool | Description |
|---|---|
| `get_instruments` | List available instruments by currency and type (option/perp/spot) |
| `get_ticker` | Get price, volume, and market data for an instrument |
| `get_orderbook` | Get bids and asks for an instrument |

### Account (authenticated)
| Tool | Description |
|---|---|
| `get_positions` | Show all open positions with P&L |
| `get_open_orders` | Show all pending orders |
| `get_balance` | Show collateral and balance per asset |

### Trading (authenticated)
| Tool | Description |
|---|---|
| `place_order` | Place a buy or sell order (limit/market) |
| `cancel_order` | Cancel a specific order by ID |
| `cancel_all_orders` | Cancel all open orders (optionally for one instrument) |

## Project Structure

```
derive-mcp-trader/
├── server.py                # MCP server entry point
├── derive_client.py         # API client (auth, signing, REST calls)
├── credentials.py           # Standalone credential setup (writes .env)
├── generate_session_key.py  # Generate Ethereum keypair for session key
├── requirements.txt         # Python dependencies
├── README.md                # This file
└── .env                     # Credentials (auto-created, gitignored)
```

## Security

- **Session Keys**: Use session keys instead of your main wallet private key
- **Hidden Input**: `credentials.py` uses `getpass` — nothing logged in shell history
- **Permissions**: `.env` is created with 600 permissions (owner only)
- **Revocation**: You can revoke session keys anytime via the Derive UI
- **Never commit**: `.env` should never be committed to version control

## Troubleshooting

### 403 Forbidden Error
Derive.xyz may block access from certain countries. Use a VPN connected to an allowed region.

### Authentication Failed
- Verify your session key is correct and hasn't expired
- Check that the Derive Wallet address matches your account
- Ensure the session key is registered for your subaccount

### Missing Credentials Error
Run `python credentials.py` to set up or re-enter your credentials.

### Protocol Constants
If `place_order` fails with signing errors, the protocol constants in `derive_client.py` may need updating from [docs.derive.xyz/reference/protocol-constants](https://docs.derive.xyz/reference/protocol-constants).

## Resources

- [Derive Documentation](https://docs.derive.xyz)
- [API Reference](https://docs.derive.xyz/reference)
- [derive_action_signing PyPI](https://pypi.org/project/derive-action-signing/)
- [Protocol Constants](https://docs.derive.xyz/reference/protocol-constants)
- [MCP Specification](https://modelcontextprotocol.io)
