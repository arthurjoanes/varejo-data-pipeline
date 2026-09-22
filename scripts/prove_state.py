"""Provas isoladas de restore/recomputação. Nenhum runtime inicia sem --execute."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from proof_contracts import MEASUREMENT_PLAN, digest, distribution, relative_name, write_json

ROOT = Path(__file__).resolve().parents[1]
IMAGE = re.compile(r"sha256:[a-f0-9]{64}\Z")
LABEL = "portfolio.pipeline.proof"
TEMP_ENV = {
    "TMPDIR": "/data/tmp",
    "JAVA_TOOL_OPTIONS": "-Djava.io.tmpdir=/data/tmp",
    "SPARK_LOCAL_DIRS": "/data/tmp/spark",
}


def private_new(path: Path) -> Path:
    path = path.resolve()
    if path.is_relative_to(ROOT) or "onedrive" in str(path).casefold():
        raise ValueError("Provas completas devem ficar fora do repositório e OneDrive.")
    path.mkdir(parents=True, exist_ok=False)
    return path


def source_identity() -> dict:
    files = sorted(
        {
            path
            for directory in ("src", "scripts", "tests", "data", "vendor")
            for path in (ROOT / directory).rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        }
        | {
            ROOT / name
            for name in (
                "Dockerfile",
                "compose.yaml",
                "pyproject.toml",
                "requirements.lock",
                "requirements-build.lock",
                "runtime-jars.lock.json",
                ".gitattributes",
                ".dockerignore",
            )
        }
    )
    names = [path.relative_to(ROOT).as_posix() for path in files]
    git = subprocess.run(
        ["git", "hash-object", "--stdin-paths"],
        input="\n".join(names) + "\n",
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    objects = git.stdout.splitlines()
    if len(objects) != len(files):
        raise ValueError("Não foi possível identificar os blobs normalizados pelo Git.")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    ).stdout.strip()
    return {
        "head": head,
        "files": {
            name: {"sha256_local_bytes": digest(path), "git_blob_oid": oid}
            for name, path, oid in zip(names, files, objects, strict=True)
        },
    }


class PhaseFailure(RuntimeError):
    def __init__(self, record):
        super().__init__("Fase isolada não aprovada; consulte a observação privada.")
        self.record = record


class Runner:
    def __init__(self, image: str, directory: Path):
        if not IMAGE.fullmatch(image):
            raise ValueError("Forneça ID sha256 imutável; tags não autorizam esta prova.")
        self.image = image
        self.directory = directory
        self.run_id = "pf-varejo-proof-" + uuid4().hex[:12]
        self.volumes = []
        self.containers = []
        self.phases = []
        self.active_deadline = None
        self.cleanup_spent_seconds = 0.0
        self.measurement = None

    def docker(self, arguments, *, timeout=30, check=True, cleanup=False):
        if cleanup:
            timeout = min(
                timeout, MEASUREMENT_PLAN["cleanup_allowance_seconds"] - self.cleanup_spent_seconds
            )
        elif self.active_deadline is not None:
            timeout = min(timeout, self.active_deadline - time.monotonic())
        if timeout <= 0:
            raise subprocess.TimeoutExpired("fase limitada", timeout)
        started = time.monotonic()
        try:
            return subprocess.run(
                ["docker", *arguments],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=check,
            )
        finally:
            if cleanup:
                self.cleanup_spent_seconds += time.monotonic() - started

    def verify_container(self, name, volume, *, timeout):
        details = json.loads(self.docker(["inspect", name], timeout=timeout).stdout)[0]
        host = details["HostConfig"]
        environment = dict(item.split("=", 1) for item in details["Config"]["Env"])
        mounts = {item["Destination"]: item for item in details["Mounts"]}
        if (
            details["Image"] != self.image
            or any(environment.get(key) != value for key, value in TEMP_ENV.items())
            or details["Config"]["Labels"].get(LABEL) != self.run_id
            or host["NetworkMode"] != "none"
            or not host["ReadonlyRootfs"]
            or host["Memory"] != MEASUREMENT_PLAN["memory_bytes"]
            or host["NanoCpus"] != MEASUREMENT_PLAN["cpus"] * 1_000_000_000
            or host["PidsLimit"] != MEASUREMENT_PLAN["pids_limit"]
            or host["Privileged"]
            or set(host["CapDrop"] or []) != {"ALL"}
            or {value.removeprefix("CAP_") for value in (host["CapAdd"] or [])} != {"DAC_OVERRIDE"}
            or "no-new-privileges:true" not in (host["SecurityOpt"] or [])
            or host.get("PortBindings")
            or host.get("PublishAllPorts")
            or set(mounts) != {"/app", "/evidence", "/data"}
            or mounts["/app"]["Type"] != "bind"
            or mounts["/app"]["RW"]
            or mounts["/evidence"]["Type"] != "bind"
            or not mounts["/evidence"]["RW"]
            or mounts["/data"]["Type"] != "volume"
            or mounts["/data"]["Name"] != volume
        ):
            raise ValueError("Runtime diverge da imagem, isolamento, recursos ou mounts fixados.")
        return details

    def volume(self, role):
        if not re.fullmatch(r"[a-z0-9-]{1,35}", role):
            raise ValueError("Papel de volume inválido.")
        name = self.run_id + "-" + role
        existing = self.docker(["volume", "inspect", name], check=False)
        if existing.returncode == 0:
            raise ValueError("Volume existente não pertence à criação desta prova.")
        self.docker(["volume", "create", "--label", LABEL + "=" + self.run_id, name])
        self.volumes.append(name)
        return name

    def snapshot(self, *, cleanup=False):
        """Estado externo observável; omite idade/status textual que muda com o relógio."""
        containers = self.docker(
            ["ps", "--all", "--no-trunc", "--format", "{{json .}}"], cleanup=cleanup
        )
        volumes = self.docker(["volume", "ls", "--format", "{{json .}}"], cleanup=cleanup)
        return {
            "containers": sorted(
                (
                    {key: row[key] for key in ("ID", "Names", "Image", "State")}
                    for line in containers.stdout.splitlines()
                    if line.strip()
                    for row in [json.loads(line)]
                    if row["Names"] not in self.containers
                ),
                key=lambda row: row["ID"],
            ),
            "volumes": sorted(
                row["Name"]
                for line in volumes.stdout.splitlines()
                if line.strip()
                for row in [json.loads(line)]
                if row["Name"] not in self.volumes
            ),
        }

    def runtime_command(self, name, volume, phase, output, extra):
        return [
            "create",
            "--name",
            name,
            "--label",
            LABEL + "=" + self.run_id,
            "--pull",
            "never",
            "--init",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--cap-add",
            "DAC_OVERRIDE",
            "--security-opt",
            "no-new-privileges:true",
            "--memory",
            str(MEASUREMENT_PLAN["memory_bytes"]),
            "--cpus",
            str(MEASUREMENT_PLAN["cpus"]),
            "--pids-limit",
            str(MEASUREMENT_PLAN["pids_limit"]),
            "--mount",
            f"type=bind,source={ROOT},target=/app,readonly",
            "--mount",
            f"type=bind,source={self.directory},target=/evidence",
            "--mount",
            f"type=volume,source={volume},target=/data",
            "--env",
            "PYTHONPATH=/app/src",
            "--env",
            "SPARK_DRIVER_MEMORY=1g",
            "--env",
            "SPARK_LOCAL_HOSTNAME=localhost",
            "--env",
            "SPARK_LOCAL_IP=127.0.0.1",
            *[part for key, value in TEMP_ENV.items() for part in ("--env", key + "=" + value)],
            "--entrypoint",
            "python",
            self.image,
            "/app/scripts/recovery_probe.py",
            phase,
            "--output",
            "/evidence/" + output,
            *extra,
        ]

    def external_load(self, snapshot, *, cleanup=False):
        running = [row["ID"] for row in snapshot["containers"] if row["State"] == "running"]
        observed = []
        if running:
            details = json.loads(self.docker(["inspect", *running], cleanup=cleanup).stdout)
            stats = self.docker(
                ["stats", "--no-stream", "--format", "{{json .}}", *running], cleanup=cleanup
            )
            sampled = {
                row["Name"]: row
                for line in stats.stdout.splitlines()
                if line.strip()
                for row in [json.loads(line)]
            }
            for row in details:
                name = row["Name"].lstrip("/")
                observed.append(
                    {
                        "name": name,
                        "id": row["Id"],
                        "image_id": row["Image"],
                        "state": row["State"]["Status"],
                        "memory_limit_bytes": row["HostConfig"]["Memory"],
                        "nano_cpus_limit": row["HostConfig"]["NanoCpus"],
                        "stats": sampled.get(name),
                    }
                )
        return {
            "containers": observed,
            "scope": "Carga externa não controlada. Duas amostras de recursos não garantem ausência de tráfego ou estabilidade durante a medição; não atribuir mudanças ao runner.",
        }

    def phase(self, volume, phase, output, *, timeout=600, extra=(), expected_failure=False):
        if volume not in self.volumes:
            raise ValueError("A fase só aceita volume criado por este runner.")
        relative_name(output)
        if timeout <= 0:
            raise subprocess.TimeoutExpired("fase limitada", timeout)
        name = self.run_id + "-" + str(len(self.phases))
        record = {
            "phase": phase,
            "output": output,
            "status": "running",
            "timeout_seconds": timeout,
            "container": name,
        }
        self.phases.append(record)
        started = time.monotonic()
        deadline = started + timeout
        log_path = self.directory / (output.removesuffix(".json") + ".log")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.docker(
                self.runtime_command(name, volume, phase, output, list(extra)),
                timeout=min(30, max(0.01, deadline - time.monotonic())),
            )
            self.containers.append(name)
            self.verify_container(name, volume, timeout=max(0.01, deadline - time.monotonic()))
            with log_path.open("xb") as log:
                completed = subprocess.run(
                    ["docker", "start", "--attach", name],
                    cwd=ROOT,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    check=False,
                    timeout=max(0.01, deadline - time.monotonic()),
                )
            details = json.loads(
                self.docker(
                    ["inspect", name], timeout=max(0.01, deadline - time.monotonic())
                ).stdout
            )[0]
            record.update(
                exit_code=completed.returncode,
                oom_killed=details["State"]["OOMKilled"],
                image_id=details["Image"],
            )
            if details["Image"] != self.image or details["HostConfig"]["NetworkMode"] != "none":
                raise ValueError("Runtime não corresponde à imagem/rede fixadas.")
            result_path = self.directory / output
            result = (
                json.loads(result_path.read_text(encoding="utf-8")) if result_path.is_file() else {}
            )
            if expected_failure:
                if (
                    completed.returncode == 0
                    or result.get("status") != "failed"
                    or result.get("error_type") != "ValueError"
                ):
                    raise ValueError("Controle negativo não demonstrou a recusa esperada.")
                record["status"] = "expected_refusal"
            else:
                if completed.returncode != 0 or result.get("status") != "passed":
                    raise ValueError("Fase terminou sem resultado funcional aprovado.")
                record["status"] = "passed"
            return result
        except subprocess.TimeoutExpired:
            record["status"] = "censored_timeout"
            raise PhaseFailure(record) from None
        except Exception as error:
            if record["status"] == "running":
                record.update(status="failed", error_type=type(error).__name__)
            raise PhaseFailure(record) from None
        finally:
            record["elapsed_seconds"] = time.monotonic() - started
            if name in self.containers:
                # Mata apenas o container que esta fase criou; volume é conservado.
                try:
                    removed = self.docker(
                        ["rm", "--force", name], timeout=20, check=False, cleanup=True
                    )
                    record["container_removed"] = removed.returncode == 0
                except Exception as error:
                    record.update(container_removed=False, cleanup_error_type=type(error).__name__)
                if not record["container_removed"]:
                    record["status"] = "failed_cleanup"
                    raise PhaseFailure(record)

    def cleanup(self):
        ids = self.docker(
            ["ps", "--all", "--quiet", "--filter", "label=" + LABEL + "=" + self.run_id],
            cleanup=True,
        ).stdout.split()
        if any(not re.fullmatch(r"[a-f0-9]{12,64}", value) for value in ids):
            raise ValueError("Identidade de container inválida no cleanup próprio.")
        if ids:
            self.docker(["rm", "--force", *ids], timeout=60, cleanup=True)
        remaining = self.docker(
            ["ps", "--all", "--quiet", "--filter", "label=" + LABEL + "=" + self.run_id],
            cleanup=True,
        ).stdout.strip()
        if remaining:
            raise ValueError("Cleanup deixou containers pertencentes à prova.")
        return {
            "containers_removed": True,
            "cleanup_spent_seconds": self.cleanup_spent_seconds,
            "volumes_preserved": self.volumes,
            "scope": "Volumes novos retidos para inspeção; nenhum prune, VACUUM ou remoção de dados compartilhados.",
        }


def prove_restore(runner):
    source, target = runner.volume("source"), runner.volume("target")
    prepared = runner.phase(source, "prepare", "source-before.json", timeout=600)
    copied = runner.phase(
        source,
        "archive",
        "archive-phase.json",
        timeout=120,
        extra=["--archive", "/evidence/state.tar", "--manifest", "/evidence/backup-manifest.json"],
    )
    runner.phase(
        target,
        "install",
        "target-installed.json",
        timeout=120,
        extra=["--archive", "/evidence/state.tar", "--manifest", "/evidence/backup-manifest.json"],
    )
    restored = runner.phase(target, "observe", "target-after.json", timeout=300)
    after = runner.phase(source, "observe", "source-after.json", timeout=300)
    if prepared["observed"] != restored["observed"] or prepared["observed"] != after["observed"]:
        raise ValueError("Publicações, versões ou linhas/totais divergiram no restore.")
    checked = runner.phase(source, "inventory", "source-inventory-after.json", timeout=120)
    if checked["inventory"] != copied["manifest"]["files"]:
        raise ValueError("Bytes da origem mudaram durante a recuperação.")
    runner.phase(
        target,
        "install",
        "occupied-refused.json",
        timeout=120,
        expected_failure=True,
        extra=["--archive", "/evidence/state.tar", "--manifest", "/evidence/backup-manifest.json"],
    )
    before_negative = runner.phase(
        target, "inventory", "target-inventory-after-refusal.json", timeout=120
    )
    if before_negative["inventory"] != copied["manifest"]["files"]:
        raise ValueError("Controle de destino ocupado alterou estado restaurado.")
    corrupted = runner.directory / "tampered.tar"
    shutil.copyfile(runner.directory / "state.tar", corrupted)
    with corrupted.open("r+b") as stream:
        stream.write(b"tampered-backup")
    refused = runner.volume("tampered-target")
    negative = runner.phase(
        refused,
        "install",
        "tampered-refused.json",
        timeout=120,
        expected_failure=True,
        extra=[
            "--archive",
            "/evidence/tampered.tar",
            "--manifest",
            "/evidence/backup-manifest.json",
        ],
    )
    if negative["root_exists"]:
        raise ValueError("Restore adulterado criou o diretório de estado antes de validar a cópia.")
    return {
        "source_preserved": True,
        "publication_rows_totals_versions_equal": True,
        "retention": restored["retention"],
        "negative_controls": ["occupied_target_refused", "tampered_archive_refused"],
        "reports": prepared["reports"],
    }


def prove_measurement(runner):
    deadline = time.monotonic() + MEASUREMENT_PLAN["measurement_deadline_seconds"]
    runner.active_deadline = deadline
    samples = [
        {
            "history_rows": size,
            "incoming_rows": MEASUREMENT_PLAN["incoming_rows"],
            "repetition": repetition,
            "status": "not_executed",
            "reason": "not_reached",
        }
        for size in MEASUREMENT_PLAN["history_rows"]
        for repetition in range(1, MEASUREMENT_PLAN["repetitions"] + 1)
    ]
    baselines = []
    # Compartilha as observações com o finally principal, mesmo em falha não prevista.
    runner.measurement = {"status": "failed", "samples": samples, "baselines": baselines}
    for size in MEASUREMENT_PLAN["history_rows"]:
        baseline = None
        archive = f"measurement/{size}/state.tar"
        manifest = f"measurement/{size}/backup.json"
        if time.monotonic() < deadline:
            try:
                volume = runner.volume("history-" + str(size))
                baseline = runner.phase(
                    volume,
                    "measure-seed",
                    f"measurement/{size}/baseline.json",
                    timeout=min(600, deadline - time.monotonic()),
                    extra=["--size", str(size)],
                )
                runner.phase(
                    volume,
                    "archive",
                    f"measurement/{size}/archived.json",
                    timeout=min(120, max(0.01, deadline - time.monotonic())),
                    extra=[
                        "--archive",
                        "/evidence/" + archive,
                        "--manifest",
                        "/evidence/" + manifest,
                    ],
                )
                baselines.append(
                    {
                        "history_rows": size,
                        "status": "passed",
                        "generation_seconds": baseline["generation_seconds"],
                        "baseline_pipeline_seconds": baseline["baseline_pipeline_seconds"],
                    }
                )
            except PhaseFailure as error:
                baseline = None
                baselines.append({"history_rows": size, "status": error.record["status"]})
                if error.record["status"] == "failed_cleanup":
                    raise
            except Exception as error:
                baseline = None
                baselines.append(
                    {
                        "history_rows": size,
                        "status": "censored_timeout"
                        if isinstance(error, subprocess.TimeoutExpired)
                        else "failed",
                        "error_type": type(error).__name__,
                    }
                )
        else:
            baselines.append(
                {"history_rows": size, "status": "not_executed", "reason": "overall_deadline"}
            )
        for sample in (item for item in samples if item["history_rows"] == size):
            if baseline is None or time.monotonic() >= deadline:
                sample["reason"] = (
                    "overall_deadline" if time.monotonic() >= deadline else "baseline_unavailable"
                )
                continue
            repetition = sample["repetition"]
            prefix = f"measurement/{size}/rep-{repetition}"
            sample.pop("reason")
            sample_started = time.monotonic()
            sample_deadline = min(
                deadline, sample_started + MEASUREMENT_PLAN["sample_deadline_seconds"]
            )
            runner.active_deadline = sample_deadline
            try:
                volume = runner.volume(f"size-{size}-rep-{repetition}")
                runner.phase(
                    volume,
                    "install",
                    prefix + "/installed.json",
                    timeout=min(120, sample_deadline - time.monotonic()),
                    extra=[
                        "--archive",
                        "/evidence/" + archive,
                        "--manifest",
                        "/evidence/" + manifest,
                    ],
                )
                result = runner.phase(
                    volume,
                    "measure",
                    prefix + "/sample.json",
                    timeout=max(0.01, sample_deadline - time.monotonic()),
                )
                sample.update(result)
            except PhaseFailure as error:
                sample.update(status=error.record["status"], failed_phase=error.record["phase"])
                if error.record["status"] == "failed_cleanup":
                    raise
            except Exception as error:
                sample.update(
                    status="censored_timeout"
                    if isinstance(error, subprocess.TimeoutExpired)
                    else "failed",
                    error_type=type(error).__name__,
                )
            finally:
                sample["observed_elapsed_seconds"] = time.monotonic() - sample_started
                runner.active_deadline = deadline
    statuses = [item["status"] for item in [*samples, *baselines]]
    status = (
        "failed"
        if any(value.startswith("failed") for value in statuses)
        else "passed"
        if all(value == "passed" for value in statuses)
        else "inconclusive"
    )
    runner.measurement.update(
        status=status,
        distribution_by_history_rows={
            str(size): distribution(
                [sample for sample in samples if sample["history_rows"] == size]
            )
            for size in MEASUREMENT_PLAN["history_rows"]
        },
    )
    return runner.measurement


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["regress", "restore", "measure"])
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        parser.error(
            "Runtime não autorizado implicitamente: --execute é obrigatório após liberar a janela."
        )
    directory = private_new(args.output)
    runner = Runner(args.image, directory)
    source = source_identity()
    record = {
        "status": "failed",
        "run_id": runner.run_id,
        "mode": args.mode,
        "image": args.image,
        "started_at": datetime.now(UTC).isoformat(),
        "source": source,
        "plan": MEASUREMENT_PLAN
        if args.mode == "measure"
        else {
            "scope": "Regressões Linux dos contratos de cópia/retenção, geração, ingestão, relatório e fronteira de publicação; seleção exata no resultado/JUnit",
            "deadline_seconds": 600,
            "memory_bytes": MEASUREMENT_PLAN["memory_bytes"],
            "cpus": 2,
            "pids_limit": MEASUREMENT_PLAN["pids_limit"],
        }
        if args.mode == "regress"
        else {
            "fixture": "64 → bloqueado64 → retomada64 → correção77",
            "copy_max_bytes": 2 * 1024**3,
            "volumes": "novos, sem escritores concorrentes",
            "scope": "Mesmo host; não comprova recuperação contra perda do computador.",
        },
    }
    write_json(directory / "plan-before-execution.json", {**record, "status": "planned"})
    try:
        record["docker_before"] = runner.snapshot()
        record["external_load_before"] = runner.external_load(record["docker_before"])
        image = json.loads(runner.docker(["image", "inspect", args.image]).stdout)[0]
        if image["Id"] != args.image:
            raise ValueError("Identidade de imagem divergente.")
        if args.mode == "regress":
            result = runner.phase(
                runner.volume("regression"), "regress", "regression.json", timeout=600
            )
        else:
            result = prove_restore(runner) if args.mode == "restore" else prove_measurement(runner)
        record.update(result)
        record["status"] = result.get("status", "passed")
        record["source_unchanged"] = source_identity() == source
        if not record["source_unchanged"]:
            raise ValueError("Fontes operacionais mudaram durante a prova.")
    except Exception as error:
        record.update(status="failed", error_type=type(error).__name__)
        raise
    finally:
        try:
            record["cleanup"] = runner.cleanup()
            record["docker_after"] = runner.snapshot(cleanup=True)
            record["external_load_after"] = runner.external_load(
                record["docker_after"], cleanup=True
            )
            record["external_docker_state_unchanged"] = (
                record.get("docker_before") == record["docker_after"]
            )
            record["external_state_scope"] = (
                "Comparação observacional dos snapshots; mudanças externas impedem afirmar igualdade, mas não provam que este runner as causou."
            )
        except Exception as error:
            record.update(status="failed", cleanup_error_type=type(error).__name__)
            raise
        finally:
            if runner.measurement is not None:
                record["measurement"] = runner.measurement
            record.update(completed_at=datetime.now(UTC).isoformat(), phases=runner.phases)
            write_json(directory / "result.json", record)
    print(
        json.dumps(
            {"status": record["status"], "run_id": runner.run_id, "output": str(directory)},
            ensure_ascii=False,
        )
    )
    return 0 if record["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
