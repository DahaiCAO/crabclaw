from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher, unified_diff
from pathlib import Path
from typing import Any

from crabclaw.utils.helpers import ensure_dir

_NON_WORD = re.compile(r"[^\w\u4e00-\u9fff]+")


@dataclass
class PromptScore:
    completeness: float
    specificity: float
    structure: float
    safety: float
    total: float

    def to_dict(self) -> dict[str, float]:
        return {
            "completeness": self.completeness,
            "specificity": self.specificity,
            "structure": self.structure,
            "safety": self.safety,
            "total": self.total,
        }


class PromptEvolutionPipeline:
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.root = ensure_dir(workspace / ".prompt_evolution")
        self.versions_dir = ensure_dir(self.root / "versions")
        self.candidates_dir = ensure_dir(self.root / "candidates")
        self.state_file = self.root / "state.json"
        self._state = self._load_state()

    def _load_state(self) -> dict[str, Any]:
        if self.state_file.exists():
            state = json.loads(self.state_file.read_text(encoding="utf-8"))
        else:
            state = {"deployments": {}, "candidates": {}, "history": []}
        state.setdefault("deployments", {})
        state.setdefault("candidates", {})
        state.setdefault("history", [])
        state.setdefault("metrics", {})
        state.setdefault("alert_rules", self.default_alert_rules())
        state.setdefault("review_drafts", {})
        self._migrate_review_drafts(state)
        return state

    def _save_state(self) -> None:
        self.state_file.write_text(
            json.dumps(self._state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _migrate_review_drafts(self, state: dict[str, Any]) -> None:
        drafts = state.setdefault("review_drafts", {})
        migrated = False
        for candidate_id, payload in list(drafts.items()):
            if not isinstance(payload, dict):
                drafts[candidate_id] = {"by_reviewer": {}}
                migrated = True
                continue
            if "by_reviewer" in payload:
                continue
            reviewer = str(payload.get("reviewer", "") or "anonymous")
            decisions = payload.get("decisions", {})
            updated_at = payload.get("updated_at")
            drafts[candidate_id] = {
                "by_reviewer": {
                    reviewer: {
                        "reviewer": reviewer,
                        "decisions": decisions if isinstance(decisions, dict) else {},
                        "updated_at": updated_at,
                    }
                }
            }
            migrated = True
        if migrated:
            state.setdefault("history", []).append(
                {
                    "type": "review_draft_migrated",
                    "at": datetime.utcnow().isoformat(),
                }
            )

    def _draft_bucket(self, candidate_id: str) -> dict[str, Any]:
        drafts = self._state.setdefault("review_drafts", {})
        bucket = drafts.get(candidate_id)
        if not isinstance(bucket, dict) or "by_reviewer" not in bucket:
            bucket = {"by_reviewer": {}}
            drafts[candidate_id] = bucket
        bucket.setdefault("by_reviewer", {})
        return bucket

    @staticmethod
    def default_alert_rules() -> dict[str, float]:
        return {
            "low_sample_canary": 5.0,
            "warning_error_rate": 0.25,
            "critical_error_rate": 0.45,
            "high_avg_turns": 4.5,
        }

    @staticmethod
    def _empty_online_metrics() -> dict[str, float]:
        return {
            "tool_calls": 0.0,
            "tool_successes": 0.0,
            "errors": 0.0,
            "turns": 0.0,
        }

    def _candidate_metrics(self, candidate_id: str) -> dict[str, float]:
        metrics = self._state.setdefault("metrics", {})
        if candidate_id not in metrics:
            metrics[candidate_id] = self._empty_online_metrics()
        return metrics[candidate_id]

    def _template_root(self) -> Path:
        return Path(__file__).resolve().parent.parent / "templates"

    def managed_files(self) -> list[str]:
        files = []
        for section in ("nature", "social", "prompts"):
            folder = self.workspace / section
            if not folder.exists():
                continue
            for item in sorted(folder.glob("*.md")):
                files.append(f"{section}/{item.name}")
        return files

    def normalize_file_rel(self, file_rel: str) -> str:
        normalized = file_rel.replace("\\", "/").strip("/")
        allowed_prefixes = ("nature/", "social/", "prompts/")
        if not normalized.startswith(allowed_prefixes):
            raise ValueError("Only workspace prompt files are supported (nature/social/prompts).")
        return normalized

    def workspace_file(self, file_rel: str) -> Path:
        rel = self.normalize_file_rel(file_rel)
        path = self.workspace / rel
        if not path.resolve().is_relative_to(self.workspace.resolve()):
            raise ValueError("Unsafe file path.")
        return path

    def template_file(self, file_rel: str) -> Path:
        rel = self.normalize_file_rel(file_rel)
        return self._template_root() / rel

    def score_content(self, content: str) -> PromptScore:
        text = content.strip()
        length = len(text)
        words = [w for w in _NON_WORD.split(text.lower()) if w]
        unique_words = len(set(words))
        lines = [x.strip() for x in text.splitlines() if x.strip()]

        completeness = min(1.0, length / 600.0)
        specificity_terms = {"must", "should", "if", "when", "never", "always", "禁止", "必须", "应当", "如果"}
        specificity_hits = sum(1 for w in words if w in specificity_terms)
        specificity = min(1.0, (specificity_hits / 8.0) + (unique_words / max(1, len(words))) * 0.4)
        heading_count = sum(1 for line in lines if line.startswith("#"))
        bullet_count = sum(1 for line in lines if line.startswith(("-", "*")))
        structure = min(1.0, heading_count * 0.2 + bullet_count * 0.08)
        risky_tokens = {"ignore previous", "bypass", "disable safety", "sudo rm -rf", "越权", "绕过"}
        safety_penalty = 0.0
        lowered = text.lower()
        for token in risky_tokens:
            if token in lowered:
                safety_penalty += 0.25
        safety = max(0.0, 1.0 - safety_penalty)
        total = completeness * 0.30 + specificity * 0.30 + structure * 0.20 + safety * 0.20
        return PromptScore(
            completeness=round(completeness, 4),
            specificity=round(specificity, 4),
            structure=round(structure, 4),
            safety=round(safety, 4),
            total=round(total, 4),
        )

    def evaluate_file(self, file_rel: str) -> dict[str, Any]:
        path = self.workspace_file(file_rel)
        if not path.exists():
            raise FileNotFoundError(f"Workspace prompt not found: {file_rel}")
        content = path.read_text(encoding="utf-8")
        score = self.score_content(content)
        return {"file": file_rel, "score": score.to_dict(), "length": len(content)}

    def _extract_learning_policies(self, max_items: int = 5) -> list[str]:
        history_file = self.workspace / "memory" / "HISTORY.md"
        if not history_file.exists():
            return []
        text = history_file.read_text(encoding="utf-8")
        lines = [x.strip() for x in text.splitlines() if x.strip()]
        candidates: list[str] = []
        for line in reversed(lines):
            lowered = line.lower()
            if any(token in lowered for token in ("fail", "error", "timeout", "not enough", "insufficient", "失败", "错误", "超时")):
                candidates.append(line)
            if len(candidates) >= max_items:
                break
        policies = []
        for i, item in enumerate(candidates, 1):
            policies.append(f"- Rule {i}: Avoid repeating pattern from event: {item[:180]}")
        return policies

    def generate_candidate_content(self, file_rel: str, reason: str = "self_learning") -> dict[str, Any]:
        path = self.workspace_file(file_rel)
        if not path.exists():
            raise FileNotFoundError(f"Workspace prompt not found: {file_rel}")
        base_content = path.read_text(encoding="utf-8")
        base_score = self.score_content(base_content)

        policies = self._extract_learning_policies()
        if not policies:
            policies = [
                "- Rule 1: Clarify constraints before tool use.",
                "- Rule 2: Prefer low-risk plans when confidence is low.",
                "- Rule 3: Explicitly check credits/energy before expensive actions.",
            ]
        section = "\n".join(
            [
                "",
                "## Evolution Policies",
                f"- Source: {reason}",
                *policies,
            ]
        )
        candidate_content = base_content.rstrip() + "\n" + section + "\n"
        candidate_score = self.score_content(candidate_content)
        candidate_id = self._create_candidate(file_rel, candidate_content, reason, base_score, candidate_score)
        return {
            "candidate_id": candidate_id,
            "base_score": base_score.to_dict(),
            "candidate_score": candidate_score.to_dict(),
            "improvement": round(candidate_score.total - base_score.total, 4),
        }

    def _create_candidate(
        self,
        file_rel: str,
        candidate_content: str,
        reason: str,
        base_score: PromptScore,
        candidate_score: PromptScore,
    ) -> str:
        ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        digest = hashlib.sha1(candidate_content.encode("utf-8")).hexdigest()[:8]
        candidate_id = f"{ts}_{digest}"
        payload = {
            "candidate_id": candidate_id,
            "file": self.normalize_file_rel(file_rel),
            "created_at": datetime.utcnow().isoformat(),
            "reason": reason,
            "base_score": base_score.to_dict(),
            "candidate_score": candidate_score.to_dict(),
            "content": candidate_content,
            "status": "created",
        }
        (self.candidates_dir / f"{candidate_id}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._state["candidates"][candidate_id] = {
            "file": payload["file"],
            "status": "created",
            "created_at": payload["created_at"],
        }
        self._state["history"].append(
            {"type": "candidate_created", "candidate_id": candidate_id, "file": payload["file"], "at": payload["created_at"]}
        )
        self._save_state()
        return candidate_id

    def load_candidate(self, candidate_id: str) -> dict[str, Any]:
        file = self.candidates_dir / f"{candidate_id}.json"
        if not file.exists():
            raise FileNotFoundError(f"Candidate not found: {candidate_id}")
        return json.loads(file.read_text(encoding="utf-8"))

    def canary_release(self, candidate_id: str, rollout_percent: int = 20) -> dict[str, Any]:
        candidate = self.load_candidate(candidate_id)
        rollout_percent = max(1, min(100, rollout_percent))
        file_rel = candidate["file"]
        self._state["deployments"][file_rel] = {
            "mode": "canary",
            "candidate_id": candidate_id,
            "rollout_percent": rollout_percent,
            "updated_at": datetime.utcnow().isoformat(),
        }
        self._state["candidates"][candidate_id]["status"] = "canary"
        self._candidate_metrics(candidate_id)
        self._state["history"].append(
            {
                "type": "canary_release",
                "candidate_id": candidate_id,
                "file": file_rel,
                "rollout_percent": rollout_percent,
                "at": datetime.utcnow().isoformat(),
            }
        )
        self._save_state()
        return self._state["deployments"][file_rel]

    def ingest_online_metrics(
        self,
        candidate_id: str,
        *,
        tool_calls: int = 0,
        tool_successes: int = 0,
        errors: int = 0,
        turns: int = 0,
    ) -> dict[str, float]:
        if candidate_id not in self._state.get("candidates", {}):
            raise FileNotFoundError(f"Candidate not found: {candidate_id}")
        m = self._candidate_metrics(candidate_id)
        m["tool_calls"] += max(0, tool_calls)
        m["tool_successes"] += max(0, tool_successes)
        m["errors"] += max(0, errors)
        m["turns"] += max(0, turns)
        self._state["history"].append(
            {
                "type": "metrics_ingest",
                "candidate_id": candidate_id,
                "tool_calls": tool_calls,
                "tool_successes": tool_successes,
                "errors": errors,
                "turns": turns,
                "at": datetime.utcnow().isoformat(),
            }
        )
        self._save_state()
        return dict(m)

    def ingest_runtime_outcome(self, action_status: str, turn_count: int = 1) -> None:
        active_candidates = []
        for deploy in self._state.get("deployments", {}).values():
            if deploy.get("mode") == "canary" and deploy.get("candidate_id"):
                active_candidates.append(deploy["candidate_id"])
        if not active_candidates:
            return
        status = (action_status or "").lower()
        is_success = status == "success"
        for candidate_id in active_candidates:
            self.ingest_online_metrics(
                candidate_id,
                tool_calls=1,
                tool_successes=1 if is_success else 0,
                errors=0 if is_success else 1,
                turns=max(1, int(turn_count)),
            )

    def evaluate_candidate_online(self, candidate_id: str) -> dict[str, float]:
        metrics = self._candidate_metrics(candidate_id)
        calls = max(1.0, metrics["tool_calls"])
        turns = max(1.0, metrics["turns"])
        tool_success_rate = metrics["tool_successes"] / calls
        error_rate = metrics["errors"] / calls
        avg_turns = turns / calls
        online_score = (
            tool_success_rate * 0.60
            + max(0.0, 1.0 - error_rate) * 0.25
            + max(0.0, 1.0 - min(avg_turns / 5.0, 1.0)) * 0.15
        )
        return {
            "tool_success_rate": round(tool_success_rate, 4),
            "error_rate": round(error_rate, 4),
            "avg_turns": round(avg_turns, 4),
            "online_score": round(online_score, 4),
            "samples": int(metrics["tool_calls"]),
        }

    def candidate_timeseries(self, candidate_id: str) -> list[dict[str, Any]]:
        running = self._empty_online_metrics()
        series: list[dict[str, Any]] = []
        for event in self._state.get("history", []):
            if event.get("type") != "metrics_ingest":
                continue
            if event.get("candidate_id") != candidate_id:
                continue
            running["tool_calls"] += max(0.0, float(event.get("tool_calls", 0)))
            running["tool_successes"] += max(0.0, float(event.get("tool_successes", 0)))
            running["errors"] += max(0.0, float(event.get("errors", 0)))
            running["turns"] += max(0.0, float(event.get("turns", 0)))
            calls = max(1.0, running["tool_calls"])
            turns = max(1.0, running["turns"])
            success_rate = running["tool_successes"] / calls
            error_rate = running["errors"] / calls
            avg_turns = turns / calls
            online_score = (
                success_rate * 0.60
                + max(0.0, 1.0 - error_rate) * 0.25
                + max(0.0, 1.0 - min(avg_turns / 5.0, 1.0)) * 0.15
            )
            series.append(
                {
                    "ts": event.get("at"),
                    "tool_success_rate": round(success_rate, 4),
                    "error_rate": round(error_rate, 4),
                    "avg_turns": round(avg_turns, 4),
                    "online_score": round(online_score, 4),
                    "samples": int(running["tool_calls"]),
                }
            )
        return series

    def auto_decide_deployments(
        self,
        *,
        min_samples: int = 10,
        promote_success_rate: float = 0.75,
        promote_error_rate: float = 0.20,
        rollback_error_rate: float = 0.45,
    ) -> list[dict[str, Any]]:
        decisions: list[dict[str, Any]] = []
        deployments = self._state.get("deployments", {})
        for file_rel, deploy in list(deployments.items()):
            if deploy.get("mode") != "canary":
                continue
            candidate_id = deploy.get("candidate_id")
            if not candidate_id:
                continue
            online = self.evaluate_candidate_online(candidate_id)
            if online["samples"] < min_samples:
                continue
            if online["error_rate"] >= rollback_error_rate:
                try:
                    rollback_result = self.rollback(file_rel=file_rel)
                except FileNotFoundError:
                    rollback_result = {"file": file_rel, "version_id": None, "note": "no_snapshot_needed"}
                    self._state["deployments"].pop(file_rel, None)
                self._state["candidates"][candidate_id]["status"] = "rejected"
                decisions.append(
                    {
                        "file": file_rel,
                        "candidate_id": candidate_id,
                        "decision": "rollback",
                        "online": online,
                        "result": rollback_result,
                    }
                )
                continue
            if online["tool_success_rate"] >= promote_success_rate and online["error_rate"] <= promote_error_rate:
                promote_result = self.promote(candidate_id)
                decisions.append(
                    {
                        "file": file_rel,
                        "candidate_id": candidate_id,
                        "decision": "promote",
                        "online": online,
                        "result": promote_result,
                    }
                )
        if decisions:
            self._state["history"].append(
                {
                    "type": "auto_decision_batch",
                    "count": len(decisions),
                    "at": datetime.utcnow().isoformat(),
                }
            )
            self._save_state()
        return decisions

    def _snapshot_current(self, file_rel: str, reason: str) -> str:
        file_path = self.workspace_file(file_rel)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        if not file_path.exists():
            file_path.write_text("", encoding="utf-8")
        file_text = file_path.read_text(encoding="utf-8")
        stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        bucket = ensure_dir(self.versions_dir / file_rel.replace("/", "__"))
        version_id = f"{stamp}_{hashlib.sha1(file_text.encode('utf-8')).hexdigest()[:8]}"
        version_path = bucket / f"{version_id}.md"
        version_path.write_text(file_text, encoding="utf-8")
        meta_path = bucket / f"{version_id}.json"
        meta_path.write_text(
            json.dumps(
                {
                    "version_id": version_id,
                    "file": file_rel,
                    "created_at": datetime.utcnow().isoformat(),
                    "reason": reason,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return version_id

    def promote(self, candidate_id: str) -> dict[str, Any]:
        candidate = self.load_candidate(candidate_id)
        file_rel = candidate["file"]
        previous_version = self._snapshot_current(file_rel, reason=f"promote:{candidate_id}")
        target = self.workspace_file(file_rel)
        target.write_text(candidate["content"], encoding="utf-8")
        self._state["deployments"][file_rel] = {
            "mode": "promoted",
            "candidate_id": candidate_id,
            "rollout_percent": 100,
            "updated_at": datetime.utcnow().isoformat(),
            "previous_version": previous_version,
        }
        self._state["candidates"][candidate_id]["status"] = "promoted"
        self._state["history"].append(
            {"type": "promote", "candidate_id": candidate_id, "file": file_rel, "at": datetime.utcnow().isoformat()}
        )
        self._save_state()
        return {"file": file_rel, "candidate_id": candidate_id, "previous_version": previous_version}

    def rollback(self, file_rel: str, version_id: str | None = None) -> dict[str, Any]:
        rel = self.normalize_file_rel(file_rel)
        bucket = self.versions_dir / rel.replace("/", "__")
        if not bucket.exists():
            raise FileNotFoundError(f"No versions available for {rel}")
        target_version = version_id
        if not target_version:
            versions = sorted(bucket.glob("*.md"))
            if not versions:
                raise FileNotFoundError(f"No versions available for {rel}")
            target_version = versions[-1].stem
        source = bucket / f"{target_version}.md"
        if not source.exists():
            raise FileNotFoundError(f"Version not found: {target_version}")
        self.workspace_file(rel).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        deployment = self._state["deployments"].get(rel)
        if deployment:
            deployment["mode"] = "rolled_back"
            deployment["updated_at"] = datetime.utcnow().isoformat()
        self._state["history"].append(
            {"type": "rollback", "file": rel, "version_id": target_version, "at": datetime.utcnow().isoformat()}
        )
        self._save_state()
        return {"file": rel, "version_id": target_version}

    def factory_reset(self, file_rel: str) -> dict[str, Any]:
        rel = self.normalize_file_rel(file_rel)
        template = self.template_file(rel)
        if not template.exists():
            raise FileNotFoundError(f"Factory template not found for {rel}")
        previous_version = self._snapshot_current(rel, reason="factory_reset")
        self.workspace_file(rel).write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
        deployment = self._state["deployments"].get(rel)
        if deployment:
            deployment["mode"] = "factory_reset"
            deployment["updated_at"] = datetime.utcnow().isoformat()
        self._state["history"].append(
            {"type": "factory_reset", "file": rel, "previous_version": previous_version, "at": datetime.utcnow().isoformat()}
        )
        self._save_state()
        return {"file": rel, "previous_version": previous_version}

    def resolve_runtime_content(self, file_rel: str, routing_key: str | None) -> str | None:
        rel = self.normalize_file_rel(file_rel)
        deploy = self._state.get("deployments", {}).get(rel)
        if not deploy:
            return None
        if deploy.get("mode") != "canary":
            return None
        candidate_id = deploy.get("candidate_id")
        if not candidate_id:
            return None
        candidate = self.load_candidate(candidate_id)
        rollout = int(deploy.get("rollout_percent", 0))
        if rollout <= 0:
            return None
        bucket_key = routing_key or "default"
        hash_num = int(hashlib.sha1(bucket_key.encode("utf-8")).hexdigest()[:8], 16) % 100
        if hash_num < rollout:
            return candidate["content"]
        return None

    def status(self) -> dict[str, Any]:
        online = {}
        candidates = {}
        series = {}
        for candidate_id in self._state.get("candidates", {}):
            online[candidate_id] = self.evaluate_candidate_online(candidate_id)
            candidates[candidate_id] = self._state["candidates"][candidate_id]
            series[candidate_id] = self.candidate_timeseries(candidate_id)
        return {
            "managed_files": self.managed_files(),
            "deployments": self._state.get("deployments", {}),
            "candidate_count": len(self._state.get("candidates", {})),
            "history_count": len(self._state.get("history", [])),
            "candidates": candidates,
            "online_metrics": online,
            "timeseries": series,
        }

    def decision_timeline(self, limit: int = 80) -> list[dict[str, Any]]:
        timeline = []
        for event in self._state.get("history", []):
            etype = event.get("type")
            if etype not in {"canary_release", "promote", "rollback", "factory_reset", "auto_decision_batch"}:
                continue
            timeline.append(
                {
                    "type": etype,
                    "at": event.get("at"),
                    "file": event.get("file"),
                    "candidate_id": event.get("candidate_id"),
                    "rollout_percent": event.get("rollout_percent"),
                    "count": event.get("count"),
                    "version_id": event.get("version_id"),
                }
            )
        return timeline[-limit:]

    def alerts(self) -> list[dict[str, Any]]:
        alerts: list[dict[str, Any]] = []
        deployments = self._state.get("deployments", {})
        rules = self._state.get("alert_rules", self.default_alert_rules())
        low_sample_canary = max(1.0, float(rules.get("low_sample_canary", 5.0)))
        warning_error_rate = max(0.0, float(rules.get("warning_error_rate", 0.25)))
        critical_error_rate = max(warning_error_rate, float(rules.get("critical_error_rate", 0.45)))
        high_avg_turns = max(0.0, float(rules.get("high_avg_turns", 4.5)))
        for file_rel, deploy in deployments.items():
            candidate_id = deploy.get("candidate_id")
            if not candidate_id:
                continue
            online = self.evaluate_candidate_online(candidate_id)
            if deploy.get("mode") == "canary" and online["samples"] < low_sample_canary:
                alerts.append(
                    {
                        "level": "warning",
                        "file": file_rel,
                        "candidate_id": candidate_id,
                        "title": "Low Canary Sample",
                        "detail": f"samples={online['samples']} < {int(low_sample_canary)}",
                    }
                )
            if online["error_rate"] >= critical_error_rate:
                alerts.append(
                    {
                        "level": "critical",
                        "file": file_rel,
                        "candidate_id": candidate_id,
                        "title": "High Error Rate",
                        "detail": f"error_rate={online['error_rate']:.3f}",
                    }
                )
            elif online["error_rate"] >= warning_error_rate:
                alerts.append(
                    {
                        "level": "warning",
                        "file": file_rel,
                        "candidate_id": candidate_id,
                        "title": "Elevated Error Rate",
                        "detail": f"error_rate={online['error_rate']:.3f}",
                    }
                )
            if online["avg_turns"] >= high_avg_turns:
                alerts.append(
                    {
                        "level": "warning",
                        "file": file_rel,
                        "candidate_id": candidate_id,
                        "title": "High Avg Turns",
                        "detail": f"avg_turns={online['avg_turns']:.3f}",
                    }
                )
        return alerts

    def set_alert_rules(self, **kwargs: float) -> dict[str, float]:
        rules = self._state.get("alert_rules", self.default_alert_rules())
        for key in self.default_alert_rules():
            if key in kwargs and kwargs[key] is not None:
                rules[key] = float(kwargs[key])
        if rules["critical_error_rate"] < rules["warning_error_rate"]:
            rules["critical_error_rate"] = rules["warning_error_rate"]
        rules["low_sample_canary"] = max(1.0, rules["low_sample_canary"])
        rules["warning_error_rate"] = max(0.0, min(1.0, rules["warning_error_rate"]))
        rules["critical_error_rate"] = max(0.0, min(1.0, rules["critical_error_rate"]))
        rules["high_avg_turns"] = max(0.0, rules["high_avg_turns"])
        self._state["alert_rules"] = rules
        self._state["history"].append(
            {
                "type": "alert_rules_updated",
                "rules": rules,
                "at": datetime.utcnow().isoformat(),
            }
        )
        self._save_state()
        return rules

    def compare_by_file(self) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for candidate_id, item in self._state.get("candidates", {}).items():
            file_rel = item.get("file")
            if not file_rel:
                continue
            online = self.evaluate_candidate_online(candidate_id)
            grouped.setdefault(file_rel, []).append(
                {
                    "candidate_id": candidate_id,
                    "status": item.get("status"),
                    "created_at": item.get("created_at"),
                    "online": online,
                }
            )
        for file_rel in grouped:
            grouped[file_rel].sort(
                key=lambda x: (x["online"]["online_score"], x["online"]["samples"]),
                reverse=True,
            )
        return grouped

    def dashboard_snapshot(self) -> dict[str, Any]:
        base = self.status()
        base["timeline"] = self.decision_timeline()
        base["alerts"] = self.alerts()
        base["comparisons"] = self.compare_by_file()
        base["alert_rules"] = self._state.get("alert_rules", self.default_alert_rules())
        return base

    def _latest_version_meta(self, file_rel: str) -> dict[str, Any] | None:
        bucket = self.versions_dir / file_rel.replace("/", "__")
        if not bucket.exists():
            return None
        metas = sorted(bucket.glob("*.json"))
        if not metas:
            return None
        meta_path = metas[-1]
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def candidate_diff(self, candidate_id: str, context_lines: int = 2) -> dict[str, Any]:
        candidate = self.load_candidate(candidate_id)
        file_rel = candidate["file"]
        workspace_path = self.workspace_file(file_rel)
        baseline = workspace_path.read_text(encoding="utf-8") if workspace_path.exists() else ""
        candidate_text = candidate.get("content", "")
        diff_lines = list(
            unified_diff(
                baseline.splitlines(),
                candidate_text.splitlines(),
                fromfile=f"workspace:{file_rel}",
                tofile=f"candidate:{candidate_id}",
                lineterm="",
                n=context_lines,
            )
        )
        added = sum(1 for line in diff_lines if line.startswith("+") and not line.startswith("+++"))
        removed = sum(1 for line in diff_lines if line.startswith("-") and not line.startswith("---"))
        changed_blocks = sum(1 for line in diff_lines if line.startswith("@@"))
        return {
            "file": file_rel,
            "candidate_id": candidate_id,
            "added_lines": added,
            "removed_lines": removed,
            "changed_blocks": changed_blocks,
            "diff_text": "\n".join(diff_lines),
        }

    def candidate_events(self, candidate_id: str, limit: int = 120) -> list[dict[str, Any]]:
        items = []
        for event in self._state.get("history", []):
            cid = event.get("candidate_id")
            if cid != candidate_id:
                continue
            items.append(event)
        return items[-limit:]

    def candidate_detail(self, candidate_id: str) -> dict[str, Any]:
        candidate = self.load_candidate(candidate_id)
        file_rel = candidate["file"]
        online = self.evaluate_candidate_online(candidate_id)
        series = self.candidate_timeseries(candidate_id)
        diff_summary = self.candidate_diff(candidate_id)
        blocks = self.candidate_blocks(candidate_id)
        events = self.candidate_events(candidate_id)
        latest_version = self._latest_version_meta(file_rel)
        draft = self.get_review_draft(candidate_id)
        draft_all = self.list_review_drafts(candidate_id)
        conflicts = self.review_conflicts(candidate_id)
        return {
            "candidate_id": candidate_id,
            "file": file_rel,
            "status": self._state.get("candidates", {}).get(candidate_id, {}).get("status"),
            "created_at": self._state.get("candidates", {}).get(candidate_id, {}).get("created_at"),
            "online": online,
            "timeseries": series,
            "base_score": candidate.get("base_score"),
            "candidate_score": candidate.get("candidate_score"),
            "content": candidate.get("content", ""),
            "diff": diff_summary,
            "blocks": blocks,
            "events": events,
            "latest_version_meta": latest_version,
            "review_draft": draft,
            "review_drafts": draft_all,
            "review_conflicts": conflicts,
        }

    def _candidate_blocks(self, candidate_id: str) -> dict[str, Any]:
        candidate = self.load_candidate(candidate_id)
        file_rel = candidate["file"]
        workspace_path = self.workspace_file(file_rel)
        baseline = workspace_path.read_text(encoding="utf-8") if workspace_path.exists() else ""
        candidate_text = candidate.get("content", "")
        base_lines = baseline.splitlines()
        cand_lines = candidate_text.splitlines()
        matcher = SequenceMatcher(None, base_lines, cand_lines)
        blocks = []
        idx = 0
        for tag, a0, a1, b0, b1 in matcher.get_opcodes():
            if tag == "equal":
                continue
            idx += 1
            blocks.append(
                {
                    "index": idx,
                    "tag": tag,
                    "a_range": [a0, a1],
                    "b_range": [b0, b1],
                    "removed_count": max(0, a1 - a0),
                    "added_count": max(0, b1 - b0),
                    "header": f"{tag} a[{a0}:{a1}] b[{b0}:{b1}]",
                }
            )
        return {
            "file": file_rel,
            "baseline": baseline,
            "candidate": candidate_text,
            "base_lines": base_lines,
            "cand_lines": cand_lines,
            "blocks": blocks,
            "candidate_id": candidate_id,
        }

    def candidate_blocks(self, candidate_id: str) -> list[dict[str, Any]]:
        return self._candidate_blocks(candidate_id)["blocks"]

    def apply_selected_blocks(self, candidate_id: str, accepted_indices: list[int]) -> dict[str, Any]:
        payload = self._candidate_blocks(candidate_id)
        file_rel = payload["file"]
        base_lines = payload["base_lines"]
        cand_lines = payload["cand_lines"]
        matcher = SequenceMatcher(None, base_lines, cand_lines)
        accepted_set = {int(x) for x in accepted_indices}
        out_lines: list[str] = []
        block_idx = 0
        for tag, a0, a1, b0, b1 in matcher.get_opcodes():
            if tag == "equal":
                out_lines.extend(base_lines[a0:a1])
                continue
            block_idx += 1
            accepted = block_idx in accepted_set
            if accepted:
                out_lines.extend(cand_lines[b0:b1])
            else:
                out_lines.extend(base_lines[a0:a1])
        merged_text = "\n".join(out_lines)
        if payload["candidate"].endswith("\n"):
            merged_text = merged_text + ("\n" if not merged_text.endswith("\n") else "")
        previous_version = self._snapshot_current(file_rel, reason=f"hunk_review:{candidate_id}")
        self.workspace_file(file_rel).write_text(merged_text, encoding="utf-8")
        self._state["history"].append(
            {
                "type": "hunk_apply",
                "candidate_id": candidate_id,
                "file": file_rel,
                "accepted_indices": sorted(accepted_set),
                "previous_version": previous_version,
                "at": datetime.utcnow().isoformat(),
            }
        )
        self._state.get("review_drafts", {}).pop(candidate_id, None)
        self._save_state()
        return {
            "file": file_rel,
            "candidate_id": candidate_id,
            "accepted_indices": sorted(accepted_set),
            "previous_version": previous_version,
            "applied_blocks": len(accepted_set),
            "total_blocks": len(payload["blocks"]),
        }

    def get_review_draft(self, candidate_id: str) -> dict[str, Any]:
        bucket = self._draft_bucket(candidate_id)
        by_reviewer = bucket.get("by_reviewer", {})
        if not by_reviewer:
            return {
                "candidate_id": candidate_id,
                "reviewer": "",
                "decisions": {},
                "updated_at": None,
            }
        draft = sorted(
            by_reviewer.values(),
            key=lambda x: str(x.get("updated_at") or ""),
            reverse=True,
        )[0]
        return {
            "candidate_id": candidate_id,
            "reviewer": draft.get("reviewer", ""),
            "decisions": draft.get("decisions", {}),
            "updated_at": draft.get("updated_at"),
        }

    def save_review_draft(
        self,
        candidate_id: str,
        *,
        reviewer: str = "",
        decisions: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        self.load_candidate(candidate_id)
        bucket = self._draft_bucket(candidate_id)
        by_reviewer = bucket.setdefault("by_reviewer", {})
        normalized_reviewer = str(reviewer or "").strip() or "anonymous"
        normalized: dict[str, str] = {}
        for key, value in (decisions or {}).items():
            decision = str(value).lower()
            if decision not in {"accepted", "rejected"}:
                continue
            normalized[str(int(key))] = decision
        draft = {
            "candidate_id": candidate_id,
            "reviewer": normalized_reviewer,
            "decisions": normalized,
            "updated_at": datetime.utcnow().isoformat(),
        }
        by_reviewer[normalized_reviewer] = draft
        self._state["history"].append(
            {
                "type": "hunk_review_draft_saved",
                "candidate_id": candidate_id,
                "reviewer": draft["reviewer"],
                "decision_count": len(normalized),
                "at": draft["updated_at"],
            }
        )
        self._save_state()
        return draft

    def clear_review_draft(self, candidate_id: str, reviewer: str | None = None) -> dict[str, Any]:
        self.load_candidate(candidate_id)
        drafts = self._state.setdefault("review_drafts", {})
        bucket = self._draft_bucket(candidate_id)
        by_reviewer = bucket.setdefault("by_reviewer", {})
        cleared_reviewer = str(reviewer or "").strip()
        if cleared_reviewer:
            removed = by_reviewer.pop(cleared_reviewer, None)
            if not by_reviewer:
                drafts.pop(candidate_id, None)
        else:
            removed = drafts.pop(candidate_id, None)
        now = datetime.utcnow().isoformat()
        self._state["history"].append(
            {
                "type": "hunk_review_draft_cleared",
                "candidate_id": candidate_id,
                "reviewer": cleared_reviewer or None,
                "had_draft": removed is not None,
                "at": now,
            }
        )
        self._save_state()
        return {
            "candidate_id": candidate_id,
            "cleared": removed is not None,
            "reviewer": cleared_reviewer or None,
            "updated_at": now,
        }

    def list_review_drafts(self, candidate_id: str) -> list[dict[str, Any]]:
        self.load_candidate(candidate_id)
        bucket = self._draft_bucket(candidate_id)
        by_reviewer = bucket.get("by_reviewer", {})
        items = []
        for reviewer, draft in by_reviewer.items():
            items.append(
                {
                    "candidate_id": candidate_id,
                    "reviewer": reviewer,
                    "decisions": draft.get("decisions", {}),
                    "updated_at": draft.get("updated_at"),
                }
            )
        items.sort(key=lambda x: str(x.get("updated_at") or ""), reverse=True)
        return items

    def review_conflicts(self, candidate_id: str) -> dict[str, Any]:
        blocks = self.candidate_blocks(candidate_id)
        drafts = self.list_review_drafts(candidate_id)
        by_hunk: dict[str, dict[str, Any]] = {}
        for block in blocks:
            idx = str(block["index"])
            by_hunk[idx] = {
                "index": block["index"],
                "header": block["header"],
                "accepted": [],
                "rejected": [],
                "status": "no_votes",
            }
        for draft in drafts:
            reviewer = draft["reviewer"]
            for idx, decision in (draft.get("decisions") or {}).items():
                h = by_hunk.get(str(idx))
                if h is None:
                    continue
                if decision == "accepted":
                    h["accepted"].append(reviewer)
                elif decision == "rejected":
                    h["rejected"].append(reviewer)
        conflict_count = 0
        consensus_count = 0
        no_vote_count = 0
        for idx, h in by_hunk.items():
            has_accept = len(h["accepted"]) > 0
            has_reject = len(h["rejected"]) > 0
            if has_accept and has_reject:
                h["status"] = "conflict"
                conflict_count += 1
            elif has_accept or has_reject:
                h["status"] = "consensus"
                consensus_count += 1
            else:
                h["status"] = "no_votes"
                no_vote_count += 1
        
        hunks_list = [by_hunk[str(block["index"])] for block in blocks]
        
        return {
            "candidate_id": candidate_id,
            "reviewer_count": len(drafts),
            "hunks": hunks_list,
            "conflict_count": conflict_count,
            "consensus_count": consensus_count,
            "no_vote_count": no_vote_count,
        }

    def generate_review_conclusion(
        self,
        candidate_id: str,
        *,
        strategy: str = "majority",
        min_votes: int = 1,
    ) -> dict[str, Any]:
        if strategy != "majority":
            raise ValueError("Only majority strategy is supported.")
        conflicts = self.review_conflicts(candidate_id)
        accepted_indices: list[int] = []
        rejected_indices: list[int] = []
        unresolved_indices: list[int] = []

        # Build map of hunk index to conflict data
        hunk_map = {str(h["index"]): h for h in conflicts.get("hunks", [])}

        # We need to iterate over all blocks to ensure we cover everything
        blocks = self.candidate_blocks(candidate_id)

        for block in blocks:
            idx = block["index"]
            h = hunk_map.get(str(idx))

            if not h:
                unresolved_indices.append(idx)
                continue

            accept_votes = len(h.get("accepted", []))
            reject_votes = len(h.get("rejected", []))
            total_votes = accept_votes + reject_votes

            if total_votes < max(1, int(min_votes)):
                unresolved_indices.append(idx)
                continue

            if accept_votes > reject_votes:
                accepted_indices.append(idx)
            elif reject_votes > accept_votes:
                rejected_indices.append(idx)
            else:
                # Tie
                unresolved_indices.append(idx)

        conclusion = {
            "candidate_id": candidate_id,
            "strategy": strategy,
            "min_votes": max(1, int(min_votes)),
            "accepted_indices": sorted(accepted_indices),
            "rejected_indices": sorted(rejected_indices),
            "unresolved_indices": sorted(unresolved_indices),
            "generated_at": datetime.utcnow().isoformat(),
        }

        self._state["history"].append(
            {
                "type": "hunk_review_conclusion_generated",
                "candidate_id": candidate_id,
                "strategy": strategy,
                "min_votes": conclusion["min_votes"],
                "accepted_count": len(accepted_indices),
                "rejected_count": len(rejected_indices),
                "unresolved_count": len(unresolved_indices),
                "at": conclusion["generated_at"],
            }
        )
        self._save_state()
        return conclusion


