import json
import os
from pathlib import Path
from crabclaw.user.manager import UserManager

# 创建临时工作目录
temp_workspace = Path("temp_workspace")
temp_workspace.mkdir(exist_ok=True)

# 创建用户管理器
manager = UserManager(temp_workspace)

# 创建测试用户
user = manager.create_user("testuser", "Test User", "password123")
user_id = user.user_id

# 测试保存通道配置
channel_config = {
    "app_id": "test_app_id",
    "app_secret": "test_app_secret",
    "allow_from": ["*"]
}

saved = manager.save_channel_config(
    user_id=user_id,
    channel_type="feishu",
    name="test_feishu",
    config=channel_config,
    is_active=True
)

print("Saved channel config:", saved)

# 检查保存的文件
channel_file = temp_workspace / "portfolios" / user_id / "channels" / "feishu" / "feishu.json"
if channel_file.exists():
    print(f"\nChannel config file content:")
    content = channel_file.read_text(encoding="utf-8")
    print(content)
    
    # 检查 allow_from 格式
    if '"allow_from": ["*"]' in content:
        print("\n✓ Success: allow_from is in compact format")
    else:
        print("\n✗ Failed: allow_from is not in compact format")
else:
    print(f"\n✗ Failed: Channel config file not found at {channel_file}")

# 清理临时文件
import shutil
shutil.rmtree(temp_workspace)