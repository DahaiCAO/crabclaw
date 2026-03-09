"""
提示词模板管理器

负责加载、管理和格式化存储在外部文件中的提示词模板。
"""
import json
from pathlib import Path
from typing import Any, Dict


class PromptManager:
    """
    管理提示词模板的加载和使用。
    """

    def __init__(self, templates_dir: Path):
        self.templates_dir = templates_dir
        self.templates: Dict[str, Dict[str, Any]] = {}
        self._load_templates()

    def _load_templates(self):
        """从目录加载所有 .json 格式的提示词模板文件。"""
        if not self.templates_dir.exists():
            self.templates_dir.mkdir(parents=True)
            # logger.warning(f"Prompts directory created at: {self.templates_dir}")
            return

        for file_path in self.templates_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    self.templates.update(json.load(f))
                # logger.info(f"Loaded prompt templates from: {file_path}")
            except (json.JSONDecodeError, IOError) as e:
                # logger.error(f"Failed to load prompt templates from {file_path}: {e}")
                pass

    def get_template(self, name: str) -> str:
        """获取原始的提示词模板字符串。"""
        return self.templates.get(name, {}).get("template", "")

    def format(self, name: str, **kwargs) -> str:
        """格式化一个提示词模板，填充占位符。"""
        template = self.get_template(name)
        if not template:
            # logger.error(f"Prompt template '{name}' not found.")
            return ""
        try:
            return template.format(**kwargs)
        except KeyError as e:
            # logger.error(f"Missing key '{e}' for formatting prompt template '{name}'")
            return ""

    def save_template(self, name: str, template_content: str, file_name: str = "user_prompts.json"):
        """
        保存或更新一个提示词模板到用户自定义文件中。
        这使得 ReflectionEngine 可以永久性地修改提示词。
        """
        file_path = self.templates_dir / file_name
        
        user_templates = {}
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    user_templates = json.load(f)
            except (json.JSONDecodeError, IOError):
                pass # 如果文件损坏，则覆盖

        # 更新或添加模板
        if name not in user_templates:
            user_templates[name] = {}
        user_templates[name]["template"] = template_content
        user_templates[name]["name"] = self.templates.get(name, {}).get("name", name) # 保留原始名称

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(user_templates, f, indent=4, ensure_ascii=False)
            # logger.info(f"Saved prompt template '{name}' to {file_path}")
            # 重新加载以使更改生效
            self.templates.update(user_templates)
        except IOError as e:
            # logger.error(f"Failed to save prompt template to {file_path}: {e}")
            pass
