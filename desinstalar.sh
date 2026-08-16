#!/bin/bash
set -e

if pacman -Q manga-reader-local >/dev/null 2>&1; then
    sudo pacman -Rns manga-reader-local
else
    echo "Manga Reader no está instalado mediante pacman."
fi

if command -v kbuildsycoca6 >/dev/null 2>&1; then
    kbuildsycoca6 --noincremental >/dev/null 2>&1 || true
fi

echo
echo "Los datos de tu biblioteca NO fueron borrados:"
echo "  ~/.local/share/manga-reader/"
