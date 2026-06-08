import os
import hashlib
import logging
import asyncio
import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================================================
#  运势库（内嵌，无需外部文件）
# ============================================================
import random as _random

_categories = [
    '事业','财运','健康','感情','学业','人际关系','出行','家庭','投资','事业突破',
    '桃花运','贵人运','小人运势','健康调理','财富积累','职业发展','创业运势','考试运','竞赛运','迁移运'
]
_templates = [
    '今日{cat}运势颇佳，{detail}，宜把握机会展现才华，稳步上升。',
    '今日{cat}运势平稳，{detail}，做事需稳扎稳打，不宜冒险。',
    '今日{cat}运势上升，{detail}，贵人运强，诸事顺遂。',
    '今日{cat}运势波动，{detail}，保持冷静，积极应对可化解。',
    '今日{cat}运势亨通，{detail}，工作表现突出有望获得认可。',
    '今日{cat}需注意防护，{detail}，及时调整状态，保持良好习惯。',
    '今日{cat}运势下降，{detail}，需注意沟通与包容。',
    '今日{cat}大吉，{detail}，诸事顺遂，好运连连。',
    '今日{cat}需谨慎，{detail}，三思而后行，稳中求进。',
    '今日{cat}有贵人相助，{detail}，困难时刻会有人伸出援手。',
    '今日{cat}运上扬，{detail}，状态越来越好，适合积极进取。',
    '今日{cat}大旺，{detail}，是突破自我的好时机，勇敢向前。',
    '今日{cat}有收获，{detail}，付出终有回报，令人欣慰。',
    '今日{cat}运势佳，{detail}，可能有意外收获降临。',
    '今日{cat}需稳中求进，{detail}，不冒进不退缩，稳步前行。',
]
_details = {
    '事业':   ['工作顺利，项目进展良好','可能有新机会出现','团队合作运佳','上级对你印象良好','有晋升机会','工作效率高'],
    '财运':   ['正财运势稳定','可能有小额偏财','适合进行长期投资','注意账目管理','有加薪机会','可能会有奖金'],
    '健康':   ['身体状态良好','注意休息和睡眠','适合进行体育锻炼','精神状态佳','需要注意饮食均衡','适合户外运动'],
    '感情':   ['感情升温','适合表白','单身者有机会脱单','需要多沟通理解','适合约会','感情需耐心培养'],
    '学业':   ['学习效率高','考试运佳','适合深入研究','需要复习巩固','成绩有进步','考试顺利'],
    '人际关系':['人际运佳','贵人运强','可能会有新朋友','适合社交活动','与同事关系融洽','适合参加聚会'],
    '出行':   ['出行顺利','注意交通安全','适合短途旅行','天气状况良好','路途平安','自驾运佳'],
    '家庭':   ['家庭和睦','适合陪伴家人','可能会有好消息','子女运势良好','亲子关系改善','家人健康'],
    '投资':   ['投资运佳','长线投资有利','注意分散风险','适合稳健投资','注意资金安全','理财收益提升'],
    '事业突破':['突破运极佳','可能晋升加薪','创业运上升','适合开拓新市场','贵人相助','适合展示才华'],
    '桃花运': ['桃花运旺盛','可能遇到心仪对象','单身者宜多参加社交','适合相亲','正缘出现','恋爱运上升'],
    '贵人运': ['贵人运强','有长辈帮助','领导赏识','朋友相助','有贵人指点','得贵人扶持'],
    '小人运势':['需防小人','谨言慎行','避免冲突','低调行事','远离小人','谨慎交友'],
    '健康调理':['注意养生','适合调理身体','饮食需注意','作息要规律','运动养生','调理见效'],
    '财富积累':['储蓄运佳','财富积累快','收入增加','适合理财','正财稳定','收入大于支出'],
    '职业发展':['职业发展顺利','有升职机会','适合跳槽','发展前景好','薪酬提升','职业瓶颈突破'],
    '创业运势':['创业运上升','适合自己创业','创业时机佳','项目有进展','盈利运上升','合伙创业运佳'],
    '考试运': ['考试运佳','复习效率高','考试顺利','成绩优异','临场发挥好','金榜题名'],
    '竞赛运': ['竞赛运佳','比赛顺利','有获奖机会','竞技状态好','获得名次','夺冠有望'],
    '迁移运': ['迁移运佳','搬家顺利','换房运上升','乔迁之喜','买房运上升','乔迁新居'],
}

_FORTUNE_TEXTS = []
_random.seed(42)
for _ in range(1000):
    cat = _random.choice(_categories)
    tmpl = _random.choice(_templates)
    detail = _random.choice(_details[cat])
    _FORTUNE_TEXTS.append(tmpl.format(cat=cat, detail=detail))

# ============================================================
#  昵称人格库（/rate 功能）
# ============================================================
PERSONAS = [
    "熬夜创业型","潜水大师型","神秘资本型","社交悍匪型","群聊观察家型",
    "信息猎人型","红包收割机型","佛系围观型","技术大神型","段子收藏家型",
    "深夜选手型","资源整合型","人脉王型","气氛组组长型","佛系躺平型",
    "卷王型","低调大佬型","话痨型","冷场终结者型","话题制造机型",
    "知识百科型","行走的广告型","表情包大师型","语音条狂人型","文件收藏家型",
    "链接狂魔型","禁言名单型","群规破坏者型","潜水冒泡型","活跃新人型",
    "神秘莫测型","数据分析师型","机会猎手型","风险厌恶型","社交牛杂型",
    "时间管理大师型","拖延症晚期型","效率达人型","灵感爆发型","灵感枯竭型",
    "情绪稳定型","暴躁老哥型","温柔体贴型","高冷傲娇型","接地气型",
    "海王型","专一深情型","理性分析型","感性冲动型","商业头脑型",
    "技术宅型","艺术气质型","运动健将型","美食家型","旅行博主型",
    "读书达人型","音乐发烧型","影视追剧型","游戏玩家型","科技前沿型",
    "区块链信仰型","AI乐观型","元宇宙看好型","传统行业坚守型",
]
_PREFIXES = ["像个","简直是","活脱脱一个","看起来像","妥妥的","堪称","简直是行走的一个","活脱脱的","简直就是一个","分明就是"]
_ROLES    = ["隐藏大佬","群聊NPC","创业狂人","深夜选手","资源达人","气氛组组长","管理员候选人","观察家","行业精英","跨界高手"]
_TRAITS   = ["总能发现机会","从不轻易发言","一出现就被注意","收藏了无数频道","掌握内部消息","总在关键时刻上线","善于把握时机","低调但实力强","人脉广泛","执行力强","眼光独到","思维活跃","信息渠道多"]
_ENDINGS  = ["气场拉满。","让人忍不住点资料。","神秘感直接拉高。","像有支线剧情。","很有记忆点。","自带主角光环。","让人充满好奇。","极具神秘感。"]
_RATE_TOTAL = len(_PREFIXES) * len(_ROLES) * len(_TRAITS) * len(_ENDINGS)

# ============================================================
#  时辰数据（/goodhours 功能）
# ============================================================
SHICHEN_DATA = [
    {"name":"子时","modern":"晚11点–凌晨1点","lucky":True},
    {"name":"丑时","modern":"凌晨1点–3点",  "lucky":True},
    {"name":"寅时","modern":"凌晨3点–5点",  "lucky":True},
    {"name":"卯时","modern":"早5点–7点",    "lucky":False},
    {"name":"辰时","modern":"早7点–9点",    "lucky":False},
    {"name":"巳时","modern":"早9点–11点",   "lucky":False},
    {"name":"午时","modern":"上午11点–下午1点","lucky":False},
    {"name":"未时","modern":"下午1点–3点",  "lucky":True},
    {"name":"申时","modern":"下午3点–5点",  "lucky":False},
    {"name":"酉时","modern":"下午5点–7点",  "lucky":False},
    {"name":"戌时","modern":"晚7点–9点",    "lucky":False},
    {"name":"亥时","modern":"晚9点–11点",   "lucky":True},
]

# ============================================================
#  工具函数
# ============================================================
def _md5int(s: str) -> int:
    return int(hashlib.md5(s.encode()).hexdigest(), 16)

def _today() -> str:
    import datetime
    return datetime.datetime.utcnow().strftime("%Y-%m-%d")

def _hourly() -> str:
    import datetime
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H")

# —— /rate ——
def score_name(name: str):
    h = _md5int(name.lower())
    score   = 60 + h % 41
    persona = PERSONAS[h % len(PERSONAS)]
    idx = h % _RATE_TOTAL
    ei = idx % len(_ENDINGS);  idx //= len(_ENDINGS)
    ti = idx % len(_TRAITS);   idx //= len(_TRAITS)
    ri = idx % len(_ROLES);    idx //= len(_ROLES)
    pi = idx % len(_PREFIXES)
    comment = f"{_PREFIXES[pi]}{_ROLES[ri]}，{_TRAITS[ti]}，{_ENDINGS[ei]}"
    return score, persona, comment

# —— /luckynumber ——
def get_lucky_number(uid: int) -> int:
    return (_md5int(f"{uid}:{_hourly()}:lucky") % 48) + 1

# —— /fortune ——
def get_fortune(uid: int) -> str:
    idx = _md5int(f"{uid}:{_today()}:fortune") % len(_FORTUNE_TEXTS)
    return _FORTUNE_TEXTS[idx]

# —— /goodhours ——
def get_good_hours(uid: int):
    seed = f"{uid}:{_today()}:hours"
    lucky = [h for h in SHICHEN_DATA if h["lucky"]]
    lucky.sort(key=lambda h: _md5int(seed + h["name"]))
    return lucky[:3]

# —— /wealth ——
def get_wealth_index(uid: int) -> int:
    return (_md5int(f"{uid}:{_hourly()}:wealth") % 30) + 70

# ============================================================
#  公共按钮
# ============================================================
MAIN_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("🎯 幸运数字", callback_data="luckynumber"),
        InlineKeyboardButton("📕 今日运势", callback_data="fortune"),
    ],
    [
        InlineKeyboardButton("⏰ 今日吉时", callback_data="goodhours"),
        InlineKeyboardButton("💰 暴富指数", callback_data="wealthindex"),
    ],
    [
        InlineKeyboardButton("🎭 飞机号测评", callback_data="rate"),
    ],
])

def display_name(user) -> str:
    return f"@{user.username}" if user.username else (user.first_name or "客官")

# ============================================================
#  回复文本生成
# ============================================================
def reply_rate(user) -> str:
    if not user.username:
        return "⚠️ 你还没有设置 Telegram 用户名，无法测评。\n请前往 设置 → 用户名 设置后再试！"
    score, persona, comment = score_name(user.username)
    share_text = "🔗 分享给朋友测测飞机号 @TGLuckBot"
    return (
        f"🎯 用户名: @{user.username}\n"
        f"⭐️ 趣味评分: {score}\n"
        f"🎭 昵称人格: {persona}\n"
        f"💬 {comment}\n\n"
        f"👉 快邀请朋友测测飞机号 @TGLuckBot"
    )

def reply_luckynumber(user) -> str:
    n = get_lucky_number(user.id)
    return (
        f"🎯 *幸运数字* 🎯\n\n"
        f"✨ 客官：{display_name(user)}\n\n"
        f"🧧 今日幸运数字为：\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"      🎲 【 {str(n).zfill(2)} 】\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"💡 每天幸运数字会随乾坤变化"
    )

def reply_fortune(user) -> str:
    f = get_fortune(user.id)
    return (
        f"📕 *今日运势* 📕\n\n"
        f"✨ 客官：{display_name(user)}\n\n"
        f"🧧 今日运势为：\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"{f}\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"💡 明日运势将会变化哦~"
    )

def reply_goodhours(user) -> str:
    hours = get_good_hours(user.id)
    lines = "\n".join(f"⏰ ㊙️ {h['name']} 即 {h['modern']} ㊙️" for h in hours)
    return (
        f"⏰ *今日吉时* ⏰\n\n"
        f"✨ 客官：{display_name(user)}\n\n"
        f"🧧 今日【吉时】为：\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"{lines}\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"💡 吉时做事，事半功倍！"
    )

def reply_wealth(user) -> str:
    w = get_wealth_index(user.id)
    if w >= 95:   tip = "🌟 今日财运爆表！大富大贵之相！"
    elif w >= 90: tip = "🌟 今日财运极佳！财运亨通！"
    elif w >= 85: tip = "✨ 今日财运不错！稳中有进！"
    elif w >= 80: tip = "✨ 今日财运良好！稳扎稳打！"
    elif w >= 75: tip = "💫 今日财运平稳！保守理财！"
    else:         tip = "💫 今日财运一般！静待时机！"
    return (
        f"💰 *今日暴富指数* 💰\n\n"
        f"✨ 客官：{display_name(user)}\n\n"
        f"🧧 今日暴富指数为：\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"      💎【 {w} 】💎\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"{tip}\n\n"
        f"💡 跟随您的财运和人气而变"
    )

# ============================================================
#  Telegram Handlers
# ============================================================
MENU_TEXT = (
    "✨ 欢迎使用出海联盟幸运机器人！\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n"
    "📋 五大功能：\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n"
    "🎯 /luckynumber  今日幸运数字\n"
    "📕 /fortune      今日运势\n"
    "⏰ /goodhours    今日吉时\n"
    "💰 /wealth       今日暴富指数\n"
    "🎭 /rate         飞机号测评\n"
    "━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "👇 点击下方按钮快速查询："
)

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(MENU_TEXT, reply_markup=MAIN_KEYBOARD)

async def cmd_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(MENU_TEXT, reply_markup=MAIN_KEYBOARD)

async def cmd_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = reply_rate(update.message.from_user)
    share_text = "🔗 分享给朋友测测飞机号 @TGLuckBot"
    share_url = "https://t.me/share/url?url=https://t.me/TGLuckBot&text=" + urllib.parse.quote(share_text)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 邀请朋友测测飞机号", url=share_url)],
        [InlineKeyboardButton("🔙 返回菜单", callback_data="menu")],
    ])
    await update.message.reply_text(text, reply_markup=kb, reply_to_message_id=update.message.message_id)

async def cmd_luckynumber(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = reply_luckynumber(update.message.from_user)
    share_text = "🔗 分享给朋友测测飞机号 @TGLuckBot"
    share_url = "https://t.me/share/url?url=https://t.me/TGLuckBot&text=" + urllib.parse.quote(share_text)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 邀请朋友测测飞机号", url=share_url)],
        [InlineKeyboardButton("🔙 返回菜单", callback_data="menu")],
    ])
    await update.message.reply_text(text, reply_markup=kb, reply_to_message_id=update.message.message_id)

async def cmd_fortune(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = reply_fortune(update.message.from_user)
    share_text = "🔗 分享给朋友测测飞机号 @TGLuckBot"
    share_url = "https://t.me/share/url?url=https://t.me/TGLuckBot&text=" + urllib.parse.quote(share_text)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 邀请朋友测测飞机号", url=share_url)],
        [InlineKeyboardButton("🔙 返回菜单", callback_data="menu")],
    ])
    await update.message.reply_text(text, reply_markup=kb, reply_to_message_id=update.message.message_id)

async def cmd_goodhours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = reply_goodhours(update.message.from_user)
    share_text = "🔗 分享给朋友测测飞机号 @TGLuckBot"
    share_url = "https://t.me/share/url?url=https://t.me/TGLuckBot&text=" + urllib.parse.quote(share_text)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 邀请朋友测测飞机号", url=share_url)],
        [InlineKeyboardButton("🔙 返回菜单", callback_data="menu")],
    ])
    await update.message.reply_text(text, reply_markup=kb, reply_to_message_id=update.message.message_id)

async def cmd_wealth(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = reply_wealth(update.message.from_user)
    share_text = "🔗 分享给朋友测测飞机号 @TGLuckBot"
    share_url = "https://t.me/share/url?url=https://t.me/TGLuckBot&text=" + urllib.parse.quote(share_text)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔗 邀请朋友测测飞机号", url=share_url)],
        [InlineKeyboardButton("🔙 返回菜单", callback_data="menu")],
    ])
    await update.message.reply_text(text, reply_markup=kb, reply_to_message_id=update.message.message_id)

async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    data = query.data

    if data == "menu":
        await query.message.reply_text(MENU_TEXT, reply_markup=MAIN_KEYBOARD)
        return

    if data == "rate":
        text = reply_rate(user)
        share_text = "🔗 分享给朋友测测飞机号 @TGLuckBot"
        share_url = "https://t.me/share/url?url=https://t.me/TGLuckBot&text=" + urllib.parse.quote(share_text)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗  邀请朋友测测飞机号", url=share_url)],
            [InlineKeyboardButton("🔙 返回菜单", callback_data="menu")],
        ])
        await query.message.reply_text(text, reply_markup=kb)
        return

    dispatch = {
        "luckynumber": reply_luckynumber,
        "fortune":     reply_fortune,
        "goodhours":   reply_goodhours,
        "wealthindex": reply_wealth,
    }
    fn = dispatch.get(data)
    if not fn:
        await query.message.reply_text("❓ 未知选项，请重试！")
        return

    text = fn(user)
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎯 幸运数字", callback_data="luckynumber"),
            InlineKeyboardButton("📕 今日运势", callback_data="fortune"),
        ],
        [
            InlineKeyboardButton("⏰ 今日吉时", callback_data="goodhours"),
            InlineKeyboardButton("💰 暴富指数", callback_data="wealthindex"),
        ],
        [
            InlineKeyboardButton("🎭 飞机号测评", callback_data="rate"),
            InlineKeyboardButton("🔙 返回菜单", callback_data="menu"),
        ],
    ])
    await query.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)

# ============================================================
#  HTTP Server + Bot 启动（主线程先绑端口）
# ============================================================
g_bot_app  = None
g_loop     = None
g_secret   = None
g_ready    = threading.Event()

def bot_thread_main(token: str, webhook_url: str):
    global g_bot_app, g_loop, g_secret

    async def _run():
        global g_bot_app, g_loop, g_secret
        g_secret  = f"/webhook/{hashlib.md5(token.encode()).hexdigest()}"
        g_bot_app = ApplicationBuilder().token(token).build()
        g_bot_app.add_handler(CommandHandler("start",       cmd_start))
        g_bot_app.add_handler(CommandHandler("menu",        cmd_menu))
        g_bot_app.add_handler(CommandHandler("rate",        cmd_rate))
        g_bot_app.add_handler(CommandHandler("luckynumber", cmd_luckynumber))
        g_bot_app.add_handler(CommandHandler("fortune",     cmd_fortune))
        g_bot_app.add_handler(CommandHandler("goodhours",   cmd_goodhours))
        g_bot_app.add_handler(CommandHandler("wealth",      cmd_wealth))
        g_bot_app.add_handler(CallbackQueryHandler(on_callback))
        g_loop = asyncio.get_running_loop()

        await g_bot_app.initialize()
        await g_bot_app.start()

        if webhook_url:
            await g_bot_app.bot.set_webhook(
                url=f"{webhook_url}{g_secret}",
                drop_pending_updates=True,
            )
            logger.info(f"Webhook 已设置: {webhook_url}{g_secret}")
        else:
            await g_bot_app.updater.start_polling(drop_pending_updates=True)
            logger.info("Polling 模式已启动")

        # 设置命令菜单
        await g_bot_app.bot.set_my_commands([
            ("start",       "🎯 欢迎使用幸运机器人"),
            ("menu",        "📋 显示功能菜单"),
            ("luckynumber", "🎲 今日幸运数字"),
            ("fortune",     "📕 今日运势"),
            ("goodhours",   "⏰ 今日吉时"),
            ("wealth",      "💰 今日暴富指数"),
            ("rate",        "🎭 飞机号测评"),
        ])

        g_ready.set()
        await asyncio.Event().wait()

    asyncio.run(_run())


class HTTPHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def do_POST(self):
        if g_secret is None or self.path != g_secret:
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length)
        try:
            data   = json.loads(body)
            update = Update.de_json(data, g_bot_app.bot)
            future = asyncio.run_coroutine_threadsafe(
                g_bot_app.process_update(update), g_loop
            )
            future.result(timeout=30)
        except Exception as e:
            logger.error(f"处理 update 出错: {e}")
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    token = os.environ.get("BOT_TOKEN", "")
    if not token:
        raise RuntimeError("BOT_TOKEN 环境变量未设置")

    webhook_url = os.environ.get("WEBHOOK_URL", "").rstrip("/")
    port        = int(os.environ.get("PORT", 10000))

    logger.info(f"运势库 {len(_FORTUNE_TEXTS)} 条 | 人格库 {len(PERSONAS)} 种 | 评语组合 {_RATE_TOTAL} 种")

    # 1. 主线程先绑端口
    server = HTTPServer(("0.0.0.0", port), HTTPHandler)
    logger.info(f"HTTP 端口 {port} 已绑定")

    # 2. Bot 子线程
    t = threading.Thread(target=bot_thread_main, args=(token, webhook_url), daemon=True)
    t.start()

    # 3. 等 Bot 就绪（最多 30 秒）
    if not g_ready.wait(timeout=30):
        logger.warning("Bot 初始化超时，HTTP 服务继续运行")

    # 4. 主线程永久服务
    logger.info("开始处理请求")
    server.serve_forever()
