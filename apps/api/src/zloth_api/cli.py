"""zloth CLI - Local execution mode without Docker.

Usage:
    zloth start [--api-only] [--web-only] [--port PORT] [--web-port PORT]
    zloth stop
    zloth status
    zloth install
    zloth version
"""

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

PIDFILE_DIR = Path.home() / ".zloth" / "pids"
API_PIDFILE = PIDFILE_DIR / "api.pid"
WEB_PIDFILE = PIDFILE_DIR / "web.pid"

# Project root: 5 levels up from this file (cli.py -> zloth_api -> src -> api -> apps -> root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent


def _ensure_dirs() -> None:
    PIDFILE_DIR.mkdir(parents=True, exist_ok=True)


def _read_pid(pidfile: Path) -> int | None:
    if pidfile.exists():
        try:
            pid = int(pidfile.read_text().strip())
            # Check if process is alive
            os.kill(pid, 0)
            return pid
        except (ValueError, ProcessLookupError, PermissionError):
            pidfile.unlink(missing_ok=True)
    return None


def _write_pid(pidfile: Path, pid: int) -> None:
    pidfile.write_text(str(pid))


def _kill_pid(pidfile: Path) -> bool:
    pid = _read_pid(pidfile)
    if pid is not None:
        try:
            os.kill(pid, signal.SIGTERM)
            # Wait up to 5 seconds for process to terminate
            for _ in range(50):
                try:
                    os.kill(pid, 0)
                    time.sleep(0.1)
                except ProcessLookupError:
                    break
            else:
                # Force kill if still running
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        except ProcessLookupError:
            pass
        pidfile.unlink(missing_ok=True)
        return True
    return False


def _find_uv() -> str:
    """Find uv binary."""
    uv = os.environ.get("UV_PATH", "uv")
    try:
        subprocess.run([uv, "--version"], capture_output=True, check=True)
        return uv
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("Error: uv is not installed.")
        print("Install it with: curl -LsSf https://astral.sh/uv/install.sh | sh")
        sys.exit(1)


def _find_npm() -> str:
    """Find npm binary."""
    npm = os.environ.get("NPM_PATH", "npm")
    try:
        subprocess.run([npm, "--version"], capture_output=True, check=True)
        return npm
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("Error: npm is not installed.")
        print("Install Node.js from: https://nodejs.org/")
        sys.exit(1)


def _load_dotenv() -> None:
    """Load .env file into environment."""
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if key and key not in os.environ:
                os.environ[key] = value


def cmd_start(args: argparse.Namespace) -> None:
    """Start zloth services locally."""
    _ensure_dirs()
    _load_dotenv()

    api_port = str(args.port)
    web_port = str(args.web_port)
    api_host = args.host

    started = []

    # Start API server
    if not args.web_only:
        existing = _read_pid(API_PIDFILE)
        if existing:
            print(f"API server is already running (PID {existing})")
        else:
            uv = _find_uv()
            api_dir = PROJECT_ROOT / "apps" / "api"

            env = os.environ.copy()
            env["PYTHONPATH"] = str(api_dir / "src")

            cmd = [
                uv,
                "run",
                "uvicorn",
                "zloth_api.main:app",
                "--host",
                api_host,
                "--port",
                api_port,
            ]
            if args.reload:
                cmd.append("--reload")

            proc = subprocess.Popen(
                cmd,
                cwd=str(api_dir),
                env=env,
            )
            _write_pid(API_PIDFILE, proc.pid)
            started.append(f"API server on http://{api_host}:{api_port}")

    # Start Web server
    if not args.api_only:
        existing = _read_pid(WEB_PIDFILE)
        if existing:
            print(f"Web server is already running (PID {existing})")
        else:
            npm = _find_npm()
            web_dir = PROJECT_ROOT / "apps" / "web"

            # Check if node_modules exists
            if not (web_dir / "node_modules").exists():
                print("Installing web dependencies...")
                subprocess.run([npm, "ci"], cwd=str(web_dir), check=True)

            env = os.environ.copy()
            env["API_URL"] = f"http://localhost:{api_port}"
            env["PORT"] = web_port

            # Use dev mode if --reload, otherwise build and start
            if args.reload:
                proc = subprocess.Popen(
                    [npm, "run", "dev"],
                    cwd=str(web_dir),
                    env=env,
                )
            else:
                # Build first if not built
                next_dir = web_dir / ".next"
                if not next_dir.exists():
                    print("Building web application...")
                    subprocess.run(
                        [npm, "run", "build"],
                        cwd=str(web_dir),
                        env=env,
                        check=True,
                    )
                proc = subprocess.Popen(
                    [npm, "run", "start", "--", "-p", web_port],
                    cwd=str(web_dir),
                    env=env,
                )

            _write_pid(WEB_PIDFILE, proc.pid)
            started.append(f"Web UI on http://localhost:{web_port}")

    if started:
        print()
        print("zloth started:")
        for s in started:
            print(f"  - {s}")
        print()
        print("Run 'zloth stop' to stop all services.")
        print("Run 'zloth status' to check service status.")


def cmd_stop(args: argparse.Namespace) -> None:
    """Stop zloth services."""
    _ensure_dirs()
    stopped = []

    if _kill_pid(API_PIDFILE):
        stopped.append("API server")

    if _kill_pid(WEB_PIDFILE):
        stopped.append("Web server")

    if stopped:
        print("Stopped: " + ", ".join(stopped))
    else:
        print("No zloth services are running.")


def cmd_status(args: argparse.Namespace) -> None:
    """Show status of zloth services."""
    _ensure_dirs()

    api_pid = _read_pid(API_PIDFILE)
    web_pid = _read_pid(WEB_PIDFILE)

    print("zloth service status:")
    print(f"  API server:  {'running (PID ' + str(api_pid) + ')' if api_pid else 'stopped'}")
    print(f"  Web server:  {'running (PID ' + str(web_pid) + ')' if web_pid else 'stopped'}")


def cmd_install(args: argparse.Namespace) -> None:
    """Install dependencies for local execution."""
    uv = _find_uv()
    npm = _find_npm()

    api_dir = PROJECT_ROOT / "apps" / "api"
    web_dir = PROJECT_ROOT / "apps" / "web"

    # Setup .env if not exists
    env_file = PROJECT_ROOT / ".env"
    env_example = PROJECT_ROOT / ".env.example"
    if not env_file.exists() and env_example.exists():
        print("Creating .env from .env.example...")
        import shutil

        shutil.copy2(str(env_example), str(env_file))
        # Generate encryption key
        try:
            import base64
            import secrets

            key = base64.b64encode(secrets.token_bytes(32)).decode()
            content = env_file.read_text()
            content = content.replace("your-encryption-key-here", key)
            env_file.write_text(content)
            print("Generated encryption key.")
        except Exception as e:
            print(f"Warning: Could not generate encryption key: {e}")

    # Install API dependencies
    print("\n==> Installing API dependencies...")
    subprocess.run([uv, "sync", "--extra", "dev"], cwd=str(api_dir), check=True)
    print("[OK] API dependencies installed")

    # Install Web dependencies
    print("\n==> Installing Web dependencies...")
    subprocess.run([npm, "ci"], cwd=str(web_dir), check=True)
    print("[OK] Web dependencies installed")

    # Create data directories
    print("\n==> Creating data directories...")
    (Path.home() / ".zloth" / "workspaces").mkdir(parents=True, exist_ok=True)
    (Path.home() / ".zloth" / "data").mkdir(parents=True, exist_ok=True)
    print("[OK] Data directories created at ~/.zloth/")

    print("\n==> Installation complete!")
    print("Run 'zloth start' to start services.")


def cmd_version(args: argparse.Namespace) -> None:
    """Show version."""
    print("zloth v0.1.0")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="zloth",
        description="zloth - Multi-model Parallel Coding Agent",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # start
    start_parser = subparsers.add_parser("start", help="Start zloth services locally")
    start_parser.add_argument("--api-only", action="store_true", help="Start only the API server")
    start_parser.add_argument("--web-only", action="store_true", help="Start only the Web server")
    start_parser.add_argument(
        "--port", type=int, default=8000, help="API server port (default: 8000)"
    )
    start_parser.add_argument(
        "--web-port", type=int, default=3000, help="Web server port (default: 3000)"
    )
    start_parser.add_argument(
        "--host", default="0.0.0.0", help="API server host (default: 0.0.0.0)"
    )
    start_parser.add_argument(
        "--reload", action="store_true", help="Enable auto-reload (development mode)"
    )
    start_parser.set_defaults(func=cmd_start)

    # stop
    stop_parser = subparsers.add_parser("stop", help="Stop zloth services")
    stop_parser.set_defaults(func=cmd_stop)

    # status
    status_parser = subparsers.add_parser("status", help="Show service status")
    status_parser.set_defaults(func=cmd_status)

    # install
    install_parser = subparsers.add_parser(
        "install", help="Install dependencies for local execution"
    )
    install_parser.set_defaults(func=cmd_install)

    # version
    version_parser = subparsers.add_parser("version", help="Show version")
    version_parser.set_defaults(func=cmd_version)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
