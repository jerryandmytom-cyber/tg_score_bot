import os, random, hashlib
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ============================================================
#  昵称人格库 50+ 种
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

# ============================================================
#  评语库：前缀 × 身份 × 行为 × 结尾 = 10000+ 条
# ============================================================
PREFIXES = [
    "像个","简直是","活脱脱一个","看起来像","妥妥的","堪称",
    "简直是行走的一个","活脱脱的","简直就是一个","分明就是",
]
ROLES = [
    "隐藏大佬","群聊NPC","创业狂人","深夜选手","资源达人",
    "气氛组组长","管理员候选人","观察家","行业精英","跨界高手",
]
TRAITS = [
    "总能发现机会","从不轻易发言","一出现就被注意","收藏了无数频道",
    "掌握内部消息","总在关键时刻上线","善于把握时机","低调但实力强",
    "人脉广泛","执行力强","眼光独到","思维活跃","信息渠道多",
]
ENDINGS = [
    "气场拉满。","让人忍不住点资料。","神秘感直接拉高。","像有支线剧情。",
    "很有记忆点。","自带主角光环。","让人充满好奇。","极具神秘感。",
]

_comments = []
for p in PREFIXES:
    for r in ROLES:
        for t in TRAITS:
            for e in ENDINGS:
                _comments.append(f"{p}{r}，{t}，{e}")

def score_name(name: str):
    h = int(hashlib.md5(name.lower().encode()).hexdigest(), 16)
    score = 60 + h % 41
    persona = PERSONAS[h % len(PERSONAS)]
    comment = _comments[h % len(_comments)]
    return score, persona, comment

def make_result_text(username: str, score: int, persona: str, comment: str) -> str:
    return (
        f"🎯 用户名: @{username}\n"
        f"⭐️ 趣味评分: {score}\n"
        f"🎭 昵称人格: {persona}\n"
        f"💬 {comment}\n\n"
        f"👉 快来测测你的飞机号有多好 @"
    )

async def rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 回复消息的 ID，指向发送指令的用户，确保多人同时使用不混乱
    reply_to_id = update.message.message_id

    if context.args:
        username = context.args[0].replace("@", "")
    else:
        await update.message.reply_text(
            "用法: /rate @用户名\n例如: /rate @Metaworld3030",
            reply_to_message_id=reply_to_id
        )
        return

    score, persona, comment = score_name(username)
    text = make_result_text(username, score, persona, comment)

    code_text = f"```\n{text}\n```"

    keyboard = [[InlineKeyboardButton("🔗 分享给朋友", switch_inline_query=username)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(code_text, parse_mode="Markdown", reply_markup=reply_markup, reply_to_message_id=reply_to_id)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👉快来测测你的飞机号有多好 @TGLuckBot"
    )

if __name__ == "__main__":
    token = os.environ["BOT_TOKEN"]
    print(f"评语库共 {len(_comments)} 条，人格库 {len(PERSONAS)} 种")
    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("rate", rate))
    app.run_polling()