#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "==> Instalando dependencias..."
sudo pacman -S --needed base-devel python pyside6

echo "==> Limpiando compilaciones anteriores..."
rm -rf src pkg
rm -f ./*.pkg.tar.zst

echo "==> Construyendo Manga Reader 1.1.0-7..."
makepkg -f

echo "==> Instalando..."
sudo pacman -U ./manga-reader-local-1.1.0-7-any.pkg.tar.zst

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    sudo gtk-update-icon-cache -f /usr/share/icons/hicolor >/dev/null 2>&1 || true
fi

if command -v kbuildsycoca6 >/dev/null 2>&1; then
    kbuildsycoca6 --noincremental >/dev/null 2>&1 || true
fi

echo
echo "Manga Reader 1.1.0-7 instalado."
