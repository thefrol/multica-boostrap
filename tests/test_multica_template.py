#!/usr/bin/env python3
"""Unit tests for bin/multica-template.

Run with:
    python3 -m unittest discover -s tests -v
    # or
    python3 tests/test_multica_template.py -v
"""

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from io import StringIO
from unittest.mock import MagicMock, patch

import yaml

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------

BIN_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "bin", "multica-template")
loader = importlib.machinery.SourceFileLoader("multica_template", BIN_PATH)
mt = loader.load_module()
sys.modules["multica_template"] = mt


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeArgs:
    """Simple namespace for mocking argparse results."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def _make_template(**overrides):
    """Return a minimal valid template dict."""
    tpl = {
        "apiVersion": "multica.template/v1",
        "kind": "WorkspaceTemplate",
        "metadata": {"name": "test-template"},
        "spec": {},
    }
    tpl.update(overrides)
    return tpl


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestValidateKeys(unittest.TestCase):
    def test_valid(self):
        mt._validate_keys({"a": 1, "b": 2}, {"a", "b"}, "root")

    def test_invalid_raises(self):
        with self.assertRaises(ValueError) as ctx:
            mt._validate_keys({"a": 1, "z": 2}, {"a", "b"}, "root")
        self.assertIn("unknown keys", str(ctx.exception))
        self.assertIn("z", str(ctx.exception))

    def test_not_a_dict(self):
        with self.assertRaises(ValueError) as ctx:
            mt._validate_keys([1, 2], {"a"}, "root")
        self.assertIn("must be a mapping", str(ctx.exception))


class TestLoadTemplate(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.template_path = os.path.join(self.tmpdir, "template.yaml")

    def tearDown(self):
        if os.path.isfile(self.template_path):
            os.remove(self.template_path)
        os.rmdir(self.tmpdir)

    def _write(self, data):
        with open(self.template_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f)

    def test_minimal_valid(self):
        self._write(_make_template())
        result = mt.load_template(self.tmpdir)
        self.assertEqual(result["kind"], "WorkspaceTemplate")

    def test_missing_file(self):
        empty_dir = tempfile.mkdtemp()
        try:
            with self.assertRaises(ValueError) as ctx:
                mt.load_template(empty_dir)
            self.assertIn("not found", str(ctx.exception))
        finally:
            os.rmdir(empty_dir)

    def test_invalid_api_version(self):
        self._write(_make_template(apiVersion="v2"))
        with self.assertRaises(ValueError) as ctx:
            mt.load_template(self.tmpdir)
        self.assertIn("apiVersion", str(ctx.exception))

    def test_invalid_kind(self):
        self._write(_make_template(kind="Foo"))
        with self.assertRaises(ValueError) as ctx:
            mt.load_template(self.tmpdir)
        self.assertIn("kind", str(ctx.exception))

    def test_missing_metadata_name(self):
        self._write(_make_template(metadata={}))
        with self.assertRaises(ValueError) as ctx:
            mt.load_template(self.tmpdir)
        self.assertIn("metadata.name", str(ctx.exception))

    def test_unknown_top_level_key(self):
        self._write(_make_template(extra=1))
        with self.assertRaises(ValueError) as ctx:
            mt.load_template(self.tmpdir)
        self.assertIn("unknown keys", str(ctx.exception))

    def test_unknown_spec_key(self):
        tpl = _make_template()
        tpl["spec"]["unknown"] = 1
        self._write(tpl)
        with self.assertRaises(ValueError) as ctx:
            mt.load_template(self.tmpdir)
        self.assertIn("spec", str(ctx.exception))

    def test_label_without_name(self):
        tpl = _make_template()
        tpl["spec"]["labels"] = [{"color": "#fff"}]
        self._write(tpl)
        with self.assertRaises(ValueError) as ctx:
            mt.load_template(self.tmpdir)
        self.assertIn("labels[0].name", str(ctx.exception))

    def test_squad_without_leader(self):
        tpl = _make_template()
        tpl["spec"]["squads"] = [{"name": "s1"}]
        self._write(tpl)
        with self.assertRaises(ValueError) as ctx:
            mt.load_template(self.tmpdir)
        self.assertIn("leader", str(ctx.exception))

    def test_autopilot_without_agent(self):
        tpl = _make_template()
        tpl["spec"]["autopilots"] = [{"name": "ap1"}]
        self._write(tpl)
        with self.assertRaises(ValueError) as ctx:
            mt.load_template(self.tmpdir)
        self.assertIn("agent", str(ctx.exception))

    def test_full_spec_passes(self):
        tpl = _make_template(spec={
            "targetWorkspace": {"id": "ws-id", "name": "ws", "create": True, "slug": "ws"},
            "workspace": {"name": "W", "description": "D", "issuePrefix": "PRE"},
            "labels": [{"name": "bug", "color": "#f00"}],
            "skills": [
                {
                    "name": "sk1",
                    "description": "desc",
                    "content": "content",
                    "files": [{"path": "SKILL.md", "content": "hi"}],
                }
            ],
            "agents": [
                {
                    "name": "ag1",
                    "description": "d",
                    "runtimeId": "r1",
                    "model": "m",
                    "instructions": "i",
                    "visibility": "workspace",
                    "maxConcurrentTasks": 3,
                    "customArgs": ["--foo"],
                    "customEnv": {"K": "V"},
                    "skills": ["sk1"],
                }
            ],
            "squads": [{"name": "sq1", "description": "d", "leader": "ag1"}],
            "autopilots": [
                {
                    "name": "ap1",
                    "title": "T",
                    "agent": "ag1",
                    "mode": "create_issue",
                    "description": "d",
                    "priority": "high",
                    "status": "active",
                }
            ],
        })
        self._write(tpl)
        result = mt.load_template(self.tmpdir)
        self.assertEqual(result["spec"]["agents"][0]["name"], "ag1")


class TestFlag(unittest.TestCase):
    def test_none_returns_empty(self):
        self.assertEqual(mt._flag("--key", None), [])

    def test_string(self):
        self.assertEqual(mt._flag("--key", "val"), ["--key", "val"])

    def test_list_serialises_json(self):
        self.assertEqual(mt._flag("--key", ["a", "b"]), ["--key", '["a", "b"]'])

    def test_dict_serialises_json(self):
        self.assertEqual(mt._flag("--key", {"a": 1}), ["--key", '{"a": 1}'])


class TestGetId(unittest.TestCase):
    def test_dict_with_id(self):
        self.assertEqual(mt._get_id({"id": "abc"}), "abc")

    def test_dict_without_id(self):
        self.assertIsNone(mt._get_id({"name": "x"}))

    def test_non_dict(self):
        self.assertIsNone(mt._get_id("abc"))


class TestSlugify(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(mt._slugify("Hello World"), "hello-world")

    def test_multiple_spaces(self):
        self.assertEqual(mt._slugify("a  b"), "a-b")

    def test_special_chars(self):
        self.assertEqual(mt._slugify("Foo@Bar#Baz"), "foo-bar-baz")

    def test_leading_trailing(self):
        self.assertEqual(mt._slugify("-hello-"), "hello")

    def test_empty_fallback(self):
        self.assertEqual(mt._slugify("!!!"), "workspace")


class TestResolveWorkspace(unittest.TestCase):
    def test_cli_workspace_id_wins(self):
        args = FakeArgs(workspace_id="cli-id")
        tpl = _make_template(spec={"targetWorkspace": {"id": "tpl-id"}})
        result = mt.resolve_workspace(args, tpl)
        self.assertEqual(result, "cli-id")

    @patch("multica_template._parse_workspace_list_table", return_value={"ws1": "uuid1"})
    def test_cli_workspace_name(self, mock_list):
        args = FakeArgs(workspace_name="ws1")
        result = mt.resolve_workspace(args, _make_template())
        self.assertEqual(result, "uuid1")

    @patch("multica_template._parse_workspace_list_table", return_value={})
    @patch("multica_template.create_workspace", return_value="new-id")
    def test_create_workspace_from_cli(self, mock_create, mock_list):
        args = FakeArgs(workspace_name="new", create_workspace=True)
        result = mt.resolve_workspace(args, _make_template())
        self.assertEqual(result, "new-id")
        mock_create.assert_called_once()

    @patch("multica_template._parse_workspace_list_table", return_value={})
    def test_missing_workspace_fails(self, mock_list):
        args = FakeArgs(workspace_name="missing")
        with self.assertRaises(SystemExit):
            mt.resolve_workspace(args, _make_template())

    def test_template_id(self):
        args = FakeArgs()
        tpl = _make_template(spec={"targetWorkspace": {"id": "tpl-id"}})
        result = mt.resolve_workspace(args, tpl)
        self.assertEqual(result, "tpl-id")

    @patch("multica_template._parse_workspace_list_table", return_value={"ws2": "uuid2"})
    def test_template_name(self, mock_list):
        args = FakeArgs()
        tpl = _make_template(spec={"targetWorkspace": {"name": "ws2"}})
        result = mt.resolve_workspace(args, tpl)
        self.assertEqual(result, "uuid2")

    @patch.dict(os.environ, {"MULTICA_WORKSPACE_ID": "env-id"}, clear=True)
    def test_env_var(self):
        args = FakeArgs()
        result = mt.resolve_workspace(args, _make_template())
        self.assertEqual(result, "env-id")

    def test_default_test_workspace(self):
        args = FakeArgs()
        # Ensure env var is not set
        env = os.environ.copy()
        env.pop("MULTICA_WORKSPACE_ID", None)
        with patch.dict(os.environ, env, clear=True):
            result = mt.resolve_workspace(args, _make_template())
        self.assertEqual(result, mt.DEFAULT_TEST_WORKSPACE)

    @patch("multica_template._parse_workspace_list_table", return_value={})
    def test_dry_run_returns_dry_run_id(self, mock_list):
        args = FakeArgs(workspace_name="new", create_workspace=True)
        result = mt.resolve_workspace(args, _make_template(), dry_run=True)
        self.assertEqual(result, mt.DRY_RUN_ID)


class TestResolveWorkspaceSimple(unittest.TestCase):
    def test_id(self):
        args = FakeArgs(workspace_id="id1")
        self.assertEqual(mt.resolve_workspace_simple(args), "id1")

    @patch("multica_template._parse_workspace_list_table", return_value={"ws": "uid"})
    def test_name(self, mock_list):
        args = FakeArgs(workspace_name="ws")
        self.assertEqual(mt.resolve_workspace_simple(args), "uid")

    @patch("multica_template._parse_workspace_list_table", return_value={})
    def test_missing_name_exits(self, mock_list):
        args = FakeArgs(workspace_name="missing")
        with self.assertRaises(SystemExit):
            mt.resolve_workspace_simple(args)

    @patch.dict(os.environ, {"MULTICA_WORKSPACE_ID": "env"}, clear=True)
    def test_env(self):
        args = FakeArgs()
        self.assertEqual(mt.resolve_workspace_simple(args), "env")

    def test_fallback_none(self):
        args = FakeArgs()
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(mt.resolve_workspace_simple(args))


class TestBuildRegistry(unittest.TestCase):
    @patch("multica_template._run_json")
    def test_dry_run_empty(self, mock_run):
        result = mt.build_registry(workspace_id=mt.DRY_RUN_ID)
        self.assertEqual(result, {})
        mock_run.assert_not_called()

    @patch("multica_template._run_json")
    def test_full_build(self, mock_run):
        mock_run.side_effect = [
            {"id": "ws1", "name": "MyWorkspace"},
            [{"id": "l1", "name": "bug"}],
            [{"id": "s1", "name": "skill1"}],
            [{"id": "a1", "name": "agent1"}],
            [{"id": "sq1", "name": "squad1"}],
            {"autopilots": [{"id": "ap1", "title": "Daily Check"}]},
        ]
        registry = mt.build_registry(workspace_id="ws1")
        self.assertEqual(registry[("workspace", "MyWorkspace")], "ws1")
        self.assertEqual(registry[("label", "bug")], "l1")
        self.assertEqual(registry[("skill", "skill1")], "s1")
        self.assertEqual(registry[("agent", "agent1")], "a1")
        self.assertEqual(registry[("squad", "squad1")], "sq1")
        self.assertEqual(registry[("autopilot", "Daily Check")], "ap1")

    @patch("multica_template._run_json")
    def test_autopilot_list_format(self, mock_run):
        # Some API versions return a plain list
        mock_run.side_effect = [
            {"id": "ws1", "name": "W"},
            [], [], [], [],
            [{"id": "ap1", "title": "T1"}],
        ]
        registry = mt.build_registry(workspace_id="ws1")
        self.assertEqual(registry[("autopilot", "T1")], "ap1")


class TestApplyWorkspace(unittest.TestCase):
    @patch("multica_template._run_cmd")
    def test_noop_when_empty(self, mock_run):
        mt.apply_workspace({}, dry_run=False, workspace_id="ws1")
        mock_run.assert_not_called()

    @patch("multica_template._run_cmd")
    def test_update(self, mock_run):
        spec = {"workspace": {"name": "New Name", "description": "D", "issuePrefix": "PRE"}}
        mt.apply_workspace(spec, dry_run=False, workspace_id="ws1")
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        self.assertIn("workspace", cmd)
        self.assertIn("update", cmd)
        self.assertIn("--name", cmd)
        self.assertIn("New Name", cmd)
        self.assertIn("--issue-prefix", cmd)
        self.assertIn("PRE", cmd)


class TestApplyLabels(unittest.TestCase):
    @patch("multica_template._run_cmd")
    def test_create(self, mock_run):
        mock_run.return_value = {"id": "l1"}
        registry = {}
        spec = {"labels": [{"name": "bug", "color": "#f00"}]}
        mt.apply_labels(spec, registry, dry_run=False, workspace_id="ws1")
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        self.assertIn("label", cmd)
        self.assertIn("create", cmd)
        self.assertEqual(registry[("label", "bug")], "l1")

    @patch("multica_template._run_cmd")
    def test_update(self, mock_run):
        mock_run.return_value = {"id": "l1-updated"}
        registry = {("label", "bug"): "l1"}
        spec = {"labels": [{"name": "bug", "color": "#0f0"}]}
        mt.apply_labels(spec, registry, dry_run=False, workspace_id="ws1")
        cmd = mock_run.call_args[0][0]
        self.assertIn("update", cmd)
        self.assertIn("l1", cmd)
        self.assertEqual(registry[("label", "bug")], "l1-updated")


class TestApplySkills(unittest.TestCase):
    @patch("multica_template._run_cmd")
    def test_create_with_file(self, mock_run):
        mock_run.return_value = {"id": "s1"}
        registry = {}
        spec = {
            "skills": [
                {
                    "name": "sk1",
                    "description": "desc",
                    "content": "c",
                    "files": [{"path": "SKILL.md", "content": "body"}],
                }
            ]
        }
        mt.apply_skills(spec, registry, dry_run=False, workspace_id="ws1")
        self.assertEqual(mock_run.call_count, 2)  # create + file upsert
        self.assertEqual(registry[("skill", "sk1")], "s1")

    @patch("multica_template._run_cmd")
    def test_update(self, mock_run):
        mock_run.return_value = {"id": "s1"}
        registry = {("skill", "sk1"): "s1-old"}
        spec = {"skills": [{"name": "sk1", "description": "new"}]}
        mt.apply_skills(spec, registry, dry_run=False, workspace_id="ws1")
        cmd = mock_run.call_args[0][0]
        self.assertIn("update", cmd)
        self.assertIn("s1-old", cmd)


class TestApplyAgents(unittest.TestCase):
    @patch("multica_template.get_available_runtimes", return_value=[{"id": "r1", "name": "default"}])
    @patch("multica_template._run_cmd")
    def test_create(self, mock_run, mock_runtimes):
        mock_run.return_value = {"id": "a1"}
        registry = {}
        spec = {"agents": [{"name": "ag1", "runtimeId": "r1"}]}
        mt.apply_agents(spec, registry, dry_run=False, workspace_id="ws1")
        cmd = mock_run.call_args[0][0]
        self.assertIn("agent", cmd)
        self.assertIn("create", cmd)
        self.assertEqual(registry[("agent", "ag1")], "a1")

    @patch("multica_template.get_available_runtimes", return_value=[{"id": "r1", "name": "default"}])
    @patch("multica_template._run_cmd")
    def test_create_with_skills(self, mock_run, mock_runtimes):
        mock_run.side_effect = [
            {"id": "a1"},
            None,  # skills set
        ]
        registry = {("skill", "sk1"): "s1"}
        spec = {"agents": [{"name": "ag1", "runtimeId": "r1", "skills": ["sk1"]}]}
        mt.apply_agents(spec, registry, dry_run=False, workspace_id="ws1")
        self.assertEqual(mock_run.call_count, 2)
        skills_cmd = mock_run.call_args_list[1][0][0]
        self.assertIn("skills", skills_cmd)
        self.assertIn("s1", skills_cmd)

    @patch("multica_template.get_available_runtimes", return_value=[{"id": "r1", "name": "default"}])
    @patch("multica_template._run_cmd")
    def test_missing_skill_ref_exits(self, mock_run, mock_runtimes):
        mock_run.return_value = {"id": "a1"}
        registry = {}
        spec = {"agents": [{"name": "ag1", "runtimeId": "r1", "skills": ["missing"]}]}
        with self.assertRaises(SystemExit):
            mt.apply_agents(spec, registry, dry_run=False, workspace_id="ws1")

    @patch("multica_template.get_available_runtimes", return_value=[])
    def test_no_runtimes_exits(self, mock_runtimes):
        registry = {}
        spec = {"agents": [{"name": "ag1"}]}
        with self.assertRaises(SystemExit):
            mt.apply_agents(spec, registry, dry_run=False, workspace_id="ws1")

    @patch("multica_template.get_available_runtimes", return_value=[{"id": "r1", "name": "default"}])
    @patch("multica_template._run_cmd")
    def test_runtime_fallback(self, mock_run, mock_runtimes):
        mock_run.return_value = {"id": "a1"}
        registry = {}
        spec = {"agents": [{"name": "ag1", "runtimeId": "bad-id"}]}
        mt.apply_agents(spec, registry, dry_run=False, workspace_id="ws1")
        cmd = mock_run.call_args[0][0]
        self.assertIn("r1", cmd)


class TestApplySquads(unittest.TestCase):
    @patch("multica_template._run_cmd")
    def test_create(self, mock_run):
        mock_run.return_value = {"id": "sq1"}
        registry = {("agent", "leader1"): "a1"}
        spec = {"squads": [{"name": "squad1", "leader": "leader1"}]}
        mt.apply_squads(spec, registry, dry_run=False, workspace_id="ws1")
        cmd = mock_run.call_args[0][0]
        self.assertIn("squad", cmd)
        self.assertIn("create", cmd)
        self.assertIn("a1", cmd)
        self.assertEqual(registry[("squad", "squad1")], "sq1")

    @patch("multica_template._run_cmd")
    def test_missing_leader_exits(self, mock_run):
        registry = {}
        spec = {"squads": [{"name": "squad1", "leader": "missing"}]}
        with self.assertRaises(SystemExit):
            mt.apply_squads(spec, registry, dry_run=False, workspace_id="ws1")

    @patch("multica_template._run_cmd")
    def test_update(self, mock_run):
        mock_run.return_value = {"id": "sq1"}
        registry = {("agent", "leader1"): "a1", ("squad", "squad1"): "sq1-old"}
        spec = {"squads": [{"name": "squad1", "leader": "leader1"}]}
        mt.apply_squads(spec, registry, dry_run=False, workspace_id="ws1")
        cmd = mock_run.call_args[0][0]
        self.assertIn("update", cmd)
        self.assertIn("sq1-old", cmd)


class TestApplyAutopilots(unittest.TestCase):
    @patch("multica_template._run_cmd")
    def test_create(self, mock_run):
        mock_run.return_value = {"id": "ap1"}
        registry = {("agent", "ag1"): "a1"}
        spec = {"autopilots": [{"name": "ap1", "agent": "ag1", "mode": "create_issue"}]}
        mt.apply_autopilots(spec, registry, dry_run=False, workspace_id="ws1")
        cmd = mock_run.call_args[0][0]
        self.assertIn("autopilot", cmd)
        self.assertIn("create", cmd)
        self.assertIn("a1", cmd)
        self.assertEqual(registry[("autopilot", "ap1")], "ap1")

    @patch("multica_template._run_cmd")
    def test_missing_agent_exits(self, mock_run):
        registry = {}
        spec = {"autopilots": [{"name": "ap1", "agent": "missing", "mode": "run_only"}]}
        with self.assertRaises(SystemExit):
            mt.apply_autopilots(spec, registry, dry_run=False, workspace_id="ws1")

    @patch("multica_template._run_cmd")
    def test_update_uses_title_as_key(self, mock_run):
        mock_run.return_value = {"id": "ap1-new"}
        registry = {("agent", "ag1"): "a1", ("autopilot", "My Title"): "ap1-old"}
        spec = {"autopilots": [{"name": "ap1", "title": "My Title", "agent": "ag1", "mode": "run_only"}]}
        mt.apply_autopilots(spec, registry, dry_run=False, workspace_id="ws1")
        cmd = mock_run.call_args[0][0]
        self.assertIn("update", cmd)
        self.assertIn("ap1-old", cmd)


class TestParseWorkspaceListTable(unittest.TestCase):
    @patch("subprocess.run")
    def test_parse(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="ID\tNAME\nws1\tTeam A\nws2\tTeam B\n",
        )
        result = mt._parse_workspace_list_table()
        self.assertEqual(result, {"Team A": "ws1", "Team B": "ws2"})

    @patch("subprocess.run")
    def test_error_exits(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr="boom")
        with self.assertRaises(SystemExit):
            mt._parse_workspace_list_table()


class TestGithubUrlParsing(unittest.TestCase):
    def test_is_github_url_true(self):
        self.assertTrue(mt.is_github_url("https://github.com/owner/repo"))
        self.assertTrue(mt.is_github_url("http://github.com/owner/repo"))
        self.assertTrue(mt.is_github_url("github.com/owner/repo"))

    def test_is_github_url_false(self):
        self.assertFalse(mt.is_github_url(""))
        self.assertFalse(mt.is_github_url(None))
        self.assertFalse(mt.is_github_url("https://gitlab.com/owner/repo"))

    def test_parse_simple(self):
        result = mt.parse_github_url("github.com/owner/repo")
        self.assertEqual(result["owner"], "owner")
        self.assertEqual(result["repo"], "repo")
        self.assertIsNone(result["path"])
        self.assertIsNone(result["ref"])

    def test_parse_with_path(self):
        result = mt.parse_github_url("github.com/owner/repo/path/to/dir")
        self.assertEqual(result["path"], "path/to/dir")

    def test_parse_tree_url(self):
        result = mt.parse_github_url("https://github.com/owner/repo/tree/main/sub")
        self.assertEqual(result["ref"], "main")
        self.assertEqual(result["path"], "sub")

    def test_parse_blob_url(self):
        result = mt.parse_github_url("https://github.com/owner/repo/blob/v1.0/README.md")
        self.assertEqual(result["ref"], "v1.0")
        self.assertEqual(result["path"], "README.md")

    def test_invalid_raises(self):
        with self.assertRaises(ValueError):
            mt.parse_github_url("https://gitlab.com/owner/repo")


class TestBuildTemplate(unittest.TestCase):
    @patch("multica_template._run_json")
    def test_empty_workspace(self, mock_run):
        mock_run.side_effect = [
            {"id": "ws1", "name": "W", "slug": "w"},
            [], [], [], [], {"autopilots": []},
        ]
        tpl = mt.build_template(workspace_id="ws1")
        self.assertEqual(tpl["apiVersion"], "multica.template/v1")
        self.assertEqual(tpl["kind"], "WorkspaceTemplate")
        self.assertEqual(tpl["metadata"]["name"], "w")
        self.assertIn("spec", tpl)
        self.assertEqual(tpl["spec"], {"workspace": {"name": "W"}})

    @patch("multica_template._run_json")
    def test_with_resources(self, mock_run):
        mock_run.side_effect = [
            # fetch_workspace
            {"id": "ws1", "name": "W", "slug": "w", "description": "Desc", "issue_prefix": "PRE"},
            # fetch_labels
            [{"id": "l1", "name": "bug", "color": "#f00"}],
            # fetch_skills list + detail
            [{"id": "s1", "name": "sk1", "description": "d", "content": "c", "files": [{"path": "SKILL.md", "content": "hi"}]}],
            {"id": "s1", "name": "sk1", "description": "d", "content": "c", "files": [{"path": "SKILL.md", "content": "hi"}]},
            # fetch_agents list + detail
            [{"id": "a1", "name": "ag1", "runtime_id": "r1", "model": "m", "instructions": "i", "visibility": "workspace", "max_concurrent_tasks": 3, "custom_args": ["--x"], "custom_env": {"K": "V"}, "skills": [{"id": "s1"}]}],
            {"id": "a1", "name": "ag1", "runtime_id": "r1", "model": "m", "instructions": "i", "visibility": "workspace", "max_concurrent_tasks": 3, "custom_args": ["--x"], "custom_env": {"K": "V"}, "skills": [{"id": "s1"}]},
            # fetch_squads
            [{"id": "sq1", "name": "sq1", "description": "d", "leader_id": "a1"}],
            # fetch_autopilots list + detail
            {"autopilots": [{"id": "ap1", "title": "Daily", "assignee_id": "a1", "execution_mode": "create_issue", "description": "d", "priority": "high", "status": "active"}]},
            {"autopilot": {"id": "ap1", "title": "Daily", "assignee_id": "a1", "execution_mode": "create_issue", "description": "d", "priority": "high", "status": "active"}},
        ]
        tpl = mt.build_template(workspace_id="ws1")
        spec = tpl["spec"]
        self.assertEqual(spec["workspace"]["name"], "W")
        self.assertEqual(spec["workspace"]["issuePrefix"], "PRE")
        self.assertEqual(spec["labels"][0]["name"], "bug")
        self.assertEqual(spec["skills"][0]["name"], "sk1")
        self.assertEqual(spec["agents"][0]["name"], "ag1")
        self.assertEqual(spec["agents"][0]["skills"], ["sk1"])
        self.assertEqual(spec["squads"][0]["leader"], "ag1")
        self.assertEqual(spec["autopilots"][0]["agent"], "ag1")
        self.assertEqual(spec["autopilots"][0]["mode"], "create_issue")


class TestWriteTemplate(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_writes_yaml(self):
        tpl = _make_template(spec={"workspace": {"name": "W"}})
        path = mt.write_template(tpl, self.tmpdir)
        self.assertTrue(os.path.isfile(path))
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self.assertEqual(data["metadata"]["name"], "test-template")


class TestStrRepresenter(unittest.TestCase):
    def test_multiline_literal(self):
        # The representer is registered globally, so yaml.dump should use | for newlines
        data = {"key": "line1\nline2\n"}
        dumped = yaml.dump(data)
        self.assertIn("|", dumped)

    def test_single_line_plain(self):
        data = {"key": "hello"}
        dumped = yaml.dump(data)
        self.assertNotIn("|", dumped)


class TestRuntimeResolution(unittest.TestCase):
    def test_valid_runtime(self):
        runtimes = [{"id": "r1", "name": "rt1"}]
        agent = {"name": "ag1", "runtimeId": "r1"}
        self.assertEqual(mt._resolve_runtime_id(agent, runtimes), "r1")

    def test_fallback(self):
        runtimes = [{"id": "r1", "name": "rt1", "provider": "p1"}]
        agent = {"name": "ag1", "runtimeId": "bad"}
        self.assertEqual(mt._resolve_runtime_id(agent, runtimes), "r1")

    def test_no_runtime_exits(self):
        with self.assertRaises(SystemExit):
            mt._resolve_runtime_id({"name": "ag1"}, [])


class TestDryRun(unittest.TestCase):
    @patch("multica_template._run_cmd")
    def test_apply_labels_dry_run_prints_command(self, mock_run):
        registry = {}
        spec = {"labels": [{"name": "bug", "color": "#f00"}]}
        mt.apply_labels(spec, registry, dry_run=True, workspace_id="ws1")
        mock_run.assert_called_once()
        _, kwargs = mock_run.call_args
        self.assertTrue(kwargs.get("dry_run"))

    @patch("multica_template._run_cmd")
    def test_apply_agents_dry_run_prints_command(self, mock_run):
        registry = {}
        spec = {"agents": [{"name": "ag1", "runtimeId": "r1"}]}
        with patch("multica_template.get_available_runtimes", return_value=[{"id": "r1"}]):
            mt.apply_agents(spec, registry, dry_run=True, workspace_id="ws1")
        self.assertTrue(mock_run.called)
        _, kwargs = mock_run.call_args
        self.assertTrue(kwargs.get("dry_run"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
