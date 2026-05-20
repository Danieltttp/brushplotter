"""Tests del módulo core/canvas_layout."""

import pytest

from brushplotter.core.canvas_layout import (
    FitStatus,
    compute_layout,
    fit_to_bed_scale,
)
from brushplotter.core.units import cm_to_inches, inches_to_cm


# Conveniencias: trabajar en cm en los tests es más legible
def cm(x: float) -> float:
    return cm_to_inches(x)


# ---------- Encaje básico ----------
def test_small_drawing_fits_with_centering():
    """Un A5 (15×21 cm) cabe holgado en un A1 (84×59 cm)."""
    r = compute_layout(
        svg_width_inches=cm(15),
        svg_height_inches=cm(21),
        bed_width_inches=cm(84.1),
        bed_height_inches=cm(59.4),
        scale=1.0,
        centered=True,
    )
    assert r.status == FitStatus.OK
    assert r.fits is True
    # Centrado: márgenes simétricos
    assert inches_to_cm(r.start_x_inches) == pytest.approx((84.1 - 15) / 2, abs=0.01)
    assert inches_to_cm(r.start_y_inches) == pytest.approx((59.4 - 21) / 2, abs=0.01)


def test_drawing_larger_than_bed_overflows():
    """Un A2 (42×59 cm) NO cabe en un A4 (21×30 cm)."""
    r = compute_layout(
        svg_width_inches=cm(42),
        svg_height_inches=cm(59),
        bed_width_inches=cm(21),
        bed_height_inches=cm(29.7),
        scale=1.0,
        centered=True,
    )
    assert r.status == FitStatus.OVERFLOW
    assert r.fits is False
    assert inches_to_cm(r.overflow_x_inches) == pytest.approx(42 - 21, abs=0.01)


def test_tight_fit_is_detected():
    """Un dibujo a 0.5 cm de los bordes debería marcarse como TIGHT."""
    r = compute_layout(
        svg_width_inches=cm(83.1),   # 84.1 - 1.0 = 83.1
        svg_height_inches=cm(58.4),  # 59.4 - 1.0
        bed_width_inches=cm(84.1),
        bed_height_inches=cm(59.4),
        scale=1.0,
        centered=True,
        tight_margin_cm=1.0,
    )
    # Margen exacto = 0.5 cm a cada lado < 1.0 cm umbral
    assert r.status == FitStatus.TIGHT


# ---------- Escala ----------
def test_scale_50_percent_halves_dimensions():
    r = compute_layout(
        svg_width_inches=cm(20),
        svg_height_inches=cm(20),
        bed_width_inches=cm(50),
        bed_height_inches=cm(50),
        scale=0.5,
        centered=True,
    )
    assert inches_to_cm(r.width_inches) == pytest.approx(10, abs=0.01)
    assert inches_to_cm(r.height_inches) == pytest.approx(10, abs=0.01)


def test_scale_200_percent_doubles_dimensions():
    r = compute_layout(
        svg_width_inches=cm(20),
        svg_height_inches=cm(20),
        bed_width_inches=cm(50),
        bed_height_inches=cm(50),
        scale=2.0,
        centered=True,
    )
    assert inches_to_cm(r.width_inches) == pytest.approx(40, abs=0.01)


def test_scale_causes_overflow():
    """Un A4 escalado a 200% en una cama A3 debe desbordar."""
    r = compute_layout(
        svg_width_inches=cm(21),
        svg_height_inches=cm(29.7),
        bed_width_inches=cm(29.7),
        bed_height_inches=cm(42),
        scale=2.0,
        centered=True,
    )
    assert r.status == FitStatus.OVERFLOW


# ---------- Posicionamiento manual ----------
def test_manual_position_not_centered():
    r = compute_layout(
        svg_width_inches=cm(10),
        svg_height_inches=cm(10),
        bed_width_inches=cm(50),
        bed_height_inches=cm(50),
        scale=1.0,
        centered=False,
        manual_start_x_inches=cm(5),
        manual_start_y_inches=cm(3),
    )
    assert inches_to_cm(r.start_x_inches) == pytest.approx(5, abs=0.01)
    assert inches_to_cm(r.start_y_inches) == pytest.approx(3, abs=0.01)


def test_manual_position_can_cause_overflow():
    """Posicionar a 45 cm un dibujo de 10 cm en cama de 50 desborda."""
    r = compute_layout(
        svg_width_inches=cm(10),
        svg_height_inches=cm(10),
        bed_width_inches=cm(50),
        bed_height_inches=cm(50),
        scale=1.0,
        centered=False,
        manual_start_x_inches=cm(45),
        manual_start_y_inches=cm(0),
    )
    assert r.status == FitStatus.OVERFLOW
    assert inches_to_cm(r.overflow_x_inches) == pytest.approx(5, abs=0.01)


# ---------- Auto-fit ----------
def test_fit_to_bed_scale_basic():
    """SVG de 20×20 cm en cama de 50×50 con margen 1 cm:
    escala máxima = (50 - 2) / 20 = 2.4"""
    s = fit_to_bed_scale(
        svg_width_inches=cm(20),
        svg_height_inches=cm(20),
        bed_width_inches=cm(50),
        bed_height_inches=cm(50),
        margin_cm=1.0,
    )
    assert s == pytest.approx(2.4, abs=0.001)


def test_fit_to_bed_scale_uses_smaller_dimension():
    """Si la proporción no encaja exactamente, escoge el lado limitante."""
    s = fit_to_bed_scale(
        svg_width_inches=cm(10),  # x 5 cabría
        svg_height_inches=cm(30),  # x 1.6 cabría
        bed_width_inches=cm(50),
        bed_height_inches=cm(50),
        margin_cm=1.0,
    )
    # El alto es el limitante: (50 - 2) / 30 = 1.6
    assert s == pytest.approx(48 / 30, abs=0.001)


def test_fit_to_bed_after_apply_actually_fits():
    """La escala devuelta por fit_to_bed_scale, aplicada, debe caber."""
    s = fit_to_bed_scale(
        svg_width_inches=cm(20),
        svg_height_inches=cm(15),
        bed_width_inches=cm(30),
        bed_height_inches=cm(40),
        margin_cm=2.0,
    )
    r = compute_layout(
        svg_width_inches=cm(20),
        svg_height_inches=cm(15),
        bed_width_inches=cm(30),
        bed_height_inches=cm(40),
        scale=s,
        centered=True,
    )
    assert r.fits is True


# ---------- Mensajes ----------
def test_message_for_overflow_mentions_amount():
    r = compute_layout(
        svg_width_inches=cm(30),
        svg_height_inches=cm(10),
        bed_width_inches=cm(20),
        bed_height_inches=cm(50),
        scale=1.0,
        centered=True,
    )
    assert r.status == FitStatus.OVERFLOW
    msg = r.message_short
    assert "No cabe" in msg
    assert "10" in msg  # excede 10 cm en ancho


def test_message_for_ok_is_friendly():
    r = compute_layout(
        svg_width_inches=cm(10),
        svg_height_inches=cm(10),
        bed_width_inches=cm(50),
        bed_height_inches=cm(50),
        scale=1.0,
        centered=True,
    )
    assert r.message_short == "Cabe en la cama"
