#!/usr/bin/env python3
"""
Debug script to check identity mappings and message routing
"""

import asyncio
from pathlib import Path

from crabclaw.config.loader import load_config
from crabclaw.user.manager import UserManager

async def debug_mappings():
    print("=== Debugging Identity Mappings ===\n")
    
    # Load config
    config = load_config()
    
    # Create user manager
    workspace = Path.home() / ".crabclaw" / "workspace"
    user_manager = UserManager(workspace)
    
    # List all users
    print("1. All Users:")
    users = user_manager.list_users()
    for user in users:
        print(f"   - User ID: {user['user_id']}")
        print(f"     Username: {user['username']}")
        print(f"     Display Name: {user['display_name']}")
        
        # List identity mappings for this user
        mappings = user_manager.list_identity_mappings(user['user_id'])
        if mappings:
            print(f"     Identity Mappings:")
            for mapping in mappings:
                print(f"       - Channel: {mapping['channel']}")
                print(f"         External ID: {mapping['external_id']}")
                print(f"         Mapping ID: {mapping['mapping_id']}")
        else:
            print(f"     No identity mappings found")
        print()
    
    # Test resolving
    print("2. Testing Resolution:")
    for user in users:
        mappings = user_manager.list_identity_mappings(user['user_id'])
        for mapping in mappings:
            resolved = user_manager.resolve_user_by_identity(mapping['channel'], mapping['external_id'])
            print(f"   Resolve {mapping['channel']}:{mapping['external_id']} -> {resolved}")
    
    print("\n=== Debug Complete ===")

if __name__ == "__main__":
    asyncio.run(debug_mappings())
