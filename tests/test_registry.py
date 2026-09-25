"""registry.py TDD：多控制器连接管理。"""
import pytest

from anp_mcp.registry import ControllerRegistry, UnknownControllerError
from conftest import SH, BJ


def make_registry() -> ControllerRegistry:
    return ControllerRegistry([SH, BJ], "sh")


def test_get_default_when_name_omitted():
    assert make_registry().get().profile is SH


def test_get_by_name():
    assert make_registry().get("bj").profile is BJ


def test_unknown_name_lists_available():
    with pytest.raises(UnknownControllerError) as ei:
        make_registry().get("nope")
    assert ei.value.available == ["bj", "sh"]
    assert "nope" in str(ei.value)


def test_connections_reused_and_isolated():
    r = make_registry()
    assert r.get("sh") is r.get("sh")        # 同连接复用
    assert r.get("sh") is not r.get("bj")    # 异连接隔离
    assert r.get("bj").profile is BJ


def test_info_metadata():
    infos = make_registry().info()
    sh = next(i for i in infos if i["name"] == "sh")
    assert sh["is_default"] is True and sh["base_url"] == "https://sh.test"
    assert sh["username"] == "admin"
    bj = next(i for i in infos if i["name"] == "bj")
    assert bj["is_default"] is False


def test_default_must_exist():
    with pytest.raises(ValueError):
        ControllerRegistry([SH], "ghost")


def test_names_sorted():
    assert make_registry().names() == ["bj", "sh"]
