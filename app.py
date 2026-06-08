import os
import hashlib
import logging
import asyncio
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================================================
#  昵称人格库
# ============================================================
PERSONAS = [
    "熬夜创业型", "潜水大师型", "神秘资本型", "社交悍匪型", "群聊观察家型",
    "信息猎人型", "红包收割机型", "佛系围观型", "技术大神型", "段子收藏家型",
    "深夜选手型", "资源整合型", "人脉王型", "气氛组组长型", "佛系躺平型",
    "卷王型", "低调大佬型", "话痨型", "冷场终结者型", "话题制造机型",
    "知识百科型", "行走的广告型", "表情包大师型", "语音条狂人型", "文件收藏家型",
    "链接狂魔型", "禁言名单型", "群规破坏者型", "潜水冒泡型", "活跃新人型",
    "神秘莫测型", "数据分析师型", "机会猎手型", "风险厌恶型", "社交牛杂型",
    "时间管理大师型", "拖延症晚期型", "效率达人型", "灵感爆发型", "灵感枯竭型",
    "情绪稳定型", "暴躁老哥型", "温柔体贴型", "高冷傲娇型", "接地气型",
    "海王型", "专一深情型", "理性分析型", "感性冲动型", "商业头脑型",
    "技术宅型", "艺术气质型", "运动健将型", "美食家型", "旅行博主型",
    "读书达人型", "音乐发烧型", "影视追剧型", "游戏玩家型", "科技前沿型",
    "区块链信仰型", "AI乐观型", "元宇宙看好型", "传统行业坚守型",
]

PREFIXES = [
    "像个", "简直是", "活脱脱一个", "看起来像", "妥妥的", "堪称",
    "简直是行走的一个", "活脱脱的", "简直就是一个", "分明就是",
]
ROLES = [
    "隐藏大佬", "群聊NPC", "创业狂人", "深夜选手", "资源达人",
    "气氛组组长", "管理员候选人", "观察家", "行业精英", "跨界高手",
]
TRAITS = [
    "总能发现机会", "从不轻易发言", "一出现就被注意", "收藏了无数频道",
    "掌握内部消息", "总在关键时刻上线", "善于把握时机", "低调但实力强",
    "人脉广泛", "执行力强", "眼光独到", "思维活跃", "信息渠道多",
]
ENDINGS = [
    "气场拉满。", "让人忍不住点资料。", "神秘感直接拉高。", "像有支线剧情。",
    "很有记忆点。", "自带主角光环。", "让人充满好奇。", "极具神秘感。",
]

TOTAL_COMMENTS = len(PREFIXES) * len(ROLES) * len(TRAITS) * len(ENDINGS)


def score_name(name: str):
    h = int(hashlib.md5(name.lower().encode()).hexdigest(), 16)
    score = 60 + h % 41
    persona = PERSONAS[h % len(PERSONAS)]
    idx = h % TOTAL_COMMENTS
    ei = idx % len(ENDINGS);  idx //= len(ENDINGS)
    ti = idx % len(TRAITS);   idx //= len(TRAITS)
    ri = idx % len(ROLES);    idx //= len(ROLES)
    pi = idx % len(PREFIXES)
    comment = f"{PREFIXES[pi]}{ROLES[ri]}，{TRAITS[ti]}，{ENDINGS[ei]}"
    return score, persona, comment


def make_result_text(username, score, persona, comment):
    return (
        f"🎯 用户名: @{username}\n"
        f"⭐️ 趣味评分: {score}\n"
        f"🎭 昵称人格: {persona}\n"
        f"💬 {comment}\n\n"
        f"👉 快邀请朋友测测飞机号 @TGLuckBot"
    )


async def rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        username = context.args[0].replace("@", "")
    else:
        await update.message.reply_text(
            "用法: /rate @用户名\n例如: /rate @Metaworld3030",
            reply_to_message_id=update.message.message_id,
        )
        return

    score, persona, comment = score_name(username)
    text = make_result_text(username, score, persona, comment)
    keyboard = [[InlineKeyboardButton("🔗 分享给朋友", switch_inline_query=username)]]

    await update.message.reply_text(
        f"```\n{text}\n```",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
        reply_to_message_id=update.message.message_id,
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 欢迎使用飞机号评测 Bot！\n\n"
        "📝 用法: /rate @用户名\n"
        "例如: /rate @Metaworld3030\n\n"
        "👉 快来测测你的飞机号有多好 @TGLuckBot"
    )


# ============================================================
#  HTTP 健康检查 + Webhook（纯标准库，无第三方依赖）
# ============================================================
def make_http_handler(bot_app, secret_path, loop):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")

        def do_POST(self):
            if self.path != secret_path:
                self.send_response(404)
                self.end_headers()
                return
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
                update = Update.de_json(data, bot_app.bot)
                future = asyncio.run_coroutine_threadsafe(
                    bot_app.process_update(update), loop
                )
                future.result(timeout=30)
            except Exception as e:
                logger.error(f"处理 update 出错: {e}")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")

        def log_message(self, *args):
            pass  # 静默 HTTP 日志

    return Handler


async def main():
    token = os.environ.get("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN 环境变量未设置")

    webhook_url = os.environ.get("WEBHOOK_URL", "").rstrip("/")
    port = int(os.environ.get("PORT", 10000))

    bot_app = ApplicationBuilder().token(token).build()
    bot_app.add_handler(CommandHandler("start", start))
    bot_app.add_handler(CommandHandler("rate", rate))

    await bot_app.initialize()
    await bot_app.start()

    loop = asyncio.get_running_loop()
    secret_path = f"/webhook/{hashlib.md5(token.encode()).hexdigest()}"

    if webhook_url:
        # Webhook 模式
        await bot_app.bot.set_webhook(
            url=f"{webhook_url}{secret_path}",
            drop_pending_updates=True,
        )
        logger.info(f"Webhook 已设置: {webhook_url}{secret_path}")
    else:
        # Polling 模式（本地开发）
        logger.info("未设置 WEBHOOK_URL，使用 Polling 模式")
        await bot_app.updater.start_polling(drop_pending_updates=True)

    # 先绑定端口，再记录日志，确保 Render 能检测到
    handler_class = make_http_handler(bot_app, secret_path, loop)
    server = HTTPServer(("0.0.0.0", port), handler_class)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    logger.info(f"HTTP 服务已启动，监听端口 {port}")

    await asyncio.Event().wait()  # 永久阻塞


if __name__ == "__main__":
    logger.info(f"评语库共 {TOTAL_COMMENTS} 种组合，人格库 {len(PERSONAS)} 种")
    asyncio.run(main())