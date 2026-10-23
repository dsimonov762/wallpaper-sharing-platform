"""Role -> permission mapping and the ownership rule (pure logic, no HTTP)."""

import pytest

from account.domain.exceptions import ForbiddenException
from account.security.authorization import ensure_owner_or_permission, is_owner
from account.security.current_user import CurrentUser
from account.security.permissions import ROLE_PERMISSIONS, Permission, permissions_for


def user(*roles: str, id: str = "u-1") -> CurrentUser:
    return CurrentUser(id=id, email=None, locale=None, roles=frozenset(roles), scope=frozenset())


def test_plain_user_cannot_list_or_delete_users() -> None:
    granted = permissions_for(["USER"])
    assert Permission.PROFILE_WRITE in granted
    assert Permission.USER_LIST not in granted
    assert Permission.USER_DELETE not in granted


def test_admin_can_list_and_delete() -> None:
    granted = permissions_for(["ADMIN"])
    assert {Permission.USER_LIST, Permission.USER_DELETE} <= granted


def test_permissions_are_the_union_of_all_roles() -> None:
    assert permissions_for(["USER", "ADMIN"]) == permissions_for(["ADMIN"])


def test_unknown_roles_grant_nothing() -> None:
    assert permissions_for(["offline_access", "uma_authorization"]) == frozenset()


def test_service_account_gets_internal_call_but_no_admin_powers() -> None:
    granted = permissions_for(["internal"])
    assert Permission.INTERNAL_CALL in granted
    assert Permission.USER_DELETE not in granted


def test_only_internal_role_grants_internal_call() -> None:
    holders = [
        role for role, perms in ROLE_PERMISSIONS.items() if Permission.INTERNAL_CALL in perms
    ]
    assert holders == ["internal"]


def test_current_user_exposes_permissions() -> None:
    assert user("ADMIN").has_permission(Permission.USER_LIST)
    assert not user("USER").has_permission(Permission.USER_LIST)


def test_owner_may_act_on_own_resource() -> None:
    ensure_owner_or_permission(user("USER", id="u-1"), "u-1", Permission.USER_DELETE)


def test_admin_override_applies_to_other_people_resources() -> None:
    ensure_owner_or_permission(user("ADMIN", id="admin-1"), "u-1", Permission.USER_DELETE)


def test_stranger_is_forbidden() -> None:
    with pytest.raises(ForbiddenException):
        ensure_owner_or_permission(user("USER", id="u-2"), "u-1", Permission.USER_DELETE)


def test_ownership_compares_uuid_objects_by_their_text_form() -> None:
    from uuid import uuid4

    identity = uuid4()
    assert is_owner(user("USER", id=str(identity)), identity)
