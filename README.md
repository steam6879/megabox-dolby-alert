# Cinema Booking Open Alert (Megabox · Lotte Cinema)

A small bot that sends a **Telegram notification when new showtimes open** for a movie you are waiting for, at specific branches and screen types of Korean cinema chains:

- **Megabox (메가박스)**, e.g. Dolby Cinema
- **Lotte Cinema (롯데시네마)**, e.g. 광음시네마, SUPER PLEX, CHARLOTTE

It runs on GitHub Actions twice a day (around 12:00 and 18:00 KST), so you don't need to keep a server or PC running.

Existing alert bots mostly cover the COEX and Namyangju Dolby Cinemas, so this project ships with **Songdo (Triple Street) Dolby Cinema** and **Lotte Cinema Bupyeong Station 광음시네마** as examples. Any other branch works by changing the config.

> This is an unofficial tool, not affiliated with any cinema chain. It only reads the publicly available showtime schedules.
> It sends notifications only and does not book tickets automatically. Please don't raise the run frequency to a level that puts load on the cinemas' servers.

## How it works

1. For each target in `config.json`, fetch the showtimes of every listed branch for all bookable dates
2. Keep only showtimes whose **screen type** and **movie title keywords** match the target
3. If a (branch, date, movie) combination is not yet in `state/snapshot.json`, send a Telegram alert and record it
4. If fetching fails, the failure itself is also sent to Telegram, so the bot never breaks silently

## Use it in your own repo

1. **Fork** this repo (or click *Use this template*)
2. In Telegram, open `@BotFather` → `/newbot` to create a bot and copy its token
3. Send any message (e.g. `/start`) to your new bot, then open `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy the number after `"chat":{"id":`
4. In your repo, go to **Settings → Secrets and variables → Actions** and add two repository secrets:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
5. Go to **Actions** → *Check cinema showtimes* → **Run workflow**
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
      "chain": "megabox",
      "branches": ["4062"],
      "theater_kinds": ["DBC"],
      "keywords": ["라라랜드", "la la land"]
    },
    {
      "name": "포드 V 페라리 부평역사 광음시네마",
      "chain": "lotte",
      "branches": ["3008"],
      "theater_kinds": ["901"],
      "keywords": ["포드 V 페라리", "Ford v Ferrari"]
    }
  ]
}
```

| Field | Description |
|---|---|
| `name` | Label shown in the alert title; also used as part of the duplicate-prevention key, so keep it unique |
| `chain` | `megabox` (default) or `lotte` |
| `branches` | List of branch codes for that chain (see tables below) |
| `theater_kinds` | Screen type codes for that chain. Empty list = all screens |
| `keywords` | Text to look for in the movie title (Korean or English). Case, spaces and punctuation are ignored, so `포드v페라리` matches `포드 V 페라리`. Empty list = all movies |
| `enabled` | Set to `false` to skip this target |
| `notify_on_error` | Send a Telegram message when a check fails (default `true`) |

### Megabox

Screen type codes (`theabKindCd`):

| Code | Screen |
|---|---|
| `DBC` | Dolby Cinema |
| `RCL` | LE RECLINER |
| `NOR` | Standard |

Branches with Dolby Cinema (`brchNo`):

| Branch | Code |
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

### Lotte Cinema

Screen type codes (`ScreenDivisionCode`):

| Code | Screen |
|---|---|
| `100` | Standard |
| `901` | 광음시네마 (Kwangeum Cinema) |
| `940` | SUPER PLEX |
| `931` | SUPER MX4D |
| `300` | CHARLOTTE |
| `301` | CHARLOTTE Private |
| `960` | Cine Family |

Example branches (`CinemaID`):

| Branch | Code |
|---|---|
| World Tower (월드타워) | `1016` |
| Bupyeong Station (부평역사) | `3008` |
| Bupyeong Galsan (부평갈산) | `3050` |
| Incheon Asiad (인천아시아드) | `3035` |
| Incheon Terminal (인천터미널) | `3038` |
| Gasan Digital (가산디지털) | `1013` |

For any other branch, the `CinemaID` appears in the `cinemaID` value of the requests the Lotte Cinema schedule page makes (the last number in `1|0002|3008`).

### CGV is not supported

CGV's website blocks requests from cloud and data-center IPs (including GitHub Actions runners) with Cloudflare, so it cannot be checked from this setup. This project does not attempt to bypass that protection.

## Run locally

```bash
pip install -r requirements.txt
python cinema_alert.py --dry-run          # print results only, no alerts or snapshot writes
export TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=...
python cinema_alert.py --test-message     # Telegram connection test
python cinema_alert.py                    # real run
```

## Adding another chain

Add a module under `providers/` that implements `fetch_showtimes(session, branch) -> list[dict]` returning the normalized fields listed in `providers/__init__.py`, then register it in `PROVIDERS`.

## Notes

- GitHub Actions `schedule` runs can start several minutes (sometimes tens of minutes) late. The cron is set slightly before the target time for this reason. If you need minute-level alerts, run it on an always-on server instead.
- GitHub disables scheduled workflows in public repos after 60 days without activity. To prevent this, the workflow updates `state/heartbeat.txt` once a month.
- If a cinema ever blocks GitHub's runner IPs, you will get a failure alert.
- The bot may stop working if a cinema changes its website. Please open an issue if that happens.

## License

MIT
