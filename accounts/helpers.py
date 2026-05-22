def get_user_role(user):
    if not user or not getattr(user, "is_authenticated", False):
        return None

    try:
        profile = user.profile
    except AttributeError:
        return None

    if not profile.is_active or not profile.role or not profile.role.is_active:
        return None

    return profile.role


def has_role(user, role_code):
    role = get_user_role(user)
    return bool(role and role.code == role_code)


def has_any_role(user, role_codes):
    role = get_user_role(user)
    return bool(role and role.code in set(role_codes))


def user_department(user):
    if not user or not getattr(user, "is_authenticated", False):
        return None

    try:
        profile = user.profile
    except AttributeError:
        return None

    if not profile.is_active:
        return None

    return profile.department
