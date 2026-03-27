import asyncio
import logging
from lark_oapi import Client, LogLevel
from lark_oapi.ws import Client as WSClient
from lark_oapi.event import EventDispatcherHandler

# 配置日志
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# 替换为实际的 app_id 和 app_secret
APP_ID = "your_app_id"
APP_SECRET = "your_app_secret"

# 创建事件处理器
event_handler = EventDispatcherHandler.builder("", "").build()

# 创建 WebSocket 客户端
ws_client = WSClient(
    app_id=APP_ID,
    app_secret=APP_SECRET,
    event_handler=event_handler,
    log_level=LogLevel.DEBUG
)

async def test_websocket():
    try:
        print("Starting WebSocket client...")
        # 在单独的线程中运行 WebSocket 客户端
        import threading
        import time
        
        def run_ws():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                ws_client.start()
            except Exception as e:
                print(f"WebSocket error: {e}")
            finally:
                loop.close()
        
        thread = threading.Thread(target=run_ws, daemon=True)
        thread.start()
        
        # 保持程序运行
        while True:
            await asyncio.sleep(1)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket())