"""
Derive Trading Bot - API Client

Wraps the derive_action_signing SDK and provides high-level trading functions.
"""

import json
import logging
from decimal import Decimal
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

import requests
from web3 import Web3

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# API endpoints
# Note: api.derive.xyz may not resolve; api.lyra.finance is the working hostname
ENDPOINTS = {
    "mainnet": {
        "rest": "https://api.lyra.finance",
        "ws": "wss://api.lyra.finance/ws",
    },
    "testnet": {
        "rest": "https://api-demo.lyra.finance",
        "ws": "wss://api-demo.lyra.finance/ws",
    },
}

# Protocol constants
# ACTION_TYPEHASH is network-independent (it's a hash of the EIP-712 type struct).
# DOMAIN_SEPARATOR and module addresses differ per network.
# Source: https://github.com/8ball030/lyra_client  (lyra/constants.py)
PROTOCOL_CONSTANTS = {
    "mainnet": {
        "DOMAIN_SEPARATOR": "0xd96e5f90797da7ec8dc4e276260c7f3f87fedf68775fbe1ef116e996fc60441b",
        "ACTION_TYPEHASH": "0x4d7a9f27c403ff9c0f19bce61d76d82f9aa29f8d6d4b0c5474607d9770d1af17",
        "TRADE_MODULE_ADDRESS": "0xB8D20c2B7a1Ad2EE33Bc50eF10876eD3035b5e7b",
    },
    "testnet": {
        "DOMAIN_SEPARATOR": "0x9bcf4dc06df5d8bf23af818d5716491b995020f377d3b7b64c29ed14e3dd1105",
        "ACTION_TYPEHASH": "0x4d7a9f27c403ff9c0f19bce61d76d82f9aa29f8d6d4b0c5474607d9770d1af17",
        "TRADE_MODULE_ADDRESS": "0x87F2863866D85E3192a35A73b388BD625D83f2be",
    },
}


@dataclass
class OrderParams:
    """Parameters for placing an order."""
    instrument_name: str  # e.g., "ETH-20260130-3000-C"
    side: str  # "buy" or "sell"
    amount: Decimal  # Size of the order
    limit_price: Decimal  # Price per contract
    order_type: str = "limit"  # "limit" or "market"
    time_in_force: str = "gtc"  # "gtc", "ioc", "fok"
    reduce_only: bool = False
    post_only: bool = False


@dataclass
class Position:
    """Represents an open position."""
    instrument_name: str
    side: str
    amount: Decimal
    average_price: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal


class DeriveClient:
    """
    Client for interacting with Derive.xyz API.
    
    Handles authentication, order signing, and API calls.
    """
    
    def __init__(
        self,
        session_key: str,
        wallet_address: str,
        subaccount_id: int,
        network: str = "mainnet",
    ):
        """
        Initialize the Derive client.
        
        Args:
            session_key: Private key for session key (hex string with 0x prefix)
            wallet_address: Derive wallet address (smart contract wallet)
            subaccount_id: Subaccount ID for trading
            network: "mainnet" or "testnet"
        """
        self.session_key = session_key
        self.wallet_address = wallet_address
        self.subaccount_id = subaccount_id
        self.network = network
        
        # Set up web3 account from session key
        self.w3 = Web3()
        self.signer = self.w3.eth.account.from_key(session_key)
        
        # API endpoints
        self.rest_url = ENDPOINTS[network]["rest"]
        self.ws_url = ENDPOINTS[network]["ws"]
        
        # Session for HTTP requests
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "X-LyraWallet": wallet_address,
        })
        
        # Auth state
        self._authenticated: bool = False
        
        logger.info(f"DeriveClient initialized for {network}")
        logger.info(f"Wallet: {wallet_address}")
        logger.info(f"Subaccount: {subaccount_id}")
        logger.info(f"Signer: {self.signer.address}")
    
    # =========================================================================
    # Authentication
    # =========================================================================
    
    def login(self) -> bool:
        """
        Authenticate with the Derive API using session key.
        
        Uses the SDK's sign_rest_auth_header to produce the correct
        EIP-191 signed timestamp headers.
        
        Returns:
            True if login successful, False otherwise.
        """
        try:
            from derive_action_signing import utils as sdk_utils

            auth_headers = sdk_utils.sign_rest_auth_header(
                self.w3, self.wallet_address, self.session_key
            )
            self.session.headers.update(auth_headers)
            
            # Verify authentication by hitting a private endpoint
            response = self._post("/private/get_subaccount", {
                "subaccount_id": self.subaccount_id,
            })
            
            if response and "result" in response:
                logger.info("✅ Login successful")
                self._authenticated = True
                return True
            
            logger.error(f"Login failed: {response}")
            return False
            
        except Exception as e:
            logger.error(f"Login error: {e}")
            return False
    
    # =========================================================================
    # Public API (no auth required)
    # =========================================================================
    
    def get_instruments(self, currency: str = "ETH", kind: str = "option") -> List[Dict]:
        """
        Get available instruments.
        
        Args:
            currency: Base currency (ETH, BTC)
            kind: Instrument type (option, perp, spot)
        
        Returns:
            List of instrument dictionaries
        """
        response = self._post("/public/get_instruments", {
            "currency": currency,
            "instrument_type": kind,
            "expired": False,
        })
        return response.get("result", []) if response else []
    
    def get_ticker(self, instrument_name: str) -> Optional[Dict]:
        """Get ticker/price info for an instrument."""
        response = self._post("/public/get_ticker", {
            "instrument_name": instrument_name,
        })
        return response.get("result") if response else None
    
    def get_orderbook(self, instrument_name: str, depth: int = 10) -> Optional[Dict]:
        """Get orderbook for an instrument."""
        response = self._post("/public/get_order_book", {
            "instrument_name": instrument_name,
            "depth": depth,
        })
        return response.get("result") if response else None
    
    # =========================================================================
    # Private API (auth required)
    # =========================================================================
    
    def get_account(self) -> Optional[Dict]:
        """Get account information."""
        self._ensure_authenticated()
        response = self._post("/private/get_account", {
            "subaccount_id": self.subaccount_id,
        })
        return response.get("result") if response else None
    
    def get_positions(self) -> List[Position]:
        """Get all open positions."""
        self._ensure_authenticated()
        response = self._post("/private/get_positions", {
            "subaccount_id": self.subaccount_id,
        })
        
        positions = []
        if response and "result" in response:
            for p in response["result"].get("positions", []):
                positions.append(Position(
                    instrument_name=p.get("instrument_name", ""),
                    side="long" if float(p.get("amount", 0)) > 0 else "short",
                    amount=Decimal(str(abs(float(p.get("amount", 0))))),
                    average_price=Decimal(str(p.get("average_price", 0))),
                    unrealized_pnl=Decimal(str(p.get("unrealized_pnl", 0))),
                    realized_pnl=Decimal(str(p.get("realized_pnl", 0))),
                ))
        
        return positions
    
    def get_open_orders(self) -> List[Dict]:
        """Get all open orders."""
        self._ensure_authenticated()
        response = self._post("/private/get_open_orders", {
            "subaccount_id": self.subaccount_id,
        })
        if response and "result" in response:
            return response["result"].get("orders", [])
        return []
    
    def get_collateral(self) -> Optional[list]:
        """Get collateral/balance information."""
        self._ensure_authenticated()
        response = self._post("/private/get_collaterals", {
            "subaccount_id": self.subaccount_id,
        })
        if response and "result" in response:
            return response["result"].get("collaterals", [])
        return None
    
    # =========================================================================
    # Order Management
    # =========================================================================
    
    def place_order(self, params: OrderParams) -> Dict:
        """
        Place a new order.
        
        Args:
            params: OrderParams with order details
        
        Returns:
            Dict with either {"order": ...} on success
            or {"error": "..."} on failure.
        """
        self._ensure_authenticated()
        
        logger.info(f"Placing order: {params.side} {params.amount} {params.instrument_name} @ {params.limit_price}")
        
        try:
            # Import signing module
            from derive_action_signing import SignedAction, TradeModuleData, utils
            
            # Get instrument details for asset address
            ticker = self.get_ticker(params.instrument_name)
            if not ticker:
                msg = f"Could not get ticker for {params.instrument_name}"
                logger.error(msg)
                return {"error": msg}
            
            # Build signed action
            action = SignedAction(
                subaccount_id=self.subaccount_id,
                owner=self.wallet_address,
                signer=self.signer.address,
                signature_expiry_sec=utils.MAX_INT_32,
                nonce=utils.get_action_nonce(),
                module_address=PROTOCOL_CONSTANTS[self.network]["TRADE_MODULE_ADDRESS"],
                module_data=TradeModuleData(
                    asset_address=ticker.get("base_asset_address"),
                    sub_id=int(ticker.get("base_asset_sub_id", 0)),
                    limit_price=params.limit_price,
                    amount=params.amount if params.side == "buy" else -params.amount,
                    max_fee=Decimal("1000"),  # Max fee willing to pay
                    recipient_id=self.subaccount_id,
                    is_bid=params.side == "buy",
                ),
                DOMAIN_SEPARATOR=PROTOCOL_CONSTANTS[self.network]["DOMAIN_SEPARATOR"],
                ACTION_TYPEHASH=PROTOCOL_CONSTANTS[self.network]["ACTION_TYPEHASH"],
            )
            
            # Sign the action
            action.sign(self.signer.key)
            
            # Submit order — merge the signed action fields into the order payload
            order_payload = {
                "instrument_name": params.instrument_name,
                "direction": params.side,
                "order_type": params.order_type,
                "mmp": False,
                "time_in_force": params.time_in_force,
                "reduce_only": params.reduce_only,
                "post_only": params.post_only,
                **action.to_json(),
            }
            
            response = self._post("/private/order", order_payload)
            
            if response and "result" in response:
                logger.info(f"✅ Order placed: {response['result']}")
                return response["result"]
            elif response and "error" in response:
                err = response["error"]
                msg = f"{err.get('message', 'Unknown')} — {err.get('data', '')}"
                logger.error(f"Order rejected: {msg}")
                return {"error": msg}
            else:
                logger.error(f"Order failed: {response}")
                return {"error": f"Unexpected response: {response}"}
                
        except ImportError:
            msg = "derive_action_signing not installed. Run: pip install derive_action_signing"
            logger.error(msg)
            return {"error": msg}
        except Exception as e:
            import traceback
            logger.error(f"Order error: {traceback.format_exc()}")
            return {"error": str(e)}
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order."""
        self._ensure_authenticated()
        
        response = self._post("/private/cancel", {
            "subaccount_id": self.subaccount_id,
            "order_id": order_id,
        })
        
        if response and "result" in response:
            logger.info(f"✅ Order {order_id} cancelled")
            return True
        
        logger.error(f"Cancel failed: {response}")
        return False
    
    def cancel_all_orders(self, instrument_name: Optional[str] = None) -> int:
        """
        Cancel all open orders.
        
        Args:
            instrument_name: If provided, only cancel orders for this instrument
        
        Returns:
            Number of orders cancelled
        """
        self._ensure_authenticated()
        
        payload = {"subaccount_id": self.subaccount_id}
        if instrument_name:
            payload["instrument_name"] = instrument_name
        
        response = self._post("/private/cancel_all", payload)
        
        if response and "result" in response:
            result = response["result"]
            # API returns either "ok" (string) or a dict with details
            if isinstance(result, str) and result == "ok":
                logger.info("✅ All orders cancelled")
                return 1  # At least one cancelled
            elif isinstance(result, dict):
                count = result.get("cancelled", 1)
                logger.info(f"✅ Cancelled {count} orders")
                return count
            else:
                logger.info(f"✅ Cancel result: {result}")
                return 1
        
        return 0
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _refresh_auth_headers(self):
        """Refresh the EIP-191 auth headers with a fresh timestamp."""
        from derive_action_signing import utils as sdk_utils
        auth_headers = sdk_utils.sign_rest_auth_header(
            self.w3, self.wallet_address, self.session_key
        )
        self.session.headers.update(auth_headers)

    def _ensure_authenticated(self):
        """Ensure we have authenticated with the API."""
        if not self._authenticated:
            if not self.login():
                raise RuntimeError("Authentication required but login failed")
        # Always refresh auth headers to prevent stale timestamps
        self._refresh_auth_headers()
    
    def _post(self, endpoint: str, payload: Dict) -> Optional[Dict]:
        """Make a POST request to the API."""
        url = f"{self.rest_url}{endpoint}"
        
        try:
            response = self.session.post(url, json=payload, timeout=30)
            
            # Try to parse JSON body regardless of status code
            try:
                body = response.json()
            except ValueError:
                body = None
            
            if not response.ok:
                logger.error(f"HTTP {response.status_code}: {response.text[:500]}")
                if response.status_code == 403:
                    logger.error("⚠️  403 Forbidden — possible geo-restriction. Try a VPN.")
                # Return the JSON body if we got one (it may contain error details)
                return body
            
            return body
        except Exception as e:
            logger.error(f"Request error: {e}")
            return None


# =============================================================================
# Convenience Functions
# =============================================================================

def create_client_from_env() -> DeriveClient:
    """Create a DeriveClient using credentials from .env file."""
    from credentials import get_credentials
    
    creds = get_credentials()
    
    return DeriveClient(
        session_key=creds["session_key"],
        wallet_address=creds["wallet_address"],
        subaccount_id=creds["subaccount_id"],
        network=creds["network"],
    )


if __name__ == "__main__":
    # Quick test
    client = create_client_from_env()
    
    print("\n" + "=" * 60)
    print("🔍 TESTING API CONNECTION")
    print("=" * 60)
    
    # Test public endpoint (no auth)
    print("\n📊 Fetching ETH options instruments...")
    instruments = client.get_instruments("ETH", "option")
    if instruments:
        print(f"   Found {len(instruments)} instruments")
        if instruments:
            print(f"   Example: {instruments[0].get('instrument_name', 'N/A')}")
    else:
        print("   ❌ Failed to fetch instruments")
    
    # Test auth
    print("\n🔐 Testing authentication...")
    if client.login():
        print("   ✅ Auth successful")
        
        # Test private endpoint
        print("\n💰 Fetching account info...")
        account = client.get_account()
        if account:
            print(f"   Account: {json.dumps(account, indent=2)[:500]}...")
        else:
            print("   ❌ Failed to fetch account")
        
        print("\n📈 Fetching positions...")
        positions = client.get_positions()
        if positions:
            for pos in positions:
                print(f"   {pos.instrument_name}: {pos.side} {pos.amount} @ {pos.average_price}")
        else:
            print("   No open positions")
        
        print("\n💵 Fetching collateral...")
        collateral = client.get_collateral()
        if collateral:
            print(f"   Collateral: {json.dumps(collateral, indent=2)[:500]}...")
    else:
        print("   ❌ Auth failed")
    
    print("\n" + "=" * 60)
