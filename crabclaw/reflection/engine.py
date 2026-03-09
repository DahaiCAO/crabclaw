"""
HABOS 架构 - 反思层 (Meta-Cognition Layer) 的核心引擎

此模块定义了 ReflectionEngine，它是一个在后台运行的独立服务，
负责读取审计日志，进行自我评估和优化，实现 Agent 的自主进化。
"""
import asyncio
import json
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from crabclaw.providers.base import LLMProvider
from crabclaw.prompts.manager import PromptManager
from crabclaw.proactive.state import InternalState

logger = logging.getLogger(__name__)


class ReflectionEngine:
    """
    反思引擎。
    """

    def __init__(
        self,
        state: InternalState,
        provider: LLMProvider,
        audit_log_path: str,
        prompt_manager: PromptManager,
        on_event: Callable[[dict], None] | None = None,
    ):
        self.state = state
        self.provider = provider
        self.audit_log_path = audit_log_path
        self.prompt_manager = prompt_manager
        self._on_event = on_event
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_log_timestamp_processed: float = state.last_reflection_ts

    def _emit(self, event: dict) -> None:
        if not self._on_event:
            return
        try:
            self._on_event(event)
        except Exception:
            return

    def _read_new_logs(self) -> List[Dict[str, Any]]:
        """读取自上次处理以来所有新的审计日志。"""
        new_logs = []
        try:
            with open(self.audit_log_path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        log_entry = json.loads(line)
                        if log_entry["timestamp"] > self._last_log_timestamp_processed:
                            new_logs.append(log_entry)
                    except (json.JSONDecodeError, KeyError):
                        continue # 跳过格式不正确的行
        except FileNotFoundError:
            logger.warning(f"Audit log file not found at: {self.audit_log_path}")
            return []
        
        if new_logs:
            # 更新处理时间戳到最新一条日志的时间
            self._last_log_timestamp_processed = new_logs[-1]["timestamp"]
        
        return new_logs

    async def run_goal_oracle(self, user_request: str, agent_response: str) -> Optional[dict]:
        """
        运行“目标预言机”，判断一次交互是否与长期目标对齐。
        """
        prompt = self.prompt_manager.format(
            "reflection_goal_oracle",
            long_term_goal=self.state.long_term_goal,
            user_request=user_request,
            agent_response=agent_response
        )
        response = await self.provider.chat(messages=[{"role": "user", "content": prompt}])
        try:
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            return json.loads(content)
        except (json.JSONDecodeError, IndexError) as e:
            logger.error(f"Failed to parse Goal Oracle response: {e}")
            return None

    async def run_cycle(self):
        """
        执行一个完整的反思“感知-分析-优化”循环。
        """
        logger.debug("Running reflection engine cycle...")

        log_entries = self._read_new_logs()
        if not log_entries:
            logger.debug("No new audit logs to reflect on.")
            return

        self._emit({"timestamp": time.time(), "stage": "logs_loaded", "count": len(log_entries)})

        logger.info(f"Reflecting on {len(log_entries)} new audit log entries.")

        # 更新状态中的反思时间戳
        self.state.last_reflection_ts = self._last_log_timestamp_processed
        self.state.update_timestamp()

        # 2. 从日志中提取完整的交互（请求/响应对）
        #    这是一个简化的实现，它假设一个请求后紧跟着一个最终响应。
        #    更复杂的实现需要处理多轮对话和并发。
        interactions = self._extract_interactions(log_entries)

        for interaction in interactions:
            # 3. 对每个交互运行“目标预言机”
            logger.debug(f"Running Goal Oracle for interaction...")
            oracle_result = await self.run_goal_oracle(
                interaction["request"], interaction["response"]
            )
            if oracle_result is not None:
                self._emit({
                    "timestamp": time.time(),
                    "stage": "goal_oracle",
                    "session_hint": interaction.get("session_key"),
                    "result": oracle_result,
                })
            if oracle_result and oracle_result.get("goal_alignment_score", 1.0) < 0.5:
                logger.warning(
                    f"Significant deviation detected! "
                    f"Score: {oracle_result['goal_alignment_score']}, "
                    f"Reason: {oracle_result['justification']}"
                )
                # 4. 触发“归因分析”
                optimization_hypothesis = await self.run_root_cause_analysis(
                    interaction["full_log_chain"],
                    oracle_result
                )
                if optimization_hypothesis:
                    logger.info(f"Generated optimization hypothesis: {optimization_hypothesis}")
                    self._emit({
                        "timestamp": time.time(),
                        "stage": "hypothesis",
                        "hypothesis": optimization_hypothesis,
                    })
                    # 5. 触发“内部模拟验证”和“自我优化”
                    await self.verify_and_apply_hypothesis(
                        interaction, optimization_hypothesis
                    )

    async def verify_and_apply_hypothesis(
        self, interaction: Dict[str, Any], hypothesis: Dict[str, Any]
    ):
        """在内部模拟、验证并最终应用一个优化假设。"""
        logger.info(f"Verifying hypothesis: {hypothesis}")

        # 1. 运行内部模拟，获取“虚拟”的新响应
        new_response_content = await self._run_internal_simulation(
            interaction, hypothesis
        )
        if new_response_content is None:
            logger.error("Internal simulation failed. Aborting hypothesis verification.")
            return

        # 2. 将新响应再次交给“目标预言机”评分
        verification_result = await self.run_goal_oracle(
            interaction["request"], new_response_content
        )
        if not verification_result:
            logger.error("Goal Oracle failed during verification. Aborting.")
            return

        original_score = interaction.get("score", 0.3) # 假设原始分数已存
        new_score = verification_result.get("goal_alignment_score", 0.0)
        logger.info(f"Verification result: New score {new_score:.2f} vs. Original score {original_score:.2f}")

        # 3. 对比验证结果，决定是否应用
        if new_score > original_score + 0.2: # 阈值，避免微小波动
            logger.info("Hypothesis verified successfully. Applying permanent optimization.")
            self._apply_permanent_optimization(hypothesis)
        else:
            logger.warning("Hypothesis verification failed. New score did not meet improvement threshold. Discarding change.")

    async def _run_internal_simulation(
        self, interaction: Dict[str, Any], hypothesis: Dict[str, Any]
    ) -> Optional[str]:
        """创建一个临时的‘虚拟 Agent’来运行模拟，并返回其响应。"""
        try:
            hypo_details = hypothesis.get("optimization_hypothesis", {})
            hypo_type = hypo_details.get("type")

            logger.info(f"Running internal simulation for hypothesis type: {hypo_type}")

            # 1. 创建一个隔离的模拟环境
            # 深度复制状态，确保模拟不影响真实状态
            virtual_state = self.state.model_copy(deep=True)
            
            # 为本次模拟创建一个临时的、被修改过的 PromptManager
            virtual_prompt_manager = self._create_virtual_prompt_manager(hypothesis)
            if not virtual_prompt_manager:
                return None

            # 创建一个使用虚拟组件的“虚拟”被动引擎
            # 注意：这是一个简化的工厂方法，实际产品中需要更完善的依赖注入
            virtual_reactive_engine = self._create_virtual_reactive_engine(
                virtual_state, virtual_prompt_manager
            )

            # 2. 在虚拟引擎上重新运行原始请求
            logger.info("Executing request on virtual engine...")
            response = await virtual_reactive_engine.process_direct(
                interaction["request"], session_key="simulation"
            )
            return response.content if response else None

        except Exception as e:
            logger.error(f"Error during internal simulation: {e}", exc_info=True)
            return None

    def _create_virtual_prompt_manager(
        self, hypothesis: Dict[str, Any]
    ) -> Optional[PromptManager]:
        """为模拟创建一个临时的、被修改过的 PromptManager。"""
        from crabclaw.prompts.manager import PromptManager
        hypo_details = hypothesis.get("optimization_hypothesis", {})
        hypo_type = hypo_details.get("type")
        hypo_target = hypo_details.get("target")
        hypo_change = hypo_details.get("proposed_change")

        if hypo_type != "prompt_template_modification":
            # 对于非提示词修改，我们可以使用原始的 prompt_manager
            return self.prompt_manager

        # 创建一个新的 PromptManager 实例，它继承了所有现有的模板
        virtual_manager = PromptManager(self.prompt_manager.templates_dir)
        # 在内存中直接覆盖要修改的模板
        if hypo_target in virtual_manager.templates:
            virtual_manager.templates[hypo_target]["template"] = hypo_change
            logger.debug(f"Virtual prompt manager created with modified template: {hypo_target}")
            return virtual_manager
        else:
            logger.error(f"Cannot create virtual prompt manager: target '{hypo_target}' not found.")
            return None

    def _create_virtual_reactive_engine(
        self, virtual_state: InternalState, virtual_prompt_manager: PromptManager
    ) -> "AgentLoop":
        """(简化版工厂) 创建一个用于模拟的被动引擎实例。"""
        from crabclaw.agent.loop import AgentLoop
        
        # 注意：这里我们只替换了核心的 provider 和 workspace，
        # 一个完整的产品级实现需要处理所有依赖。
        return AgentLoop(
            bus=self.bus, # 共享 bus 以便接收响应
            provider=self.provider, # 共享 provider
            workspace=Path("~/.crabclaw/simulation_workspace"), # 使用一个隔离的工作区
            internal_state=virtual_state,
            audit_logger=None, # 模拟过程不产生审计日志
            prompt_manager=virtual_prompt_manager
        )

    def _apply_permanent_optimization(self, hypothesis: Dict[str, Any]):
        """将一个已验证的优化假设永久性地应用到 Agent 的配置中。"""
        try:
            hypo_type = hypothesis.get("optimization_hypothesis", {}).get("type")
            hypo_target = hypothesis.get("optimization_hypothesis", {}).get("target")
            hypo_change = hypothesis.get("optimization_hypothesis", {}).get("proposed_change")

            if not all([hypo_type, hypo_target, hypo_change]):
                logger.error(f"Invalid hypothesis format: {hypothesis}")
                return

            if hypo_type == "state_parameter_adjustment":
                # 处理对 InternalState 参数的直接调整
                if hasattr(self.state, hypo_target):
                    current_value = getattr(self.state, hypo_target)
                    # 简单的数学运算处理
                    if isinstance(current_value, (int, float)):
                        # 注意：eval() 有安全风险，此处用非常受限的方式处理
                        if hypo_change.startswith(("+", "-")):
                            new_value = current_value + float(hypo_change)
                        else:
                            new_value = float(hypo_change)
                        setattr(self.state, hypo_target, new_value)
                        logger.info(f"Adjusted state parameter '{hypo_target}' from {current_value} to {new_value}")
                        self.state.update_timestamp()
                    else:
                        logger.warning(f"Cannot apply arithmetic change to non-numeric state parameter '{hypo_target}'")
                else:
                    logger.error(f"Attempted to adjust non-existent state parameter: {hypo_target}")
            
            elif hypo_type == "prompt_template_modification":
                self.prompt_manager.save_template(hypo_target, hypo_change)
                logger.info(f"Applied prompt modification for '{hypo_target}'.")
                self._emit({
                    "timestamp": time.time(),
                    "stage": "applied",
                    "type": hypo_type,
                    "target": hypo_target,
                })

            else:
                logger.warning(f"Unknown hypothesis type: {hypo_type}")

        except Exception as e:
            logger.error(f"Failed to apply optimization hypothesis: {e}", exc_info=True)

    async def run_root_cause_analysis(
        self, log_chain: List[Dict[str, Any]], oracle_result: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """对低分行为进行根本原因分析，并生成优化假设。"""
        prompt = self.prompt_manager.format(
            "reflection_root_cause_analysis",
            long_term_goal=self.state.long_term_goal,
            goal_alignment_score=oracle_result.get('goal_alignment_score'),
            justification=oracle_result.get('justification'),
            log_chain_json=json.dumps(log_chain, indent=2, ensure_ascii=False)
        )
        response = await self.provider.chat(messages=[{"role": "user", "content": prompt}])
        try:
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            return json.loads(content)
        except (json.JSONDecodeError, IndexError) as e:
            logger.error(f"Failed to parse Root Cause Analysis response: {e}")
            return None

    def _extract_interactions(self, logs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """从日志条目中按 session_key 提取完整的交互链。"""
        sessions: Dict[str, List[Dict[str, Any]]] = {}
        for log in logs:
            session_key = log.get("details", {}).get("session_key")
            if session_key:
                if session_key not in sessions:
                    sessions[session_key] = []
                sessions[session_key].append(log)

        interactions = []
        for session_key, session_logs in sessions.items():
            # 简单的假设：每个会话的第一个 InboundMessage 是请求，最后一个 OutboundMessage 是响应
            inbound_logs = [log for log in session_logs if log["event_type"] == "InboundMessage"]
            outbound_logs = [log for log in session_logs if log["event_type"] == "OutboundMessage"]

            if inbound_logs and outbound_logs:
                interactions.append({
                    "request": inbound_logs[0]["details"].get("content", ""),
                    "response": outbound_logs[-1]["details"].get("content", ""),
                    "full_log_chain": session_logs
                })
        return interactions

    async def _loop(self, interval_seconds: int):
        """
        引擎的主循环，定期运行 run_cycle。
        """
        self._running = True
        logger.info(f"Reflection Engine started with {interval_seconds}s interval.")
        while self._running:
            try:
                await self.run_cycle()
                await asyncio.sleep(interval_seconds)
            except asyncio.CancelledError:
                self._running = False
                break
            except Exception as e:
                logger.error(f"Error in reflection engine loop: {e}", exc_info=True)
                await asyncio.sleep(interval_seconds)
        logger.info("Reflection Engine stopped.")

    def start(self, interval_seconds: int = 3600):  # 默认为每小时反思一次
        """在后台启动反思引擎。"""
        if not self._running:
            self._task = asyncio.create_task(self._loop(interval_seconds))

    def stop(self):
        """停止反思引擎。"""
        if self._task and not self._task.done():
            self._task.cancel()
