# 项目结构、贡献与路线图（中文）

<p align="center">
  <a href="../en/project-structure-contributing-roadmap.md"><strong>English</strong></a> | <a href="../zh-CN/project-structure-contributing-roadmap.md"><strong>中文</strong></a>
</p>

## 项目结构
```
crabclaw/
├── agent/          # 🧠 Agent 核心逻辑
│   ├── loop.py     #    Agent 循环（LLM + 工具执行）
│   ├── context.py  #    上下文/提示构建
│   ├── memory.py   #    持久化记忆
│   ├── skills.py   #    Skills 加载
│   ├── subagent.py #    后台任务执行
│   └── tools/      #    内置工具（含 spawn）
├── skills/         # 🎯 内置技能（github、weather、tmux 等）
├── channels/       # 📱 多平台通道集成
├── bus/            # 🚌 消息路由
├── cron/           # ⏰ 计划任务
├── heartbeat/      # 💓 主动唤醒
├── providers/      # 🤖 LLM Providers + 转写
├── session/        # 💬 会话管理
├── config/         # ⚙️ 配置
├── proactive/      # 🔴 主动引擎（engine、selector、state、triggers）
├── reflection/     # 🪞 反思引擎（评估与记录）
├── prompts/        # 🧾 Prompt 管理与默认配置
├── i18n/           # 🌐 多语言
├── templates/      # 📄 Workspace 模板（HEARTBEAT、SOUL、TOOLS）
├── utils/          # 🔧 工具库（logging、http_pool、metrics、plugins）
├── dashboard/      # 📊 简易 Dashboard（静态页、broadcaster）
└── cli/            # 🖥️ 命令行
```

```
顶层目录
├── bridge/         # 🌉 TypeScript bridge（WhatsApp、server）
├── dashboard/      # 📊 Dashboard 服务（Python）
└── tests/          # ✅ 单元测试
```

## 贡献
欢迎 PR。代码库保持小而美，易读易改。

## 路线图
- 多模态（图片、语音、视频）
- 更强长期记忆
- 更强推理（规划与反思）
- 更多集成（日历等）
- 自我改进（反馈闭环）

详情见根目录 [README.md](../../README.md)。
