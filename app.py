import os
import hashlib
import logging
import asyncio
import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ── 人格库 ──────────────────────────────────────────────────
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
PREFIXES = ["像个","简直是","活脱脱一个","看起来像","妥妥的","堪称",
            "简直是行走的一个","活脱脱的","简直就是一个","分明就是"]
ROLES    = ["隐藏大佬","群聊NPC","创业狂人","深夜选手","资源达人",
            "气氛组组长","管理员候选人","观察家","行业精英","跨界高手"]
TRAITS   = ["总能发现机会","从不轻易发言","一出现就被注意","收藏了无数频道",
            "掌握内部消息","总在关键时刻上线","善于把握时机","低调但实力强",
            "人脉广泛","执行力强","眼光独到","思维活跃","信息渠道多"]
ENDINGS  = ["气场拉满。","让人忍不住点资料。","神秘感直接拉高。","像有支线剧情。",
            "很有记忆点。","自带主角光环。","让人充满好奇。","极具神秘感。"]

TOTAL = len(PREFIXES) * len(ROLES) * len(TRAITS) * len(ENDINGS)


def score_name(name: str):
    h = int(hashlib.md5(name.lower().encode()).hexdigest(), 16)
    score   = 60 + h % 41
    persona = PERSONAS[h % len(PERSONAS)]
    idx = h % TOTAL
    ei = idx % len(ENDINGS);  idx //= len(ENDINGS)
    ti = idx % len(TRAITS);   idx //= len(TRAITS)
    ri = idx % len(ROLES);    idx //= len(ROLES)
    pi = idx % len(PREFIXES)
    comment = f"{PREFIXES[pi]}{ROLES[ri]}，{TRAITS[ti]}，{ENDINGS[ei]}"
    return score, persona, comment


# ── Telegram handlers ────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 快测一下你的飞机号值多少钱！㊙️\n\n"
        "📝 用法: /rate @用户名\n"
        "例如: /rate @TG"
    )

async def rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "用法: /rate @用户名\n例如: /rate @TG",
            reply_to_message_id=update.message.message_id,
        )
        return
    username = context.args[0].lstrip("@")
    score, persona, comment = score_name(username)
    text = (
        f"🎯 用户名: @{username}\n"
        f"⭐️ 趣味评分: {score}个小目标\n"
        f"🎭 昵称人格: {persona}\n"
        f"💬 {comment}\n\n"
        f"👉 快邀请朋友测测飞机号 @TGLuckBot"
    )
    share_text = (
    f"🎯 用户名: @goole\n\n"
    f"⭐️ 趣味评分: 80个小目标\n\n"
    f"🎭 昵称人格: 活跃新人型\n\n"
    f"💬 分明就是气氛组组长，信息渠道多，自带主角光环\n\n"
    f"👉 快邀请朋友测测飞机号 @TGLuckBot")
    share_url = "https://t.me/share/url?url=https://t.me/TGLuckBot&text=" + urllib.parse.quote(share_text)
    keyboard = [[InlineKeyboardButton("🔗 分享给朋友", url=share_url)]]
    await update.message.reply_text(
        f"```\n{text}\n```",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
        reply_to_message_id=update.message.message_id,
    )


# ── Bot 异步主循环（跑在子线程里）────────────────────────────
# 全局变量供 HTTP handler 使用
g_bot_app   = None
g_loop      = None
g_secret    = None
g_ready     = threading.Event()   # 通知主线程 bot 已就绪

def bot_thread_main(token: str, webhook_url: str):
    global g_bot_app, g_loop, g_secret

    async def _run():
        global g_bot_app, g_loop, g_secret

        g_secret  = f"/webhook/{hashlib.md5(token.encode()).hexdigest()}"
        g_bot_app = ApplicationBuilder().token(token).build()
        g_bot_app.add_handler(CommandHandler("start", start))
        g_bot_app.add_handler(CommandHandler("rate",  rate))
        g_loop    = asyncio.get_running_loop()

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

        g_ready.set()           # 告诉主线程可以接请求了
        await asyncio.Event().wait()   # 永久阻塞

    asyncio.run(_run())


# ── HTTP Server（主线程，保证 Render 检测到端口）────────────
class Handler(BaseHTTPRequestHandler):
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

    logger.info(f"评语库 {TOTAL} 种组合，人格库 {len(PERSONAS)} 种")

    # 1. 先绑定端口（主线程，Render 立刻能检测到）
    server = HTTPServer(("0.0.0.0", port), Handler)
    logger.info(f"HTTP 端口 {port} 已绑定")

    # 2. Bot 跑在子线程
    t = threading.Thread(target=bot_thread_main, args=(token, webhook_url), daemon=True)
    t.start()

    # 3. 等 bot 初始化完成（最多 30 秒）
    if not g_ready.wait(timeout=30):
        logger.warning("Bot 初始化超时，但 HTTP 服务继续运行")

    # 4. 主线程永久服务 HTTP 请求
    logger.info("开始处理请求")
    server.serve_forever()
