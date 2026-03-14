"""Prompt manager for loading and formatting prompt templates."""

import asyncio
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent

logger = logging.getLogger(__name__)


class PromptFileHandler(FileSystemEventHandler):
    """Handler for prompt file changes."""
    
    def __init__(self, manager: "PromptManager"):
        self.manager = manager
    
    def on_modified(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith('.md'):
            self.manager._reload_template(Path(event.src_path))
    
    def on_created(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith('.md'):
            self.manager._reload_template(Path(event.src_path))


class PromptManager:
    """
    Manages prompt templates from the templates/prompts directory.
    Supports hot-reloading of templates when files change.
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
        
        # Hot reload support
        self._observer: Observer | None = None
        self._change_callbacks: List[Callable[[str, str], None]] = []
        self._start_watching()

    def _start_watching(self):
        """Start watching for file changes."""
        if not self.templates_dir.exists():
            return
        
        try:
            self._observer = Observer()
            handler = PromptFileHandler(self)
            self._observer.schedule(handler, str(self.templates_dir), recursive=False)
            self._observer.start()
            logger.info("Started watching prompt templates directory: %s", self.templates_dir)
        except Exception as e:
            logger.error("Failed to start file watcher: %s", e)

    def stop_watching(self):
        """Stop watching for file changes."""
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
            logger.info("Stopped watching prompt templates directory")

    def _load_templates(self):
        """Load all prompt templates from the templates directory."""
        if not self.templates_dir.exists():
            return

        # Load MD templates
        for file_path in self.templates_dir.glob("*.md"):
            self._load_single_template(file_path)

    def _load_single_template(self, file_path: Path) -> bool:
        """Load a single template file.
        
        Args:
            file_path: Path to the template file.
            
        Returns:
            True if loaded successfully, False otherwise.
        """
        try:
            content = file_path.read_text(encoding="utf-8")
            template_name = file_path.stem.lower()
            
            # Extract template content from the code block
            template_content = self._extract_template_content(content)
            
            self.templates[template_name] = {
                "name": file_path.stem,
                "template": template_content
            }
            logger.debug("Loaded template: %s", template_name)
            return True
        except (IOError, Exception) as e:
            logger.error("Failed to load template %s: %s", file_path, e)
            return False

    def _reload_template(self, file_path: Path):
        """Reload a single template when file changes.
        
        Args:
            file_path: Path to the changed template file.
        """
        template_name = file_path.stem.lower()
        old_content = self.templates.get(template_name, {}).get("template", "")
        
        if self._load_single_template(file_path):
            new_content = self.templates[template_name]["template"]
            logger.info("Hot-reloaded template: %s", template_name)
            
            # Notify callbacks
            for callback in self._change_callbacks:
                try:
                    callback(template_name, new_content)
                except Exception as e:
                    logger.error("Error in change callback: %s", e)

    def _extract_template_content(self, content: str) -> str:
        """Extract template content from markdown code block.
        
        Args:
            content: Raw file content.
            
        Returns:
            Extracted template content.
        """
        if "```" in content:
            start = content.find("```") + 3
            end = content.rfind("```")
            if start < end:
                return content[start:end].strip()
        return content.strip()

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
        logger.info("Saved template: %s", template_name)

    def add_change_callback(self, callback: Callable[[str, str], None]):
        """Add a callback to be called when a template changes.
        
        Args:
            callback: Function to call with (template_name, new_content) when a template changes.
        """
        self._change_callbacks.append(callback)

    def remove_change_callback(self, callback: Callable[[str, str], None]):
        """Remove a change callback.
        
        Args:
            callback: The callback function to remove.
        """
        if callback in self._change_callbacks:
            self._change_callbacks.remove(callback)

    def list_templates(self) -> List[str]:
        """List all available template names.
        
        Returns:
            List of template names.
        """
        return list(self.templates.keys())
