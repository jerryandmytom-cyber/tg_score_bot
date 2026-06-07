# Telegram Username Score Bot

根据 Telegram 用户名生成趣味评分、昵称人格和专属评语。

## 功能

- `/start` - 查看使用说明
- `/rate @用户名` - 获取趣味评分、昵称人格和专属评语

## 数据规模

- 昵称人格库：**59 种**不同人格类型
- 评语库：**10000 条**唯一评语（10前缀 × 10身份 × 10行为 × 10结尾）

## 部署

### Render（推荐）

1. Fork 本仓库
2. 在 Render 创建 Web Service，连接 GitHub 仓库
3. 设置环境变量 `BOT_TOKEN`（从 @BotFather 获取）
4. 部署

### 本地运行

```bash
pip install -r requirements.txt
export BOT_TOKEN="你的bot_token"
python app.py
```

## 获取 BOT_TOKEN

1. 在 Telegram 搜索 @BotFather
2. 发送 /newbot
3. 按提示创建机器人
4. 复制获得的 token 设置为环境变量