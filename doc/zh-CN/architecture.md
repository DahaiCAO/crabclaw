# 架构（中文）

<p align="center">
  <a href="../en/architecture.md"><strong>English</strong></a> | <a href="../zh-CN/architecture.md"><strong>中文</strong></a>
</p>

crabclaw 以 HABOS 为指导，通过一个 **行为总调度器** 驱动 **双引擎核心**：

- 被动引擎（Reactive）：经典 ReAct 循环，处理外部输入（消息、文件）。
- 主动引擎（Proactive）：后台自主循环，由内部状态驱动；在“价值 > 打扰成本”时触发高价值行动。

六层认知栈与模块映射：
1. 动机（Soul）：InternalState（目标、任务、风险、价值观）
2. 感知（Nerves）：MessageBus + TriggerSystem
3. 认知（Mind）：ContextBuilder
4. 决策（Brain）：BehaviorScheduler + ActionSelector
5. 执行（Hands）：ToolRegistry
6. 反思（Conscience）：ReflectionEngine

完整架构详见根目录 [README.md](../../README.md)。
