# 用户手册（当前设计）

## 1. 初始化与基础配置

```bash
crabclaw onboard
```

然后编辑 `~/.crabclaw/config.json`：
- 配置模型 API Key；
- 设置默认 provider/model；
- 按需开启通道。

## 2. 启动服务

```bash
crabclaw gateway
```

可选启动 Dashboard：

```bash
crabclaw dashboard
```

访问：`http://127.0.0.1:18791`

## 3. 账号登录

- 首次会自动创建管理员：
  - 用户名：`admin`
  - 密码：`admin2891`
- Dashboard 使用 token 登录链路：
  - `/api/login`
  - `/api/me`

## 4. 多通道使用流程

1. 在配置文件启用通道；
2. 填写通道必要凭据；
3. 在 Dashboard 的 Channels 页面维护：
   - 用户通道配置；
   - 身份映射。

映射示例：
- `channel=feishu, external_id=ou_xxx` 映射到当前用户。

## 5. 多端同步预期

- 一个通道的入站消息可在同用户多端同步展示；
- 回复可扇出到该用户映射的多个通道；
- 重复消息会被去重。

## 6. 账号生命周期操作

用户菜单支持：
- Switch Account：清理本地认证并回登录页；
- Logout：服务端注销 + 本地状态清理；
- Delete Account：删除用户档案与隔离 portfolio。

## 7. 安全建议

- 生产环境强烈建议配置精确 `allowFrom`；
- `allowFrom: []` 默认拒绝所有；
- 如需全部放开，显式设置 `["*"]`；
- 建议开启 `tools.restrictToWorkspace=true`。

## 8. 端到端可观测验证

```bash
python scripts/e2e_multichannel_sync_check.py \
  --dashboard-http http://127.0.0.1:18791 \
  --dashboard-ws ws://127.0.0.1:18792/ws \
  --gateway-http http://127.0.0.1:18790 \
  --username admin \
  --password admin2891
```

通过条件：
- 两个客户端都收到 inbound/outbound；
- 无重复事件；
- outbound `event_id` 一致。
