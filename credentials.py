"""
Derive Trading Bot - Credentials Management

Prompts for session key, wallet address, and subaccount ID via stdin
(not logged in shell history) and saves them to a .env file.
Overwrites any existing credentials each time it is run.
"""

import os
import sys
from pathlib import Path
from getpass import getpass

ENV_FILE = Path(__file__).parent / ".env"


def load_env_file():
    """Load environment variables from .env file if it exists."""
    if ENV_FILE.exists():
        with open(ENV_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    value = value.strip().strip('"').strip("'")
                    os.environ[key] = value


def get_credentials() -> dict:
    """
    Load credentials from .env file.
    Raises ValueError if .env is missing or incomplete.
    """
    load_env_file()

    sk = os.environ.get("DERIVE_SESSION_KEY", "")
    wa = os.environ.get("DERIVE_WALLET_ADDRESS", "")
    sub = os.environ.get("DERIVE_SUBACCOUNT_ID", "")

    if not all([sk, wa, sub]):
        missing = [name for name, val in [
            ("DERIVE_SESSION_KEY", sk),
            ("DERIVE_WALLET_ADDRESS", wa),
            ("DERIVE_SUBACCOUNT_ID", sub),
        ] if not val]
        raise ValueError(
            f"Missing credentials: {', '.join(missing)}. "
            f"Run 'python credentials.py' to set them up."
        )

    return {
        "session_key": sk,
        "wallet_address": wa,
        "subaccount_id": int(sub),
        "network": os.environ.get("DERIVE_NETWORK", "mainnet"),
    }


def prompt_and_save():
    """Prompt for all three credentials and overwrite .env."""
    print("\n" + "=" * 60)
    print("🔐 DERIVE TRADING BOT - CREDENTIAL SETUP")
    print("=" * 60)
    print("\nAll input is hidden to prevent logging in shell history.\n")

    session_key = getpass("  Session Key (0x...):     ").strip()
    wallet_address = getpass("  Wallet Address (0x...):  ").strip()
    subaccount_id = getpass("  Subaccount ID:           ").strip()

    # Validate
    errors = []
    if not session_key.startswith("0x") or len(session_key) != 66:
        errors.append("Session key must be 66 chars (0x + 64 hex digits)")
    if not wallet_address.startswith("0x") or len(wallet_address) != 42:
        errors.append("Wallet address must be 42 chars (0x + 40 hex digits)")
    try:
        if int(subaccount_id) <= 0:
            raise ValueError
    except ValueError:
        errors.append("Subaccount ID must be a positive integer")

    if errors:
        print("\n❌ Validation errors:")
        for e in errors:
            print(f"   - {e}")
        sys.exit(1)

    with open(ENV_FILE, "w") as f:
        f.write("# Derive Trading Bot Credentials\n")
        f.write("# WARNING: Never commit this file to version control!\n\n")
        f.write(f'DERIVE_SESSION_KEY="{session_key}"\n')
        f.write(f'DERIVE_WALLET_ADDRESS="{wallet_address}"\n')
        f.write(f'DERIVE_SUBACCOUNT_ID="{subaccount_id}"\n')
        f.write('DERIVE_NETWORK="mainnet"\n')

    os.chmod(ENV_FILE, 0o600)
    print(f"\n✅ Credentials saved to {ENV_FILE} (permissions: 600)")
    print("\n📋 Saved values:")
    print(f"   Session Key:     {session_key[:6]}...{session_key[-4:]}")
    print(f"   Wallet Address:  {wallet_address}")
    print(f"   Subaccount ID:   {subaccount_id}")
    print(f"   Network:         mainnet")


if __name__ == "__main__":
    prompt_and_save()
