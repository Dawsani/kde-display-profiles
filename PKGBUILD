# Maintainer: Dawson Matthews <dawsonwmatthews@proton.me>

pkgname=kde-display-profiles
pkgver=1.0.0
pkgrel=1
pkgdesc="Display profile manager that uses kscreen-doctor to save and load display profiles on KDE Plasma"
arch=('any')
url="https://github.com/Dawsani/KDE-Display-Profiles"
license=('MIT')
depends=('python' 'pyside6' 'libkscreen')
makedepends=('python-build' 'python-installer' 'python-setuptools' 'python-wheel')
# Point to local files for testing
source=("pyproject.toml"
        "kde_display_profiles.py"
        "kde-display-profiles.desktop"
        "icon.png"
        "LICENSE"
        "README.md")
sha256sums=('SKIP'
            'SKIP'
            'SKIP'
            'SKIP'
            'SKIP'
            'SKIP')

build() {
  # We are already in $srcdir, no need to cd
  python -m build --wheel --no-isolation
}

package() {
  python -m installer --destdir="$pkgdir" dist/*.whl

  # Install desktop file
  install -Dm644 "$pkgname.desktop" "$pkgdir/usr/share/applications/$pkgname.desktop"

  # Install icon
  install -Dm644 icon.png "$pkgdir/usr/share/icons/hicolor/128x128/apps/$pkgname.png"

  # Install license
  install -Dm644 LICENSE "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
}
