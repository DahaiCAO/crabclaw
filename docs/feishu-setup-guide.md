# 飞书 (Feishu) 配置指南

## 📋 配置检查清单

### 1. 创建飞书应用

1. 访问 [飞书开放平台](https://open.feishu.cn/app)
2. 点击"创建企业自建应用"
3. 填写应用名称和描述
4. 记录 **App ID** 和 **App Secret**

### 2. 启用机器人能力

1. 进入应用详情页
2. 点击"添加应用能力"
3. 选择"机器人"
4. 启用机器人能力

### 3. 配置事件订阅 (WebSocket 模式)

1. 进入"事件与回调"页面
2. **选择"长连接"模式**（不是"请求网址"模式）
3. 点击"添加事件"
4. 搜索并订阅以下事件：
   - ✅ `im.message.receive_v1` - 接收消息（**必需**）
   - `im.message.message_read_v1` - 消息已读（可选）
   - `im.message.reaction_created_v1` - 表情回应（可选）
   - `im.chat.access_event.bot_p2p_chat_entered_v1` - 用户进入单聊（可选）

### 4. 配置权限

1. 进入"权限管理"页面
2. 申请并开通以下权限：
   - ✅ `im:message` - 获取与发送单聊、群组消息（**必需**）
   - ✅ `im:message.group_at_msg` - 获取群组中@机器人的消息（**必需**）
   - ✅ `im:message:send_as_bot` - 以机器人身份发送消息（**必需**）
   - `im:chat:readonly` - 获取群组信息（可选）
   - `im:resource` - 获取用户基本信息（可选）
   - `contact:user.employee_id:readonly` - 获取用户 employee ID（可选）

### 5. 发布应用

1. 进入"版本管理与发布"页面
2. 点击"创建版本"
3. 填写版本信息
4. 点击"申请发布"
5. 等待管理员审核通过

### 6. 将应用添加到企业/团队

1. 在飞书客户端中搜索你的应用名称
2. 点击"添加"或"使用"
3. 或者让管理员在管理后台将应用添加到企业

## 🔧 常见问题

### WebSocket 连接断开

**错误信息**：`no close frame received or sent`

**可能原因**：
1. 应用未发布
2. 应用未添加到企业/团队
3. 权限未开通
4. App ID 或 App Secret 不正确

**解决方案**：
1. 确认应用已发布并通过审核
2. 确认应用已添加到当前企业/团队
3. 检查权限管理中的权限是否已开通
4. 重新检查 App ID 和 App Secret

### 无法接收消息

**可能原因**：
1. 事件订阅未配置正确
2. 未订阅 `im.message.receive_v1` 事件
3. 机器人未添加到群组（如果是群聊消息）

**解决方案**：
1. 确认事件订阅模式为"长连接"（WebSocket）
2. 确认已订阅 `im.message.receive_v1` 事件
3. 将机器人添加到群组（对于群聊消息）

## 📝 配置示例

运行 `crabclaw onboard` 后，按以下流程配置：

```
启用飞书 (Feishu)？ [y/N]: y

📖 配置指南：访问 https://open.feishu.cn/app 创建企业自建应用
💡 提示：使用 WebSocket 模式，无需公网 IP 或配置 Webhook

输入飞书 App ID: cli_xxxxxxxxxxxxxxxx
输入飞书 App Secret: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

🔒 可选：事件订阅安全设置（可在飞书开放平台获取）
输入 Encrypt Key（可选）: 
输入 Verification Token（可选）: 

配置谁可以与机器人对话：
允许所有用户与机器人对话？（测试时推荐） [Y/n]: Y

配置群聊响应策略：
在群聊中响应所有消息？（否 = 仅响应@机器人的消息） [y/N]: N
```

## 🔗 相关链接

- [飞书开放平台](https://open.feishu.cn/)
- [机器人开发指南](https://open.feishu.cn/document/home/develop-a-bot-in-5-minutes/overview)
- [事件订阅文档](https://open.feishu.cn/document/server-docs/event-subscription-guide/event-subscription-overview)
- [权限说明](https://open.feishu.cn/document/server-docs/permission-management/permission-list)
