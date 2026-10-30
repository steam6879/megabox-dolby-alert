# Megabox Dolby Cinema Booking Alert

A small bot that sends a **Telegram notification when new showtimes open** for a movie you are waiting for, at a specific Megabox (메가박스) branch and screen type such as Dolby Cinema.
It runs on GitHub Actions twice a day (around 12:00 and 18:00 KST), so you don't need to keep a server or PC running.

Existing alert bots mostly cover the COEX and Namyangju Dolby Cinemas, so this project uses **Songdo (Triple Street) Dolby Cinema** as the default example. Any other branch works by changing the config.

> This is an unofficial tool, not affiliated with Megabox. It only reads the publicly available showtime schedule.
> It sends notifications only and does not book tickets automatically. Please don't raise the run frequency to a level that puts load on Megabox's servers.

## How it works

1. Fetch the list of bookable dates for each configured branch
2. For each date, keep only showtimes whose **screen type** and **movie title keywords** match the config
3. If a (branch, date, movie) combination is not yet in `state/snapshot.json`, send a Telegram alert and record it
4. If fetching fails, the failure itself is also sent to Telegram, so the bot never breaks silently

## Use it in your own repo

1. **Fork** this repo (or click *Use this template*)
2. In Telegram, open `@BotFather` → `/newbot` to create a bot and copy its token
3. Send any message (e.g. `/start`) to your new bot, then open `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy the number after `"chat":{"id":`
4. In your repo, go to **Settings → Secrets and variables → Actions** and add two repository secrets:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
5. Go to **Actions** → *Check Megabox showtimes* → **Run workflow**
   - Check `test_message` → sends a Telegram connection test
   - Leave it unchecked → runs one real check
6. Edit `config.json` for the movies and branches you want

## config.json

```json
{
  "notify_on_error": true,
  "targets": [
    {
      "name": "라라랜드 송도 돌비",
      "enabled": true,
      "branches": ["4062"],
      "theater_kinds": ["DBC"],
      "keywords": ["라라랜드", "la la land"]
    }
  ]
}
```

| Field | Description |
|---|---|
| `name` | Label shown in the alert title; also used as part of the duplicate-prevention key |
| `branches` | List of Megabox branch codes (`brchNo`, see table below) |
| `theater_kinds` | Screen type codes. Empty list = all screens |
| `keywords` | Substrings to look for in the movie title (Korean or English, case-insensitive). Empty list = all movies |
| `enabled` | Set to `false` to skip this target |
| `notify_on_error` | Send a Telegram message when a check fails (default `true`) |

### Screen type codes (`theabKindCd`)

| Code | Screen |
|---|---|
| `DBC` | Dolby Cinema |
| `RCL` | LE RECLINER |
| `NOR` | Standard |

Other premium screen codes can be found in the `theabKindCd` field of Megabox's schedule response.

### Branches with Dolby Cinema (`brchNo`)

| Branch | `brchNo` |
|---|---|
| COEX (코엑스) | `1351` |
| Songdo Triple Street (송도 트리플스트리트) | `4062` |
| Namyangju Hyundai Outlet Space1 (남양주현대아울렛 스페이스원) | `0019` |
| Anseong Starfield (안성스타필드) | `0020` |
| Hanam Starfield (하남스타필드) | `4651` |
| Suwon AK Plaza (수원AK플라자) | `0052` |
| Daejeon Shinsegae Art & Science (대전신세계 아트앤사이언스) | `0028` |
| Daegu Shinsegae (대구신세계) | `7011` |

For any other branch, the code is the `brchNo=` value in the branch page URL (e.g. `megabox.co.kr/theater?brchNo=4062`).

## Run locally

```bash
pip install -r requirements.txt
python megabox_alert.py --dry-run          # print results only, no alerts or snapshot writes
export TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=...
python megabox_alert.py --test-message     # Telegram connection test
python megabox_alert.py                    # real run
```

## Notes

- GitHub Actions `schedule` runs can start several minutes (sometimes tens of minutes) late. The cron is set slightly before the target time for this reason. If you need minute-level alerts, run it on an always-on server instead.
- GitHub disables scheduled workflows in public repos after 60 days without activity. To prevent this, the workflow updates `state/heartbeat.txt` once a month.
- If Megabox ever blocks GitHub's runner IPs, you will get a failure alert. In that case, run the script with cron on a home PC or a Raspberry Pi.
- The bot may stop working if Megabox changes its website. Please open an issue if that happens.

## License

MIT
