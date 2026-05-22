from unittest.mock import MagicMock, patch

import pytest

from app.utils.sandbox import (
    SandboxExecutionError,
    SandboxManager,
    SandboxResult,
    get_sandbox_manager,
)


class TestSandboxExecutionError:
    def test_is_exception(self):
        assert issubclass(SandboxExecutionError, Exception)


class TestSandboxResult:
    def test_attributes(self):
        result = SandboxResult(success=True, output="test", execution_id="e1")
        assert result.success is True
        assert result.output == "test"
        assert result.execution_id == "e1"


class TestSandboxManager:
    @pytest.mark.asyncio
    async def test_execute_sandbox_disabled(self):
        from app.config.settings import get_settings

        test_settings = get_settings()
        test_settings.sandbox_enabled = False
        sm = SandboxManager()
        sm.settings = test_settings
        result = await sm.execute("agent-1", "print(1)")
        assert result.success is True
        assert result.output == "print(1)"
        assert isinstance(result.execution_id, str)

    @pytest.mark.asyncio
    async def test_execute_import_error(self):
        sm = SandboxManager()
        with (
            patch.object(sm.settings, "sandbox_enabled", True),
            patch.dict("sys.modules", {"docker": None}),
        ):
            result = await sm.execute("agent-1", "print(1)")
            assert result.success is True
            assert result.output == "print(1)"

    @pytest.mark.asyncio
    async def test_execute_docker_success(self):
        sm = SandboxManager()
        mock_container = MagicMock()
        mock_container.wait.return_value = {"StatusCode": 0}
        mock_container.logs.return_value = b"hello from container\n"
        mock_docker = MagicMock()
        mock_docker.from_env.return_value.containers.run.return_value = mock_container

        with (
            patch.object(sm.settings, "sandbox_enabled", True),
            patch.dict("sys.modules", {"docker": mock_docker}),
        ):
            result = await sm.execute("agent-1", "print('hi')", timeout=30)
            assert result.success is True
            assert result.output == "hello from container\n"
            assert isinstance(result.execution_id, str)

    @pytest.mark.asyncio
    async def test_execute_docker_nonzero_exit(self):
        sm = SandboxManager()
        mock_container = MagicMock()
        mock_container.wait.return_value = {"StatusCode": 1}
        mock_container.logs.return_value = b"runtime error\n"
        mock_docker = MagicMock()
        mock_docker.from_env.return_value.containers.run.return_value = mock_container

        with (
            patch.object(sm.settings, "sandbox_enabled", True),
            patch.dict("sys.modules", {"docker": mock_docker}),
        ):
            result = await sm.execute("agent-1", "bad_code()", timeout=30)
            assert result.success is False
            assert "runtime error" in result.output

    @pytest.mark.asyncio
    async def test_execute_docker_error_raises_sandbox_error(self):
        sm = SandboxManager()
        mock_docker = MagicMock()
        mock_docker.from_env.side_effect = Exception("docker daemon unreachable")

        with (
            patch.object(sm.settings, "sandbox_enabled", True),
            patch.dict("sys.modules", {"docker": mock_docker}),
            pytest.raises(SandboxExecutionError, match="Sandbox execution failed"),
        ):
            await sm.execute("agent-1", "print(1)")

    @pytest.mark.asyncio
    async def test_get_sandbox_manager_singleton(self):
        import app.utils.sandbox as sandbox_module

        with patch.object(sandbox_module, "_sandbox_manager", None):
            s1 = get_sandbox_manager()
            s2 = get_sandbox_manager()
            assert s1 is s2
