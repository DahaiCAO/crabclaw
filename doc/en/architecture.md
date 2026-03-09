# Architecture (EN)

<p align="center">
  <a href="../en/architecture.md"><strong>English</strong></a> | <a href="../zh-CN/architecture.md"><strong>中文</strong></a>
</p>

crabclaw reimagines agents through HABOS with a Dual-Engine Core orchestrated by a Behavior Scheduler:

- Reactive Engine (Executor): classic ReAct loop; handles external inputs (messages, files).
- Proactive Engine (Thinker): autonomous background loop; driven by Internal State, triggers high-value actions when value outweighs interruption cost.

Six cognitive layers mapped to code modules:
1. Motivation (Soul): InternalState (goals, tasks, risks, values)
2. Perception (Nerves): MessageBus + TriggerSystem
3. Cognitive (Mind): ContextBuilder
4. Decision (Brain): BehaviorScheduler + ActionSelector
5. Execution (Hands): ToolRegistry
6. Reflection (Conscience): ReflectionEngine

See the full architecture in [README.md](../../README.md).
