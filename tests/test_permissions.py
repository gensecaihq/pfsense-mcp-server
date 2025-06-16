#!/usr/bin/env python3
"""Test permission system"""

import pytest
from main import PermissionManager, AccessLevel

class TestPermissions:
    def test_permission_hierarchy(self):
        """Test permission hierarchy"""
        # READ_ONLY can't write
        assert not PermissionManager.check_permission(
            AccessLevel.READ_ONLY, 
            AccessLevel.SECURITY_WRITE
        )
        
        # ADMIN can do security operations
        assert PermissionManager.check_permission(
            AccessLevel.ADMIN_WRITE,
            AccessLevel.SECURITY_WRITE
        )
        
        # EMERGENCY can do everything
        assert PermissionManager.check_permission(
            AccessLevel.EMERGENCY_WRITE,
            AccessLevel.READ_ONLY
        )
    
    def test_allowed_tools(self):
        """Test tool access by level"""
        read_only_tools = PermissionManager.get_allowed_tools(AccessLevel.READ_ONLY)
        assert "system_status" in read_only_tools
        assert "block_ip" not in read_only_tools
        
        security_tools = PermissionManager.get_allowed_tools(AccessLevel.SECURITY_WRITE)
        assert "block_ip" in security_tools
        assert "emergency_block_all" not in security_tools
