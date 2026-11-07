"""
ShopGuard AI - FCM Credentials Diagnostic Script
Runs a DRY-RUN message send to identify exactly what FCM returns for the stored token.
Run with: .\venv\Scripts\python diagnose_fcm.py
"""

import json
import os
import warnings

CREDS_FILE = "config/firebase_credentials.json"
TOKENS_FILE = "config/fcm_tokens.json"

print("=" * 60)
print("ShopGuard AI FCM Diagnostic")
print("=" * 60)

# 1. Check credentials file
if not os.path.isfile(CREDS_FILE):
    print(f"[FAIL] Credentials file not found: {CREDS_FILE}")
    exit(1)

with open(CREDS_FILE) as f:
    creds_data = json.load(f)
print(f"[OK]   Credentials project_id  : {creds_data.get('project_id')}")
print(f"[OK]   Credentials client_email: {creds_data.get('client_email')}")
print(f"[OK]   Credentials type        : {creds_data.get('type')}")

# 2. Check tokens file
if not os.path.isfile(TOKENS_FILE):
    print(f"[WARN] Tokens file not found: {TOKENS_FILE}")
    tokens = {}
else:
    with open(TOKENS_FILE) as f:
        tokens_data = json.load(f)
    tokens = tokens_data.get("tokens", {})

print(f"\n[INFO] Registered device tokens: {len(tokens)}")

if not tokens:
    print("\n[WARN] No tokens stored. The token was likely auto-pruned after a failed send.")
    print("       Re-open the ShopGuard app → connect to agent → token will re-register.")
    manual_token = input("\nPaste your FCM token here to test it directly (or press Enter to skip): ").strip()
    if manual_token:
        tokens = {manual_token: {"device_name": "Manual Test", "app_version": "diag"}}
    else:
        print("No token to test. Exiting.")
        exit(0)

# 3. Initialize Firebase Admin SDK
import firebase_admin
from firebase_admin import credentials, messaging

print("\n[INFO] Initializing Firebase Admin SDK...")
try:
    try:
        app = firebase_admin.get_app("diag_app")
    except ValueError:
        cred = credentials.Certificate(CREDS_FILE)
        app = firebase_admin.initialize_app(cred, name="diag_app")
    print("[OK]   Firebase Admin SDK initialized successfully.")
except Exception as e:
    print(f"[FAIL] SDK init failed: {e}")
    exit(1)

# 4. Run DRY RUN for each token
print("\n[INFO] Sending DRY RUN message (no actual notification delivered)...")
print("-" * 60)

for raw_token, meta in tokens.items():
    masked = f"{raw_token[:6]}...{raw_token[-6:]}" if len(raw_token) > 12 else "***"
    device = meta.get("device_name", "Unknown")
    print(f"\n  Token : {masked}")
    print(f"  Device: {device}")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            msg = messaging.Message(
                token=raw_token,
                notification=messaging.Notification(
                    title="ShopGuard Diagnostic Test",
                    body="DRY RUN - no actual notification"
                ),
                data={"test": "true"},
                android=messaging.AndroidConfig(
                    priority="high",
                    notification=messaging.AndroidNotification(
                        channel_id="shopguard_security_alerts",
                    ),
                ),
            )

        result = messaging.send(msg, dry_run=True, app=app)
        print(f"  [SUCCESS] DRY RUN passed. FCM message ID: {result}")
        print(f"  => The backend credentials ARE valid for this token.")

    except messaging.UnregisteredError as e:
        print(f"  [FAIL] UnregisteredError: {e}")
        try:
            cause = getattr(e, 'cause', None)
            resp = getattr(cause, 'response', None)
            if resp:
                print(f"         HTTP Status : {resp.status_code}")
                print(f"         HTTP Body   : {resp.text[:500]}")
        except Exception:
            pass

    except messaging.SenderIdMismatchError as e:
        print(f"  [FAIL] SenderIdMismatchError: {e}")
        print("         => The service account is from a DIFFERENT Firebase project than the app.")

    except firebase_admin.exceptions.FirebaseError as e:
        print(f"  [FAIL] FirebaseError: type={type(e).__name__}, code={getattr(e,'code',None)}, msg={e}")
        try:
            cause = getattr(e, 'cause', None)
            resp = getattr(cause, 'response', None)
            if resp:
                print(f"         HTTP Status : {resp.status_code}")
                print(f"         HTTP Body   : {resp.text[:500]}")
        except Exception:
            pass

    except Exception as e:
        print(f"  [FAIL] Unexpected error: {type(e).__name__}: {e}")

print("\n" + "=" * 60)
print("Diagnostic complete.")
print("=" * 60)
