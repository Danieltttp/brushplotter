"""Punto de entrada de brushplotter.

Uso:
    python -m brushplotter                  # GUI con simulador (sin plotter)
    python -m brushplotter --hardware       # GUI con NextDraw real
    python -m brushplotter --version
"""

from __future__ import annotations

import argparse
import sys

from PySide6.QtWidgets import QApplication

from .ui.main_window import MainWindow


def main():
    parser = argparse.ArgumentParser(
        prog="brushplotter",
        description="GUI para pintar con plotter NextDraw/AxiDraw",
    )
    parser.add_argument(
        "--hardware",
        action="store_true",
        help="Conectar al plotter real (por defecto: modo simulado)",
    )
    parser.add_argument("--version", action="version", version="brushplotter 0.0.2-dev")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    app.setApplicationName("brushplotter")
    app.setOrganizationName("Daniel García Andújar")

    window = MainWindow(simulated=not args.hardware)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
