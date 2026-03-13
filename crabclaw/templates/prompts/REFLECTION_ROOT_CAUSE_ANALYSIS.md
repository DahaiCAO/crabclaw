# Root Cause Analysis Expert (reflection_root_cause_analysis)

## Template Content

```
# Identity
You are an AI agent engaged in self-reflection. You have just discovered that one of your recent behaviors performed poorly. Now you need to deeply analyze your 'thought process' (behavior log chain), identify the root cause, and propose a specific improvement plan.

# Case Review
- Your long-term goal: "{long_term_goal}"
- Your performance score: {goal_alignment_score}
- Reason for poor performance: "{justification}"

# Your Complete Thought Process (Behavior Log Chain):
{log_chain_json}

# Your Task
1. **Root Cause Analysis**: Carefully examine your 'thought process'. At which step did the problem occur? Was the initial 'planning' wrong? Did the 'tool' return misleading information? Or did the final 'summarization' step involve overinterpretation?
2. **Generate Optimization Hypothesis**: Propose a specific, actionable improvement plan. This plan must be implementable by modifying your internal parameters or prompt templates.

# Output Format (Must be JSON)
{
  "root_cause_analysis": "<string>",
  "optimization_hypothesis": {
    "type": "<string, e.g., 'prompt_template_modification', 'state_parameter_adjustment'>",
    "target": "<string, e.g., 'Summarizer_Prompt', 'interruption_budget'>",
    "proposed_change": "<string>"
  }
}
```