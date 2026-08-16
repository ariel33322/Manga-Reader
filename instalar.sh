#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "==> Instalando dependencias de construcción..."
sudo pacman -S --needed base-devel python pyside6

echo
echo "==> Limpiando compilaciones anteriores..."
rm -rf src pkg
rm -f ./*.pkg.tar.zst

echo
echo "==> Construyendo Manga Reader 1.0.0-3..."
makepkg -f

PKG="$(ls -1t ./manga-reader-local-1.0.0-3-any.pkg.tar.zst | head -n1)"

echo
echo "==> Instalando $PKG..."
sudo pacman -U "$PKG"

echo
echo "==> Actualizando cachés..."
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    sudo gtk-update-icon-cache -f /usr/share/icons/hicolor >/dev/null 2>&1 || true
fi

if command -v kbuildsycoca6 >/dev/null 2>&1; then
    kbuildsycoca6 --noincremental >/dev/null 2>&1 || true
fi

echo
echo "Instalación terminada."
echo "Abre Manga Reader desde el menú de aplicaciones."
