import os
import glob
import asyncio
import random
import time

from telethon import TelegramClient, events, functions

# ========== [1] 텔레그램 API 설정 ==========
API_ID = int(os.getenv("API_ID", "25051141"))
API_HASH = os.getenv("API_HASH", "b2e42c6781f403f905d2f4d0640b120b")
PHONE_NUMBER = os.getenv("PHONE_NUMBER", "+821080194291")  # 예시 번호

SESSION_NAME = "my_telethon_session"
client = TelegramClient(
    SESSION_NAME,
    API_ID,
    API_HASH,
    timeout=60,
    auto_reconnect=True
)

# ========== [2] 폴더 경로 설정 ==========
AD_TEXTS_DIR = "ad_texts"     # 여러 txt 광고 문구 파일이 들어있는 폴더
AD_IMAGES_DIR = "ad_images"   # 여러 이미지 파일이 들어있는 폴더

# ========== [3] 랜덤 메시지/이미지 로드 함수 ==========
def load_random_message():
    """
    ad_texts 폴더에 있는 .txt 파일 중 하나를 무작위로 골라 읽는다.
    파일이 하나도 없으면 기본 문구 반환.
    """
    txt_files = glob.glob(os.path.join(AD_TEXTS_DIR, "*.txt"))
    if not txt_files:
        return "광고 문구가 없습니다."
    choice_file = random.choice(txt_files)
    with open(choice_file, "r", encoding="utf-8") as f:
        return f.read().strip()

def get_random_image():
    """
    ad_images 폴더에 있는 이미지 파일(.jpg, .png 등) 중 하나를 무작위로 선택.
    없으면 None 반환.
    """
    img_patterns = ("*.jpg", "*.jpeg", "*.png", "*.gif")  # 필요한 확장자 패턴
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
    10분마다 호출할 예정.
    간단한 API 호출로 Telethon 연결 상태 유지.
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
    # 그룹(슈퍼그룹), 채널(방송 채널 포함) 모두 가져옴
    return [d.id for d in dialogs if d.is_group or d.is_channel]

# ========== [7] 모든 그룹에 "랜덤 메시지+이미지" 전송 후 2~2.5시간 대기 반복 ==========
async def send_messages_loop():
    """
    1) 모든 그룹에 '랜덤으로 선택한 메시지/이미지' 전송
    2) 전송 완료 후 2~2.5시간 대기
    3) 무한 반복
    """
    while True:
        try:
            await ensure_connected()
            group_list = await load_all_groups()

            if not group_list:
                print("[WARN] 가입된 그룹/채널이 없습니다. 10분 뒤 재시도합니다.")
                await asyncio.sleep(600)
                continue

            print(f"[INFO] 이번 라운드에서 {len(group_list)}개 그룹에 메시지를 전송합니다.")
            # 전송에 쓸 메시지/이미지를 "한 번 선택"하는 게 아니라,
            # 그룹마다 매번 새로 랜덤화하려면 아래 루프 안에서 각각 불러도 됨
            # => 아래서는 '각 그룹' 전송 시점마다 새로 랜덤화하는 코드 예시

            for grp_id in group_list:
                # (1) 메시지/이미지 각각 랜덤 선택
                text_msg = load_random_message()
                img_path = get_random_image()

                try:
                    if img_path:
                        # 이미지와 함께 전송
                        await client.send_file(grp_id, img_path, caption=text_msg)
                        print(f"[INFO] (이미지+캡션) 전송 성공 → {grp_id}")
                    else:
                        # 이미지가 없으면 텍스트만 전송
                        await client.send_message(grp_id, text_msg)
                        print(f"[INFO] (텍스트만) 전송 성공 → {grp_id}")
                except Exception as e:
                    print(f"[ERROR] 전송 실패(chat_id={grp_id}): {e}")

            # 모든 그룹 전송 완료 후 2~2.5시간(7200~9000초) 대기
            rest_time = random.randint(7200, 9000)  # 2h ~ 2.5h
            print(f"[INFO] 모든 그룹 전송 완료. {rest_time // 60}분 뒤 다음 라운드를 시작합니다.")
            await asyncio.sleep(rest_time)

        except Exception as e:
            print(f"[ERROR] send_messages_loop() 에러: {e}")
            # 에러 발생 시 잠시 대기 후 재시도
            await asyncio.sleep(600)

# ========== [8] 메인 함수 ==========
async def main():
    # (1) 텔레그램 연결 시도
    await client.connect()
    print("[INFO] client.connect() 완료")

    # (2) 세션 인증 여부
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

    # (3) keep_alive 10분 간격 실행
    async def keep_alive_scheduler():
        while True:
            await keep_alive()
            await asyncio.sleep(600)  # 10분

    # (4) send_messages_loop()와 keep_alive_scheduler()를 병행 실행
    await asyncio.gather(
        send_messages_loop(),
        keep_alive_scheduler()
    )

# ========== [9] 프로그램 시작점 ==========
if __name__ == "__main__":
    asyncio.run(main())