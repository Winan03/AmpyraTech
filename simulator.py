import argparse
import os
import random
import time
from dataclasses import dataclass
from typing import Any

import requests
from dotenv import load_dotenv

DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_BRANCH_COUNT = 10
VOLTAGE = 220.0
DEMO_SEQUENCE = ["both_off", "out_of_schedule", "branch_overload"]
SUPPORTED_SCENARIOS = [
    "both_off",
    "one_idle",
    "one_workload",
    "two_idle",
    "two_workload",
    "out_of_schedule",
    "room_normal",
    "branch_overload",
    "mixed_alerts",
    "room_overload",
    "idle",
    "normal",
    "overload",
]

SCENARIO_ALIASES = {
    "idle": "both_off",
    "normal": "room_normal",
    "overload": "branch_overload",
}


@dataclass(frozen=True)
class BranchProfile:
    sensor_id: str
    pc_start: int
    pc_end: int
    source: str

    @property
    def label(self) -> str:
        return f"{self.sensor_id} (PC {self.pc_start:02d}-{self.pc_end:02d})"

    @property
    def circuit_label(self) -> str:
        return f"{self.label} - {self.source}"


def _parse_csv(raw_value: str) -> list[str]:
    return [value.strip() for value in raw_value.split(",") if value.strip()]


def _parse_scenario_sequence(raw_value: str) -> list[str]:
    scenarios = _parse_csv(raw_value)
    unsupported = [scenario for scenario in scenarios if scenario not in SUPPORTED_SCENARIOS]
    if unsupported:
        raise ValueError(f"Escenarios no soportados: {', '.join(unsupported)}")
    return scenarios


def _default_branch_ids() -> list[str]:
    return [f"C-{index:02d}" for index in range(1, DEFAULT_BRANCH_COUNT + 1)]


def _branch_ids() -> list[str]:
    raw_value = os.getenv("SIMULATED_BRANCH_IDS") or os.getenv("MONITORED_SENSOR_IDS", "")
    branch_ids = _parse_csv(raw_value) if raw_value else _default_branch_ids()
    if branch_ids == ["LAB-PC-01"]:
        return _default_branch_ids()
    return branch_ids


def _physical_branch_id() -> str:
    return os.getenv("PHYSICAL_BRANCH_ID", "C-01").strip() or "C-01"


def _branch_profiles() -> list[BranchProfile]:
    physical_branch_id = _physical_branch_id()
    profiles: list[BranchProfile] = []
    for index, sensor_id in enumerate(_branch_ids(), start=1):
        profiles.append(
            BranchProfile(
                sensor_id=sensor_id,
                pc_start=(index - 1) * 2 + 1,
                pc_end=index * 2,
                source="Prototipo fisico" if sensor_id == physical_branch_id else "Simulado",
            )
        )
    return profiles


def _backend_url() -> str:
    return os.getenv("SAFYRA_BACKEND_URL", DEFAULT_BACKEND_URL).rstrip("/")


def _request_timeout_seconds() -> float:
    raw_value = os.getenv("IOT_SIMULATOR_TIMEOUT_SECONDS", str(int(DEFAULT_TIMEOUT_SECONDS)))
    try:
        return max(1.0, float(raw_value))
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS


def _response_detail(response: requests.Response) -> str:
    try:
        return str(response.json())
    except ValueError:
        return response.text.strip() or response.reason


def _reading_range(profile_name: str) -> tuple[float, float]:
    ranges = {
        "both_off": (0.125, 0.145),
        "one_idle": (0.165, 0.190),
        "one_workload": (0.195, 0.220),
        "two_idle": (0.205, 0.240),
        "two_workload": (0.245, 0.285),
        "high_use": (0.320, 0.520),
        "branch_overload": (16.2, 17.4),
    }
    return ranges[profile_name]


def _random_current(profile_name: str) -> float:
    start, end = _reading_range(profile_name)
    return round(random.uniform(start, end), 3)


def _branch_profile_name(scenario: str, branch: BranchProfile, branch_index: int) -> str:
    normalized_scenario = SCENARIO_ALIASES.get(scenario, scenario)
    physical_branch_id = _physical_branch_id()

    if normalized_scenario in {"both_off", "one_idle", "one_workload", "two_idle", "two_workload"}:
        return normalized_scenario
    if normalized_scenario == "out_of_schedule":
        return "one_idle" if branch.sensor_id == physical_branch_id else "both_off"
    if normalized_scenario == "room_normal":
        cycle = ["two_idle", "two_workload", "one_idle", "two_idle", "both_off"]
        return cycle[(branch_index - 1) % len(cycle)]
    if normalized_scenario == "branch_overload":
        return "branch_overload" if branch.sensor_id == physical_branch_id else "both_off"
    if normalized_scenario == "mixed_alerts":
        if branch.sensor_id == physical_branch_id:
            return "branch_overload"
        if branch_index == 2:
            return "one_workload"
        return "both_off"
    if normalized_scenario == "room_overload":
        return "high_use"
    raise ValueError(f"Escenario no soportado: {scenario}")


def _scenario_current(scenario: str, branch: BranchProfile, branch_index: int) -> float:
    return _random_current(_branch_profile_name(scenario, branch, branch_index))


def _post_reading(branch: BranchProfile, scenario: str, branch_index: int) -> dict[str, Any]:
    token = os.getenv("SAFYRA_IOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("SAFYRA_IOT_TOKEN no esta configurado en el .env")

    irms = _scenario_current(scenario, branch, branch_index)
    payload = {
        "sensor_id": branch.sensor_id,
        "circuito": branch.circuit_label,
        "irms": irms,
        "potencia": round(irms * VOLTAGE, 3),
        "voltage": VOLTAGE,
    }
    started_at = time.perf_counter()
    try:
        response = requests.post(
            f"{_backend_url()}/api/data/iot/readings",
            json=payload,
            headers={"X-Safyra-Iot-Token": token},
            timeout=_request_timeout_seconds(),
        )
    except requests.Timeout as exc:
        raise RuntimeError(
            f"Timeout enviando {branch.sensor_id} en {scenario} despues de {_request_timeout_seconds():.1f}s. "
            "El backend puede seguir procesando la lectura; revisa el dashboard/correo antes de repetir."
        ) from exc
    except requests.RequestException as exc:
        raise RuntimeError(f"Error HTTP enviando {branch.sensor_id} en {scenario}: {exc}") from exc
    latency_ms = (time.perf_counter() - started_at) * 1000
    if not response.ok:
        raise RuntimeError(
            f"Backend rechazo {branch.sensor_id} en {scenario}: "
            f"{response.status_code} {response.reason} - {_response_detail(response)}"
        )
    result = response.json()
    result["latency_ms"] = round(latency_ms, 1)
    return result


def run_once(scenario: str) -> None:
    total_current = 0.0
    total_power = 0.0
    latencies: list[float] = []
    for index, branch in enumerate(_branch_profiles(), start=1):
        result = _post_reading(branch, scenario, index)
        sensor = result["sensor"]
        notification = result["notification"]
        latency_ms = float(result.get("latency_ms", 0.0))
        latencies.append(latency_ms)
        total_current += float(sensor["irms"])
        total_power += float(sensor["potencia"])
        print(
            f"[{scenario}] {branch.circuit_label} -> {sensor['estado']} | "
            f"{sensor['irms']:.3f} A | {sensor['potencia']:.1f} W | "
            f"notificacion={notification.get('queued')} {notification.get('reason') or ''} | "
            f"latencia={latency_ms:.1f} ms"
        )
    average_latency = sum(latencies) / len(latencies) if latencies else 0.0
    max_latency = max(latencies) if latencies else 0.0
    print(
        f"Total salon estimado: {total_current:.3f} A | {total_power:.1f} W | "
        f"latencia_promedio={average_latency:.1f} ms | latencia_max={max_latency:.1f} ms"
    )


def run_sequence(scenarios: list[str], interval_seconds: float) -> None:
    if not scenarios:
        raise ValueError("La secuencia debe incluir al menos un escenario")

    wait_seconds = max(1.0, interval_seconds)
    for index, scenario in enumerate(scenarios, start=1):
        print(f"\n=== Escenario {index}/{len(scenarios)}: {scenario} ===")
        run_once(scenario)
        if index < len(scenarios):
            time.sleep(wait_seconds)


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Simulador IoT SafyraShield por ramales")
    parser.add_argument(
        "--scenario",
        choices=SUPPORTED_SCENARIOS,
        default="branch_overload",
    )
    parser.add_argument("--demo", action="store_true", help="Ejecuta la secuencia recomendada para demostracion")
    parser.add_argument("--sequence", help="Lista de escenarios separados por coma")
    parser.add_argument("--loop", action="store_true", help="Ejecuta escenarios en bucle")
    parser.add_argument("--interval", type=float, default=5.0, help="Segundos entre escenarios")
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Timeout HTTP por lectura. Util si Firebase o n8n responden lento.",
    )
    args = parser.parse_args()
    if args.timeout is not None:
        os.environ["IOT_SIMULATOR_TIMEOUT_SECONDS"] = str(max(1.0, args.timeout))

    selected_scenarios = DEMO_SEQUENCE if args.demo else _parse_scenario_sequence(args.sequence) if args.sequence else [args.scenario]

    if not args.loop and len(selected_scenarios) == 1:
        run_once(selected_scenarios[0])
        return

    if not args.loop:
        run_sequence(selected_scenarios, args.interval)
        return

    index = 0
    while True:
        run_once(selected_scenarios[index])
        index = (index + 1) % len(selected_scenarios)
        time.sleep(max(1.0, args.interval))


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1) from exc
