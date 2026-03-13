"""Prompt manager for loading and formatting prompt templates."""

import re
from pathlib import Path
from typing import Any, Dict


class PromptManager:
    """
    Manages prompt templates from the templates/prompts directory.
    """

    def __init__(self, templates_dir: Path | str):
        """
        Initialize the prompt manager.
        
        Args:
            templates_dir: Path to the directory containing prompt templates.
        """
        self.templates_dir = Path(templates_dir)
        self.templates: Dict[str, Dict[str, str]] = {}
        self._load_templates()

    def _load_templates(self):
        """Load all prompt templates from the templates directory."""
        if not self.templates_dir.exists():
            return

        # Load MD templates
        for file_path in self.templates_dir.glob("*.md"):
            try:
                content = file_path.read_text(encoding="utf-8")
                # Extract template name from filename (without extension)
                template_name = file_path.stem.lower()
                # Extract template content from the code block
                if "```" in content:
                    # Find the code block
                    start = content.find("```") + 3
                    end = content.rfind("```")
                    if start < end:
                        template_content = content[start:end].strip()
                        self.templates[template_name] = {
                            "name": file_path.stem,
                            "template": template_content
                        }
            except (IOError):
                pass

    def get_template(self, template_name: str) -> str | None:
        """
        Get a template by name.
        
        Args:
            template_name: Name of the template (case-insensitive).
            
        Returns:
            The template content, or None if not found.
        """
        template_key = template_name.lower()
        if template_key in self.templates:
            return self.templates[template_key]["template"]
        return None

    def format(self, template_name: str, **kwargs) -> str:
        """
        Format a template with the provided variables.
        
        Args:
            template_name: Name of the template to format.
            **kwargs: Variables to substitute in the template.
            
        Returns:
            The formatted template string.
            
        Raises:
            ValueError: If the template is not found.
        """
        template = self.get_template(template_name)
        if template is None:
            raise ValueError(f"Template '{template_name}' not found")
        
        # Use Python's string formatting
        try:
            return template.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Missing variable in template '{template_name}': {e}")

    def save_template(self, template_name: str, content: str):
        """
        Save a template to the templates directory.
        
        Args:
            template_name: Name of the template.
            content: Content of the template.
        """
        file_path = self.templates_dir / f"{template_name.upper()}.md"
        file_path.write_text(content, encoding="utf-8")
        # Update the in-memory cache
        self.templates[template_name.lower()] = {
            "name": template_name.upper(),
            "template": content
        }
