"""conftest: 共享 fixture 与测试用 profile。"""
import pytest
from anp_mcp.config import ControllerProfile

SH = ControllerProfile(name="sh", base_url="https://sh.test", username="admin",
                       password_md5="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", verify_ssl=False,
                       timeout=5.0)
BJ = ControllerProfile(name="bj", base_url="https://bj.test", username="ops",
                       password_md5="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb", verify_ssl=False,
                       timeout=5.0)


@pytest.fixture
def two_profiles():
    return [SH, BJ], "sh"
