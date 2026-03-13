#!/usr/bin/env python3
"""Test script to verify prompt files are correctly copied and loaded."""

import tempfile
from pathlib import Path

from crabclaw.utils.helpers import sync_workspace_templates
from crabclaw.templates.manager import PromptManager

def test_sync_prompts():
    """Test that prompt files are synced to workspace/prompts."""
    with tempfile.TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir)
        
        # Sync templates
        added_files = sync_workspace_templates(workspace, silent=True)
        print(f"Added files: {added_files}")
        
        # Check if prompts directory was created
        prompts_dir = workspace / "prompts"
        print(f"Prompts directory exists: {prompts_dir.exists()}")
        
        # Check if prompt files were copied
        prompt_files = list(prompts_dir.glob("*.md"))
        print(f"Prompt files in workspace/prompts: {[f.name for f in prompt_files]}")
        
        # Test PromptManager loading
        prompt_manager = PromptManager(prompts_dir)
        print(f"Loaded templates: {list(prompt_manager.templates.keys())}")
        
        # Test if specific templates are loaded
        test_templates = [
            "proactive_selector_scorer",
            "reflection_goal_oracle",
            "reflection_root_cause_analysis",
            "subagent_researcher"
        ]
        
        for template_name in test_templates:
            template = prompt_manager.get_template(template_name)
            print(f"Template {template_name} loaded: {bool(template)}")
            if template:
                print(f"  Template length: {len(template)}")

if __name__ == "__main__":
    test_sync_prompts()
