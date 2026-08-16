pkgname=manga-reader-local
pkgver=1.0.0
pkgrel=3
pkgdesc="Lector local de manga con biblioteca, progreso y soporte PDF/CBZ/ZIP"
arch=('any')
url="https://local.invalid/manga-reader"
license=('custom')
depends=('python' 'pyside6')
source=('main.py' 'manga-reader' 'manga-reader.desktop' 'manga-reader-cat.png')
sha256sums=('SKIP' 'SKIP' 'SKIP' 'SKIP')

package() {
    install -Dm644 "$srcdir/main.py" \
        "$pkgdir/usr/share/manga-reader/main.py"

    install -Dm644 "$srcdir/manga-reader-cat.png" \
        "$pkgdir/usr/share/manga-reader/manga-reader-cat.png"

    install -Dm755 "$srcdir/manga-reader" \
        "$pkgdir/usr/bin/manga-reader"

    install -Dm644 "$srcdir/manga-reader.desktop" \
        "$pkgdir/usr/share/applications/manga-reader.desktop"

    install -Dm644 "$srcdir/manga-reader-cat.png" \
        "$pkgdir/usr/share/icons/hicolor/256x256/apps/manga-reader-cat.png"
}
