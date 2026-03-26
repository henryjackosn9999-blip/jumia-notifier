"""
Jumia Kenya Multi-Shop Order Notifier + Telegram Bot
Fixed version with correct Jumia Kenya API endpoints and verbose logging
"""

import requests
import time
import json
import os
from datetime import datetime, timezone

TELEGRAM_BOT_TOKEN = "8736505320:AAExDEhGuW0yJP6sFjLUjQ7gyRKj5hd2XIU"
TELEGRAM_CHAT_ID   = "8092667233"

SHOPS = [
    {
        "name":          "Shop 1 - Meliverse agencies",
        "client_id":     "18bddd88-1701-40fc-b0d7-097c1ea0b99e",
        "refresh_token": "vuK7ZRREApvCagXcfRnD73A_QxxVk5zaMboFxhF5MbU",
    },
    # ADD MORE SHOPS HERE
    # {
    #     "name":          "Shop 2 - Your Shop Name",
    #     "client_id":     "PASTE_CLIENT_ID_HERE",
    #     "refresh_token": "PASTE_REFRESH_TOKEN_HERE",
    # },
]

JUMIA_AUTH_URL   = "https://vendorcenter.jumia.co.ke/api/v1/auth/token"
JUMIA_ORDERS_URL = "https://vendorcenter.jumia.co.ke/api/v1/orders"
JUMIA_RTS_URL    = "https://vendorcenter.jumia.co.ke/api/v1/orders/{order_id}/ready-to-ship"

CHECK_INTERVAL   = 60
SEEN_ORDERS_FILE = "seen_orders.json"


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


def get_access_token(shop):
    for payload_type in ["json", "form"]:
        try:
            payload = {
                "grant_type":    "refresh_token",
                "client_id":     shop["client_id"],
                "refresh_token": shop["refresh_token"],
            }
            if payload_type == "json":
                resp = requests.post(JUMIA_AUTH_URL, json=payload, timeout=15)
            else:
                resp = requests.post(JUMIA_AUTH_URL, data=payload, timeout=15)
            print(f"[{now()}] Auth [{payload_type}] {shop['name']}: {resp.status_code} | {resp.text[:300]}")
            if resp.status_code == 200:
                data = resp.json()
                token = data.get("access_token") or data.get("token")
                if token:
                    return token
        except Exception as e:
            print(f"[{now()}] Auth error [{payload_type}] {shop['name']}: {e}")
    return None


def get_pending_orders(shop, token):
    try:
        resp = requests.get(
            JUMIA_ORDERS_URL,
            headers={"Authorization": f"Bearer {token}"},
            params={"status": "pending", "limit": 50},
            timeout=15,
        )
        print(f"[{now()}] Orders {shop['name']}: {resp.status_code} | {resp.text[:300]}")
        if resp.status_code == 200:
            data = resp.json()
            return data.get("orders", data.get("items", data if isinstance(data, list) else []))
    except Exception as e:
        print(f"[{now()}] Orders error {shop['name']}: {e}")
    return []


def mark_ready_to_ship(shop, order_id):
    token = get_access_token(shop)
    if not token:
        return False, "Could not authenticate"
    try:
        url  = JUMIA_RTS_URL.format(order_id=order_id)
        resp = requests.post(url, headers={"Authorization": f"Bearer {token}"}, timeout=15)
        if resp.status_code in [200, 201, 204]:
            return True, "OK"
        return False, f"HTTP {resp.status_code}: {resp.text[:100]}"
    except Exception as e:
        return False, str(e)


def send_telegram(text, reply_markup=None):
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json=payload, timeout=10,
        )
        print(f"[{now()}] Telegram sendMessage: {resp.status_code} | {resp.text[:200]}")
        return resp.status_code == 200
    except Exception as e:
        print(f"[{now()}] Telegram error: {e}")
        return False


def answer_callback(cq_id, text):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/answerCallbackQuery",
            json={"callback_query_id": cq_id, "text": text}, timeout=10,
        )
    except Exception:
        pass


def edit_message(chat_id, msg_id, text):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/editMessageText",
            json={"chat_id": chat_id, "message_id": msg_id, "text": text, "parse_mode": "HTML"},
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
            params=params, timeout=8,
        )
        if resp.status_code == 200:
            return resp.json().get("result", [])
    except Exception:
        pass
    return []


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
    send_telegram(text, reply_markup={"inline_keyboard": [[
        {"text": "✅ Tap here → Ready to Ship", "callback_data": f"rts|{shop_idx}|{order_id}"}
    ]]})


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
    answer_callback(cq_id, "Marking as Ready to Ship...")
    success, reason = mark_ready_to_ship(shop, order_id)
    if success:
        edit_message(chat_id, msg_id,
            f"✅ <b>Order {order_id} Ready to Ship!</b>\n🏪 {shop['name']}\n🕐 {now()}")
    else:
        answer_callback(cq_id, f"Error: {reason}")


def main():
    print(f"[{now()}] Starting Jumia Notifier — {len(SHOPS)} shop(s)")
    send_telegram(
        f"🚀 <b>Jumia Order Notifier is LIVE!</b>\n\n"
        f"🏪 Watching <b>{len(SHOPS)} shop(s)</b>\n"
        f"⏱ Checking every <b>{CHECK_INTERVAL}s</b>\n\n"
        f"Every new order will appear here with a\n"
        f"<b>✅ Ready to Ship</b> button!"
    )
    seen_orders   = load_seen_orders()
    update_offset = None
    while True:
        updates = get_updates(update_offset)
        for upd in updates:
            update_offset = upd["update_id"] + 1
            if "callback_query" in upd:
                handle_callback(upd)
        for shop in SHOPS:
            print(f"[{now()}] Checking {shop['name']}")
            token = get_access_token(shop)
            if not token:
                continue
            orders = get_pending_orders(shop, token)
            for order in orders:
                uid = f"{shop['client_id']}::{order.get('order_id') or order.get('id','')}"
                if uid not in seen_orders:
                    notify_new_order(shop, order)
                    seen_orders.add(uid)
        save_seen_orders(seen_orders)
        print(f"[{now()}] Done. Next in {CHECK_INTERVAL}s\n")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
