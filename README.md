# 메가박스 돌비시네마 예매 오픈 알리미

메가박스 특정 지점·특정 상영관(예: 돌비시네마)에 원하는 영화의 회차가 **새로 열리면 Telegram으로 알려주는** 작은 봇입니다.
GitHub Actions에서 하루 두 번(점심 12시·저녁 6시 무렵, KST) 실행되므로 서버나 PC를 켜둘 필요가 없습니다.

기존 알리미들이 코엑스·남양주 돌비 위주라서, **송도(트리플스트리트) 돌비시네마**를 기본 예시로 만들었고 다른 지점도 설정만 바꾸면 됩니다.

> 이 프로젝트는 메가박스와 무관한 비공식 도구이며, 누구나 볼 수 있는 상영시간표 정보만 조회합니다.
> 알림 용도이고 자동 예매 기능은 없습니다. 서버에 부담을 주지 않도록 실행 빈도를 과하게 올리지 마세요.

## 동작 방식

1. 지점의 예매 가능한 날짜 목록을 가져옴
2. 날짜별 상영시간표에서 `상영관 종류`와 `영화 제목 키워드`가 일치하는 회차만 추림
3. `state/snapshot.json`에 없는 (지점, 날짜, 영화) 조합이면 Telegram 알림 전송 후 기록
4. 조회가 실패하면 실패 사실도 Telegram으로 알림 (조용히 고장나는 것 방지)

## 내 repo에서 쓰기

1. 이 repo를 **Fork** (또는 Use this template)
2. Telegram에서 `@BotFather` → `/newbot` 으로 봇을 만들고 token 받기
3. 만든 봇에게 아무 메시지나 보낸 뒤 `https://api.telegram.org/bot<TOKEN>/getUpdates` 에서 `chat.id` 확인
4. repo **Settings → Secrets and variables → Actions** 에 등록
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
5. **Settings → Actions → General → Workflow permissions** 를 *Read and write permissions* 로 변경
6. **Actions** 탭 → *Megabox 예매 오픈 확인* → *Run workflow*
   - `test_message` 체크 → Telegram 연결 테스트
   - 체크 해제 → 실제 조회 1회 실행
7. `config.json` 을 원하는 영화·지점으로 수정

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

| 필드 | 설명 |
|---|---|
| `name` | 알림 제목에 표시되는 이름 (중복 방지 기록의 key로도 쓰임) |
| `branches` | 메가박스 지점 코드 목록 (아래 표 참고) |
| `theater_kinds` | 상영관 종류 코드. 비우면 모든 상영관 |
| `keywords` | 영화 제목(한글/영문)에 포함될 문자열. 대소문자 무시, 비우면 모든 영화 |
| `enabled` | `false`면 건너뜀 |

### 상영관 종류 코드 (`theabKindCd`)

| 코드 | 상영관 |
|---|---|
| `DBC` | Dolby Cinema |
| `RCL` | 르 리클라이너 |
| `NOR` | 일반관 |

다른 특별관 코드는 메가박스 상영시간표 응답의 `theabKindCd` 값을 보면 확인할 수 있습니다.

### 돌비시네마 운영 지점 코드 (`brchNo`)

| 지점 | brchNo |
|---|---|
| 코엑스 | `1351` |
| 송도(트리플스트리트) | `4062` |
| 남양주현대아울렛 스페이스원 | `0019` |
| 안성스타필드 | `0020` |
| 하남스타필드 | `4651` |
| 수원AK플라자(수원역) | `0052` |
| 대전신세계 아트앤사이언스 | `0028` |
| 대구신세계(동대구) | `7011` |

다른 지점 코드는 메가박스 극장 페이지 주소의 `brchNo=` 값입니다. (예: `megabox.co.kr/theater?brchNo=4062`)

## 로컬 실행

```bash
pip install -r requirements.txt
python megabox_alert.py --dry-run          # 알림·기록 없이 결과만 출력
export TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=...
python megabox_alert.py --test-message     # Telegram 연결 테스트
python megabox_alert.py                    # 실제 실행
```

## 알아둘 점

- GitHub Actions의 `schedule`은 정시보다 늦게 실행될 수 있습니다. 분 단위 선착순 알림이 필요하면 상시 실행 서버를 쓰세요.
- 공개 repo는 60일간 활동이 없으면 schedule이 자동으로 꺼집니다. 이를 막기 위해 매월 `state/heartbeat.txt`를 갱신합니다.
- 메가박스가 해외 IP(GitHub runner)를 차단하면 조회 실패 알림이 옵니다. 그때는 집 PC나 Raspberry Pi에서 cron으로 실행하세요.
- 메가박스 사이트 구조가 바뀌면 동작하지 않을 수 있습니다. 이슈로 알려주세요.

## License

MIT
