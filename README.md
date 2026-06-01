# WeChat Desktop Group Chat Scraper

A Python CLI tool that auto-scrolls WeChat Desktop group chats on macOS, extracts messages via OCR, and saves them as structured JSON. Fully offline after initial setup.

## How It Works

```
WeChat Desktop (macOS)
       │
       │  pyautogui scrolls up through chat history
       │  Pillow captures screenshots of the message area
       ▼
┌─────────────────┐
│  Perceptual Hash │  Skip duplicate frames, detect end of history
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   PaddleOCR      │  Chinese+English text extraction (lang='ch')
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Message Parser  │  Group text blocks → sender + timestamp + content
└────────┬────────┘
         │
         ▼
     output/<chat_name>.json
```

## Setup

```bash
./setup.sh
```

This creates a virtual environment, installs all dependencies (PaddleOCR, pyautogui, pyobjc, OpenCV), and checks that WeChat is detectable.

**Required:** Grant Accessibility permissions to your terminal app in System Settings → Privacy & Security → Accessibility.

## Usage

```bash
source .venv/bin/activate

# Scrape all chats listed in chats.json (resume mode)
python scraper.py

# Scrape specific chats only
python scraper.py --chats "投资讨论群,股票交流群"

# Full history crawl (ignore checkpoints)
python scraper.py --backfill

# Test mode — screenshot only, no JSON written
python scraper.py --dry-run

# Custom output directory
python scraper.py --output ./my_folder
```

## Configuration

Edit `chats.json`:

```json
{
  "chats": ["投资讨论群", "股票交流群"],
  "scroll_step": 800,
  "scroll_delay": 1.0,
  "output_dir": "./output"
}
```

## Output Format

One JSON file per chat in `./output/`:

```json
{
  "chat_name": "投资讨论群",
  "last_updated": "2025-05-29T10:00:00+08:00",
  "message_count": 1432,
  "messages": [
    {
      "sender": "张伟",
      "timestamp": "2025-05-28T14:32:00+08:00",
      "message_text": "这只股票值得关注",
      "message_hash": "a3f9e2b1...",
      "chat_name": "投资讨论群"
    }
  ]
}
```

## Resume Support

The scraper saves checkpoints to `state.json` after each chat. On subsequent runs, it scrolls until it hits the last-seen message hash, then stops. Use `--backfill` to ignore checkpoints and scrape full history.

## Constraints

- macOS only (uses AppKit/Quartz for window management)
- WeChat Desktop must be open and logged in
- Read-only — only scrolls, never sends messages or clicks buttons
- All output is local JSON, zero network calls after setup
- Ctrl+C saves progress gracefully
