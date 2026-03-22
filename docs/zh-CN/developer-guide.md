# 开发指南（当前设计）

## 1. 开发环境

```bash
git clone https://github.com/DahaiCAO/crabclaw.git
cd crabclaw
python -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install -e .
```

前端 bridge：

```bash
cd bridge
npm install
npm run build
```

## 2. 代码目录

- `crabclaw/agent`：调度器、I/O 循环、认知运行时；
- `crabclaw/bus`：队列与广播基元；
- `crabclaw/channels`：各通道适配器；
- `crabclaw/dashboard`：仪表盘后端与静态前端；
- `crabclaw/user`：用户、身份映射、账号生命周期；
- `tests`：多用户与运行时行为测试。

## 3. 设计约束

1. 新功能必须保留 `user_scope` 语义。
2. 新出站链路必须携带 `request_id` 与 `event_id`。
3. 新通道必须考虑回环保护与去重友好负载。
4. 所有架构变更需同步更新中英文文档。

## 4. 新增通道步骤

1. 在 `crabclaw/channels` 新建适配器；
2. 在接收链路使用 `_handle_message`；
3. metadata 支持 `user_id`、`request_id`；
4. 实现 `send`；
5. 在 `config/schema.py` 扩展配置结构；
6. 验证 Dashboard Channels 自动表单渲染。

## 5. 身份映射与扇出

- 使用 `UserManager.map_identity` 绑定外部身份；
- 用户解析顺序：
  - `resolve_user_by_identity(channel, sender_id)`
  - fallback `resolve_user_by_identity(channel, chat_id)`；
- 扇出目标来自映射，尽量跳过来源端点。

## 6. 测试与校验

```bash
ruff check crabclaw tests scripts
python -m pytest -q tests/test_multi_user_isolation.py
node --check crabclaw/dashboard/static/app.js
python scripts/e2e_multichannel_sync_check.py --help
```

## 7. 文档更新要求

涉及架构/行为变化的 PR 必须同步更新：
- `README.md`、`README.zh-CN.md`
- `docs/en/*`、`docs/zh-CN/*`
- 示例命令、配置字段与实际实现保持一致。
