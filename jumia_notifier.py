"""
Jumia Multi-Shop Order Notifier + Telegram Bot
================================================
- Monitors ALL your Jumia shops for new orders
- Sends Telegram notification for every new order
- Tap "Ready to Ship" button directly from Telegram
- Add shops yourself without touching the rest of the code

SETUP:
  pip install requests

RUN:
  python jumia_notifier.py

HOST FREE (runs 24/7):
  Upload to Railway.app or Render.com
  Start command: python jumia_notifier.py
"""

import requests
import time
import json
import os
from datetime import datetime, timezone

# ═══════════════════════════════════════════════════════════════
#  TELEGRAM SETTINGS
# ═══════════════════════════════════════════════════════════════
TELEGRAM_BOT_TOKEN = "8736505320:AAExDEhGuW0yJP6sFjLUjQ7gyRKj5hd2XIU"
TELEGRAM_CHAT_ID   = "8092667233"

# ═══════════════════════════════════════════════════════════════
#  YOUR SHOPS — Add all 6 shops here
#  For each new shop:
#    1. Go to Vendor Center → Settings → Applications
#    2. Create Application (Self Authorization)
#    3. Copy the Client ID and Refresh Token
#    4. Paste them in a new block below (copy the template)
# ═══════════════════════════════════════════════════════════════
SHOPS = [
    {
        "name":          "Shop 1 – Meliverse agencies",
        "client_id":     "18bddd88-1701-40fc-b0d7-097c1ea0b99e",
        "refresh_token": "vuK7ZRREApvCagXcfRnD73A_QxxVk5zaMboFxhF5MbU",
        "api_base":      "https://vendorcenter.jumia.com/api/v1",
    },

    # ── PASTE YOUR OTHER 5 SHOPS BELOW ─────────────────────────
    # Just copy this block and fill in the details for each shop:

    # {
    #     "name":          "Shop 2 – Name of your shop",
    #     "client_id":     "PASTE_CLIENT_ID_HERE",
    #     "refresh_token": "PASTE_REFRESH_TOKEN_HERE",
    #     "api_base":      "https://vendorcenter.jumia.com/api/v1",
    # },
    # {
    #     "name":          "Shop 3 – Name of your shop",
    #     "client_id":     "PASTE_CLIENT_ID_HERE",
    #     "refresh_token": "PASTE_REFRESH_TOKEN_HERE",
    #     "api_base":      "https://vendorcenter.jumia.com/api/v1",
    # },
    # {
    #     "name":          "Shop 4 – Name of your shop",
    #     "client_id":     "PASTE_CLIENT_ID_HERE",
    #     "refresh_token": "PASTE_REFRESH_TOKEN_HERE",
    #     "api_base":      "https://vendorcenter.jumia.com/api/v1",
    # },
    # {
    #     "name":          "Shop 5 – Name of your shop",
    #     "client_id":     "PASTE_CLIENT_ID_HERE",
    #     "refresh_token": "PASTE_REFRESH_TOKEN_HERE",
    #     "api_base":      "https://vendorcenter.jumia.com/api/v1",
    # },
    # {
    #     "name":          "Shop 6 – Name of your shop",
    #     "client_id":     "PASTE_CLIENT_ID_HERE",
    #     "refresh_token": "PASTE_REFRESH_TOKEN_HERE",
    #     "api_base":      "https://vendorcenter.jumia.com/api/v1",
    # },
]

# How often to check for new orders (seconds). 60 = every 1 minute
CHECK_INTERVAL   = 60
SEEN_ORDERS_FILE = "seen_orders.json"
# ═══════════════════════════════════════════════════════════════


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def load_seen_orders():
    if os.path.exists(SEEN_ORDERS_FILE):
        with open(SEEN_ORDERS_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_seen_orders(seen):
    with open(SEEN_ORDERS_FILE, "w") as f:
        json.dump(list(seen), f)


# ── Jumia API helpers ────────────────────────────────────────────

def get_access_token(shop):
    try:
        resp = requests.post(
            f"{shop['api_base']}/auth/token",
            json={
                "grant_type":    "refresh_token",
                "client_id":     shop["client_id"],
                "refresh_token": shop["refresh_token"],
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json().get("access_token")
    except Exception as e:
        print(f"[{now()}] [{shop['name']}] Token error: {e}")
        return None


def get_pending_orders(shop, token):
    try:
        resp = requests.get(
            f"{shop['api_base']}/orders",
            headers={"Authorization": f"Bearer {token}"},
            params={"status": "pending", "limit": 50},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("orders", data.get("items", []))
    except Exception as e:
        print(f"[{now()}] [{shop['name']}] Orders error: {e}")
        return []


def mark_ready_to_ship(shop, order_id):
    token = get_access_token(shop)
    if not token:
        return False, "Could not authenticate with Jumia"
    try:
        resp = requests.post(
            f"{shop['api_base']}/orders/{order_id}/ready-to-ship",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        resp.raise_for_status()
        return True, "OK"
    except Exception as e:
        return False, str(e)


# ── Telegram helpers ─────────────────────────────────────────────

def send_telegram(text, reply_markup=None):
    payload = {
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       text,
        "parse_mode": "HTML",
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json=payload,
            timeout=10,
        ).raise_for_status()
    except Exception as e:
        print(f"[{now()}] Telegram send error: {e}")


def answer_callback(cq_id, text):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery",
            json={"callback_query_id": cq_id, "text": text},
            timeout=10,
        )
    except Exception:
        pass


def edit_message(chat_id, msg_id, text):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText",
            json={
                "chat_id":    chat_id,
                "message_id": msg_id,
                "text":       text,
                "parse_mode": "HTML",
            },
            timeout=10,
        )
    except Exception:
        pass


def get_updates(offset=None):
    try:
        params = {"timeout": 2, "allowed_updates": ["callback_query", "message"]}
        if offset:
            params["offset"] = offset
        resp = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates",
            params=params,
            timeout=8,
        )
        resp.raise_for_status()
        return resp.json().get("result", [])
    except Exception:
        return []


# ── Notification builder ─────────────────────────────────────────

def notify_new_order(shop, order):
    order_id    = str(order.get("order_id") or order.get("id", "N/A"))
    customer    = order.get("customer_name") or order.get("shipping_name", "Customer")
    total       = order.get("price") or order.get("total", "N/A")
    currency    = order.get("currency", "KES")
    items_count = order.get("items_count", "?")
    created_at  = order.get("created_at", now())

    text = (
        f"🛒 <b>NEW ORDER!</b>\n"
        f"🏪 <b>{shop['name']}</b>\n\n"
        f"📦 Order ID: <b>{order_id}</b>\n"
        f"👤 Customer: {customer}\n"
        f"💰 Amount: <b>{currency} {total}</b>\n"
        f"🔢 Items: {items_count}\n"
        f"🕐 Time: {created_at}\n"
    )

    shop_idx = SHOPS.index(shop)
    send_telegram(text, reply_markup={
        "inline_keyboard": [[
            {
                "text":          "✅ Tap here → Ready to Ship",
                "callback_data": f"rts|{shop_idx}|{order_id}",
            }
        ]]
    })


# ── Callback handler (button taps) ───────────────────────────────

def handle_callback(update):
    cq      = update.get("callback_query", {})
    cq_id   = cq.get("id")
    data    = cq.get("data", "")
    msg     = cq.get("message", {})
    msg_id  = msg.get("message_id")
    chat_id = msg.get("chat", {}).get("id")

    if not data.startswith("rts|"):
        return

    parts = data.split("|", 2)
    if len(parts) != 3:
        return

    _, shop_idx_str, order_id = parts
    shop = SHOPS[int(shop_idx_str)]

    answer_callback(cq_id, "⏳ Marking as Ready to Ship...")
    success, reason = mark_ready_to_ship(shop, order_id)

    if success:
        edit_message(
            chat_id, msg_id,
            f"✅ <b>Order {order_id} → Ready to Ship!</b>\n"
            f"🏪 Shop: {shop['name']}\n"
            f"🕐 Done at: {now()}"
        )
        print(f"[{now()}] [{shop['name']}] Order {order_id} marked Ready to Ship ✓")
    else:
        answer_callback(cq_id, f"❌ Error: {reason}")
        print(f"[{now()}] [{shop['name']}] Ready to Ship failed: {reason}")


# ── Main loop ────────────────────────────────────────────────────

def main():
    print(f"[{now()}] 🚀 Jumia Multi-Shop Notifier started — {len(SHOPS)} shop(s)")

    send_telegram(
        f"🚀 <b>Jumia Order Notifier is LIVE!</b>\n\n"
        f"🏪 Watching <b>{len(SHOPS)} shop(s)</b>\n"
        f"⏱ Checking every <b>{CHECK_INTERVAL} seconds</b>\n\n"
        f"Every new order will appear here with a\n"
        f"<b>✅ Ready to Ship</b> button you can tap!"
    )

    seen_orders   = load_seen_orders()
    update_offset = None

    while True:
        # 1. Handle any button taps from Telegram
        updates = get_updates(update_offset)
        for upd in updates:
            update_offset = upd["update_id"] + 1
            if "callback_query" in upd:
                handle_callback(upd)

        # 2. Check every shop for new orders
        for shop in SHOPS:
            print(f"[{now()}] Checking → {shop['name']}")
            token = get_access_token(shop)
            if not token:
                continue

            orders = get_pending_orders(shop, token)
            for order in orders:
                uid = f"{shop['client_id']}::{order.get('order_id') or order.get('id', '')}"
                if uid not in seen_orders:
                    notify_new_order(shop, order)
                    seen_orders.add(uid)
                    print(f"[{now()}] New order notified: {uid}")

        save_seen_orders(seen_orders)
        print(f"[{now()}] ✓ All shops checked. Next in {CHECK_INTERVAL}s\n")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
