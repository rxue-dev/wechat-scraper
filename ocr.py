"""PaddleOCR wrapper and message parser for WeChat screenshots."""

import hashlib
import re
from datetime import datetime, timezone, timedelta

from paddleocr import PaddleOCR


CST = timezone(timedelta(hours=8))

_ocr_instance = None


def get_ocr():
    """Lazy-initialize PaddleOCR (heavy startup, reuse across calls)."""
    global _ocr_instance
    if _ocr_instance is None:
        _ocr_instance = PaddleOCR(use_textline_orientation=True, lang="ch")
    return _ocr_instance


def extract_messages(image_path, chat_name):
    """Run OCR on a screenshot and parse into structured messages.

    Returns a list of message dicts sorted top-to-bottom (as they appear on screen).
    """
    ocr = get_ocr()
    result = ocr.predict(str(image_path))

    if not result:
        return []

    # PaddleOCR 3.x returns a list of result dicts (one per image) with parallel
    # lists: rec_texts, rec_scores, and polygons (rec_polys or dt_polys).
    res = result[0]
    texts = res["rec_texts"]
    scores = res["rec_scores"]
    polys = res.get("rec_polys")
    if polys is None:
        polys = res["dt_polys"]

    text_blocks = []
    for text, confidence, bbox in zip(texts, scores, polys):
        if confidence < 0.5:
            continue

        y_center = (bbox[0][1] + bbox[2][1]) / 2
        x_left = bbox[0][0]
        text_blocks.append({
            "text": text.strip(),
            "y": y_center,
            "x": x_left,
            "bbox": bbox,
            "confidence": confidence,
        })

    text_blocks.sort(key=lambda b: b["y"])
    messages = _parse_blocks_to_messages(text_blocks, chat_name)
    return messages


def _parse_blocks_to_messages(blocks, chat_name):
    """Group OCR text blocks into messages.

    WeChat message layout (top to bottom):
    - Optional timestamp header (centered, gray text like "昨天 14:32")
    - Sender name (left-aligned or right-aligned)
    - Message text (below sender name, in speech bubble)

    Heuristic: timestamp lines are centered and match date patterns.
    Sender lines are short (< 20 chars) and precede longer message text.
    """
    messages = []
    current_timestamp = None
    current_sender = None
    current_text_parts = []

    for block in blocks:
        text = block["text"]

        parsed_time = _try_parse_timestamp(text)
        if parsed_time:
            if current_sender and current_text_parts:
                messages.append(_build_message(
                    current_sender, current_timestamp, current_text_parts, chat_name
                ))
                current_text_parts = []
                current_sender = None
            current_timestamp = parsed_time
            continue

        if _looks_like_sender(text) and not current_text_parts:
            if current_sender and current_text_parts:
                messages.append(_build_message(
                    current_sender, current_timestamp, current_text_parts, chat_name
                ))
                current_text_parts = []
            current_sender = text
            continue

        if _looks_like_sender(text) and current_text_parts:
            messages.append(_build_message(
                current_sender, current_timestamp, current_text_parts, chat_name
            ))
            current_text_parts = []
            current_sender = text
            continue

        if _is_media_indicator(text):
            continue
        else:
            current_text_parts.append(text)

    if current_sender and current_text_parts:
        messages.append(_build_message(
            current_sender, current_timestamp, current_text_parts, chat_name
        ))

    return messages


def _build_message(sender, timestamp, text_parts, chat_name):
    """Construct a message dict with hash for deduplication."""
    message_text = " ".join(text_parts)
    ts_str = timestamp.isoformat() if timestamp else ""

    hash_input = f"{sender or ''}|{ts_str}|{message_text}"
    message_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]

    return {
        "sender": sender or "[unknown]",
        "timestamp": ts_str,
        "message_text": message_text,
        "message_hash": message_hash,
        "chat_name": chat_name,
    }


def _try_parse_timestamp(text):
    """Try to parse WeChat timestamp formats into datetime.

    Supported formats:
    - "14:32" (today)
    - "昨天 14:32" (yesterday)
    - "星期一 14:32" (this week)
    - "5月27日 09:15"
    - "2024年3月1日 14:32"
    - "2024/3/1 14:32"
    """
    text = text.strip()

    m = re.match(r"^(\d{4})年(\d{1,2})月(\d{1,2})日\s+(\d{1,2}):(\d{2})$", text)
    if m:
        return datetime(
            int(m.group(1)), int(m.group(2)), int(m.group(3)),
            int(m.group(4)), int(m.group(5)), tzinfo=CST,
        )

    m = re.match(r"^(\d{4})/(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{2})$", text)
    if m:
        return datetime(
            int(m.group(1)), int(m.group(2)), int(m.group(3)),
            int(m.group(4)), int(m.group(5)), tzinfo=CST,
        )

    m = re.match(r"^(\d{1,2})月(\d{1,2})日\s+(\d{1,2}):(\d{2})$", text)
    if m:
        now = datetime.now(CST)
        return datetime(
            now.year, int(m.group(1)), int(m.group(2)),
            int(m.group(3)), int(m.group(4)), tzinfo=CST,
        )

    m = re.match(r"^昨天\s+(\d{1,2}):(\d{2})$", text)
    if m:
        now = datetime.now(CST)
        yesterday = now - timedelta(days=1)
        return yesterday.replace(
            hour=int(m.group(1)), minute=int(m.group(2)),
            second=0, microsecond=0,
        )

    m = re.match(r"^前天\s+(\d{1,2}):(\d{2})$", text)
    if m:
        now = datetime.now(CST)
        day_before = now - timedelta(days=2)
        return day_before.replace(
            hour=int(m.group(1)), minute=int(m.group(2)),
            second=0, microsecond=0,
        )

    weekday_map = {"星期一": 0, "星期二": 1, "星期三": 2, "星期四": 3,
                   "星期五": 4, "星期六": 5, "星期日": 6, "星期天": 6}
    for day_name, day_num in weekday_map.items():
        m = re.match(rf"^{day_name}\s+(\d{{1,2}}):(\d{{2}})$", text)
        if m:
            now = datetime.now(CST)
            days_back = (now.weekday() - day_num) % 7
            if days_back == 0:
                days_back = 7
            target = now - timedelta(days=days_back)
            return target.replace(
                hour=int(m.group(1)), minute=int(m.group(2)),
                second=0, microsecond=0,
            )

    m = re.match(r"^(\d{1,2}):(\d{2})$", text)
    if m:
        now = datetime.now(CST)
        return now.replace(
            hour=int(m.group(1)), minute=int(m.group(2)),
            second=0, microsecond=0,
        )

    return None


def _looks_like_sender(text):
    """Heuristic: sender names are short, no punctuation-heavy content."""
    if len(text) > 20:
        return False
    if _try_parse_timestamp(text):
        return False
    if re.search(r"[。，！？、：；""''【】《》]", text):
        return False
    if len(text) < 2:
        return False
    return True


def _is_media_indicator(text):
    """Detect WeChat media placeholders."""
    media_patterns = [
        "[图片]", "[语音]", "[视频]", "[动画表情]", "[文件]",
        "[链接]", "[位置]", "[名片]", "[音乐]", "[红包]",
        "[转账]", "[拍一拍]",
    ]
    return text.strip() in media_patterns
