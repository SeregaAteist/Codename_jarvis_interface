def test_list_profiles():
    from modules.rafail.core.profile_manager import ProfileManager

    pm = ProfileManager()
    profiles = pm.list_profiles()
    assert isinstance(profiles, list)


def test_load_lk_energy():
    from modules.rafail.core.profile_manager import ProfileManager

    pm = ProfileManager()
    profile = pm.load("lk_energy")
    assert profile.name == "LK Energy Group"
    assert profile.active_role == "trainee"
