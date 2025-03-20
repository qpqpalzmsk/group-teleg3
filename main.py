import os
import glob
import asyncio
import random
import time

from telethon import TelegramClient, events, functions

# ========== [1] 텔레그램 API 설정 ==========
API_ID = int(os.getenv("API_ID", "21946248"))
API_HASH = os.getenv("API_HASH", "78c61b073bcaf43c2a03b472aae5199f")
PHONE_NUMBER = os.getenv("PHONE_NUMBER", "+819016714809")  # 예시 번호

SESSION_NAME = "my_telethon_session"
client = TelegramClient(
    SESSION_NAME,
    API_ID,
    API_HASH,
    timeout=60,
    auto_reconnect=True
)

# ========== [2] 예: 여러 광고 텍스트/이미지 폴더 ==========
AD_TEXTS_DIR = "ad_texts"
AD_IMAGES_DIR = "ad_images"

# ========== [3] 랜덤 메시지/이미지 선택 함수 (선택사항) ==========
def load_random_message():
    """
    ad_texts 폴더에 있는 .txt 파일 중 하나를 무작위로 골라 내용을 반환.
    파일이 없다면 기본 문구 반환.
    """
    txt_files = glob.glob(os.path.join(AD_TEXTS_DIR, "*.txt"))
    if not txt_files:
        return "광고 문구가 없습니다."
    choice_file = random.choice(txt_files)
    with open(choice_file, "r", encoding="utf-8") as f:
        return f.read().strip()

def get_random_image():
    """
    ad_images 폴더에 있는 이미지 파일(.jpg, .png 등) 중 하나를 무작위로 반환.
    없으면 None
    """
    img_patterns = ("*.jpg", "*.jpeg", "*.png", "*.gif")
    img_files = []
    for pattern in img_patterns:
        img_files.extend(glob.glob(os.path.join(AD_IMAGES_DIR, pattern)))

    if not img_files:
        return None
    return random.choice(img_files)

# ========== [4] 연결/세션 확인 함수 ==========
async def ensure_connected():
    if not client.is_connected():
        print("[INFO] Telethon is disconnected. Reconnecting...")
        await client.connect()

    if not await client.is_user_authorized():
        print("[WARN] 세션 없음/만료 → OTP 로그인 시도")
        await client.start(phone=PHONE_NUMBER)
        print("[INFO] 재로그인(OTP) 완료")

# ========== [5] keep_alive 함수 ==========
async def keep_alive():
    """
    10분(600초)마다 호출하여 간단한 API 요청으로 Telethon 연결 상태 유지.
    """
    try:
        await ensure_connected()
        await client(functions.help.GetNearestDcRequest())
        print("[INFO] keep_alive ping success")
    except Exception as e:
        print(f"[ERROR] keep_alive ping fail: {e}")

# ========== [6] '내 계정'이 가입된 그룹/채널 불러오기 ==========
async def load_all_groups():
    await ensure_connected()
    dialogs = await client.get_dialogs()
    return [d.id for d in dialogs if d.is_group or d.is_channel]

# ========== [7] 전송 로직:  
#    - 그룹 리스트 무작위 섞기  
#    - 10~20개씩 배치 전송 + 배치 내 그룹 간 5~15초 쉬기  
#    - 배치 간 20분 쉬기  
#    - 한 사이클 끝나면 40~50분 쉬기  
#    - 반복  
# =========================================
async def send_messages_loop():
    while True:
        try:
            # (A) 그룹 목록 불러오기
            await ensure_connected()
            group_list = await load_all_groups()
            if not group_list:
                print("[WARN] 가입된 그룹/채널이 없습니다. 10분 뒤 재시도합니다.")
                await asyncio.sleep(600)
                continue

            # (B) 그룹 순서 무작위 섞기
            random.shuffle(group_list)

            print(f"[INFO] 이번 사이클: 총 {len(group_list)}개 그룹 → 10~20개 배치씩 전송")

            index = 0
            while index < len(group_list):
                # (1) 이번 배치 크기: 10 ~ 20 사이 랜덤
                batch_size = random.randint(10, 20)
                batch = group_list[index: index + batch_size]
                if not batch:
                    break

                print(f"[INFO] 배치 전송 (index={index} ~ {index + len(batch) - 1}), 그룹 수={len(batch)}")

                # (2) 배치 내 각 그룹에 전송
                for grp_id in batch:
                    text_msg = load_random_message()  # 랜덤 텍스트
                    img_path = get_random_image()      # 랜덤 이미지

                    try:
                        if img_path:
                            await client.send_file(grp_id, img_path, caption=text_msg)
                            print(f"[INFO] (이미지+캡션) 전송 성공 → {grp_id}")
                        else:
                            await client.send_message(grp_id, text_msg)
                            print(f"[INFO] (텍스트만) 전송 성공 → {grp_id}")
                    except Exception as e:
                        print(f"[ERROR] 전송 실패(chat_id={grp_id}): {e}")

                    # (2-1) 배치 내 그룹 간 짧은 대기 (5~15초)
                    small_delay = random.randint(5, 15)
                    print(f"[INFO] 다음 그룹 전송까지 {small_delay}초 대기...")
                    await asyncio.sleep(small_delay)

                index += batch_size

                # (3) 배치 간 대기: 20분(1200초)
                print("[INFO] 이번 배치 전송 완료. 20분 대기 후 다음 배치로 넘어갑니다.")
                await asyncio.sleep(1200)  # 20분

            # (C) 한 사이클(모든 그룹) 끝났으니 40~50분 쉬기
            rest_time = random.randint(2400, 3000)  # 40~50분(초 단위)
            print(f"[INFO] 모든 그룹 전송 사이클 종료. {rest_time // 60}분 뒤 다음 사이클 시작.")
            await asyncio.sleep(rest_time)

        except Exception as e:
            print(f"[ERROR] send_messages_loop() 에러: {e}")
            # 에러 시 잠시 대기 후 재시도
            await asyncio.sleep(600)

# ========== [8] 메인 함수 ==========
async def main():
    await client.connect()
    print("[INFO] client.connect() 완료")

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

    # (A) keep_alive : 10분 간격
    async def keep_alive_scheduler():
        while True:
            await keep_alive()
            await asyncio.sleep(600)  # 10분

    # (B) 메인 전송 루프와 keep_alive 스케줄 병행 실행
    await asyncio.gather(
        send_messages_loop(),
        keep_alive_scheduler()
    )

# ========== [9] 실제 실행 ==========
if __name__ == "__main__":
    asyncio.run(main())