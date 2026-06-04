import pytest

from tools.iot import simulator


def test_simulador_usa_diez_ramales_por_defecto(monkeypatch):
    monkeypatch.delenv("SIMULATED_BRANCH_IDS", raising=False)
    monkeypatch.delenv("MONITORED_SENSOR_IDS", raising=False)

    branch_ids = simulator._branch_ids()

    assert branch_ids == ["C-01", "C-02", "C-03", "C-04", "C-05", "C-06", "C-07", "C-08", "C-09", "C-10"]


def test_simulador_marca_prototipo_fisico(monkeypatch):
    monkeypatch.setenv("SIMULATED_BRANCH_IDS", "C-01,C-02")
    monkeypatch.setenv("PHYSICAL_BRANCH_ID", "C-02")

    profiles = simulator._branch_profiles()

    assert profiles[0].circuit_label == "C-01 (PC 01-02) - Simulado"
    assert profiles[1].circuit_label == "C-02 (PC 03-04) - Prototipo fisico"


def test_out_of_schedule_solo_enciende_ramal_fisico(monkeypatch):
    monkeypatch.setenv("SIMULATED_BRANCH_IDS", "C-01,C-02")
    monkeypatch.setenv("PHYSICAL_BRANCH_ID", "C-01")
    profiles = simulator._branch_profiles()

    assert simulator._branch_profile_name("out_of_schedule", profiles[0], 1) == "one_idle"
    assert simulator._branch_profile_name("out_of_schedule", profiles[1], 2) == "both_off"


def test_alias_overload_usa_sobrecarga_de_ramal(monkeypatch):
    monkeypatch.setenv("SIMULATED_BRANCH_IDS", "C-01,C-02")
    monkeypatch.setenv("PHYSICAL_BRANCH_ID", "C-01")
    profiles = simulator._branch_profiles()

    assert simulator._branch_profile_name("overload", profiles[0], 1) == "branch_overload"
    assert simulator._branch_profile_name("overload", profiles[1], 2) == "both_off"


def test_mixed_alerts_combina_sobrecarga_y_consumo_fuera_de_horario(monkeypatch):
    monkeypatch.setenv("SIMULATED_BRANCH_IDS", "C-01,C-02,C-03")
    monkeypatch.setenv("PHYSICAL_BRANCH_ID", "C-01")
    profiles = simulator._branch_profiles()

    assert simulator._branch_profile_name("mixed_alerts", profiles[0], 1) == "branch_overload"
    assert simulator._branch_profile_name("mixed_alerts", profiles[1], 2) == "one_workload"
    assert simulator._branch_profile_name("mixed_alerts", profiles[2], 3) == "both_off"


def test_sobrecarga_supera_umbral_alto():
    start, end = simulator._reading_range("branch_overload")

    assert start > 15.0
    assert end > start


def test_una_pc_con_programas_usa_rango_intermedio():
    start, end = simulator._reading_range("one_workload")

    assert 0.19 <= start < end <= 0.23


def test_parse_sequence_rechaza_escenario_desconocido():
    with pytest.raises(ValueError, match="Escenarios no soportados"):
        simulator._parse_scenario_sequence("both_off,desconocido")


def test_run_sequence_ejecuta_escenarios_en_orden(monkeypatch):
    executed = []
    sleeps = []

    monkeypatch.setattr(simulator, "run_once", lambda scenario: executed.append(scenario))
    monkeypatch.setattr(simulator.time, "sleep", lambda seconds: sleeps.append(seconds))

    simulator.run_sequence(["both_off", "out_of_schedule", "branch_overload"], 2.0)

    assert executed == ["both_off", "out_of_schedule", "branch_overload"]
    assert sleeps == [2.0, 2.0]


def test_post_reading_muestra_detalle_de_error(monkeypatch):
    class FakeResponse:
        ok = False
        status_code = 422
        reason = "Unprocessable Entity"

        def json(self):
            return {"detail": "Sensor no monitoreado: C-01"}

    monkeypatch.setenv("SAFYRA_IOT_TOKEN", "test-iot-token")
    monkeypatch.setattr(simulator.requests, "post", lambda *args, **kwargs: FakeResponse())

    branch = simulator.BranchProfile("C-01", 1, 2, "Simulado")

    with pytest.raises(RuntimeError, match="Sensor no monitoreado: C-01"):
        simulator._post_reading(branch, "room_normal", 1)
