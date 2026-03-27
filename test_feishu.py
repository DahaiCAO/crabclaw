import asyncio
import time
from crabclaw.channels.feishu import FeishuChannel
from crabclaw.bus.queue import MessageBus
from crabclaw.config.schema import FeishuConfig

# 创建配置
config = FeishuConfig(
    enabled=True,
    app_id="your_app_id",  # 请替换为实际的 app_id
    app_secret="your_app_secret",  # 请替换为实际的 app_secret
    group_policy="open"
)

# 创建消息总线
bus = MessageBus()

# 创建 Feishu 通道
channel = FeishuChannel(config, bus)

async def test_feishu_connection():
    try:
        print("Starting Feishu channel...")
        await channel.start()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_feishu_connection())