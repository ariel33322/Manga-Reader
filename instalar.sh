#!/bin/bash
set -e
cd "$(dirname "$0")"

sudo pacman -S --needed base-devel python pyside6

rm -rf src pkg
rm -f ./*.pkg.tar.zst

makepkg -f
sudo pacman -U ./manga-reader-local-1.0.0-5-any.pkg.tar.zst

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    sudo gtk-update-icon-cache -f /usr/share/icons/hicolor >/dev/null 2>&1 || true
fi

if command -v kbuildsycoca6 >/dev/null 2>&1; then
    kbuildsycoca6 --noincremental >/dev/null 2>&1 || true
fi

echo "Manga Reader 1.0.0-5 instalado."
