import uuid

from app.config.settings import get_settings
from app.utils.logging import get_logger

logger = get_logger("sandbox")


class SandboxExecutionError(Exception):
    pass


class SandboxResult:
    def __init__(self, success: bool, output: str, execution_id: str):
        self.success = success
        self.output = output
        self.execution_id = execution_id


class SandboxManager:
    def __init__(self):
        self.settings = get_settings()

    async def execute(
        self,
        agent_name: str,
        code: str,
        timeout: int = 60,
        network_access: bool = True,
    ) -> SandboxResult:
        execution_id = str(uuid.uuid4())

        if not self.settings.sandbox_enabled:
            logger.log_action(
                agent_id=agent_name,
                action="sandbox_execute",
                status="skipped",
                project_id=execution_id,
                details={"reason": "sandbox_disabled"},
            )
            return SandboxResult(success=True, output=code, execution_id=execution_id)

        logger.log_action(
            agent_id=agent_name,
            action="sandbox_execute",
            status="running",
            project_id=execution_id,
        )

        try:
            import docker

            client = docker.from_env()
            container_network = self.settings.sandbox_network if network_access else "none"

            container = client.containers.run(
                image="python:3.13-slim",
                command=["python", "-c", code],
                network=container_network,
                detach=True,
                remove=True,
                mem_limit="512m",
                nano_cpus=int(0.5 * 1e9),
                environment={
                    "AGENT_NAME": agent_name,
                    "EXECUTION_ID": execution_id,
                },
            )

            result = container.wait(timeout=timeout)
            logs = container.logs().decode("utf-8")

            if result["StatusCode"] != 0:
                logger.log_error(
                    agent_id=agent_name,
                    action="sandbox_execute",
                    error=f"Exit code {result['StatusCode']}",
                    project_id=execution_id,
                    details={"logs": logs[:1000]},
                )
                return SandboxResult(success=False, output=logs, execution_id=execution_id)

            logger.log_action(
                agent_id=agent_name,
                action="sandbox_execute",
                status="completed",
                project_id=execution_id,
            )
            return SandboxResult(success=True, output=logs, execution_id=execution_id)

        except ImportError:
            logger.log_warn(
                agent_id=agent_name,
                action="sandbox_execute",
                message="docker SDK not installed, simulating sandbox",
                project_id=execution_id,
            )
            return SandboxResult(success=True, output=code, execution_id=execution_id)

        except Exception as e:
            logger.log_error(
                agent_id=agent_name,
                action="sandbox_execute",
                error=str(e),
                project_id=execution_id,
            )
            raise SandboxExecutionError(f"Sandbox execution failed: {e}") from e


_sandbox_manager: SandboxManager | None = None


def get_sandbox_manager() -> SandboxManager:
    global _sandbox_manager
    if _sandbox_manager is None:
        _sandbox_manager = SandboxManager()
    return _sandbox_manager
