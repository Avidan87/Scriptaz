"""
Scriptaz Interim App Icon & Tray Icon Generator
Creates high-DPI 512x512 PNG, 64x64 PNG, and SVG vector app icons.
"""

import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtCore import QByteArray, QSize, Qt

ROOT_DIR = Path(__file__).resolve().parent.parent
ICONS_DIR = ROOT_DIR / "resources" / "icons"
ICONS_DIR.mkdir(parents=True, exist_ok=True)

APP_ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">
  <defs>
    <linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#C8102E;stop-opacity:1" />
      <stop offset="100%" style="stop-color:#8B0000;stop-opacity:1" />
    </linearGradient>
  </defs>
  <!-- Background Rounded Canvas -->
  <rect width="512" height="512" rx="112" fill="url(#grad)"/>
  
  <!-- Open Scripture Book in Pure White -->
  <g transform="translate(96, 120) scale(13.3)" stroke="#FFFFFF" stroke-width="1.8" fill="none" stroke-linecap="round" stroke-linejoin="round">
    <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"></path>
    <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"></path>
    <!-- Cross on the page -->
    <line x1="7" y1="8" x2="7" y2="14" stroke="#FFFFFF" stroke-width="1.2"></line>
    <line x1="5" y1="10" x2="9" y2="10" stroke="#FFFFFF" stroke-width="1.2"></line>
  </g>
</svg>"""

TRAY_ICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#C8102E" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"></path>
  <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"></path>
</svg>"""

def generate_icons():
    app = QApplication.instance() or QApplication(sys.argv)

    # 1. Save SVG files
    svg_app_path = ICONS_DIR / "app_icon.svg"
    svg_tray_path = ICONS_DIR / "tray_icon.svg"

    with open(svg_app_path, "w", encoding="utf-8") as f:
        f.write(APP_ICON_SVG)

    with open(svg_tray_path, "w", encoding="utf-8") as f:
        f.write(TRAY_ICON_SVG)

    # 2. Render 512x512 App Icon PNG
    renderer = QSvgRenderer(QByteArray(APP_ICON_SVG.encode("utf-8")))
    pixmap_512 = QPixmap(512, 512)
    pixmap_512.fill(Qt.transparent)
    painter = QPainter(pixmap_512)
    renderer.render(painter)
    painter.end()
    pixmap_512.save(str(ICONS_DIR / "app_icon.png"))

    # 3. Render 32x32 Tray Icon PNG
    tray_renderer = QSvgRenderer(QByteArray(TRAY_ICON_SVG.encode("utf-8")))
    pixmap_32 = QPixmap(64, 64)   # 2x Retina
    pixmap_32.fill(Qt.transparent)
    p_tray = QPainter(pixmap_32)
    tray_renderer.render(p_tray)
    p_tray.end()
    pixmap_32.save(str(ICONS_DIR / "tray_icon.png"))

    print("✅ Created Scriptaz app icons in resources/icons/")

if __name__ == "__main__":
    generate_icons()
