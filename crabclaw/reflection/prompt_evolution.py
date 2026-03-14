"""Prompt evolution system for continuous self-improvement of prompt templates."""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from crabclaw.templates.manager import PromptManager
from crabclaw.providers.base import LLMProvider

logger = logging.getLogger(__name__)


@dataclass
class PromptPerformance:
    """Tracks performance metrics for a prompt template."""
    template_name: str
    usage_count: int = 0
    success_count: int = 0
    error_count: int = 0
    avg_response_quality: float = 0.0
    last_evaluated: datetime = field(default_factory=datetime.now)
    feedback_scores: List[float] = field(default_factory=list)


@dataclass
class PromptEvolutionRecord:
    """Records a single evolution event."""
    timestamp: datetime
    template_name: str
    change_type: str  # 'modification', 'creation', 'deletion'
    previous_version: Optional[str]
    new_version: str
    rationale: str
    expected_improvement: str


class PromptEvolutionManager:
    """
    Manages the continuous evolution and optimization of prompt templates.
    
    This system:
    1. Tracks prompt performance metrics
    2. Analyzes conversation quality to identify prompt issues
    3. Proposes and applies prompt improvements
    4. Maintains evolution history
    """

    def __init__(
        self,
        prompt_manager: PromptManager,
        provider: LLMProvider,
        workspace: Path,
    ):
        self.prompt_manager = prompt_manager
        self.provider = provider
        self.workspace = workspace
        self.evolution_dir = workspace / "evolution"
        self.evolution_dir.mkdir(exist_ok=True)
        
        self.performance_file = self.evolution_dir / "prompt_performance.json"
        self.history_file = self.evolution_dir / "evolution_history.jsonl"
        
        self._performance_data: Dict[str, PromptPerformance] = {}
        self._load_performance_data()

    def _load_performance_data(self):
        """Load performance data from disk."""
        if self.performance_file.exists():
            try:
                with open(self.performance_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for name, metrics in data.items():
                        self._performance_data[name] = PromptPerformance(
                            template_name=name,
                            usage_count=metrics.get('usage_count', 0),
                            success_count=metrics.get('success_count', 0),
                            error_count=metrics.get('error_count', 0),
                            avg_response_quality=metrics.get('avg_response_quality', 0.0),
                            last_evaluated=datetime.fromisoformat(
                                metrics.get('last_evaluated', datetime.now().isoformat())
                            ),
                            feedback_scores=metrics.get('feedback_scores', [])
                        )
            except Exception as e:
                logger.error("Failed to load performance data: %s", e)

    def _save_performance_data(self):
        """Save performance data to disk."""
        try:
            data = {}
            for name, perf in self._performance_data.items():
                data[name] = {
                    'usage_count': perf.usage_count,
                    'success_count': perf.success_count,
                    'error_count': perf.error_count,
                    'avg_response_quality': perf.avg_response_quality,
                    'last_evaluated': perf.last_evaluated.isoformat(),
                    'feedback_scores': perf.feedback_scores
                }
            with open(self.performance_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error("Failed to save performance data: %s", e)

    def record_usage(self, template_name: str, success: bool, quality_score: float = 0.0):
        """Record a prompt template usage event."""
        if template_name not in self._performance_data:
            self._performance_data[template_name] = PromptPerformance(
                template_name=template_name
            )
        
        perf = self._performance_data[template_name]
        perf.usage_count += 1
        if success:
            perf.success_count += 1
        else:
            perf.error_count += 1
        
        if quality_score > 0:
            perf.feedback_scores.append(quality_score)
            # Keep only last 100 scores
            perf.feedback_scores = perf.feedback_scores[-100:]
            perf.avg_response_quality = sum(perf.feedback_scores) / len(perf.feedback_scores)
        
        perf.last_evaluated = datetime.now()
        self._save_performance_data()

    async def analyze_and_evolve(self) -> List[PromptEvolutionRecord]:
        """
        Analyze prompt performance and propose evolutions.
        
        Returns:
            List of evolution records for applied changes.
        """
        # Collect performance metrics
        quality_metrics = self._collect_quality_metrics()
        usage_stats = self._collect_usage_stats()
        identified_issues = await self._identify_issues()
        
        # Get evolution proposals from LLM
        prompt = self.prompt_manager.format(
            "reflection_prompt_evolution",
            quality_metrics=json.dumps(quality_metrics, indent=2, ensure_ascii=False),
            usage_stats=json.dumps(usage_stats, indent=2, ensure_ascii=False),
            identified_issues=json.dumps(identified_issues, indent=2, ensure_ascii=False),
            user_feedback="[]"  # TODO: Collect user feedback
        )
        
        try:
            response = await self.provider.chat(messages=[{"role": "user", "content": prompt}])
            content = response.content
            
            # Extract JSON from response
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            evolution_plan = json.loads(content.strip())
            
            # Apply improvements
            records = []
            for improvement in evolution_plan.get("prompt_improvements", []):
                record = await self._apply_improvement(improvement)
                if record:
                    records.append(record)
            
            return records
            
        except Exception as e:
            logger.error("Failed to analyze and evolve prompts: %s", e)
            return []

    def _collect_quality_metrics(self) -> Dict[str, Any]:
        """Collect quality metrics for all prompts."""
        metrics = {}
        for name, perf in self._performance_data.items():
            success_rate = perf.success_count / max(perf.usage_count, 1)
            metrics[name] = {
                "success_rate": success_rate,
                "avg_quality": perf.avg_response_quality,
                "total_usage": perf.usage_count,
                "recent_errors": perf.error_count
            }
        return metrics

    def _collect_usage_stats(self) -> Dict[str, Any]:
        """Collect usage statistics."""
        stats = {
            "total_templates": len(self.prompt_manager.list_templates()),
            "template_usage": {}
        }
        for name, perf in self._performance_data.items():
            stats["template_usage"][name] = perf.usage_count
        return stats

    async def _identify_issues(self) -> List[Dict[str, Any]]:
        """Identify issues based on performance data."""
        issues = []
        for name, perf in self._performance_data.items():
            if perf.usage_count < 5:
                continue  # Not enough data
            
            success_rate = perf.success_count / perf.usage_count
            if success_rate < 0.7:
                issues.append({
                    "template": name,
                    "issue_type": "low_success_rate",
                    "description": f"Success rate is {success_rate:.2%}, below 70% threshold",
                    "severity": "high" if success_rate < 0.5 else "medium"
                })
            
            if perf.avg_response_quality > 0 and perf.avg_response_quality < 0.6:
                issues.append({
                    "template": name,
                    "issue_type": "low_quality",
                    "description": f"Average quality score is {perf.avg_response_quality:.2f}, below 0.6 threshold",
                    "severity": "medium"
                })
        
        return issues

    async def _apply_improvement(self, improvement: Dict[str, Any]) -> Optional[PromptEvolutionRecord]:
        """Apply a single prompt improvement."""
        template_name = improvement.get("template_name", "").lower()
        
        if not template_name:
            return None
        
        # Get current version
        current_version = self.prompt_manager.get_template(template_name)
        
        # Apply the change
        proposed_change = improvement.get("proposed_change", "")
        
        # For now, we append the improvement as a new section
        # In a more sophisticated system, this could use diff/patch
        if current_version:
            new_version = current_version + "\n\n# Evolution Note (" + datetime.now().isoformat() + ")\n" + proposed_change
        else:
            new_version = proposed_change
        
        # Save the new version
        self.prompt_manager.save_template(template_name, new_version)
        
        # Record the evolution
        record = PromptEvolutionRecord(
            timestamp=datetime.now(),
            template_name=template_name,
            change_type="modification",
            previous_version=current_version,
            new_version=new_version,
            rationale=improvement.get("rationale", ""),
            expected_improvement=improvement.get("expected_outcome", "")
        )
        
        self._record_evolution(record)
        
        logger.info(
            "Applied prompt evolution to '{}': {}",
            template_name,
            improvement.get("rationale", "No rationale provided")
        )
        
        return record

    def _record_evolution(self, record: PromptEvolutionRecord):
        """Record an evolution event to history."""
        try:
            with open(self.history_file, 'a', encoding='utf-8') as f:
                data = {
                    "timestamp": record.timestamp.isoformat(),
                    "template_name": record.template_name,
                    "change_type": record.change_type,
                    "rationale": record.rationale,
                    "expected_improvement": record.expected_improvement
                }
                f.write(json.dumps(data, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error("Failed to record evolution: %s", e)

    def get_evolution_history(self, template_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get evolution history, optionally filtered by template name."""
        history = []
        if self.history_file.exists():
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        data = json.loads(line)
                        if template_name is None or data.get("template_name") == template_name:
                            history.append(data)
            except Exception as e:
                logger.error("Failed to read evolution history: %s", e)
        return history
