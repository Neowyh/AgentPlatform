"""Regression tests for provisioner PVC volume support.

The provisioner keeps skills read-only and split into per-user public /
custom / legacy views (hostPath mode), while user-data stays writable and
per-thread. PVC mode collapses skills to a single read-only mount and scopes
user-data by subPath. These tests pin that contract: volume sets, host and
container paths, user isolation, and read/write permissions.
"""


# ── _build_volumes ─────────────────────────────────────────────────────


class TestBuildVolumes:
    """Tests for _build_volumes: PVC vs hostPath selection."""

    def test_hostpath_mode_mounts_three_way_skills_layout(self, provisioner_module):
        """Without a skills PVC, public/custom/legacy views are separate hostPaths."""
        provisioner_module.SKILLS_PVC_NAME = ""
        volumes = provisioner_module._build_volumes("thread-1", user_id="user-7")
        skill_volumes = [v for v in volumes if v.name.startswith("skills-")]
        assert [v.name for v in skill_volumes] == ["skills-public", "skills-custom", "skills-legacy"]
        by_name = {v.name: v for v in skill_volumes}
        assert by_name["skills-public"].host_path.path == "/.deer-flow/skills_view/public"
        assert by_name["skills-public"].host_path.type == "Directory"
        assert by_name["skills-custom"].host_path.path == "/.deer-flow/users/user-7/skills_view/custom"
        assert by_name["skills-legacy"].host_path.path == "/.deer-flow/users/user-7/skills_view/legacy"
        for volume in skill_volumes:
            assert volume.persistent_volume_claim is None

    def test_custom_skills_view_is_user_scoped(self, provisioner_module):
        """Different users resolve different custom-skill host paths."""
        provisioner_module.SKILLS_PVC_NAME = ""
        volumes_a = provisioner_module._build_volumes("thread-1", user_id="user-a")
        volumes_b = provisioner_module._build_volumes("thread-1", user_id="user-b")
        custom_a = next(v for v in volumes_a if v.name == "skills-custom")
        custom_b = next(v for v in volumes_b if v.name == "skills-custom")
        assert custom_a.host_path.path.endswith("/users/user-a/skills_view/custom")
        assert custom_b.host_path.path.endswith("/users/user-b/skills_view/custom")
        assert custom_a.host_path.path != custom_b.host_path.path

    def test_hostpath_userdata_keeps_thread_scoped_path(self, provisioner_module):
        """hostPath user-data stays per-thread and is created on demand."""
        provisioner_module.USERDATA_PVC_NAME = ""
        volumes = provisioner_module._build_volumes("my-thread-42")
        userdata_vol = volumes[-1]
        assert userdata_vol.name == "user-data"
        assert userdata_vol.host_path is not None
        assert userdata_vol.host_path.path == "/.deer-flow/threads/my-thread-42/user-data"
        assert userdata_vol.host_path.type == "DirectoryOrCreate"
        assert userdata_vol.persistent_volume_claim is None

    def test_skills_pvc_overrides_hostpath(self, provisioner_module):
        """When SKILLS_PVC_NAME is set, one read-only skills PVC replaces the views."""
        provisioner_module.SKILLS_PVC_NAME = "my-skills-pvc"
        volumes = provisioner_module._build_volumes("thread-1")
        skills_volumes = [v for v in volumes if v.name.startswith("skills")]
        assert [v.name for v in skills_volumes] == ["skills"]
        skills_vol = skills_volumes[0]
        assert skills_vol.persistent_volume_claim is not None
        assert skills_vol.persistent_volume_claim.claim_name == "my-skills-pvc"
        assert skills_vol.persistent_volume_claim.read_only is True
        assert skills_vol.host_path is None

    def test_userdata_pvc_overrides_hostpath(self, provisioner_module):
        """When USERDATA_PVC_NAME is set, user-data uses the claim."""
        provisioner_module.USERDATA_PVC_NAME = "my-userdata-pvc"
        volumes = provisioner_module._build_volumes("thread-1")
        userdata_vol = volumes[-1]
        assert userdata_vol.name == "user-data"
        assert userdata_vol.persistent_volume_claim is not None
        assert userdata_vol.persistent_volume_claim.claim_name == "my-userdata-pvc"
        assert userdata_vol.host_path is None

    def test_both_pvc_set(self, provisioner_module):
        """When both PVC names are set, both surfaces use claims."""
        provisioner_module.SKILLS_PVC_NAME = "skills-pvc"
        provisioner_module.USERDATA_PVC_NAME = "userdata-pvc"
        volumes = provisioner_module._build_volumes("thread-1")
        assert any(v.persistent_volume_claim is not None and v.name == "skills" for v in volumes)
        assert any(v.persistent_volume_claim is not None and v.name == "user-data" for v in volumes)

    def test_user_data_volume_is_always_present(self, provisioner_module):
        """Every mode ends with exactly one user-data volume."""
        for skills_pvc, userdata_pvc in (("", ""), ("a", ""), ("", "b"), ("a", "b")):
            provisioner_module.SKILLS_PVC_NAME = skills_pvc
            provisioner_module.USERDATA_PVC_NAME = userdata_pvc
            volumes = provisioner_module._build_volumes("t")
            assert [v.name for v in volumes if v.name == "user-data"] == ["user-data"]


# ── _build_volume_mounts ───────────────────────────────────────────────


class TestBuildVolumeMounts:
    """Tests for _build_volume_mounts: mount paths and permission behavior."""

    def test_hostpath_mode_mounts_skill_categories_below_root(self, provisioner_module):
        """hostPath mode exposes public/custom/legacy below the skills root."""
        provisioner_module.SKILLS_PVC_NAME = ""
        mounts = provisioner_module._build_volume_mounts("thread-1")
        skill_mounts = [m for m in mounts if m.name.startswith("skills-")]
        assert [(m.name, m.mount_path, m.read_only) for m in skill_mounts] == [
            ("skills-public", "/mnt/skills/public", True),
            ("skills-custom", "/mnt/skills/custom", True),
            ("skills-legacy", "/mnt/skills/legacy", True),
        ]

    def test_hostpath_user_data_has_no_subpath(self, provisioner_module):
        """hostPath mode should not set sub_path on user-data mount."""
        provisioner_module.USERDATA_PVC_NAME = ""
        mounts = provisioner_module._build_volume_mounts("thread-1")
        userdata_mount = mounts[-1]
        assert userdata_mount.name == "user-data"
        assert userdata_mount.sub_path is None

    def test_pvc_sets_user_scoped_subpath(self, provisioner_module):
        """PVC mode should include user_id in the user-data subPath."""
        provisioner_module.USERDATA_PVC_NAME = "my-pvc"
        mounts = provisioner_module._build_volume_mounts("thread-42", user_id="user-7")
        userdata_mount = mounts[-1]
        assert userdata_mount.sub_path == "deer-flow/users/user-7/threads/thread-42/user-data"

    def test_pvc_defaults_to_default_user_subpath(self, provisioner_module):
        """Older callers should still land under a stable default user namespace."""
        provisioner_module.USERDATA_PVC_NAME = "my-pvc"
        mounts = provisioner_module._build_volume_mounts("thread-42")
        userdata_mount = mounts[-1]
        assert userdata_mount.sub_path == "deer-flow/users/default/threads/thread-42/user-data"

    def test_skills_mounts_are_read_only(self, provisioner_module):
        """Every skills surface is read-only for the sandbox."""
        provisioner_module.SKILLS_PVC_NAME = ""
        mounts = provisioner_module._build_volume_mounts("thread-1")
        assert all(m.read_only is True for m in mounts if m.name.startswith("skills"))

    def test_pvc_skills_mount_is_read_only(self, provisioner_module):
        provisioner_module.SKILLS_PVC_NAME = "skills-pvc"
        mounts = provisioner_module._build_volume_mounts("thread-1")
        skills_mount = next(m for m in mounts if m.name.startswith("skills"))
        assert skills_mount.read_only is True
        assert skills_mount.mount_path == "/mnt/skills"

    def test_userdata_mount_read_write(self, provisioner_module):
        """User-data mount should always be read-write."""
        mounts = provisioner_module._build_volume_mounts("thread-1")
        userdata_mount = mounts[-1]
        assert userdata_mount.name == "user-data"
        assert userdata_mount.read_only is False
        assert userdata_mount.mount_path == "/mnt/user-data"


# ── _build_pod integration ─────────────────────────────────────────────


class TestBuildPodVolumes:
    """Integration: _build_pod should wire volumes and mounts correctly."""

    def test_pod_spec_has_volumes(self, provisioner_module):
        """Pod spec carries the three-way skills views plus user-data."""
        provisioner_module.SKILLS_PVC_NAME = ""
        provisioner_module.USERDATA_PVC_NAME = ""
        pod = provisioner_module._build_pod("sandbox-1", "thread-1")
        volume_names = [v.name for v in pod.spec.volumes]
        assert volume_names == ["skills-public", "skills-custom", "skills-legacy", "user-data"]

    def test_pod_spec_has_volume_mounts(self, provisioner_module):
        """Container mounts mirror the volume list."""
        provisioner_module.SKILLS_PVC_NAME = ""
        provisioner_module.USERDATA_PVC_NAME = ""
        pod = provisioner_module._build_pod("sandbox-1", "thread-1")
        assert [m.name for m in pod.spec.containers[0].volume_mounts] == [
            "skills-public",
            "skills-custom",
            "skills-legacy",
            "user-data",
        ]

    def test_pod_pvc_mode_uses_user_scoped_subpath(self, provisioner_module):
        """Pod should use a user-scoped subPath for PVC user-data."""
        provisioner_module.SKILLS_PVC_NAME = "skills-pvc"
        provisioner_module.USERDATA_PVC_NAME = "userdata-pvc"
        pod = provisioner_module._build_pod("sandbox-1", "thread-1", user_id="user-7")
        assert pod.spec.volumes[0].persistent_volume_claim is not None
        userdata_mount = pod.spec.containers[0].volume_mounts[-1]
        assert userdata_mount.sub_path == "deer-flow/users/user-7/threads/thread-1/user-data"

    def test_pod_user_data_volume_is_thread_scoped(self, provisioner_module):
        """Two pods for different threads never share a user-data hostPath."""
        provisioner_module.SKILLS_PVC_NAME = ""
        provisioner_module.USERDATA_PVC_NAME = ""
        pod_a = provisioner_module._build_pod("sandbox-a", "thread-a")
        pod_b = provisioner_module._build_pod("sandbox-b", "thread-b")
        userdata_a = next(v for v in pod_a.spec.volumes if v.name == "user-data")
        userdata_b = next(v for v in pod_b.spec.volumes if v.name == "user-data")
        assert userdata_a.host_path.path != userdata_b.host_path.path
