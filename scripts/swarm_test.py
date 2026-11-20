#!/usr/bin/env python3
"""Real Docker/HTTP checks for the Bash workflow; no mocked success results."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import platform
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


class Verifier:
    def __init__(self, base_url: str, log_path: pathlib.Path | None = None):
        self.base = base_url.rstrip("/")
        self.log_path = log_path
        self.token: str | None = None

    def log(self, message: str) -> None:
        print(message, flush=True)
        if self.log_path:
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(f"{now()} {message}\n")

    def docker(self, *args: str, quiet: bool = False) -> str:
        if not quiet:
            self.log("> docker " + " ".join(args))
        run = subprocess.run(
            ["docker", *args], cwd=ROOT, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=180, check=False,
        )
        if not quiet and (run.stdout or run.stderr):
            self.log((run.stdout + run.stderr).strip())
        if run.returncode:
            raise RuntimeError(f"docker {' '.join(args)} failed ({run.returncode}): {(run.stdout + run.stderr).strip()}")
        return run.stdout.strip()

    def manager(self) -> None:
        if self.docker("info", "--format", "{{.OSType}}", quiet=True) != "linux":
            raise RuntimeError("Linux containers are required.")
        if self.docker("info", "--format", "{{.Swarm.ControlAvailable}}", quiet=True) != "true":
            raise RuntimeError("Use a Swarm manager; run scripts/deploy.sh first.")

    def tasks(self, service: str) -> list[str]:
        output = self.docker(
            "service", "ps", "--no-trunc", "--filter", "desired-state=running",
            "--format", "{{.ID}}|{{.CurrentState}}", service, quiet=True,
        )
        return [line.split("|", 1)[0] for line in output.splitlines() if "|Running " in line]

    def wait_service(self, service: str, replicas: int, absent: str = "") -> list[str]:
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            tasks = self.tasks(service)
            desired = int(self.docker("service", "inspect", "--format", "{{.Spec.Mode.Replicated.Replicas}}", service, quiet=True))
            if desired == replicas and len(tasks) == replicas and absent not in tasks:
                return tasks
            time.sleep(2)
        self.docker("service", "ps", "--no-trunc", service)
        raise TimeoutError(f"{service} did not reach {replicas}/{replicas} tasks in time.")

    def request(self, path: str, method: str = "GET", body: dict | None = None,
                auth: bool = False, base: str | None = None, log: bool = True):
        if log:
            self.log(f"> HTTP {method} {(base or self.base).rstrip('/')}{path}")
        headers = {"Accept": "application/json"}
        data = None
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"
        if auth:
            if not self.token:
                raise RuntimeError("Missing administrator token.")
            headers["X-Admin-Token"] = self.token
        request = urllib.request.Request((base or self.base).rstrip("/") + path,
                                         data=data, headers=headers, method=method)
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read()
            return json.loads(raw) if raw else None

    def wait_api(self) -> dict:
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            try:
                health = self.request("/api/health", log=False)
                if health.get("status") == "ok" and health.get("database") == "ok":
                    return health
            except (OSError, ValueError):
                pass
            time.sleep(2)
        raise TimeoutError("API/database readiness timeout.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8080")
    parser.add_argument("--public-url", default="")
    parser.add_argument("--wait-ready", action="store_true", help="Only wait for initial deployment readiness.")
    args = parser.parse_args()
    if args.wait_ready:
        verifier = Verifier(args.base_url)
        verifier.manager()
        for service, count in (("db", 1), ("backend", 2), ("frontend", 1)):
            verifier.wait_service("dronelog_" + service, count)
        verifier.log(json.dumps(verifier.wait_api(), ensure_ascii=False))
        return 0

    run_id = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    evidence_dir = ROOT / "evidence" / ("run_" + run_id)
    evidence_dir.mkdir(parents=True)
    verifier = Verifier(args.base_url, evidence_dir / "commands.txt")
    result = {
        "schema_version": 1, "project": "DroneLog", "run_id": run_id,
        "started_at": now(), "finished_at": None, "environment": {},
        "urls": {"local": verifier.base, "public": args.public_url.rstrip("/") or None},
        "checks": [],
        "manual_checks": {"ui_create_and_read": {"status": "pending"}, "external_network": {"status": "pending"}},
        "test_record": None, "replica_restore": {"from": 3, "to": None, "status": "not_needed"},
        "evidence_files": {"commands": "commands.txt"}, "success": False,
        "limitations": [
            "Browser create/read demonstration is still required.",
            "A public URL request from this host does not prove a separate mobile-network check.",
            "Replacing a container on one node does not demonstrate node-level availability.",
            "PostgreSQL uses a local volume on one labelled node; no database replication or backup is configured.",
        ],
    }
    current_id, current_label = "preflight", "Swarm manager and application readiness"
    original_replicas = None

    def record(check_id: str, label: str, status: str, details: dict) -> None:
        result["checks"].append({"id": check_id, "label": label, "status": status, "details": details, "checked_at": now()})
        verifier.log(f"[{status.upper()}] {check_id}: {label}")

    try:
        verifier.manager()
        nodes = verifier.docker("node", "ls", "--format", "{{.ID}}", quiet=True).splitlines()
        result["environment"] = {
            "docker_context": verifier.docker("context", "show", quiet=True),
            "node_id": verifier.docker("info", "--format", "{{.Swarm.NodeID}}", quiet=True),
            "docker_server_version": verifier.docker("version", "--format", "{{.Server.Version}}", quiet=True),
            "python_version": platform.python_version(), "single_node": len(nodes) == 1,
        }
        if len(nodes) != 1:
            raise RuntimeError("Automatic tests are designed for the one-node project; use the manual procedure for multiple nodes.")
        original_replicas = int(verifier.docker("service", "inspect", "--format", "{{.Spec.Mode.Replicated.Replicas}}", "dronelog_backend", quiet=True))
        result["replica_restore"]["to"] = original_replicas
        health = verifier.wait_api()
        verifier.token = (ROOT / ".secrets" / "admin_token.txt").read_text(encoding="utf-8").strip()
        if len(verifier.token) < 32:
            raise RuntimeError("Local administrator token is missing or too short.")
        verifier.docker("node", "ls")
        verifier.docker("stack", "services", "dronelog")
        verifier.docker("network", "inspect", "--format", "{{.Name}} driver={{.Driver}} scope={{.Scope}} internal={{.Internal}}", "dronelog_app_net", "dronelog_data_net")
        verifier.docker("volume", "inspect", "--format", "{{.Name}} driver={{.Driver}} scope={{.Scope}}", "dronelog_pgdata")
        verifier.docker("secret", "ls", "--format", "{{.Name}}")
        for service in ("dronelog_frontend", "dronelog_backend", "dronelog_db"):
            verifier.docker("service", "inspect", "--format", "{{.Spec.Name}} image={{.Spec.TaskTemplate.ContainerSpec.Image}}", service)
        record(current_id, current_label, "passed", {"health": health, "original_backend_replicas": original_replicas})

        current_id, current_label = "functional_api", "Authenticated create, read and update; unauthenticated write rejected"
        payload = {
            "title": "Swarm verification " + run_id, "location": "Demo test area", "aircraft": "Training UAV",
            "mission_date": dt.date.today().isoformat(), "flight_minutes": 12, "status": "planned",
            "notes": "Fictional test record generated by scripts/test.sh; keep as evidence.",
        }
        denied_status = 0
        try:
            verifier.request("/api/missions", "POST", payload)
        except urllib.error.HTTPError as error:
            denied_status = error.code
        if denied_status not in (401, 403):
            raise RuntimeError(f"Unauthenticated write was not rejected with 401/403; received {denied_status}.")
        created = verifier.request("/api/missions", "POST", payload, auth=True)
        result["test_record"] = {"id": created["id"], "title": created["title"]}
        listed = verifier.request("/api/missions?limit=500")
        if not any(item["id"] == created["id"] and item["title"] == created["title"] for item in listed["items"]):
            raise RuntimeError("Created record could not be read back.")
        updated = verifier.request(f"/api/missions/{created['id']}", "PATCH", {"status": "completed"}, auth=True)
        if updated["status"] != "completed":
            raise RuntimeError("PATCH did not return the requested status.")
        record(current_id, current_label, "passed", {"record_id": created["id"], "title": created["title"], "unauthorized_status": denied_status, "updated_status": updated["status"]})

        current_id, current_label = "scale", "Backend scaled from two to three running replicas"
        verifier.docker("service", "scale", "--detach=true", "dronelog_backend=2")
        verifier.wait_service("dronelog_backend", 2)
        verifier.docker("stack", "services", "dronelog")
        verifier.docker("service", "scale", "--detach=true", "dronelog_backend=3")
        scaled = verifier.wait_service("dronelog_backend", 3)
        verifier.wait_api()
        verifier.docker("stack", "services", "dronelog")
        record(current_id, current_label, "passed", {"from": 2, "to": 3, "running_task_ids": scaled})

        current_id, current_label = "self_healing", "Stopped backend task replaced automatically by Swarm"
        before = verifier.tasks("dronelog_backend")
        containers = verifier.docker("ps", "--filter", "label=com.docker.swarm.service.name=dronelog_backend", "--filter", "status=running", "--format", "{{.ID}}", quiet=True).splitlines()
        if not containers:
            raise RuntimeError("No local backend task; the automatic test expects one node.")
        victim = containers[0]
        labels = json.loads(verifier.docker("inspect", "--format", "{{json .Config.Labels}}", victim, quiet=True))
        victim_task = labels["com.docker.swarm.task.id"]
        verifier.docker("stop", "--time", "5", victim)
        after = verifier.wait_service("dronelog_backend", 3, absent=victim_task)
        replacements = [task for task in after if task not in before]
        if not replacements:
            raise RuntimeError("No newly created task ID was observed.")
        verifier.wait_api()
        verifier.docker("service", "ps", "--no-trunc", "dronelog_backend")
        record(current_id, current_label, "passed", {"stopped_container": victim, "stopped_task": victim_task, "replacement_task_ids": replacements, "running_task_ids": after, "scope": "container replacement on one node"})

        current_id, current_label = "persistence", "Database task recreated; same record and update survived"
        before_db = verifier.tasks("dronelog_db")
        if len(before_db) != 1:
            raise RuntimeError("Expected exactly one running database task.")
        verifier.docker("service", "update", "--force", "--detach=true", "dronelog_db")
        after_db = verifier.wait_service("dronelog_db", 1, absent=before_db[0])
        verifier.wait_api()
        persisted = verifier.request("/api/missions?limit=500")
        if not any(item["id"] == created["id"] and item["title"] == created["title"] and item["status"] == "completed" for item in persisted["items"]):
            raise RuntimeError("The record/update did not survive database task replacement.")
        verifier.docker("service", "ps", "--no-trunc", "dronelog_db")
        record(current_id, current_label, "passed", {"old_task": before_db[0], "new_task": after_db[0], "preserved_record_id": created["id"], "volume": "dronelog_pgdata", "same_node": result["environment"]["node_id"]})

        current_id, current_label = "public_http", "Public URL HTTP check from the deployment computer"
        if args.public_url:
            parsed = urllib.parse.urlparse(args.public_url)
            if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.hostname in ("localhost", "127.0.0.1", "::1"):
                raise ValueError("Use a public absolute HTTP(S) URL without embedded credentials.")
            public_health = verifier.request("/api/health", base=args.public_url)
            public_records = verifier.request("/api/missions?limit=500", base=args.public_url)
            if public_health.get("status") != "ok" or not any(item["id"] == created["id"] and item["title"] == created["title"] for item in public_records["items"]):
                raise RuntimeError("The public URL did not return the same live application and record.")
            record(current_id, current_label, "passed", {"url": args.public_url.rstrip("/"), "health": public_health, "matched_record_id": created["id"], "independent_network_verified": False})
        else:
            record(current_id, current_label, "skipped", {"reason": "No --public-url supplied. Start the tunnel, then rerun with the current URL."})
        result["success"] = True
    except Exception as error:
        record(current_id, current_label, "failed", {"error": str(error)})
        result["success"] = False
    finally:
        if original_replicas is not None:
            try:
                verifier.docker("service", "scale", "--detach=true", f"dronelog_backend={original_replicas}")
                verifier.wait_service("dronelog_backend", original_replicas)
                result["replica_restore"]["status"] = "passed"
            except Exception as error:
                result["replica_restore"].update(status="failed", error=str(error))
                result["success"] = False
                verifier.log("WARNING: could not restore original replica count: " + str(error))
        completed = {check["id"] for check in result["checks"]}
        for pending in ("preflight", "functional_api", "scale", "self_healing", "persistence", "public_http"):
            if pending not in completed:
                record(pending, "Not run", "skipped", {"reason": "An earlier test failed."})
        verifier.token = None
        result["finished_at"] = now()
        (evidence_dir / "test-results.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        verifier.log("Evidence saved: " + str(evidence_dir))
        verifier.log("Still required: browser create/read, independent mobile-data URL check, screenshots and current submission links.")
    return 0 if result["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
