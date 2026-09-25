"""config.py TDD：三级配置源解析与 fail-fast。"""
import json

import pytest

from anp_mcp.config import load_config, md5_password, ConfigError


def test_md5_password_matches_doc_example():
    assert md5_password("admin") == "21232f297a57a5a743894a0e4a801fc3"


def test_single_env_builds_default_profile():
    profiles, default = load_config(
        {"ANP_BASE_URL": "https://c1", "ANP_USERNAME": "u", "ANP_PASSWORD": "admin"})
    assert default == "default" and len(profiles) == 1
    p = profiles[0]
    assert p.name == "default" and p.base_url == "https://c1"
    assert p.password_md5 == md5_password("admin")


def test_single_env_md5_takes_precedence():
    profiles, _ = load_config({"ANP_BASE_URL": "https://c1", "ANP_USERNAME": "u",
                               "ANP_PASSWORD": "plain", "ANP_PASSWORD_MD5": "ff" * 16})
    assert profiles[0].password_md5 == "ff" * 16


def test_single_env_missing_username_raises():
    with pytest.raises(ConfigError, match="username"):
        load_config({"ANP_BASE_URL": "https://c1", "ANP_PASSWORD": "x"})


def test_single_env_missing_credential_raises():
    with pytest.raises(ConfigError, match="password"):
        load_config({"ANP_BASE_URL": "https://c1", "ANP_USERNAME": "u"})


def test_inline_json_source():
    raw = json.dumps({"default": "sh", "controllers": {
        "sh": {"base_url": "https://a", "username": "u", "password": "p"},
        "bj": {"base_url": "https://b", "username": "v",
               "password_md5": "ee" * 16}}})
    profiles, default = load_config({"ANP_CONTROLLERS": raw})
    assert default == "sh" and {p.name for p in profiles} == {"sh", "bj"}


def test_inline_priority_over_file(tmp_path):
    f = tmp_path / "c.json"
    f.write_text(json.dumps({"controllers": {
        "filectl": {"base_url": "https://f", "username": "u", "password": "p"}}}),
        encoding="utf-8")
    raw = json.dumps({"controllers": {
        "inl": {"base_url": "https://i", "username": "u", "password": "p"}}})
    profiles, _ = load_config({"ANP_CONTROLLERS": raw, "ANP_CONTROLLERS_FILE": str(f)})
    assert {p.name for p in profiles} == {"inl"}


def test_file_source(tmp_path):
    f = tmp_path / "c.json"
    f.write_text(json.dumps({"controllers": {
        "fc": {"base_url": "https://f/", "username": "u", "password": "p"}}}),
        encoding="utf-8")
    profiles, default = load_config({"ANP_CONTROLLERS_FILE": str(f)})
    assert default == "fc" and profiles[0].base_url == "https://f"


def test_file_missing_raises():
    with pytest.raises(ConfigError, match="not found"):
        load_config({"ANP_CONTROLLERS_FILE": "Z:/no/such.json"})


def test_invalid_json_raises():
    with pytest.raises(ConfigError, match="invalid JSON"):
        load_config({"ANP_CONTROLLERS": "{oops"})


def test_default_unknown_raises():
    raw = json.dumps({"default": "nope", "controllers": {
        "sh": {"base_url": "https://a", "username": "u", "password": "p"}}})
    with pytest.raises(ConfigError, match="unknown controller"):
        load_config({"ANP_CONTROLLERS": raw})


def test_single_env_fills_default_when_named_lacks_it():
    raw = json.dumps({"controllers": {
        "sh": {"base_url": "https://a", "username": "u", "password": "p"}}})
    profiles, default = load_config({"ANP_CONTROLLERS": raw, "ANP_BASE_URL": "https://s",
                                     "ANP_USERNAME": "x", "ANP_PASSWORD_MD5": "dd" * 16})
    assert default == "default" and {p.name for p in profiles} == {"sh", "default"}


def test_named_default_key_wins_over_single_env():
    raw = json.dumps({"default": "sh", "controllers": {
        "sh": {"base_url": "https://a", "username": "u", "password": "p"}}})
    profiles, default = load_config({"ANP_CONTROLLERS": raw, "ANP_BASE_URL": "https://s",
                                     "ANP_USERNAME": "x", "ANP_PASSWORD": "y"})
    assert default == "sh" and {p.name for p in profiles} == {"sh"}


def test_verify_ssl_env_string_parsing():
    profiles, _ = load_config({"ANP_BASE_URL": "https://c1", "ANP_USERNAME": "u",
                               "ANP_PASSWORD": "p", "ANP_VERIFY_SSL": "true"})
    assert profiles[0].verify_ssl is True


def test_no_config_at_all_raises():
    with pytest.raises(ConfigError, match="no controller configured"):
        load_config({})
