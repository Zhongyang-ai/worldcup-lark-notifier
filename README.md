# World Cup 2026 Lark Notifier

实时轮询 2026 世界杯比赛状态，并向 Lark 自定义机器人推送：

- 开赛、进球、红牌、半场、终场
- 比分回滚 / 可能的 VAR 取消进球
- SQLite 去重，服务重启不会重复发送
- 每日心跳与 HTTP 健康检查
- 每晚 22:00（新加坡时间）推送次日赛程

## 你需要提供的两项内容

1. Lark 群自定义机器人的 Webhook URL；启用签名时还需要 Secret。
2. 一台可运行 Docker 的云服务器。

数据默认来自 ESPN 的公开比分端点，无需 API Key。该端点不是带 SLA 的商业数据 Feed，不能保证与电视直播同步，也不应作为自动下注的唯一依据。

## 本地配置

```bash
cp .env.example .env
```

编辑 `.env`，至少填写 `LARK_WEBHOOK_URL`。然后测试机器人：

```bash
python scripts/test_lark.py
```

启动：

```bash
docker compose up -d --build
docker compose logs -f
```

健康检查：

```bash
curl http://127.0.0.1:8080/health
```

## 运行逻辑

- 有直播比赛时每 8 秒查询一次；没有直播时每 60 秒查询一次。
- 初次启动会记录当前比分和已有事件，但不会补发旧进球。
- 进球详情暂时缺失时，比分变化会先触发兜底通知。
- 数据源出现比分回滚时，发送 VAR / 比分修正提醒。
- `.env` 与运行数据库均已加入 `.gitignore`。

## 测试

```bash
python -m unittest discover -s tests -v
```
