import discord
import os
import aiohttp
import asyncio
from discord.ext import tasks
from discord import app_commands
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
import random
from flask import Flask
import threading


# -------------------
# .env 불러오기
# -------------------
load_dotenv()
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
KOYEB_URL = os.getenv("KOYEB_URL")
print("KOYEB_URL:", KOYEB_URL, type(KOYEB_URL))
CHANNEL_ID = None

# -------------------
# Discord 봇 세팅
# -------------------
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# -------------------
# Flask 헬스체크
# -------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "OK", 200
def run_flask():
    app.run(host="0.0.0.0", port=8000)

# Flask 백그라운드 실행
threading.Thread(target=run_flask).start()

# -------------------
# Self-Ping
# -------------------
async def ping_self():
    await bot.wait_until_ready()
    while not bot.is_closed():
        url = os.getenv("KOYEB_URL")
        if not url:
            print("KOYEB_URL not set, ping skipped")
            await asyncio.sleep(180)
            continue
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    print("Ping successful:", resp.status)
        except Exception as e:
            print("Ping failed:", e)
        await asyncio.sleep(180)


# -------------------
# 오라클 목록 및 효과
# -------------------
ORACLE_EFFECTS = {
    "힘(Strength)": "최대 대미지 증가 (+35)",
    "황제(The Emperor)": "크리티컬 대미지 증가 (+2%)",
    "여제(The Empress)": "풍년가 지속시간 증가 (+300초)",
    "태양(The Sun)": "비바체 지속시간 증가 (+300초)",
    "정의(Justice)": "최대 생명력 증가 (+1000)",
    "심판(Judgement)": "채집 속도 증가 (+20)",
    "교황(The Hierophant)": "휴즈 확률 증가 (+10%)",
    "고위 여사제(The High Priestess)": "교역시 이동 속도 증가 (+20)",
    "연인(The Lovers)": "음악 버프 효과 증가 (+2)",
    "전차(The Chariot)": "전장의 서곡 지속시간 증가 (+300초)",
    "달(The Moon)": "최대 스태미나 증가 (+1000)",
    "탑(The Tower)": "연금술 대미지 증가 (+15)",
    "매달린 남자(The Hanged Man)": "전투 경험치 2배",
    "세계(The World)": "피어싱 증가 (+1)",
    "절제(Temperance)": "이동 속도 증가 (+40)",
    "은둔자(The Hermit)": "방어/마법 방어 증가 (+20)",
    "마법사(The Magician)": "마법 공격력 증가 (+35)",
    "죽음(Death)": "아르바이트 성공 횟수 2배",
    "바보(The Fool)": "탐험 경험치 2배",
    "악마(The Devil)": "크리티컬 확률 최대값 증가 (+1)",
    "운명의 수레바퀴(Wheel of Fortune)": "생산 성공률 증가 (+5%)",
    "별(The Star)": "최대 마나 증가 (+1000)"
}

# -------------------
# 관리자 체크
# -------------------
def is_admin(interaction: discord.Interaction):
    role_names = [role.name for role in interaction.user.roles]
    return "길드마스터" in role_names or "운영진" in role_names

# -------------------
# 주차 계산 (해당 월 첫 목요일 기준)
# -------------------
def get_year_week(dt: datetime):
    first_day = dt.replace(day=1)
    first_thursday = first_day + timedelta(days=(3 - first_day.weekday()) % 7)
    week_number = ((dt - first_thursday).days // 7) + 1
    return dt.month, week_number

# -------------------
# 오라클 게임 클래스
# -------------------
class OracleGame:
    def __init__(self):
        self.current_oracle = None
        self.last_reset_time = None
        self.week_index = 0
        self.winner_found = False
        self.user_data = {}  # user_id -> dict
        

    # 유저 초기화
    def _init_user(self, user_id):
        if user_id not in self.user_data:
            self.user_data[user_id] = {
                "last_draw_date": None,    # 하루 1회 체크
                "last_draw_type": None,    # normal/boost
                "week_boost_used": False,  # 주 1회 체크
                "attempts": 0,             # 시도횟수
                "sacred_used": 0,          # 성수 사용 누적
                "reward": 0,               # 성수 지급 누적
                "consec_win": 0,
                "last_win_week": 0,
                "can_sacred": False        # 성수 뽑기 가능 여부
            }

    # -------------------
    # 유저 재설정
    # -------------------
    # def reset_oracle(self, user_id, nickname):
    #     if self.winner_found:
    #         return None, None, "⚠️ 이번 주 오라클은 종료되어 재설정 불가."
    #     if self.last_reset_time and datetime.now() - self.last_reset_time < timedelta(minutes=10):
    #         remain = 10 - int((datetime.now() - self.last_reset_time).total_seconds() // 60)
    #         return None, None, f"⚠️ 재설정 쿨타임: **{remain}분** 남았습니다."

    #     self._init_user(user_id)
    #     user = self.user_data[user_id]

    #     # 성수 1개 차감
    #     user["sacred_used"] -= 1
    #     # user["attempts"] += 1

    #     # 새로운 오라클 선택
    #     new_oracle = random.choice(list(ORACLE_EFFECTS.keys()))
    #     self.current_oracle = new_oracle
    #     self.last_reset_time = datetime.now()

    #     # 이미 뽑은 유저 중 마지막으로 해당 오라클 뽑은 사람만 후보
    #     candidates = [uid for uid, u in self.user_data.items()
    #                   if u.get("last_drawn_oracle") == self.current_oracle]

    #     winner_info = ""
    #     if candidates:
    #         if len(candidates) == 1:
    #             winner_uid = candidates[0]
    #             self.user_data[winner_uid]["reward"] += 5
    #             winner_info = f"🏆 최종 당첨자: <@{winner_uid}>"
    #         else:
    #             rolls = {uid: random.randint(1, 100) for uid in candidates}
    #             winner_uid = max(rolls, key=rolls.get)
    #             self.user_data[winner_uid]["reward"] += 5
    #             winner_info = "🎲 후보 주사위 결과:\n" + "\n".join([f"- <@{uid}>: {val}" for uid, val in rolls.items()])
    #             winner_info += f"\n🏆 최종 당첨자: <@{winner_uid}>"


    #     public_msg = (
    #         f"♻️ **{nickname}**님이 당첨 오라클을 재설정했습니다!\n"
    #         f"- 새로운 오라클 : **{new_oracle}**\n"
    #         f"- 재설정 후 **10분**동안 재설정 불가하며, 뽑기는 가능합니다.\n"
    #         f"{winner_info}"
    #     )
    #     return None, public_msg, None

    # -------------------
    # 관리자 하드리셋
    # -------------------
    def hard_reset(self):
        self.current_oracle = random.choice(list(ORACLE_EFFECTS.keys()))
        self.last_reset_time = None
        self.winner_found = False
        self.week_index += 1
        for user in self.user_data.values():
            user["last_draw_date"] = None
            user["last_draw_type"] = None
            user["week_boost_used"] = False
            user["attempts"] = 0
            user["sacred_used"] = 0
            user["reward"] = 0
            user["can_sacred"] = False
            

        now = datetime.now(timezone.utc) + timedelta(hours=9)  # KST 변환
        month, week = get_year_week(now)
        msg = f"📅 {month}월 {week}주차 당첨 오라클\n- **{self.current_oracle}**"
        return msg

    # -------------------
    # 뽑기 가능 여부 체크
    # -------------------
    def can_draw(self, user_id, draw_type):
        self._init_user(user_id)
        now = datetime.now(timezone.utc) + timedelta(hours=9)  # KST 변환
        today = now.date()
        user = self.user_data[user_id]
        

        if draw_type in ["normal", "boost"]:
            if user["last_draw_date"] == today:
                return False, f"오늘 이미 뽑기를 하셨습니다. (종류: {user['last_draw_type']})"
            if draw_type == "boost" and user["week_boost_used"]:
                return False, "이번 주 이미 부스트 뽑기를 사용하셨습니다."
        elif draw_type == "sacred":
            if not user.get("can_sacred", False):
                return False, "성수 뽑기는 일반/부스트 뽑기 후 1회만 가능합니다."
        return True, None

    # -------------------
    # 뽑기 실행
    # -------------------
    def draw_oracle(self, user_id, nickname, draw_type="normal"):
        self._init_user(user_id)
        user = self.user_data[user_id]
        now = datetime.now(timezone.utc) + timedelta(hours=9)  # KST 변환
        today = now.date()

        # 오라클이 아직 생성되지 않은 경우 (예: 목요일 이전, 봇 처음 추가)
        if self.current_oracle is None:
            return None, None, "⚠️ 아직 이번 주 오라클이 설정되지 않았습니다.\n문제가 있는 경우 관리자에 문의하세요."

        # --------------------
        # 주차 게임 종료 여부 체크
        # --------------------
        if self.winner_found:
            return None, None, "⚠️ 이번 주 오라클 게임은 이미 종료되었습니다."
        
        # --------------------
        # 일반 조건 검사
        # --------------------
        can, msg = self.can_draw(user_id, draw_type)
        if not can:
            return None, None, msg

        # --------------------
        # 실제 뽑기 로직
        # --------------------
        pool = list(ORACLE_EFFECTS.keys())
        if draw_type == "boost":
            pool.append(self.current_oracle)

        result = random.choice(pool)

        if draw_type in ["normal", "boost"]:
            user["last_draw_date"] = today
            user["last_draw_type"] = draw_type
            if draw_type == "boost":
                user["week_boost_used"] = True
            user["can_sacred"] = True
        elif draw_type == "sacred":
            user["can_sacred"] = False
            user["sacred_used"] -= 1
            # user["attempts"] += 1
            result = random.choice(pool)

        user["attempts"] += 1
        public_msg = f"🔮 **{nickname}**님이 뽑은 오라클\n- **{result}**"

        if result == self.current_oracle and not self.winner_found:
            self.winner_found = True
            user["reward"] += 5
            if user["last_win_week"] == self.week_index - 1:
                user["consec_win"] += 1
            else:
                user["consec_win"] = 1
            user["last_win_week"] = self.week_index
            if user["consec_win"] >= 3:
                user["reward"] += 10
                user["consec_win"] = 0
                public_msg += f"\n🎉 **{nickname}**님, 3주 연속 당첨! 성수 10개 추가 지급!"
            public_msg += f"\n\n✨ 이번 주 게임은 종료되었습니다.\n\n{self.summary()}"

        return result, public_msg, None

    # -------------------
    # 결산
    # -------------------
    def summary(self):
        now = datetime.now(timezone.utc) + timedelta(hours=9)  # KST 변환
        month, week = get_year_week(now)
        lines = [f"📅 {month}월 {week}주차 오라클\n- **{self.current_oracle}**", "\n**참여정보 결산**"]
        for uid, data in self.user_data.items():
            attempts = data.get("attempts", 0)
            sacred_used = data.get("sacred_used", 0)
            reward = data.get("reward", 0)
            final = reward + sacred_used
            lines.append(f"- <@{uid}> | 시도횟수: {attempts} , 성수사용: {sacred_used} , 성수지급: {reward} // 💰 최종: {final:+}")
        return "\n".join(lines)

# -------------------
# 게임 객체
# -------------------
game = OracleGame()

# -------------------
# 유저용 커맨드
# -------------------
@tree.command(name="뽑기", description="일반 오라클 뽑기")
async def draw(interaction: discord.Interaction):
    result, public_msg, private_msg = game.draw_oracle(interaction.user.id, interaction.user.display_name, "normal")
    if public_msg:
        await interaction.response.send_message(public_msg)
    elif private_msg:
        await interaction.response.send_message(private_msg, ephemeral=True)

@tree.command(name="부스트뽑기", description="확률 2배 오라클 뽑기 (주 1회)")
async def boost_draw(interaction: discord.Interaction):
    result, public_msg, private_msg = game.draw_oracle(interaction.user.id, interaction.user.display_name, "boost")
    if public_msg:
        await interaction.response.send_message(public_msg)
    elif private_msg:
        await interaction.response.send_message(private_msg, ephemeral=True)

@tree.command(name="성수뽑기", description="오늘 일반/부스트 뽑기 후 1회 가능한 성수 뽑기")
async def sacred_draw(interaction: discord.Interaction):
    result, public_msg, private_msg = game.draw_oracle(interaction.user.id, interaction.user.display_name, "sacred")
    if public_msg:
        await interaction.response.send_message(public_msg)
    elif private_msg:
        await interaction.response.send_message(private_msg, ephemeral=True)

@tree.command(name="채널뽑기", description="득템 하세요 여러분들")
async def pick_channel(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    valid_channels = [i for i in range(1, 39) if i != 11]
    today_channel = random.choice(valid_channels)
    
    msg = (
        f"🎲 **오늘의 추천 채널**\n\n"
        f"✨ 오늘은 **{today_channel}채널**"
    )

    await interaction.response.send_message(msg)

# @tree.command(name="재설정", description="성수 1개 사용 후 오라클 재설정 (10분 쿨타임)")
# async def reset(interaction: discord.Interaction):
#     result, public_msg, private_msg = game.reset_oracle(interaction.user.id, interaction.user.display_name)
#     if public_msg:
#         await interaction.response.send_message(public_msg)
#     elif private_msg:
#         await interaction.response.send_message(private_msg, ephemeral=True)

# -------------------
# 관리자용 커맨드
# -------------------
@tree.command(name="결산", description="이번주 참여 유저 성수 내역 확인")
async def summary_cmd(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("⚠️ 관리자 권한이 필요합니다.", ephemeral=True)
        return

    # ⏳ 즉시 응답 (타임아웃 방지)
    await interaction.response.defer(ephemeral=True)
    await asyncio.sleep(0.3)

    msg = game.summary()
    await interaction.followup.send(msg, ephemeral=True)


@tree.command(name="하드리셋", description="이번주 오라클 초기화 및 새 오라클 생성")
async def hard_reset_cmd(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("⚠️ 관리자 권한이 필요합니다.", ephemeral=True)
        return

    # ⏳ 즉시 응답 (타임아웃 방지)
    await interaction.response.defer(ephemeral=True)
    await asyncio.sleep(0.3)

    msg = game.hard_reset()
    await interaction.response.send_message(msg)


@tree.command(name="채널등록", description="오라클 메시지를 보낼 채널 지정")
async def set_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    global CHANNEL_ID
    if not is_admin(interaction):
        await interaction.response.send_message("⚠️ 관리자 권한이 필요합니다.", ephemeral=True)
        return

    # ⏳ 즉시 응답 (타임아웃 방지)
    await interaction.response.defer(ephemeral=True)
    await asyncio.sleep(0.3)

    CHANNEL_ID = channel.id
    await interaction.followup.send(f"✅ 오라클 메시지 채널이 **{channel.name}**로 설정되었습니다.", ephemeral=True)

# -------------------
# 자동 주차 오라클 생성
# -------------------
@tasks.loop(seconds=10)  # 10초마다 체크
async def weekly_oracle_task():
    now = datetime.now(timezone.utc) + timedelta(hours=9)  # KST 변환
    if CHANNEL_ID is None:
        
        return

   # 목요일 오전 10시 ~ 10시 10분
    if now.weekday() == 3 and now.hour == 10 and 0 <= now.minute < 59:
        # 이미 오늘 실행됐는지 체크
        if hasattr(weekly_oracle_task, "last_run_date"):
            if weekly_oracle_task.last_run_date == now.date():
                print("Already Created", weekly_oracle_task.last_run_date)
                return  # 오늘 이미 실행됨

        weekly_oracle_task.last_run_date = now.date()
        channel = bot.get_channel(CHANNEL_ID)
        msg = game.hard_reset()
        await channel.send(msg)

# -------------------
# 봇 시작
# -------------------

@bot.event
async def on_message(message):
    # 봇 자신은 무시
    if message.author.bot:
        return
    
    # 지정 채널에서만 적용
    if message.channel.id == CHANNEL_ID:
        # Slash Command가 Interaction으로 처리되므로 일반 메시지만 삭제
        # 즉, 일반 텍스트라면 삭제
        if not message.content.startswith("/"):
            await message.delete()


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await tree.sync()
    weekly_oracle_task.start()
    bot.loop.create_task(ping_self())

bot.run(BOT_TOKEN)
