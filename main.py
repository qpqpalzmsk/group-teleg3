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
MARKETING_USER = "@cuz_z"  # 유저네임 혹은 정수 ID

# ========== [3] 기본 설정 ==========
MAX_GROUPS = 20          # 한 계정에 20개 그룹
BATCH_SIZE = 5           # 한 번에 5개씩 배치
GROUP_DELAY_RANGE = (150, 210)      # 그룹 간 30~60초
BATCH_DELAY_RANGE = (900, 1200)   # 배치 끝 15~20분 (초 단위: 900=15분, 1200=20분)
CYCLE_DELAY_RANGE = (1200, 1800)  # 사이클 끝 20~30분

# ========== [4] 연결/세션 확인 ==========
async def ensure_connected():
    if not client.is_connected():
        print("[INFO] Telethon is disconnected. Reconnecting...")
        await client.connect()
    if not await client.is_user_authorized():
        print("[WARN] 세션 없음/만료 → OTP 로그인 시도")
        await client.start(phone=PHONE_NUMBER)
        print("[INFO] 재로그인(OTP) 완료")

# ========== [5] keep_alive (연결 유지) ==========
async def keep_alive():
    """
    (예) 10분(600초) 간격으로 Telethon 연결 상태 유지
    """
    try:
        await ensure_connected()
        await client(functions.help.GetNearestDcRequest())
        print("[INFO] keep_alive ping success")
    except Exception as e:
        print(f"[ERROR] keep_alive ping fail: {e}")

# ========== [6] 그룹 로드 (20개까지만) ==========
async def load_twenty_groups():
    await ensure_connected()
    dialogs = await client.get_dialogs()
    group_list = [d.id for d in dialogs if (d.is_group or d.is_channel)]
    return group_list[:MAX_GROUPS]  # 최대 20개만

# ========== [7] 홍보 계정 메시지 불러오기 (3개) ==========
async def get_recent_messages(user, limit=3):
    await ensure_connected()
    msgs = await client.get_messages(user, limit=limit)
    return msgs  # 최신순으로 msgs[0]이 가장 최근

# ========== [8] 20개 그룹을 5개씩 배치로 포워드 + 스팸 방지 대기 ==========
async def forward_one_cycle():
    """
    - (1) 홍보 계정의 최근 3개 메시지 가져옴
    - (2) 20개 그룹 대상
    - (3) 5개씩 배치 전송 + 각 그룹 간 30~60초, 배치 끝 15~20분
    - (4) 사이클 끝나면 20~30분 대기
    """
    # (A) 홍보 메시지 3개
    marketing_msgs = await get_recent_messages(MARKETING_USER, limit=3)
    if not marketing_msgs:
        print("[WARN] 홍보 메시지 없음. 10분 후 재시도.")
        await asyncio.sleep(600)
        return

    num_msgs = len(marketing_msgs)
    print(f"[INFO] 홍보 메시지 {num_msgs}개 확보.")

    # (B) 20개 그룹
    target_groups = await load_twenty_groups()
    if not target_groups:
        print("[WARN] 그룹 0개. 10분 후 재시도.")
        await asyncio.sleep(600)
        return

    print(f"[INFO] 총 {len(target_groups)}개 그룹. 5개씩 배치로 진행.")
    # 무작위 셔플 (원하시면 생략 가능)
    random.shuffle(target_groups)

    # (C) 메시지 순환
    msg_idx = 0
    index = 0

    while index < len(target_groups):
        batch = target_groups[index : index + BATCH_SIZE]
        if not batch:
            break

        print(f"[INFO] 배치 전송 (index={index}, size={len(batch)})")

        # (C-1) 배치 내 그룹 전송
        for grp in batch:
            current_msg = marketing_msgs[msg_idx]
            try:
                await client.forward_messages(
                    entity=grp,
                    messages=current_msg.id,
                    from_peer=current_msg.sender_id
                )
                print(f"[INFO] Forward 성공: group={grp}, msg_idx={msg_idx}")
            except FloodWaitError as e:
                print(f"[ERROR] FloodWait {e.seconds}초 → 대기 후 재시도")
                await asyncio.sleep(e.seconds + 5)
                # 재시도
                try:
                    await client.forward_messages(
                        entity=grp,
                        messages=current_msg.id,
                        from_peer=current_msg.sender_id
                    )
                except Exception as e2:
                    print(f"[ERROR] 재시도 실패(chat_id={grp}): {e2}")
            except RPCError as e:
                print(f"[ERROR] RPCError(chat_id={grp}): {e}")
            except Exception as e:
                print(f"[ERROR] Forward 실패(chat_id={grp}): {e}")

            # 메시지 순환
            msg_idx = (msg_idx + 1) % num_msgs

            # 그룹 간 30~60초
            delay_g = random.randint(*GROUP_DELAY_RANGE)
            print(f"[INFO] 다음 그룹까지 {delay_g}초 대기...")
            await asyncio.sleep(delay_g)

        index += BATCH_SIZE

        # (C-2) 배치 간 15~20분
        if index < len(target_groups):
            delay_b = random.randint(*BATCH_DELAY_RANGE)
            print(f"[INFO] 배치 완료. {delay_b//60}분 후 다음 배치 진행.")
            await asyncio.sleep(delay_b)

    # (D) 사이클 끝 - 20~30분
    delay_c = random.randint(*CYCLE_DELAY_RANGE)
    print(f"[INFO] 사이클(20개) 전송 완료. {delay_c//60}분 후 다시 시작.")
    await asyncio.sleep(delay_c)

# ========== [9] 메인 전송 루프 ==========
async def send_messages_loop():
    while True:
        try:
            await forward_one_cycle()
        except Exception as e:
            print(f"[ERROR] send_messages_loop() 에러: {e}")
            print("[INFO] 10분 후 재시도.")
            await asyncio.sleep(600)

# ========== [10] 메인 함수 ==========
async def main():
    await client.connect()
    print("[INFO] client.connect() 완료")

    if not (await client.is_user_authorized()):
        print("[INFO] 세션 없음/만료 → OTP 로그인 시도")
        await client.start(phone=PHONE_NUMBER)
        print("[INFO] 로그인/재인증 성공")
    else:
        print("[INFO] 이미 인증된 세션 (OTP 불필요)")

    # 명령어 예시 (/ping)
    @client.on(events.NewMessage(pattern="/ping"))
    async def ping_handler(event):
        await event.respond("pong!")

    print("[INFO] 텔레그램 로그인(세션) 준비 완료")

    # (A) keep_alive 10분 간격
    async def keep_alive_scheduler():
        while True:
            await keep_alive()
            await asyncio.sleep(600)  # 10분

    # (B) 전송 루프 병행
    await asyncio.gather(
        send_messages_loop(),
        keep_alive_scheduler()
    )

if __name__ == "__main__":
    asyncio.run(main())