"""Tests de core/preferences.

Usamos un QSettings aislado por test (formato IniFormat en un archivo
temporal) para no tocar las preferencias reales del usuario.
"""

import pytest
from PySide6.QtCore import QCoreApplication, QSettings

from brushplotter.core.preferences import (
    Preferences,
    apply_calibration_to_session,
)
from brushplotter.core.stroke_model import (
    InkColor,
    PaintingSession,
    Point,
    Stroke,
    WaterStation,
)


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, monkeypatch):
    """Cada test usa un QSettings que escribe en un archivo INI temporal."""
    # Forzar a QSettings a usar IniFormat en un path controlado
    ini_path = str(tmp_path / "test_settings.ini")
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        str(tmp_path),
    )
    # Aplicación temporal para no chocar con otras
    QCoreApplication.setOrganizationName("brushplotter-test")
    QCoreApplication.setApplicationName("brushplotter-test")
    yield ini_path


def test_defaults_when_nothing_saved():
    p = Preferences()
    assert p.get_plotter_model() == "nextdraw_2234"
    assert p.get_material_key() == "acuarela"
    assert p.get_speed_pendown() == 5
    assert p.get_recharge_cm() == pytest.approx(12.7)
    assert p.get_uses_water_before_dip() is True
    assert p.get_uses_water_on_color_change() is True
    assert p.get_inkwells() == {}
    assert p.get_water_station() is None
    assert p.get_last_svg_dir() == ""


def test_roundtrip_scalars():
    p = Preferences()
    p.set_plotter_model("axidraw_v3")
    p.set_material_key("tinta_china")
    p.set_speed_pendown(12)
    p.set_recharge_cm(8.5)
    p.set_uses_water_before_dip(False)
    p.set_uses_water_on_color_change(False)
    p.set_last_svg_dir("/Users/x/Pictures")
    p.sync()

    p2 = Preferences()
    assert p2.get_plotter_model() == "axidraw_v3"
    assert p2.get_material_key() == "tinta_china"
    assert p2.get_speed_pendown() == 12
    assert p2.get_recharge_cm() == pytest.approx(8.5)
    assert p2.get_uses_water_before_dip() is False
    assert p2.get_uses_water_on_color_change() is False
    assert p2.get_last_svg_dir() == "/Users/x/Pictures"


def test_upsert_inkwell_and_retrieve():
    p = Preferences()
    color = InkColor(
        name="Azul cobalto",
        hex="#1e3a8a",
        inkwell_position=Point(1.5, 2.5),
    )
    p.upsert_inkwell("Azul cobalto", color)
    p.sync()

    stored = Preferences().get_inkwells()
    assert "Azul cobalto" in stored
    assert stored["Azul cobalto"]["x"] == pytest.approx(1.5)
    assert stored["Azul cobalto"]["y"] == pytest.approx(2.5)
    assert stored["Azul cobalto"]["hex"] == "#1e3a8a"


def test_upsert_inkwell_overwrites_same_name():
    p = Preferences()
    c1 = InkColor("Rojo", "#ff0000", inkwell_position=Point(1, 1))
    c2 = InkColor("Rojo", "#cc0000", inkwell_position=Point(3, 4))
    p.upsert_inkwell("Rojo", c1)
    p.upsert_inkwell("Rojo", c2)
    p.sync()
    stored = Preferences().get_inkwells()
    assert len(stored) == 1
    assert stored["Rojo"]["x"] == pytest.approx(3)
    assert stored["Rojo"]["hex"] == "#cc0000"


def test_uncalibrated_inkwell_is_not_saved():
    p = Preferences()
    color = InkColor(name="Sin cal", hex="#000", inkwell_position=None)
    p.upsert_inkwell("Sin cal", color)
    p.sync()
    assert Preferences().get_inkwells() == {}


def test_water_station_roundtrip():
    p = Preferences()
    w = WaterStation(position=Point(0.5, 0.7), name="Agua")
    p.set_water_station(w)
    p.sync()
    recovered = Preferences().get_water_station()
    assert recovered is not None
    assert recovered.x == pytest.approx(0.5)
    assert recovered.y == pytest.approx(0.7)


def test_water_station_uncalibrated_removes_entry():
    p = Preferences()
    p.set_water_station(WaterStation(position=Point(1, 1)))
    p.sync()
    assert Preferences().get_water_station() is not None
    p.set_water_station(WaterStation(position=None))
    p.sync()
    assert Preferences().get_water_station() is None


def test_apply_calibration_to_session():
    """Si una sesión tiene un color con el mismo nombre que uno guardado,
    debe recibir la posición guardada."""
    # Setup: guardar un tintero "Azul" en preferencias
    p = Preferences()
    p.upsert_inkwell("Azul", InkColor("Azul", "#0000ff", inkwell_position=Point(2.0, 3.0)))
    p.set_water_station(WaterStation(position=Point(0.5, 0.5)))
    p.sync()

    # Crear una sesión con un color "Azul" sin calibrar
    session = PaintingSession(svg_file_path="dummy.svg")
    session.colors["c1"] = InkColor(name="Azul", hex="#0000ff")  # sin posición
    session.strokes = [Stroke(points=[(0, 0), (1, 1)], color_id="c1")]

    # Aplicar
    n = apply_calibration_to_session(session)
    assert n == 1
    assert session.colors["c1"].inkwell_position.x == pytest.approx(2.0)
    assert session.colors["c1"].inkwell_position.y == pytest.approx(3.0)
    assert session.water_station.is_calibrated
    assert session.water_station.position.x == pytest.approx(0.5)


def test_apply_calibration_skips_unknown_color_names():
    p = Preferences()
    p.upsert_inkwell("Rojo", InkColor("Rojo", "#f00", inkwell_position=Point(1, 1)))
    p.sync()
    session = PaintingSession(svg_file_path="dummy.svg")
    session.colors["c1"] = InkColor(name="Verde", hex="#0f0")
    n = apply_calibration_to_session(session)
    assert n == 0
    assert not session.colors["c1"].is_calibrated


def test_reset_all_clears_everything():
    p = Preferences()
    p.set_plotter_model("axidraw_v3")
    p.upsert_inkwell("X", InkColor("X", "#000", inkwell_position=Point(1, 1)))
    p.sync()
    assert Preferences().get_inkwells() != {}

    p.reset_all()
    p2 = Preferences()
    assert p2.get_inkwells() == {}
    assert p2.get_plotter_model() == "nextdraw_2234"  # vuelve al default
