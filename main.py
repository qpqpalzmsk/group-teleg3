import os
import asyncio
import random
import time

from telethon import TelegramClient, events, functions
from telethon.errors import FloodWaitError, RPCError

# ========== [1] 텔레그램 API 설정 ==========
API_ID = int(os.getenv("API_ID", "27565874"))
API_HASH = os.getenv("API_HASH", "de8f48b4a95aceea0ed754f7bb3af0c3")
PHONE_NUMBER = os.getenv("PHONE_NUMBER", "+821080133483")  # 예시

SESSION_NAME = "my_telethon_session"
client = TelegramClient(
    SESSION_NAME,
    API_ID,
    API_HASH,
    timeout=60,
    auto_reconnect=True
)

# ========== [2] 홍보용 계정(마케팅 계정) 설정 ==========
#    - '@계정형식' 또는 숫자 ID 등
MARKETING_USER = "@cuz_z"  # 예시

# ========== [3] 연결/세션 확인 함수 ==========
async def ensure_connected():
    if not client.is_connected():
        print("[INFO] Telethon is disconnected. Reconnecting...")
        await client.connect()

    if not await client.is_user_authorized():
        print("[WARN] 세션 없음/만료 → OTP 로그인 시도")
        await client.start(phone=PHONE_NUMBER)
        print("[INFO] 재로그인(OTP) 완료")

# ========== [4] keep_alive 함수 ==========
async def keep_alive():
    """
    - 주기적으로(예: 10분 간격) 호출해 Telethon 연결 상태 점검
    - 간단한 API 호출로 서버와 통신
    """
    try:
        await ensure_connected()
        await client(functions.help.GetNearestDcRequest())
        print("[INFO] keep_alive ping success")
    except Exception as e:
        print(f"[ERROR] keep_alive ping fail: {e}")

# ========== [5] 그룹 목록 로드 ==========
async def load_all_groups():
    await ensure_connected()
    dialogs = await client.get_dialogs()
    return [d.id for d in dialogs if (d.is_group or d.is_channel)]

# ========== [6] 홍보용 계정의 '최근 메시지' 가져오기 ==========
async def get_last_message_from_user(user):
    """
    - user로부터 최근 메시지 1개(Telethon의 Message 객체) 불러오기
    - 없으면 None 반환
    """
    try:
        await ensure_connected()
        msgs = await client.get_messages(user, limit=1)
        if msgs:
            return msgs[0]  # 가장 최근 메시지 객체
        else:
            return None
    except RPCError as e:
        print(f"[ERROR] get_last_message_from_user RPC 에러: {e}")
        return None

# ========== [7] 전체 그룹에 '최근 메시지'를 전달(Forward) ==========
async def forward_ad_to_groups():
    """
    1) 홍보용 계정의 최근 메시지 1개를 가져오기
    2) 그룹 리스트(전체) 불러오기
    3) 그룹마다 forward_messages()
    4) 그룹 간 딜레이 (원하는 만큼)
    """
    # (A) 최근 메시지 가져오기
    last_msg = await get_last_message_from_user(MARKETING_USER)
    if not last_msg:
        print("[WARN] 홍보용 계정에서 메시지를 못 가져옴. 건너뜀.")
        return

    # (B) 그룹 리스트 가져오기
    group_list = await load_all_groups()
    if not group_list:
        print("[WARN] 가입된 그룹이 없습니다.")
        return

    print(f"[INFO] 총 {len(group_list)}개 그룹에 홍보 메시지 전달 시작.")

    # (C) 순차적 포워딩
    for idx, grp_id in enumerate(group_list, start=1):
        try:
            # forward_messages(destination, message_ids, from_peer)
            await client.forward_messages(grp_id, last_msg.id, from_peer=last_msg.sender_id)

            print(f"[INFO] {idx}/{len(group_list)} → Forward 성공: {grp_id}")

        except FloodWaitError as e:
            print(f"[ERROR] FloodWait: {e}. 일정 시간 대기 후 재시도 필요.")
            # 텔레그램에서 대기 시간(e.seconds)을 주는 경우, 그만큼 sleep 후 재시도 가능
            await asyncio.sleep(e.seconds + 10)

        except RPCError as e:
            print(f"[ERROR] Forward RPCError(chat_id={grp_id}): {e}")

        except Exception as e:
            print(f"[ERROR] Forward 실패(chat_id={grp_id}): {e}")

        # (C-1) 그룹 간 딜레이 (PLACEHOLDER)
        #       필요에 따라 조정 (ex. 30~60초, 2~5분 등)
        delay = random.randint(30, 60)  # 예시로 고정 30초 (직접 수정 필요)
        # delay = random.randint(60, 120)  # 1~2분 랜덤 등
        print(f"[INFO] 다음 그룹 전송까지 {delay}초 대기...")
        await asyncio.sleep(delay)

    print("[INFO] 모든 그룹 전송(Forward) 완료.")

# ========== [8] 전송 사이클(반복) ==========
async def send_messages_loop():
    """
    - 무한 루프
    - forward_ad_to_groups() 실행
    - 사이클 간 대기 (PLACEHOLDER)
    """
    while True:
        try:
            await ensure_connected()

            # (1) 전체 그룹에 포워딩
            await forward_ad_to_groups()

            # (2) 사이클 간 대기 (PLACEHOLDER)
            #     예: 1시간 대기
            cycle_delay = 1 * 60 * 60  # 3시간
            print(f"[INFO] 한 사이클 끝. {cycle_delay//3600}시간 대기 후 재시작.")
            await asyncio.sleep(cycle_delay)

        except Exception as e:
            print(f"[ERROR] send_messages_loop() 에러: {e}")
            # 에러 시 잠시 대기 후 재시도
            await asyncio.sleep(600)

# ========== [9] 메인 함수 ==========
async def main():
    # 1) 텔레그램 연결
    await client.connect()
    print("[INFO] client.connect() 완료")

    # 2) 세션 인증 여부
    if not (await client.is_user_authorized()):
        print("[INFO] 세션 없음 or 만료 → OTP 로그인 시도")
        await client.start(phone=PHONE_NUMBER)
        print("[INFO] 첫 로그인 or 재인증 성공")
    else:
        print("[INFO] 이미 인증된 세션 (OTP 불필요)")

    @client.on(events.NewMessage(pattern="/ping"))
    async def ping_handler(event):
        await event.respond("pong!")

    print("[INFO] 텔레그램 로그인(세션) 준비 완료")

    # (A) keep_alive 주기적으로 실행
    async def keep_alive_scheduler():
        while True:
            await keep_alive()
            await asyncio.sleep(600)  # 10분

    # (B) send_messages_loop + keep_alive_scheduler 병행
    await asyncio.gather(
        send_messages_loop(),
        keep_alive_scheduler()
    )

# ========== [10] 실행 ==========
if __name__ == "__main__":
    asyncio.run(main())
