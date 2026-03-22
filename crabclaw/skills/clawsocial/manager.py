"""
ClawSocial skill manager for Crabclaw.

Registers all ClawSocial tools with the tool registry.
"""
import logging
from typing import TYPE_CHECKING

from .scripts.registry import RegistryTool, RegistryListTool, ProfileUpdateTool
from .scripts.private_chat import PrivateChatSendTool, PrivateChatHistoryTool
from crabclaw.skills.clawsocial.scripts.group_chat import (
    GroupCreateTool, GroupJoinTool, GroupLeaveTool, GroupSendTool, GroupHistoryTool, GroupListTool
)
from crabclaw.skills.clawsocial.scripts.group_admin import (
    GroupGrantAdminTool, GroupRevokeAdminTool, GroupRemoveMemberTool, GroupSetAnnouncementTool, GroupMembersTool
)
from crabclaw.skills.clawsocial.scripts.contacts import (
    ContactsAddTool, ContactsRemoveTool, ContactsListTool
)

if TYPE_CHECKING:
    from crabclaw.agent.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


def register_clawsocial_tools(tool_registry: "ToolRegistry"):
    """Register all ClawSocial tools with the tool registry."""
    logger.info("Registering ClawSocial tools...")
    
    # Registry tools
    tool_registry.register(RegistryTool())
    logger.info("  - Registered tool: clawsocial_register")
    tool_registry.register(ProfileUpdateTool())
    logger.info("  - Registered tool: clawsocial_profile_update")
    tool_registry.register(RegistryListTool())
    logger.info("  - Registered tool: clawsocial_register_list")
    
    # Private chat tools
    tool_registry.register(PrivateChatSendTool())
    logger.info("  - Registered tool: clawsocial_private_chat_send")
    tool_registry.register(PrivateChatHistoryTool())
    logger.info("  - Registered tool: clawsocial_private_chat_history")
    
    # Group chat tools
    tool_registry.register(GroupCreateTool())
    logger.info("  - Registered tool: clawsocial_group_create")
    tool_registry.register(GroupJoinTool())
    logger.info("  - Registered tool: clawsocial_group_join")
    tool_registry.register(GroupLeaveTool())
    logger.info("  - Registered tool: clawsocial_group_leave")
    tool_registry.register(GroupSendTool())
    logger.info("  - Registered tool: clawsocial_group_send")
    tool_registry.register(GroupHistoryTool())
    logger.info("  - Registered tool: clawsocial_group_history")
    tool_registry.register(GroupListTool())
    logger.info("  - Registered tool: clawsocial_group_list")
    
    # Group admin tools
    tool_registry.register(GroupGrantAdminTool())
    logger.info("  - Registered tool: clawsocial_group_grant_admin")
    tool_registry.register(GroupRevokeAdminTool())
    logger.info("  - Registered tool: clawsocial_group_revoke_admin")
    tool_registry.register(GroupRemoveMemberTool())
    logger.info("  - Registered tool: clawsocial_group_remove_member")
    tool_registry.register(GroupSetAnnouncementTool())
    logger.info("  - Registered tool: clawsocial_group_set_announcement")
    tool_registry.register(GroupMembersTool())
    logger.info("  - Registered tool: clawsocial_group_members")
    
    # Contacts tools
    tool_registry.register(ContactsAddTool())
    logger.info("  - Registered tool: clawsocial_contacts_add")
    tool_registry.register(ContactsRemoveTool())
    logger.info("  - Registered tool: clawsocial_contacts_remove")
    tool_registry.register(ContactsListTool())
    logger.info("  - Registered tool: clawsocial_contacts_list")
    
    logger.info("ClawSocial tools registered successfully")
