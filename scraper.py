"""WeChat Desktop group chat scraper — main entry point."""

import argparse
import json
import signal
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import cv2
import numpy as np
import pyautogui
from PIL import ImageGrab

from window import find_wechat_window, focus_wechat, get_chat_area_bounds, click_chat_by_name, is_wechat_running
from ocr import extract_messages
from resume import get_checkpoint, update_checkpoint


CST = timezone(timedelta(hours=8))

collected_messages = {}
current_chat = None
should_exit = False


def signal_handler(sig, frame):
    """Handle Ctrl+C: save progress before exiting."""
    global should_exit
    print("\n\nCtrl+C detected — saving progress...")
    should_exit = True


signal.signal(signal.SIGINT, signal_handler)


def main():
    args = parse_args()
    config = load_config()

    if not is_wechat_running():
        print("ERROR: WeChat Desktop is not running. Please open it and log in first.")
        sys.exit(1)

    if not focus_wechat():
        print("ERROR: Could not focus WeChat window.")
        sys.exit(1)

    window = find_wechat_window()
    if not window:
        print("ERROR: Could not find WeChat window bounds.")
        sys.exit(1)

    print(f"WeChat window found: {window['width']}x{window['height']} at ({window['x']}, {window['y']})")

    chats = args.chats.split(",") if args.chats else config["chats"]
    output_dir = Path(args.output) if args.output else Path(config.get("output_dir", "./output"))
    output_dir.mkdir(parents=True, exist_ok=True)

    scroll_step = config.get("scroll_step", 800)
    scroll_delay = config.get("scroll_delay", 1.0)

    for chat_name in chats:
        if should_exit:
            break

        print(f"\n{'='*50}")
        print(f"  Scraping: {chat_name}")
        print(f"{'='*50}")

        if not click_chat_by_name(chat_name, window):
            print(f"  WARNING: Could not navigate to chat '{chat_name}', skipping.")
            continue

        time.sleep(1.0)
        messages = scrape_chat(
            chat_name=chat_name,
            window=window,
            scroll_step=scroll_step,
            scroll_delay=scroll_delay,
            backfill=args.backfill,
            dry_run=args.dry_run,
        )

        if not args.dry_run and messages:
            save_chat(chat_name, messages, output_dir)
            if messages:
                latest = messages[-1]
                update_checkpoint(chat_name, latest["message_hash"], latest["timestamp"])

    print("\nDone.")


def scrape_chat(chat_name, window, scroll_step, scroll_delay, backfill, dry_run):
    """Scroll through a chat and collect messages via OCR."""
    global should_exit

    chat_area = get_chat_area_bounds(window)
    checkpoint = None if backfill else get_checkpoint(chat_name)
    checkpoint_hash = checkpoint["last_hash"] if checkpoint else None

    all_messages = {}
    scroll_count = 0
    duplicate_frame_count = 0
    max_duplicate_frames = 3
    prev_frame_hash = None

    center_x = chat_area["x"] + chat_area["width"] // 2
    center_y = chat_area["y"] + chat_area["height"] // 2

    pyautogui.click(center_x, center_y)
    time.sleep(0.3)

    while not should_exit:
        pyautogui.scroll(scroll_step // 100, x=center_x, y=center_y)
        time.sleep(scroll_delay)

        screenshot = wait_for_render(chat_area)
        if screenshot is None:
            break

        frame_hash = perceptual_hash(screenshot)

        if frame_hash == prev_frame_hash:
            duplicate_frame_count += 1
            if duplicate_frame_count >= max_duplicate_frames:
                print(f"  Reached top of chat history ({scroll_count} scrolls)")
                break
        else:
            duplicate_frame_count = 0
        prev_frame_hash = frame_hash

        scroll_count += 1

        temp_path = Path(f"/tmp/wechat_frame_{scroll_count:04d}.png")
        screenshot.save(str(temp_path))

        messages = extract_messages(temp_path, chat_name)

        hit_checkpoint = False
        for msg in messages:
            if checkpoint_hash and msg["message_hash"] == checkpoint_hash:
                hit_checkpoint = True
                break
            all_messages[msg["message_hash"]] = msg

        if hit_checkpoint:
            print(f"  Reached checkpoint after {scroll_count} scrolls")
            break

        print(f"  Scroll {scroll_count}: {len(all_messages)} unique messages collected", end="\r")

    print(f"\n  Total: {len(all_messages)} messages from {scroll_count} scrolls")

    result = sorted(all_messages.values(), key=lambda m: m["timestamp"])
    return result


def wait_for_render(chat_area, timeout=3.0, interval=0.3):
    """Wait until the chat area stops changing (WeChat finished rendering).

    Takes two screenshots `interval` apart and compares them.
    Returns the stable screenshot, or the last one if timeout is reached.
    """
    region = (chat_area["x"], chat_area["y"], chat_area["width"], chat_area["height"])
    deadline = time.time() + timeout

    prev = capture_region(region)
    while time.time() < deadline:
        time.sleep(interval)
        curr = capture_region(region)
        if perceptual_hash(prev) == perceptual_hash(curr):
            return curr
        prev = curr

    return prev


def capture_region(region):
    """Capture a screen region. region = (x, y, width, height)."""
    x, y, w, h = region
    bbox = (x, y, x + w, y + h)
    return ImageGrab.grab(bbox)


def perceptual_hash(image, hash_size=16):
    """Compute a perceptual hash of a PIL image for duplicate detection.

    Uses average hash: resize to small grayscale, threshold at mean.
    """
    img_array = np.array(image.convert("L"))
    resized = cv2.resize(img_array, (hash_size, hash_size))
    mean_val = resized.mean()
    bits = (resized > mean_val).flatten()
    return bits.tobytes()


def save_chat(chat_name, messages, output_dir):
    """Write messages to a JSON file."""
    output_path = output_dir / f"{chat_name}.json"

    existing_messages = {}
    if output_path.exists():
        with open(output_path) as f:
            data = json.load(f)
            for msg in data.get("messages", []):
                existing_messages[msg["message_hash"]] = msg

    for msg in messages:
        existing_messages[msg["message_hash"]] = msg

    all_msgs = sorted(existing_messages.values(), key=lambda m: m["timestamp"])

    output = {
        "chat_name": chat_name,
        "last_updated": datetime.now(CST).isoformat(),
        "message_count": len(all_msgs),
        "messages": all_msgs,
    }

    with open(output_path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"  Saved {len(all_msgs)} messages to {output_path}")


def load_config():
    """Load chats.json config file."""
    config_path = Path(__file__).parent / "chats.json"
    if not config_path.exists():
        print("WARNING: chats.json not found, using defaults.")
        return {"chats": [], "scroll_step": 800, "scroll_delay": 1.0, "output_dir": "./output"}
    with open(config_path) as f:
        return json.load(f)


def parse_args():
    parser = argparse.ArgumentParser(description="WeChat Desktop group chat scraper")
    parser.add_argument("--chats", type=str, default=None,
                        help="Comma-separated chat names to scrape (overrides chats.json)")
    parser.add_argument("--backfill", action="store_true",
                        help="Ignore checkpoints, scrape full history")
    parser.add_argument("--dry-run", action="store_true",
                        help="Screenshot only, no JSON written")
    parser.add_argument("--output", type=str, default=None,
                        help="Custom output directory")
    return parser.parse_args()


if __name__ == "__main__":
    main()
