"""
Quick WhatsApp sandbox test script.

Usage:
    python scripts/test_whatsapp.py +1YOURNUMBER

Prerequisites:
    1. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM in .env
    2. Join the Twilio sandbox from your phone first (see instructions below)
"""
import sys
import os

# Add project root to path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


def check_config():
    """Verify Twilio env vars are set."""
    sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    token = os.getenv("TWILIO_AUTH_TOKEN", "")
    from_num = os.getenv("TWILIO_WHATSAPP_FROM", "")

    issues = []
    if not sid or sid.startswith("your-"):
        issues.append("TWILIO_ACCOUNT_SID not set")
    if not token or token.startswith("your-"):
        issues.append("TWILIO_AUTH_TOKEN not set")
    if not from_num:
        issues.append("TWILIO_WHATSAPP_FROM not set")

    if issues:
        print("\n--- Configuration Issues ---")
        for i in issues:
            print(f"  - {i}")
        print("\nFix these in your .env file, then re-run.")
        return False

    print(f"  Account SID: {sid[:6]}...{sid[-4:]}")
    print(f"  From number: {from_num}")
    return True


def test_send(to_phone: str):
    """Send a test WhatsApp message."""
    from twilio.rest import Client

    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    from_num = os.getenv("TWILIO_WHATSAPP_FROM")

    client = Client(sid, token)

    print(f"\nSending test message to whatsapp:{to_phone} ...")
    message = client.messages.create(
        body="Hello from ClassBridge! This is a WhatsApp integration test.",
        from_=f"whatsapp:{from_num}",
        to=f"whatsapp:{to_phone}",
    )
    print(f"  SID:    {message.sid}")
    print(f"  Status: {message.status}")
    print("\nCheck your WhatsApp — you should receive the message shortly.")


def main():
    print("=== ClassBridge WhatsApp Test ===\n")

    # Step 1: Check config
    print("[1/2] Checking Twilio configuration...")
    if not check_config():
        sys.exit(1)

    # Step 2: Send test message
    if len(sys.argv) < 2:
        print("\n[2/2] No phone number provided.")
        print("\nUsage: python scripts/test_whatsapp.py +1YOURNUMBER")
        print("\nIMPORTANT: Before sending, you must join the Twilio sandbox:")
        print("  1. Open WhatsApp on your phone")
        print("  2. Send 'join <word> <word>' to +1 415 523 8886")
        print("     (Get your exact join phrase from Twilio Console)")
        print("  3. Wait for the confirmation reply")
        print("  4. Then run this script with your phone number")
        sys.exit(0)

    to_phone = sys.argv[1]
    if not to_phone.startswith("+"):
        print(f"\nError: Phone number must include country code (e.g., +1{to_phone})")
        sys.exit(1)

    print(f"\n[2/2] Sending test message to {to_phone}...")
    try:
        test_send(to_phone)
    except Exception as e:
        print(f"\n  FAILED: {e}")
        if "not a valid phone number" in str(e).lower():
            print("  Hint: Use E.164 format: +14165551234")
        elif "sandbox" in str(e).lower() or "not opted" in str(e).lower():
            print("  Hint: You need to join the sandbox first!")
            print("  Send 'join <word> <word>' to +14155238886 on WhatsApp")
        sys.exit(1)


if __name__ == "__main__":
    main()
