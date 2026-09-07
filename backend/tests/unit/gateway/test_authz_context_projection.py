from types import SimpleNamespace


def test_authenticated_context_projects_cached_department_to_authz_attributes():
    from app.gateway.services import build_run_config, inject_authenticated_user_context

    request = SimpleNamespace(
        state=SimpleNamespace(
            auth_source="session",
            user=SimpleNamespace(id="caller", system_role="user", oauth_provider=None, oauth_id=None),
            _ideer_rbac_user={"user_id": "caller", "role": "user", "department_id": "dept-7"},
        )
    )
    config = build_run_config("thread-authz", None, None)

    inject_authenticated_user_context(config, request)

    assert config["context"]["user_role"] == "user"
    assert config["context"]["authz_attributes"] == {"department_id": "dept-7"}
