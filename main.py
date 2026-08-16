import sys
import json
import sqlite3
import re
import zipfile
from io import BytesIO
from pathlib import Path

from PySide6.QtCore import Qt, QDir, QSettings, QStorageInfo, QSize
from PySide6.QtGui import QCursor, QPixmap, QImage, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileSystemModel,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

try:
    from PySide6.QtPdf import QPdfDocument
    HAS_QTPDF = True
except Exception:
    HAS_QTPDF = False


# ============================================================
# CONFIGURACIÓN
# ============================================================

APP_DIR = Path.home() / ".local" / "share" / "manga-reader"
DATABASE_PATH = APP_DIR / "library.db"

APP_ORG = "MangaReader"
APP_NAME = "MangaReader"

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
}

CHAPTER_EXTENSIONS = {
    ".pdf",
    ".cbz",
    ".zip",
}


# ============================================================
# UTILIDADES
# ============================================================

def natural_sort_key(value):
    text = Path(value).name.lower()

    return [
        int(part) if part.isdigit() else part
        for part in re.split(r"(\d+)", text)
    ]


def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)

        widget = item.widget()

        if widget:
            widget.deleteLater()

        child_layout = item.layout()

        if child_layout:
            clear_layout(child_layout)


# ============================================================
# BASE DE DATOS
# ============================================================

class Database:
    def __init__(self):
        APP_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.connection = sqlite3.connect(
            DATABASE_PATH
        )

        self.create_tables()
        self.migrate_database()

    def create_tables(self):
        cursor = self.connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS manga (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                cover TEXT,
                synopsis TEXT,
                genres TEXT,
                status TEXT,
                favorite INTEGER DEFAULT 0,
                reading_state TEXT DEFAULT 'Leyendo'
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chapters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                manga_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                content_type TEXT NOT NULL,
                content TEXT NOT NULL,
                position INTEGER DEFAULT 0,
                is_read INTEGER DEFAULT 0
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS progress (
                manga_id INTEGER PRIMARY KEY,
                chapter_id INTEGER,
                page_index INTEGER DEFAULT 0
            )
        """)

        self.connection.commit()

    def migrate_database(self):
        cursor = self.connection.cursor()

        cursor.execute(
            "PRAGMA table_info(manga)"
        )

        manga_columns = {
            row[1]
            for row in cursor.fetchall()
        }

        if "favorite" not in manga_columns:
            cursor.execute("""
                ALTER TABLE manga
                ADD COLUMN favorite INTEGER DEFAULT 0
            """)

        if "reading_state" not in manga_columns:
            cursor.execute("""
                ALTER TABLE manga
                ADD COLUMN reading_state TEXT DEFAULT 'Leyendo'
            """)

        cursor.execute(
            "PRAGMA table_info(chapters)"
        )

        chapter_columns = {
            row[1]
            for row in cursor.fetchall()
        }

        if "is_read" not in chapter_columns:
            cursor.execute("""
                ALTER TABLE chapters
                ADD COLUMN is_read INTEGER DEFAULT 0
            """)

        self.connection.commit()

    # --------------------------------------------------------
    # MANGA
    # --------------------------------------------------------

    def add_manga(
        self,
        title,
        cover,
        synopsis,
        genres,
        status,
        favorite=False,
        reading_state="Leyendo",
    ):
        cursor = self.connection.cursor()

        cursor.execute("""
            INSERT INTO manga (
                title,
                cover,
                synopsis,
                genres,
                status,
                favorite,
                reading_state
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            title,
            cover,
            synopsis,
            genres,
            status,
            int(favorite),
            reading_state,
        ))

        self.connection.commit()

        return cursor.lastrowid

    def update_manga(
        self,
        manga_id,
        title,
        cover,
        synopsis,
        genres,
        status,
        favorite,
        reading_state,
    ):
        cursor = self.connection.cursor()

        if reading_state == "Finalizado":
            favorite = False

        cursor.execute("""
            UPDATE manga
            SET
                title = ?,
                cover = ?,
                synopsis = ?,
                genres = ?,
                status = ?,
                favorite = ?,
                reading_state = ?
            WHERE id = ?
        """, (
            title,
            cover,
            synopsis,
            genres,
            status,
            int(favorite),
            reading_state,
            manga_id,
        ))

        self.connection.commit()

    def update_reading_state(
        self,
        manga_id,
        reading_state,
    ):
        cursor = self.connection.cursor()

        if reading_state == "Finalizado":
            cursor.execute("""
                UPDATE manga
                SET
                    reading_state = ?,
                    favorite = 0
                WHERE id = ?
            """, (
                reading_state,
                manga_id,
            ))
        else:
            cursor.execute("""
                UPDATE manga
                SET reading_state = ?
                WHERE id = ?
            """, (
                reading_state,
                manga_id,
            ))

        self.connection.commit()

    def toggle_favorite(
        self,
        manga_id,
    ):
        manga = self.get_manga_by_id(
            manga_id
        )

        if not manga:
            return False

        reading_state = manga[7]

        if reading_state == "Finalizado":
            return False

        new_value = not bool(
            manga[6]
        )

        cursor = self.connection.cursor()

        cursor.execute("""
            UPDATE manga
            SET favorite = ?
            WHERE id = ?
        """, (
            int(new_value),
            manga_id,
        ))

        self.connection.commit()

        return new_value

    def get_manga(self):
        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT
                id,
                title,
                cover,
                synopsis,
                genres,
                status,
                favorite,
                reading_state
            FROM manga
            ORDER BY title COLLATE NOCASE
        """)

        return cursor.fetchall()

    def get_manga_by_id(
        self,
        manga_id,
    ):
        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT
                id,
                title,
                cover,
                synopsis,
                genres,
                status,
                favorite,
                reading_state
            FROM manga
            WHERE id = ?
        """, (
            manga_id,
        ))

        return cursor.fetchone()

    def delete_manga(
        self,
        manga_id,
    ):
        cursor = self.connection.cursor()

        cursor.execute(
            "DELETE FROM progress WHERE manga_id = ?",
            (manga_id,)
        )

        cursor.execute(
            "DELETE FROM chapters WHERE manga_id = ?",
            (manga_id,)
        )

        cursor.execute(
            "DELETE FROM manga WHERE id = ?",
            (manga_id,)
        )

        self.connection.commit()

    # --------------------------------------------------------
    # CAPÍTULOS
    # --------------------------------------------------------

    def add_chapter(
        self,
        manga_id,
        title,
        content_type,
        content,
    ):
        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT COALESCE(MAX(position), 0)
            FROM chapters
            WHERE manga_id = ?
        """, (
            manga_id,
        ))

        position = (
            cursor.fetchone()[0] + 1
        )

        cursor.execute("""
            INSERT INTO chapters (
                manga_id,
                title,
                content_type,
                content,
                position,
                is_read
            )
            VALUES (?, ?, ?, ?, ?, 0)
        """, (
            manga_id,
            title,
            content_type,
            json.dumps(content),
            position,
        ))

        self.connection.commit()

    def get_chapters(
        self,
        manga_id,
        reverse=False,
    ):
        cursor = self.connection.cursor()

        direction = "DESC" if reverse else "ASC"

        cursor.execute(f"""
            SELECT
                id,
                manga_id,
                title,
                content_type,
                content,
                position,
                is_read
            FROM chapters
            WHERE manga_id = ?
            ORDER BY position {direction}, id {direction}
        """, (
            manga_id,
        ))

        return cursor.fetchall()

    def get_chapter(
        self,
        chapter_id,
    ):
        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT
                id,
                manga_id,
                title,
                content_type,
                content,
                position,
                is_read
            FROM chapters
            WHERE id = ?
        """, (
            chapter_id,
        ))

        return cursor.fetchone()

    def set_chapter_read(
        self,
        chapter_id,
        is_read=True,
    ):
        cursor = self.connection.cursor()

        cursor.execute("""
            UPDATE chapters
            SET is_read = ?
            WHERE id = ?
        """, (
            int(is_read),
            chapter_id,
        ))

        self.connection.commit()

    def delete_chapter(
        self,
        chapter_id,
    ):
        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT manga_id
            FROM chapters
            WHERE id = ?
        """, (
            chapter_id,
        ))

        row = cursor.fetchone()

        cursor.execute(
            "DELETE FROM chapters WHERE id = ?",
            (chapter_id,)
        )

        if row:
            manga_id = row[0]

            cursor.execute("""
                SELECT chapter_id
                FROM progress
                WHERE manga_id = ?
            """, (
                manga_id,
            ))

            progress = cursor.fetchone()

            if (
                progress
                and progress[0] == chapter_id
            ):
                cursor.execute(
                    "DELETE FROM progress WHERE manga_id = ?",
                    (manga_id,)
                )

        self.connection.commit()

    # --------------------------------------------------------
    # PROGRESO / CONTINUAR
    # --------------------------------------------------------

    def set_progress(
        self,
        manga_id,
        chapter_id,
        page_index=0,
    ):
        cursor = self.connection.cursor()

        cursor.execute("""
            INSERT INTO progress (
                manga_id,
                chapter_id,
                page_index
            )
            VALUES (?, ?, ?)

            ON CONFLICT(manga_id)
            DO UPDATE SET
                chapter_id = excluded.chapter_id,
                page_index = excluded.page_index
        """, (
            manga_id,
            chapter_id,
            page_index,
        ))

        self.connection.commit()

    def get_progress(
        self,
        manga_id,
    ):
        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT
                chapter_id,
                page_index
            FROM progress
            WHERE manga_id = ?
        """, (
            manga_id,
        ))

        return cursor.fetchone()

    def get_continue_manga(self):
        """
        Continuar muestra mangas que ya fueron empezados y todavía
        tienen capítulos sin leer.

        La tarjeta muestra el PRIMER capítulo pendiente, no el último
        capítulo guardado en progress. Así, si 1 y 2 están leídos y
        el 3 no, Continuar mostrará "Capítulo 3".
        """

        cursor = self.connection.cursor()

        cursor.execute("""
            SELECT
                m.id,
                m.title,
                m.cover,
                m.synopsis,
                m.genres,
                m.status,
                m.favorite,
                m.reading_state,
                pending.title,
                pending.position

            FROM manga m

            JOIN progress p
                ON p.manga_id = m.id

            JOIN chapters pending
                ON pending.id = (
                    SELECT c2.id
                    FROM chapters c2
                    WHERE
                        c2.manga_id = m.id
                        AND c2.is_read = 0
                    ORDER BY
                        c2.position ASC,
                        c2.id ASC
                    LIMIT 1
                )

            ORDER BY m.title COLLATE NOCASE
        """)

        return cursor.fetchall()


# ============================================================
# SELECTOR PROPIO DE ARCHIVOS
# ============================================================

class FilePickerDialog(QDialog):
    def __init__(
        self,
        parent=None,
        mode="cover",
    ):
        super().__init__(parent)

        self.mode = mode
        self.selected_files = []

        if mode == "cover":
            self.setWindowTitle(
                "Seleccionar portada"
            )

            title_text = (
                "Seleccionar portada"
            )

            self.allowed_extensions = IMAGE_EXTENSIONS

        elif mode == "images":
            self.setWindowTitle(
                "Seleccionar imágenes"
            )

            title_text = (
                "Seleccionar imágenes del capítulo"
            )

            self.allowed_extensions = IMAGE_EXTENSIONS

        else:
            self.setWindowTitle(
                "Seleccionar capítulo"
            )

            title_text = (
                "Seleccionar PDF / CBZ / ZIP"
            )

            self.allowed_extensions = CHAPTER_EXTENSIONS

        self.resize(
            1000,
            650,
        )

        root = QVBoxLayout(self)

        root.setContentsMargins(
            18,
            18,
            18,
            18,
        )

        root.setSpacing(
            12
        )

        title = QLabel(
            title_text
        )

        title.setObjectName(
            "pickerTitle"
        )

        root.addWidget(
            title
        )

        body = QHBoxLayout()

        body.setSpacing(
            12
        )

        self.locations = QListWidget()

        self.locations.setFixedWidth(
            250
        )

        body.addWidget(
            self.locations
        )

        explorer = QVBoxLayout()

        self.path_label = QLineEdit()

        self.path_label.setReadOnly(
            True
        )

        explorer.addWidget(
            self.path_label
        )

        self.model = QFileSystemModel()

        self.model.setFilter(
            QDir.AllDirs
            | QDir.Files
            | QDir.NoDotAndDotDot
        )

        self.model.setRootPath(
            "/"
        )

        self.model.setNameFilters([
            f"*{extension}"
            for extension
            in sorted(
                self.allowed_extensions
            )
        ])

        self.model.setNameFilterDisables(
            False
        )

        self.tree = QTreeView()

        self.tree.setModel(
            self.model
        )

        self.tree.hideColumn(1)
        self.tree.hideColumn(2)
        self.tree.hideColumn(3)

        self.tree.setSelectionBehavior(
            QAbstractItemView.SelectRows
        )

        if mode == "images":
            self.tree.setSelectionMode(
                QAbstractItemView.ExtendedSelection
            )
        else:
            self.tree.setSelectionMode(
                QAbstractItemView.SingleSelection
            )

        self.tree.doubleClicked.connect(
            self.double_click
        )

        explorer.addWidget(
            self.tree,
            1,
        )

        self.selection_text = QLabel(
            "Selecciona el contenido."
        )

        explorer.addWidget(
            self.selection_text
        )

        body.addLayout(
            explorer,
            1,
        )

        root.addLayout(
            body,
            1,
        )

        buttons = QHBoxLayout()

        buttons.addStretch()

        cancel_button = QPushButton(
            "Cancelar"
        )

        select_button = QPushButton(
            "Seleccionar"
        )

        select_button.setObjectName(
            "primaryButton"
        )

        cancel_button.clicked.connect(
            self.reject
        )

        select_button.clicked.connect(
            self.accept_selection
        )

        buttons.addWidget(
            cancel_button
        )

        buttons.addWidget(
            select_button
        )

        root.addLayout(
            buttons
        )

        self.locations.itemClicked.connect(
            self.location_clicked
        )

        self.load_locations()
        self.apply_styles()

    def add_location(
        self,
        name,
        path,
    ):
        path = Path(path)

        if not path.exists():
            return

        item = QListWidgetItem(
            name
        )

        item.setData(
            Qt.UserRole,
            str(path),
        )

        self.locations.addItem(
            item
        )

    def load_locations(self):
        added = set()

        def add_unique(
            name,
            path,
        ):
            path = Path(path)

            if not path.exists():
                return

            try:
                key = str(
                    path.resolve()
                )
            except Exception:
                key = str(
                    path
                )

            if key in added:
                return

            self.add_location(
                name,
                path,
            )

            added.add(
                key
            )

        home = Path.home()

        add_unique(
            "Carpeta personal",
            home,
        )

        common = [
            ("Escritorio", home / "Escritorio"),
            ("Desktop", home / "Desktop"),
            ("Descargas", home / "Descargas"),
            ("Downloads", home / "Downloads"),
            ("Documentos", home / "Documentos"),
            ("Documents", home / "Documents"),
            ("Imágenes", home / "Imágenes"),
            ("Pictures", home / "Pictures"),
            ("Vídeos", home / "Vídeos"),
            ("Videos", home / "Videos"),
        ]

        for name, path in common:
            if path.exists():
                add_unique(
                    name,
                    path,
                )

        separator = QListWidgetItem(
            "── Dispositivos ──"
        )

        separator.setFlags(
            Qt.NoItemFlags
        )

        self.locations.addItem(
            separator
        )

        ignored = (
            "/proc",
            "/sys",
            "/dev",
            "/run/user",
            "/snap",
        )

        for storage in QStorageInfo.mountedVolumes():
            if not storage.isValid():
                continue

            if not storage.isReady():
                continue

            path = storage.rootPath()

            if not path:
                continue

            if path == "/":
                continue

            if path.startswith(
                ignored
            ):
                continue

            name = (
                storage
                .displayName()
                .strip()
            )

            if not name:
                name = (
                    Path(path).name
                    or "Disco"
                )

            add_unique(
                name,
                path,
            )

        separator2 = QListWidgetItem(
            "── Sistema ──"
        )

        separator2.setFlags(
            Qt.NoItemFlags
        )

        self.locations.addItem(
            separator2
        )

        add_unique(
            "Sistema de archivos",
            "/",
        )

        self.open_path(
            str(home)
        )

    def location_clicked(
        self,
        item,
    ):
        path = item.data(
            Qt.UserRole
        )

        if path:
            self.open_path(
                path
            )

    def open_path(
        self,
        path,
    ):
        index = self.model.index(
            path
        )

        if not index.isValid():
            return

        self.tree.setRootIndex(
            index
        )

        self.path_label.setText(
            path
        )

    def double_click(
        self,
        index,
    ):
        path = self.model.filePath(
            index
        )

        file_path = Path(
            path
        )

        if file_path.is_dir():
            self.open_path(
                str(file_path)
            )

            return

        if (
            file_path.suffix.lower()
            in self.allowed_extensions
        ):
            self.selected_files = [
                str(file_path)
            ]

            self.accept()

    def accept_selection(self):
        indexes = (
            self.tree
            .selectionModel()
            .selectedRows(0)
        )

        files = []

        for index in indexes:
            path = Path(
                self.model.filePath(
                    index
                )
            )

            if not path.is_file():
                continue

            if (
                path.suffix.lower()
                not in self.allowed_extensions
            ):
                continue

            files.append(
                str(path)
            )

        if not files:
            QMessageBox.warning(
                self,
                "Manga Reader",
                "Selecciona contenido compatible.",
            )

            return

        if self.mode != "images":
            files = [
                files[0]
            ]

        self.selected_files = files

        self.accept()

    def get_files(self):
        if (
            self.exec()
            != QDialog.Accepted
        ):
            return []

        return self.selected_files

    def apply_styles(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #151519;
            }

            QWidget {
                color: #eeeeee;
                font-size: 14px;
            }

            #pickerTitle {
                font-size: 22px;
                font-weight: bold;
            }

            QListWidget,
            QTreeView {
                background-color: #1d1d23;
                border: 1px solid #303038;
                border-radius: 10px;
                padding: 6px;
            }

            QListWidget::item,
            QTreeView::item {
                padding: 8px;
            }

            QListWidget::item:selected,
            QTreeView::item:selected {
                background-color: #6d5dfc;
                color: white;
            }

            QLineEdit {
                background-color: #202027;
                border: 1px solid #34343d;
                border-radius: 8px;
                padding: 9px;
            }

            QPushButton {
                border: none;
                border-radius: 8px;
                padding: 10px 16px;
                background-color: #292931;
            }

            QPushButton:hover {
                background-color: #353540;
            }

            #primaryButton {
                background-color: #6d5dfc;
                color: white;
                font-weight: bold;
            }
        """)


# ============================================================
# CONFIRMACIÓN
# ============================================================

class ConfirmDeleteDialog(QDialog):
    def __init__(
        self,
        title,
        message,
        parent=None,
    ):
        super().__init__(parent)

        self.setWindowTitle(
            title
        )

        self.resize(
            470,
            230,
        )

        layout = QVBoxLayout(
            self
        )

        layout.setContentsMargins(
            22,
            22,
            22,
            22,
        )

        layout.setSpacing(
            16
        )

        message_label = QLabel(
            message
        )

        message_label.setWordWrap(
            True
        )

        layout.addWidget(
            message_label
        )

        self.no_more = QCheckBox(
            "No volver a mostrar esta confirmación"
        )

        layout.addWidget(
            self.no_more
        )

        layout.addStretch()

        buttons = QHBoxLayout()

        buttons.addStretch()

        cancel = QPushButton(
            "Cancelar"
        )

        delete = QPushButton(
            "Eliminar"
        )

        delete.setObjectName(
            "dangerButton"
        )

        cancel.clicked.connect(
            self.reject
        )

        delete.clicked.connect(
            self.accept
        )

        buttons.addWidget(
            cancel
        )

        buttons.addWidget(
            delete
        )

        layout.addLayout(
            buttons
        )

        self.setStyleSheet("""
            QDialog {
                background-color: #151519;
            }

            QWidget {
                color: #eeeeee;
                font-size: 14px;
            }

            QPushButton {
                border: none;
                border-radius: 8px;
                padding: 10px 16px;
                background-color: #292931;
            }

            #dangerButton {
                background-color: #b74646;
                color: white;
                font-weight: bold;
            }
        """)

    def skip_future(
        self,
    ):
        return (
            self.no_more
            .isChecked()
        )


# ============================================================
# EDITOR DE MANGA
# ============================================================

class MangaEditor(QDialog):
    def __init__(
        self,
        parent=None,
        manga=None,
    ):
        super().__init__(parent)

        self.manga = manga
        self.cover_path = ""

        if manga:
            self.cover_path = (
                manga[2] or ""
            )

        self.setWindowTitle(
            "Editar manga"
            if manga
            else "Nuevo manga"
        )

        self.resize(
            730,
            650,
        )

        root = QVBoxLayout(self)

        root.setContentsMargins(
            22,
            22,
            22,
            22,
        )

        root.setSpacing(
            18
        )

        title = QLabel(
            "Editar manga"
            if manga
            else "Nuevo manga"
        )

        title.setObjectName(
            "dialogTitle"
        )

        root.addWidget(
            title
        )

        body = QHBoxLayout()

        body.setSpacing(
            24
        )

        cover_layout = QVBoxLayout()

        self.cover_preview = QLabel(
            "Sin portada"
        )

        self.cover_preview.setFixedSize(
            200,
            285,
        )

        self.cover_preview.setAlignment(
            Qt.AlignCenter
        )

        self.cover_preview.setObjectName(
            "coverPreview"
        )

        choose_cover = QPushButton(
            "Elegir portada"
        )

        choose_cover.clicked.connect(
            self.choose_cover
        )

        cover_layout.addWidget(
            self.cover_preview
        )

        cover_layout.addWidget(
            choose_cover
        )

        cover_layout.addStretch()

        body.addLayout(
            cover_layout
        )

        form = QFormLayout()

        form.setSpacing(
            14
        )

        self.title_input = QLineEdit()

        self.synopsis_input = QTextEdit()

        self.synopsis_input.setFixedHeight(
            180
        )

        self.genres_input = QLineEdit()

        self.publication_status = QComboBox()

        self.publication_status.addItems([
            "En emisión",
            "Pausado",
            "Finalizado",
            "Cancelado",
            "Desconocido",
        ])

        form.addRow(
            "Nombre:",
            self.title_input,
        )

        form.addRow(
            "Sinopsis:",
            self.synopsis_input,
        )

        form.addRow(
            "Géneros:",
            self.genres_input,
        )

        form.addRow(
            "Publicación:",
            self.publication_status,
        )

        body.addLayout(
            form,
            1,
        )

        root.addLayout(
            body,
            1,
        )

        buttons = QHBoxLayout()

        buttons.addStretch()

        cancel = QPushButton(
            "Cancelar"
        )

        save = QPushButton(
            "Guardar"
        )

        save.setObjectName(
            "primaryButton"
        )

        cancel.clicked.connect(
            self.reject
        )

        save.clicked.connect(
            self.validate
        )

        buttons.addWidget(
            cancel
        )

        buttons.addWidget(
            save
        )

        root.addLayout(
            buttons
        )

        if manga:
            self.load_manga()

        self.apply_styles()

    def load_manga(self):
        (
            manga_id,
            title,
            cover,
            synopsis,
            genres,
            status,
            favorite,
            reading_state,
        ) = self.manga

        self.title_input.setText(
            title or ""
        )

        self.synopsis_input.setPlainText(
            synopsis or ""
        )

        self.genres_input.setText(
            genres or ""
        )

        index = (
            self.publication_status
            .findText(
                status or ""
            )
        )

        if index >= 0:
            self.publication_status.setCurrentIndex(
                index
            )

        if cover:
            self.show_cover(
                cover
            )

    def choose_cover(self):
        picker = FilePickerDialog(
            self,
            "cover",
        )

        files = picker.get_files()

        if not files:
            return

        self.cover_path = files[0]

        self.show_cover(
            self.cover_path
        )

    def show_cover(
        self,
        file_path,
    ):
        pixmap = QPixmap(
            file_path
        )

        if pixmap.isNull():
            return

        self.cover_preview.setPixmap(
            pixmap.scaled(
                self.cover_preview.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
        )

    def validate(self):
        if not self.title_input.text().strip():
            QMessageBox.warning(
                self,
                "Manga Reader",
                "Escribe un nombre para el manga.",
            )

            return

        self.accept()

    def get_data(self):
        return {
            "title":
                self.title_input
                .text()
                .strip(),

            "cover":
                self.cover_path,

            "synopsis":
                self.synopsis_input
                .toPlainText()
                .strip(),

            "genres":
                self.genres_input
                .text()
                .strip(),

            "status":
                self.publication_status
                .currentText(),
        }

    def apply_styles(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #151519;
            }

            QWidget {
                color: #eeeeee;
                font-size: 14px;
            }

            #dialogTitle {
                font-size: 24px;
                font-weight: bold;
            }

            #coverPreview {
                background-color: #292930;
                border: 1px solid #3a3a44;
                border-radius: 10px;
                color: #888894;
            }

            QLineEdit,
            QTextEdit,
            QComboBox {
                background-color: #202027;
                border: 1px solid #34343d;
                border-radius: 8px;
                padding: 9px;
            }

            QPushButton {
                border: none;
                border-radius: 8px;
                padding: 10px 16px;
                background-color: #292931;
            }

            #primaryButton {
                background-color: #6d5dfc;
                color: white;
                font-weight: bold;
            }
        """)


# ============================================================
# AGREGAR CAPÍTULO
# ============================================================

class AddChapterDialog(QDialog):
    def __init__(
        self,
        parent=None,
        number=1,
    ):
        super().__init__(parent)

        self.selected_files = []
        self.content_type = None

        self.setWindowTitle(
            "Agregar capítulo"
        )

        self.resize(
            620,
            560,
        )

        root = QVBoxLayout(self)

        root.setContentsMargins(
            22,
            22,
            22,
            22,
        )

        root.setSpacing(
            16
        )

        title = QLabel(
            "Agregar capítulo"
        )

        title.setObjectName(
            "dialogTitle"
        )

        root.addWidget(
            title
        )

        root.addWidget(
            QLabel(
                "Nombre o número del capítulo"
            )
        )

        self.name_input = QLineEdit()

        self.name_input.setText(
            f"Capítulo {number}"
        )

        root.addWidget(
            self.name_input
        )

        image_button = QPushButton(
            "Seleccionar imágenes"
        )

        image_button.setObjectName(
            "primaryButton"
        )

        file_button = QPushButton(
            "Seleccionar PDF / CBZ / ZIP"
        )

        image_button.clicked.connect(
            self.choose_images
        )

        file_button.clicked.connect(
            self.choose_file
        )

        root.addWidget(
            image_button
        )

        root.addWidget(
            file_button
        )

        self.selection_label = QLabel(
            "Todavía no has seleccionado contenido."
        )

        root.addWidget(
            self.selection_label
        )

        note = QLabel(
            "Formatos compatibles\n\n"
            "Imágenes: JPG, JPEG, PNG, WEBP, BMP\n"
            "Archivos: PDF, CBZ, ZIP\n\n"
            "Si usas imágenes, selecciona todas las páginas "
            "del capítulo al mismo tiempo. Manga Reader las "
            "ordenará automáticamente por el nombre del archivo."
        )

        note.setWordWrap(
            True
        )

        note.setObjectName(
            "note"
        )

        root.addWidget(
            note
        )

        root.addStretch()

        buttons = QHBoxLayout()

        buttons.addStretch()

        cancel = QPushButton(
            "Cancelar"
        )

        add = QPushButton(
            "Agregar capítulo"
        )

        add.setObjectName(
            "primaryButton"
        )

        cancel.clicked.connect(
            self.reject
        )

        add.clicked.connect(
            self.validate
        )

        buttons.addWidget(
            cancel
        )

        buttons.addWidget(
            add
        )

        root.addLayout(
            buttons
        )

        self.apply_styles()

    def choose_images(self):
        picker = FilePickerDialog(
            self,
            "images",
        )

        files = picker.get_files()

        if not files:
            return

        self.selected_files = sorted(
            files,
            key=natural_sort_key,
        )

        self.content_type = "images"

        self.selection_label.setText(
            "Contenido seleccionado."
        )

    def choose_file(self):
        picker = FilePickerDialog(
            self,
            "chapter",
        )

        files = picker.get_files()

        if not files:
            return

        file_path = files[0]

        self.selected_files = [
            file_path
        ]

        self.content_type = (
            Path(file_path)
            .suffix
            .lower()
            .replace(".", "")
        )

        self.selection_label.setText(
            "Contenido seleccionado."
        )

    def validate(self):
        if not self.name_input.text().strip():
            QMessageBox.warning(
                self,
                "Manga Reader",
                "Escribe un nombre para el capítulo.",
            )

            return

        if not self.selected_files:
            QMessageBox.warning(
                self,
                "Manga Reader",
                "Selecciona el contenido del capítulo.",
            )

            return

        self.accept()

    def get_data(self):
        return {
            "title":
                self.name_input
                .text()
                .strip(),

            "content_type":
                self.content_type,

            "content":
                self.selected_files,
        }

    def apply_styles(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #151519;
            }

            QWidget {
                color: #eeeeee;
                font-size: 14px;
            }

            #dialogTitle {
                font-size: 24px;
                font-weight: bold;
            }

            #note {
                background-color: #1d1d23;
                border: 1px solid #292932;
                border-radius: 10px;
                padding: 14px;
                color: #aaaab5;
            }

            QLineEdit {
                background-color: #202027;
                border: 1px solid #34343d;
                border-radius: 8px;
                padding: 10px;
            }

            QPushButton {
                border: none;
                border-radius: 8px;
                padding: 10px;
                background-color: #292931;
            }

            #primaryButton {
                background-color: #6d5dfc;
                color: white;
                font-weight: bold;
            }
        """)


# ============================================================
# LECTOR DE CAPÍTULOS
# ============================================================

class ChapterReader(QDialog):
    def __init__(
        self,
        database,
        chapter_id,
        parent=None,
    ):
        super().__init__(parent)

        self.database = database
        self.chapter_id = chapter_id
        self.manga_id = None
        self.chapter = None
        self.title = ""
        self.content_type = ""
        self.content = []

        self.setWindowTitle(
            "Lector"
        )

        self.resize(
            1100,
            800,
        )

        root = QVBoxLayout(self)

        root.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        root.setSpacing(
            0
        )

        # ----------------------------------------------------
        # Navegación del capítulo
        # ----------------------------------------------------

        nav_frame = QFrame()
        nav_frame.setObjectName(
            "readerNavBar"
        )

        nav_layout = QHBoxLayout(
            nav_frame
        )

        nav_layout.setContentsMargins(
            14,
            8,
            14,
            8,
        )

        nav_layout.setSpacing(
            10
        )

        nav_layout.addStretch()

        self.previous_button = QPushButton(
            "‹  Anterior"
        )

        self.previous_button.setObjectName(
            "chapterArrow"
        )

        self.previous_button.setFixedSize(
            130,
            42,
        )

        self.previous_button.clicked.connect(
            self.go_previous
        )

        self.title_label = QLabel()

        self.title_label.setObjectName(
            "readerTitle"
        )

        self.title_label.setAlignment(
            Qt.AlignCenter
        )

        self.title_label.setMinimumWidth(
            240
        )

        self.next_button = QPushButton(
            "Siguiente  ›"
        )

        self.next_button.setObjectName(
            "chapterArrow"
        )

        self.next_button.setFixedSize(
            130,
            42,
        )

        self.next_button.clicked.connect(
            self.go_next
        )

        nav_layout.addWidget(
            self.previous_button
        )

        nav_layout.addWidget(
            self.title_label
        )

        nav_layout.addWidget(
            self.next_button
        )

        nav_layout.addStretch()

        root.addWidget(
            nav_frame
        )

        # ----------------------------------------------------
        # Área del lector
        # ----------------------------------------------------

        self.scroll = QScrollArea()

        self.scroll.setWidgetResizable(
            True
        )

        root.addWidget(
            self.scroll,
            1,
        )

        self.scroll.verticalScrollBar().valueChanged.connect(
            self.on_scroll
        )

        self.load_chapter(
            chapter_id
        )

        self.apply_styles()

    # ========================================================
    # CAMBIO DE CAPÍTULO
    # ========================================================

    def get_adjacent_chapter_id(
        self,
        direction,
    ):
        if not self.manga_id:
            return None

        chapters = (
            self.database
            .get_chapters(
                self.manga_id,
                reverse=False,
            )
        )

        ids = [
            chapter[0]
            for chapter in chapters
        ]

        if self.chapter_id not in ids:
            return None

        index = ids.index(
            self.chapter_id
        )

        target_index = (
            index + direction
        )

        if (
            target_index < 0
            or target_index >= len(ids)
        ):
            return None

        return ids[
            target_index
        ]

    def update_navigation_buttons(self):
        previous_id = (
            self.get_adjacent_chapter_id(
                -1
            )
        )

        next_id = (
            self.get_adjacent_chapter_id(
                1
            )
        )

        self.previous_button.setEnabled(
            previous_id is not None
        )

        self.next_button.setEnabled(
            next_id is not None
        )

    def go_previous(self):
        chapter_id = (
            self.get_adjacent_chapter_id(
                -1
            )
        )

        if chapter_id is None:
            return

        self.load_chapter(
            chapter_id
        )

    def go_next(self):
        chapter_id = (
            self.get_adjacent_chapter_id(
                1
            )
        )

        if chapter_id is None:
            return

        self.load_chapter(
            chapter_id
        )

    # ========================================================
    # CARGAR CAPÍTULO
    # ========================================================

    def load_chapter(
        self,
        chapter_id,
    ):
        chapter = (
            self.database
            .get_chapter(
                chapter_id
            )
        )

        if not chapter:
            return

        # Guardamos progreso del capítulo anterior antes
        # de cambiar de capítulo.
        if self.manga_id is not None:
            current_scroll = (
                self.scroll
                .verticalScrollBar()
                .value()
            )

            self.database.set_progress(
                self.manga_id,
                self.chapter_id,
                current_scroll,
            )

        self.chapter_id = (
            chapter_id
        )

        self.chapter = (
            chapter
        )

        self.manga_id = (
            chapter[1]
        )

        self.title = (
            chapter[2]
        )

        self.content_type = (
            chapter[3]
        )

        try:
            self.content = json.loads(
                chapter[4]
            )
        except Exception:
            self.content = []

        # Abrir un capítulo lo marca inmediatamente como leído.
        # Se guarda directamente en SQLite antes de dibujar el contenido.
        self.database.set_chapter_read(
            self.chapter_id,
            True,
        )

        self.setWindowTitle(
            self.title
        )

        self.title_label.setText(
            self.title
        )

        self.build_reader_widget()

        self.database.set_progress(
            self.manga_id,
            self.chapter_id,
            0,
        )

        self.restore_progress()

        self.update_navigation_buttons()

    def build_reader_widget(self):
        # No reemplazamos el widget completo del QScrollArea al cambiar
        # de capítulo. Reutilizamos el mismo contenedor y solo limpiamos
        # sus páginas. Esto evita que la vista quede negra al navegar
        # con Anterior / Siguiente.

        if not hasattr(
            self,
            "reader_widget",
        ):
            self.reader_widget = QWidget()

            self.reader_layout = QVBoxLayout(
                self.reader_widget
            )

            self.reader_layout.setContentsMargins(
                20,
                20,
                20,
                30,
            )

            self.reader_layout.setSpacing(
                6
            )

            self.reader_layout.setAlignment(
                Qt.AlignTop
                | Qt.AlignHCenter
            )

            self.scroll.setWidget(
                self.reader_widget
            )

        else:
            # Limpiar únicamente las páginas del capítulo anterior.
            while self.reader_layout.count():
                item = self.reader_layout.takeAt(
                    0
                )

                widget = item.widget()

                if widget is not None:
                    widget.deleteLater()

                child_layout = item.layout()

                if child_layout is not None:
                    while child_layout.count():
                        child_item = child_layout.takeAt(
                            0
                        )

                        child_widget = child_item.widget()

                        if child_widget is not None:
                            child_widget.deleteLater()

        # Volver al inicio inmediatamente al cambiar de capítulo.
        self.scroll.verticalScrollBar().setValue(
            0
        )

        self.load_content()

        # Forzar actualización visual después de crear todas las páginas.
        self.reader_widget.adjustSize()
        self.reader_widget.updateGeometry()
        self.scroll.viewport().update()
        QApplication.processEvents()

    # ========================================================
    # CONTENIDO
    # ========================================================

    def add_pixmap(
        self,
        pixmap,
    ):
        if pixmap.isNull():
            return

        label = QLabel()

        label.setAlignment(
            Qt.AlignCenter
        )

        label.setPixmap(
            pixmap
        )

        self.reader_layout.addWidget(
            label,
            0,
            Qt.AlignHCenter,
        )

    def scale_pixmap_to_reader(
        self,
        pixmap,
    ):
        max_width = 950

        if pixmap.width() <= max_width:
            return pixmap

        return pixmap.scaledToWidth(
            max_width,
            Qt.SmoothTransformation,
        )

    def load_content(self):
        if self.content_type == "images":
            self.load_images()

        elif self.content_type in {
            "cbz",
            "zip",
        }:
            self.load_archive()

        elif self.content_type == "pdf":
            self.load_pdf()

        else:
            self.show_error(
                "Formato de capítulo no compatible."
            )

        self.reader_layout.addStretch()

    def load_images(self):
        files = sorted(
            self.content,
            key=natural_sort_key,
        )

        for file_path in files:
            path = Path(
                file_path
            )

            if not path.exists():
                continue

            pixmap = QPixmap(
                str(path)
            )

            if pixmap.isNull():
                continue

            pixmap = (
                self.scale_pixmap_to_reader(
                    pixmap
                )
            )

            self.add_pixmap(
                pixmap
            )

    def load_archive(self):
        if not self.content:
            self.show_error(
                "El capítulo no contiene ningún archivo."
            )
            return

        archive_path = Path(
            self.content[0]
        )

        if not archive_path.exists():
            self.show_error(
                "No se encontró el archivo del capítulo."
            )
            return

        try:
            with zipfile.ZipFile(
                archive_path,
                "r",
            ) as archive:
                names = [
                    name
                    for name
                    in archive.namelist()
                    if (
                        not name.endswith("/")
                        and Path(name)
                        .suffix
                        .lower()
                        in IMAGE_EXTENSIONS
                    )
                ]

                names.sort(
                    key=natural_sort_key
                )

                for name in names:
                    data = archive.read(
                        name
                    )

                    pixmap = QPixmap()

                    if not pixmap.loadFromData(
                        data
                    ):
                        continue

                    pixmap = (
                        self.scale_pixmap_to_reader(
                            pixmap
                        )
                    )

                    self.add_pixmap(
                        pixmap
                    )

        except Exception as error:
            self.show_error(
                f"No se pudo abrir el archivo:\n{error}"
            )

    def load_pdf(self):
        if not self.content:
            self.show_error(
                "El capítulo no contiene ningún PDF."
            )
            return

        pdf_path = Path(
            self.content[0]
        )

        if not pdf_path.exists():
            self.show_error(
                "No se encontró el PDF."
            )
            return

        if not HAS_QTPDF:
            self.show_error(
                "Tu instalación de PySide6 no incluye QtPdf."
            )
            return

        document = QPdfDocument(
            self
        )

        document.load(
            str(pdf_path)
        )

        if document.pageCount() <= 0:
            self.show_error(
                "No se pudo leer el PDF."
            )
            return

        for page in range(
            document.pageCount()
        ):
            try:
                point_size = (
                    document
                    .pagePointSize(
                        page
                    )
                )

                width = 950

                if point_size.width() > 0:
                    ratio = (
                        point_size.height()
                        / point_size.width()
                    )
                else:
                    ratio = 1.414

                height = max(
                    1,
                    int(
                        width * ratio
                    )
                )

                image = document.render(
                    page,
                    QSize(
                        width,
                        height,
                    )
                )

                pixmap = QPixmap.fromImage(
                    image
                )

                if not pixmap.isNull():
                    self.add_pixmap(
                        pixmap
                    )

            except Exception as error:
                self.show_error(
                    f"Error al mostrar una página del PDF:\n{error}"
                )
                break

    def show_error(
        self,
        text,
    ):
        label = QLabel(
            text
        )

        label.setWordWrap(
            True
        )

        label.setAlignment(
            Qt.AlignCenter
        )

        label.setObjectName(
            "readerError"
        )

        self.reader_layout.addWidget(
            label
        )

    # ========================================================
    # PROGRESO
    # ========================================================

    def restore_progress(self):
        progress = (
            self.database
            .get_progress(
                self.manga_id
            )
        )

        if not progress:
            return

        saved_chapter_id = progress[0]
        saved_scroll = progress[1] or 0

        if saved_chapter_id != self.chapter_id:
            return

        QApplication.processEvents()

        self.scroll.verticalScrollBar().setValue(
            saved_scroll
        )

    def on_scroll(
        self,
        value,
    ):
        if not self.manga_id:
            return

        self.database.set_progress(
            self.manga_id,
            self.chapter_id,
            value,
        )


    # ========================================================
    # ESTILO
    # ========================================================

    def apply_styles(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #101014;
            }

            QWidget {
                color: #eeeeee;
                font-size: 14px;
            }

            #readerNavBar {
                background-color: #151519;
                border-bottom: 1px solid #2e2e36;
            }

            #readerTitle {
                background-color: #202027;
                border: 1px solid #3b3b45;
                border-radius: 9px;
                padding: 9px 20px;
                font-size: 15px;
                font-weight: bold;
                color: #eeeeee;
            }

            #chapterArrow {
                border: 1px solid #4a4a56;
                border-radius: 9px;
                background-color: #292931;
                color: #eeeeee;
                font-size: 15px;
                font-weight: bold;
                text-align: center;
                padding: 0;
            }

            #chapterArrow:hover {
                background-color: #3a3a44;
            }

            #chapterArrow:disabled {
                color: #55555f;
                background-color: #1b1b20;
            }

            #readerError {
                color: #d6a0a0;
                padding: 30px;
            }

            QPushButton {
                border: none;
                border-radius: 8px;
                padding: 9px 12px;
                background-color: #292931;
            }

            QPushButton:hover {
                background-color: #353540;
            }

            QScrollArea {
                background-color: #101014;
                border: none;
            }

            QScrollBar:vertical {
                background-color: #17171c;
                width: 11px;
            }

            QScrollBar::handle:vertical {
                background-color: #484854;
                border-radius: 5px;
                min-height: 30px;
            }
        """)



# ============================================================
# DETALLES DEL MANGA
# ============================================================

class MangaDetails(QDialog):
    def __init__(
        self,
        database,
        manga_id,
        parent=None,
    ):
        super().__init__(parent)

        self.database = database
        self.manga_id = manga_id
        self.reverse_chapters = False

        self.setWindowTitle(
            "Manga"
        )

        self.resize(
            920,
            720,
        )

        self.root = QVBoxLayout(
            self
        )

        self.root.setContentsMargins(
            20,
            20,
            20,
            20,
        )

        self.root.setSpacing(
            14
        )

        self.build_ui()
        self.refresh()
        self.apply_styles()

    def build_ui(self):
        header = QHBoxLayout()

        self.cover_label = QLabel(
            "Sin portada"
        )

        self.cover_label.setFixedSize(
            180,
            260,
        )

        self.cover_label.setAlignment(
            Qt.AlignCenter
        )

        self.cover_label.setObjectName(
            "detailCover"
        )

        header.addWidget(
            self.cover_label
        )

        info = QVBoxLayout()

        title_row = QHBoxLayout()

        self.title_label = QLabel()

        self.title_label.setObjectName(
            "detailTitle"
        )

        title_row.addWidget(
            self.title_label
        )

        title_row.addStretch()

        self.favorite_button = QPushButton(
            "☆"
        )

        self.favorite_button.setObjectName(
            "favoriteButton"
        )

        self.favorite_button.setFixedSize(
            38,
            38,
        )

        self.favorite_button.clicked.connect(
            self.toggle_favorite
        )

        self.state_combo = QComboBox()

        self.state_combo.addItems([
            "Leyendo",
            "Finalizado",
        ])

        self.state_combo.currentTextChanged.connect(
            self.change_reading_state
        )

        title_row.addWidget(
            self.favorite_button
        )

        title_row.addWidget(
            self.state_combo
        )

        info.addLayout(
            title_row
        )

        self.publication_badge = QLabel()

        self.publication_badge.setObjectName(
            "publicationBadge"
        )

        self.publication_badge.setAlignment(
            Qt.AlignCenter
        )

        self.publication_badge.setMaximumWidth(
            120
        )

        info.addWidget(
            self.publication_badge
        )

        self.genres_container = QWidget()

        self.genres_layout = QHBoxLayout(
            self.genres_container
        )

        self.genres_layout.setContentsMargins(
            0,
            2,
            0,
            2,
        )

        self.genres_layout.setSpacing(
            6
        )

        self.genres_layout.setAlignment(
            Qt.AlignLeft
        )

        info.addWidget(
            self.genres_container
        )

        self.synopsis_label = QLabel()

        self.synopsis_label.setWordWrap(
            True
        )

        self.synopsis_label.setTextInteractionFlags(
            Qt.TextSelectableByMouse
        )

        info.addSpacing(
            6
        )

        info.addWidget(
            self.synopsis_label
        )

        info.addStretch()

        header.addLayout(
            info,
            1,
        )

        self.root.addLayout(
            header
        )

        chapters_header = QHBoxLayout()

        chapter_title = QLabel(
            "Capítulos"
        )

        chapter_title.setObjectName(
            "sectionTitle"
        )

        self.chapter_order = QComboBox()

        self.chapter_order.addItems([
            "Primero → Último",
            "Último → Primero",
        ])

        self.chapter_order.currentIndexChanged.connect(
            self.change_chapter_order
        )

        chapters_header.addWidget(
            chapter_title
        )

        chapters_header.addStretch()

        chapters_header.addWidget(
            self.chapter_order
        )

        self.root.addLayout(
            chapters_header
        )

        self.chapter_list = QListWidget()

        self.chapter_list.setSpacing(
            5
        )

        self.chapter_list.setSelectionMode(
            QAbstractItemView.SingleSelection
        )

        self.chapter_list.setContextMenuPolicy(
            Qt.CustomContextMenu
        )

        self.chapter_list.customContextMenuRequested.connect(
            self.chapter_context_menu
        )

        self.chapter_list.itemSelectionChanged.connect(
            self.update_chapter_selection
        )

        self.chapter_list.itemDoubleClicked.connect(
            self.open_chapter
        )

        self.root.addWidget(
            self.chapter_list,
            1,
        )

        hint = QLabel(
            "Doble clic para abrir. "
            "Clic derecho para marcar o desmarcar como leído."
        )

        hint.setObjectName(
            "chapterHint"
        )

        self.root.addWidget(
            hint
        )

    def refresh(self):
        manga = self.database.get_manga_by_id(
            self.manga_id
        )

        if not manga:
            return

        (
            manga_id,
            title,
            cover,
            synopsis,
            genres,
            status,
            favorite,
            reading_state,
        ) = manga

        self.title_label.setText(
            title
        )

        self.set_publication_badge(
            status
        )

        self.set_genres(
            genres
        )

        self.synopsis_label.setText(
            synopsis
            or "Sin sinopsis."
        )

        self.state_combo.blockSignals(
            True
        )

        index = self.state_combo.findText(
            reading_state
        )

        if index >= 0:
            self.state_combo.setCurrentIndex(
                index
            )

        self.state_combo.blockSignals(
            False
        )

        if (
            reading_state
            == "Finalizado"
        ):
            self.favorite_button.setText(
                "☆"
            )

            self.favorite_button.setEnabled(
                False
            )

        else:
            self.favorite_button.setEnabled(
                True
            )

            self.favorite_button.setText(
                "★"
                if favorite
                else "☆"
            )

        self.cover_label.clear()

        if cover:
            pixmap = QPixmap(
                cover
            )

            if not pixmap.isNull():
                self.cover_label.setPixmap(
                    pixmap.scaled(
                        self.cover_label.size(),
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                )
            else:
                self.cover_label.setText(
                    "Sin portada"
                )
        else:
            self.cover_label.setText(
                "Sin portada"
            )

        self.refresh_chapters()

    def set_publication_badge(
        self,
        status,
    ):
        status = status or "Desconocido"

        display_text = {
            "En emisión": "Emisión",
            "Pausado": "Pausado",
            "Finalizado": "Finalizado",
            "Cancelado": "Cancelado",
            "Desconocido": "Desconocido",
        }.get(
            status,
            status,
        )

        self.publication_badge.setText(
            display_text
        )

        colors = {
            "En emisión": (
                "#173c2a",
                "#70d99b",
                "#2e7650",
            ),
            "Pausado": (
                "#172e49",
                "#7db8ff",
                "#315f91",
            ),
            "Finalizado": (
                "#421d22",
                "#ff8b94",
                "#7f3941",
            ),
            "Cancelado": (
                "#453218",
                "#f3c66b",
                "#80602e",
            ),
            "Desconocido": (
                "#292930",
                "#b3b3bd",
                "#45454f",
            ),
        }

        background, text, border = colors.get(
            status,
            colors["Desconocido"],
        )

        self.publication_badge.setStyleSheet(
            f"""
            QLabel {{
                background-color: {background};
                color: {text};
                border: 1px solid {border};
                border-radius: 9px;
                padding: 5px 10px;
                font-weight: bold;
            }}
            """
        )

    def set_genres(
        self,
        genres_text,
    ):
        clear_layout(
            self.genres_layout
        )

        genres = [
            genre.strip()
            for genre
            in (
                genres_text or ""
            ).split(",")
            if genre.strip()
        ]

        if not genres:
            genres = [
                "Sin género"
            ]

        for genre in genres:
            label = QLabel(
                genre
            )

            label.setObjectName(
                "genreBadge"
            )

            label.setStyleSheet("""
                QLabel {
                    background-color: #292935;
                    color: #c8c2ff;
                    border: 1px solid #3b3b4d;
                    border-radius: 9px;
                    padding: 5px 9px;
                }
            """)

            self.genres_layout.addWidget(
                label
            )

        self.genres_layout.addStretch()

    def change_chapter_order(
        self,
        index,
    ):
        self.reverse_chapters = (
            index == 1
        )

        self.refresh_chapters()

    def refresh_chapters(
        self,
        keep_selected_id=None,
    ):
        if keep_selected_id is None:
            current = self.chapter_list.currentItem()

            if current:
                keep_selected_id = current.data(
                    Qt.UserRole
                )

        self.chapter_list.clear()

        chapters = (
            self.database
            .get_chapters(
                self.manga_id,
                reverse=self.reverse_chapters,
            )
        )

        if not chapters:
            item = QListWidgetItem(
                "Todavía no hay capítulos."
            )

            item.setFlags(
                Qt.NoItemFlags
            )

            self.chapter_list.addItem(
                item
            )

            return

        selected_item = None

        for chapter in chapters:
            chapter_id = chapter[0]
            title = chapter[2]
            is_read = bool(
                chapter[6]
            )

            display_title = (
                f"✓  {title}"
                if is_read
                else f"   {title}"
            )

            item = QListWidgetItem(
                display_title
            )

            item.setData(
                Qt.UserRole,
                chapter_id,
            )

            item.setData(
                Qt.UserRole + 1,
                is_read,
            )

            item.setData(
                Qt.UserRole + 2,
                title,
            )

            item.setSizeHint(
                QSize(
                    0,
                    46,
                )
            )

            if is_read:
                item.setForeground(
                    Qt.gray
                )

            self.chapter_list.addItem(
                item
            )

            if (
                keep_selected_id
                and chapter_id == keep_selected_id
            ):
                selected_item = item

        if selected_item:
            self.chapter_list.setCurrentItem(
                selected_item
            )

            self.chapter_list.scrollToItem(
                selected_item
            )

        self.update_chapter_selection()

    def chapter_context_menu(
        self,
        position,
    ):
        item = self.chapter_list.itemAt(
            position
        )

        if not item:
            return

        chapter_id = item.data(
            Qt.UserRole
        )

        if not chapter_id:
            return

        is_read = bool(
            item.data(
                Qt.UserRole + 1
            )
        )

        self.database.set_chapter_read(
            chapter_id,
            not is_read,
        )

        self.refresh_chapters(
            keep_selected_id=chapter_id
        )

    def update_chapter_selection(self):
        current = self.chapter_list.currentItem()

        for index in range(
            self.chapter_list.count()
        ):
            item = self.chapter_list.item(
                index
            )

            chapter_id = item.data(
                Qt.UserRole
            )

            if not chapter_id:
                continue

            is_selected = (
                item is current
            )

            is_read = bool(
                item.data(
                    Qt.UserRole + 1
                )
            )

            font = item.font()

            if is_selected:
                font.setPointSize(
                    13
                )
                font.setBold(
                    True
                )

                item.setSizeHint(
                    QSize(
                        0,
                        64,
                    )
                )
            else:
                font.setPointSize(
                    10
                )
                font.setBold(
                    False
                )

                item.setSizeHint(
                    QSize(
                        0,
                        46,
                    )
                )

            item.setFont(
                font
            )

            if is_read:
                item.setForeground(
                    Qt.gray
                )
            else:
                item.setForeground(
                    Qt.white
                )

    def change_reading_state(
        self,
        state,
    ):
        self.database.update_reading_state(
            self.manga_id,
            state,
        )

        self.refresh()

    def toggle_favorite(self):
        self.database.toggle_favorite(
            self.manga_id
        )

        self.refresh()

    def open_chapter(
        self,
        item,
    ):
        chapter_id = item.data(
            Qt.UserRole
        )

        if not chapter_id:
            return

        self.database.set_progress(
            self.manga_id,
            chapter_id,
            0,
        )

        reader = ChapterReader(
            self.database,
            chapter_id,
            self,
        )

        reader.exec()

        self.refresh_chapters()

    def apply_styles(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #151519;
            }

            QWidget {
                color: #eeeeee;
                font-size: 14px;
            }

            #detailCover {
                background-color: #292930;
                border: 1px solid #34343d;
                border-radius: 10px;
            }

            #detailTitle {
                font-size: 28px;
                font-weight: bold;
            }

            #sectionTitle {
                font-size: 20px;
                font-weight: bold;
            }

            #chapterHint {
                color: #8f8f9b;
                font-size: 12px;
            }

            #favoriteButton {
                border: none;
                border-radius: 8px;
                background-color: #292931;
                font-size: 20px;
                text-align: center;
            }

            #favoriteButton:hover {
                background-color: #353540;
            }

            QComboBox {
                background-color: #292931;
                border: none;
                border-radius: 8px;
                padding: 8px 12px;
            }

            QListWidget {
                background-color: #1d1d23;
                border: 1px solid #303038;
                border-radius: 10px;
                padding: 6px;
            }

            QListWidget::item {
                padding: 12px;
                border-radius: 7px;
            }

            QListWidget::item:selected {
                background-color: #292936;
                border: 1px solid #57506f;
                border-radius: 9px;
                color: white;
            }
        """)


# ============================================================
# CONFIGURACIÓN / ADMINISTRACIÓN
# ============================================================

class SettingsDialog(QDialog):
    def __init__(
        self,
        database,
        parent=None,
    ):
        super().__init__(parent)

        self.database = database

        self.setWindowTitle(
            "Configuración"
        )

        self.resize(
            800,
            600,
        )

        root = QVBoxLayout(self)

        root.setContentsMargins(
            20,
            20,
            20,
            20,
        )

        root.setSpacing(
            14
        )

        title = QLabel(
            "Configuración"
        )

        title.setObjectName(
            "settingsTitle"
        )

        root.addWidget(
            title
        )

        create_manga = QPushButton(
            "+ Crear manga"
        )

        create_manga.setObjectName(
            "primaryButton"
        )

        create_manga.clicked.connect(
            self.create_manga
        )

        root.addWidget(
            create_manga
        )

        section = QLabel(
            "Administrar mangas"
        )

        section.setObjectName(
            "sectionTitle"
        )

        root.addWidget(
            section
        )

        self.manga_list = QListWidget()

        root.addWidget(
            self.manga_list,
            1,
        )

        buttons = QHBoxLayout()

        edit = QPushButton(
            "Editar"
        )

        add_chapter = QPushButton(
            "Agregar capítulo"
        )

        remove_chapter = QPushButton(
            "Eliminar capítulo"
        )

        remove_manga = QPushButton(
            "Eliminar manga"
        )

        remove_manga.setObjectName(
            "dangerButton"
        )

        edit.clicked.connect(
            self.edit_manga
        )

        add_chapter.clicked.connect(
            self.add_chapter
        )

        remove_chapter.clicked.connect(
            self.delete_chapter
        )

        remove_manga.clicked.connect(
            self.delete_manga
        )

        buttons.addWidget(
            edit
        )

        buttons.addWidget(
            add_chapter
        )

        buttons.addWidget(
            remove_chapter
        )

        buttons.addWidget(
            remove_manga
        )

        root.addLayout(
            buttons
        )

        self.reload()
        self.apply_styles()

    def reload(self):
        self.manga_list.clear()

        for manga in self.database.get_manga():
            item = QListWidgetItem(
                manga[1]
            )

            item.setData(
                Qt.UserRole,
                manga[0],
            )

            self.manga_list.addItem(
                item
            )

    def selected_manga(self):
        item = self.manga_list.currentItem()

        if not item:
            return None

        manga_id = item.data(
            Qt.UserRole
        )

        return self.database.get_manga_by_id(
            manga_id
        )

    def create_manga(self):
        dialog = MangaEditor(
            self
        )

        if (
            dialog.exec()
            != QDialog.Accepted
        ):
            return

        data = dialog.get_data()

        self.database.add_manga(
            data["title"],
            data["cover"],
            data["synopsis"],
            data["genres"],
            data["status"],
            False,
            "Leyendo",
        )

        self.reload()

    def edit_manga(self):
        manga = self.selected_manga()

        if not manga:
            return

        dialog = MangaEditor(
            self,
            manga,
        )

        if (
            dialog.exec()
            != QDialog.Accepted
        ):
            return

        data = dialog.get_data()

        self.database.update_manga(
            manga[0],
            data["title"],
            data["cover"],
            data["synopsis"],
            data["genres"],
            data["status"],
            bool(manga[6]),
            manga[7],
        )

        self.reload()

    def add_chapter(self):
        manga = self.selected_manga()

        if not manga:
            return

        chapters = self.database.get_chapters(
            manga[0]
        )

        dialog = AddChapterDialog(
            self,
            len(chapters) + 1,
        )

        if (
            dialog.exec()
            != QDialog.Accepted
        ):
            return

        data = dialog.get_data()

        self.database.add_chapter(
            manga[0],
            data["title"],
            data["content_type"],
            data["content"],
        )

    def delete_chapter(self):
        manga = self.selected_manga()

        if not manga:
            return

        chapters = self.database.get_chapters(
            manga[0]
        )

        if not chapters:
            QMessageBox.information(
                self,
                "Manga Reader",
                "Este manga todavía no tiene capítulos.",
            )

            return

        dialog = QDialog(
            self
        )

        dialog.setWindowTitle(
            "Eliminar capítulo"
        )

        dialog.resize(
            430,
            430,
        )

        layout = QVBoxLayout(
            dialog
        )

        chapter_list = QListWidget()

        for chapter in chapters:
            item = QListWidgetItem(
                chapter[2]
            )

            item.setData(
                Qt.UserRole,
                chapter[0],
            )

            chapter_list.addItem(
                item
            )

        layout.addWidget(
            chapter_list
        )

        delete_button = QPushButton(
            "Eliminar seleccionado"
        )

        delete_button.setObjectName(
            "dangerButton"
        )

        layout.addWidget(
            delete_button
        )

        def remove():
            item = chapter_list.currentItem()

            if not item:
                return

            chapter_id = item.data(
                Qt.UserRole
            )

            settings = QSettings(
                APP_ORG,
                APP_NAME,
            )

            skip = settings.value(
                "skip_delete_chapter_confirmation",
                False,
                type=bool,
            )

            if not skip:
                confirm = ConfirmDeleteDialog(
                    "Eliminar capítulo",
                    (
                        f'¿Eliminar “{item.text()}” de Manga Reader?\n\n'
                        "Los archivos originales no serán borrados."
                    ),
                    dialog,
                )

                if (
                    confirm.exec()
                    != QDialog.Accepted
                ):
                    return

                if confirm.skip_future():
                    settings.setValue(
                        "skip_delete_chapter_confirmation",
                        True,
                    )

            self.database.delete_chapter(
                chapter_id
            )

            dialog.accept()

        delete_button.clicked.connect(
            remove
        )

        dialog.exec()

    def delete_manga(self):
        manga = self.selected_manga()

        if not manga:
            return

        settings = QSettings(
            APP_ORG,
            APP_NAME,
        )

        skip = settings.value(
            "skip_delete_manga_confirmation",
            False,
            type=bool,
        )

        if not skip:
            confirm = ConfirmDeleteDialog(
                "Eliminar manga",
                (
                    f'¿Eliminar “{manga[1]}” de Manga Reader?\n\n'
                    "Los capítulos y la ficha desaparecerán de la aplicación, "
                    "pero los archivos originales del disco no serán borrados."
                ),
                self,
            )

            if (
                confirm.exec()
                != QDialog.Accepted
            ):
                return

            if confirm.skip_future():
                settings.setValue(
                    "skip_delete_manga_confirmation",
                    True,
                )

        self.database.delete_manga(
            manga[0]
        )

        self.reload()

    def apply_styles(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #151519;
            }

            QWidget {
                color: #eeeeee;
                font-size: 14px;
            }

            #settingsTitle {
                font-size: 27px;
                font-weight: bold;
            }

            #sectionTitle {
                font-size: 18px;
                font-weight: bold;
            }

            QListWidget {
                background-color: #1d1d23;
                border: 1px solid #303038;
                border-radius: 10px;
                padding: 6px;
            }

            QListWidget::item {
                padding: 11px;
                border-radius: 7px;
            }

            QListWidget::item:selected {
                background-color: #6d5dfc;
                color: white;
            }

            QPushButton {
                border: none;
                border-radius: 8px;
                padding: 10px 13px;
                background-color: #292931;
            }

            QPushButton:hover {
                background-color: #353540;
            }

            #primaryButton {
                background-color: #6d5dfc;
                color: white;
                font-weight: bold;
            }

            #dangerButton {
                background-color: #a94040;
                color: white;
            }
        """)


# ============================================================
# PORTADA CLICABLE
# ============================================================

class MangaCover(QLabel):
    def __init__(
        self,
        manga_id,
        callback,
        parent=None,
    ):
        super().__init__(parent)

        self.manga_id = manga_id
        self.callback = callback

        self.setCursor(
            QCursor(
                Qt.PointingHandCursor
            )
        )

    def mousePressEvent(
        self,
        event,
    ):
        if (
            event.button()
            == Qt.LeftButton
        ):
            self.callback(
                self.manga_id
            )

        super().mousePressEvent(
            event
        )


# ============================================================
# TARJETA DE MANGA
# ============================================================

class MangaCard(QFrame):
    def __init__(
        self,
        manga,
        open_callback,
        continue_label=None,
    ):
        super().__init__()

        self.manga = manga

        self.setObjectName(
            "mangaCard"
        )

        self.setFixedWidth(
            190
        )

        layout = QVBoxLayout(
            self
        )

        layout.setContentsMargins(
            10,
            10,
            10,
            12,
        )

        layout.setSpacing(
            7
        )

        cover = MangaCover(
            manga[0],
            open_callback,
        )

        cover.setFixedSize(
            170,
            240,
        )

        cover.setAlignment(
            Qt.AlignCenter
        )

        cover.setText(
            "Sin portada"
        )

        cover.setObjectName(
            "cover"
        )

        if manga[2]:
            pixmap = QPixmap(
                manga[2]
            )

            if not pixmap.isNull():
                cover.setPixmap(
                    pixmap.scaled(
                        cover.size(),
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation,
                    )
                )

        title = QLabel(
            manga[1]
        )

        title.setAlignment(
            Qt.AlignCenter
        )

        title.setWordWrap(
            True
        )

        title.setObjectName(
            "mangaTitle"
        )

        layout.addWidget(
            cover
        )

        layout.addWidget(
            title
        )

        if continue_label:
            chapter_label = QLabel(
                continue_label
            )

            chapter_label.setAlignment(
                Qt.AlignCenter
            )

            chapter_label.setObjectName(
                "continueLabel"
            )

            layout.addWidget(
                chapter_label
            )


# ============================================================
# VENTANA PRINCIPAL
# ============================================================

class MangaReader(QMainWindow):
    def __init__(self):
        super().__init__()

        self.database = Database()

        self.current_filter = "all"
        self.sidebar_open = True

        self.setWindowTitle(
            "Manga Reader"
        )

        self.resize(
            1280,
            800,
        )

        self.build_ui()
        self.refresh_library()

    def build_ui(self):
        central = QWidget()

        self.setCentralWidget(
            central
        )

        main = QHBoxLayout(
            central
        )

        main.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        main.setSpacing(
            0
        )

        # ----------------------------------------------------
        # SIDEBAR
        # ----------------------------------------------------

        self.sidebar = QFrame()

        self.sidebar.setObjectName(
            "sidebar"
        )

        self.sidebar.setFixedWidth(
            205
        )

        sidebar_layout = QVBoxLayout(
            self.sidebar
        )

        sidebar_layout.setContentsMargins(
            14,
            18,
            14,
            18,
        )

        sidebar_layout.setSpacing(
            10
        )

        top = QHBoxLayout()

        logo = QLabel(
            "Manga Reader"
        )

        logo.setObjectName(
            "logo"
        )

        self.sidebar_button = QPushButton(
            "☰"
        )

        self.sidebar_button.setFixedWidth(
            38
        )

        self.sidebar_button.clicked.connect(
            self.toggle_sidebar
        )

        top.addWidget(
            logo
        )

        top.addStretch()

        top.addWidget(
            self.sidebar_button
        )

        sidebar_layout.addLayout(
            top
        )

        library_button = QPushButton(
            "Biblioteca"
        )

        library_button.clicked.connect(
            lambda:
                self.set_filter("all")
        )

        sidebar_layout.addWidget(
            library_button
        )

        sidebar_layout.addSpacing(
            15
        )

        network_title = QLabel(
            "Red local"
        )

        network_title.setObjectName(
            "smallTitle"
        )

        sidebar_layout.addWidget(
            network_title
        )

        network_button = QPushButton(
            "Bibliotecas en red"
        )

        network_button.clicked.connect(
            self.network_placeholder
        )

        sidebar_layout.addWidget(
            network_button
        )

        sidebar_layout.addStretch()

        settings_button = QPushButton(
            "Configuración"
        )

        settings_button.clicked.connect(
            self.open_settings
        )

        sidebar_layout.addWidget(
            settings_button
        )

        main.addWidget(
            self.sidebar
        )

        # ----------------------------------------------------
        # CONTENIDO
        # ----------------------------------------------------

        content = QWidget()

        content_layout = QVBoxLayout(
            content
        )

        content_layout.setContentsMargins(
            20,
            18,
            20,
            20,
        )

        content_layout.setSpacing(
            10
        )

        topbar = QHBoxLayout()

        self.menu_button = QPushButton(
            "☰"
        )

        self.menu_button.setFixedSize(
            38,
            38,
        )

        self.menu_button.clicked.connect(
            self.toggle_sidebar
        )

        self.menu_button.hide()

        self.page_title = QLabel(
            "Mi biblioteca"
        )

        self.page_title.setObjectName(
            "pageTitle"
        )

        self.search = QLineEdit()

        self.search.setPlaceholderText(
            "Buscar manga..."
        )

        self.search.setMaximumWidth(
            300
        )

        self.search.textChanged.connect(
            self.refresh_library
        )

        topbar.addWidget(
            self.menu_button
        )

        topbar.addWidget(
            self.page_title
        )

        topbar.addStretch()

        topbar.addWidget(
            self.search
        )

        content_layout.addLayout(
            topbar
        )

        filter_frame = QFrame()

        filter_frame.setObjectName(
            "filterBar"
        )

        filter_layout = QHBoxLayout(
            filter_frame
        )

        filter_layout.setContentsMargins(
            6,
            6,
            6,
            6,
        )

        filter_layout.setSpacing(
            4
        )

        filter_options = [
            ("continue", "Continuar"),
            ("favorite", "Favoritos"),
            ("reading", "Leyendo"),
            ("finished", "Finalizados"),
        ]

        self.filter_buttons = {}

        for key, text in filter_options:
            button = QPushButton(
                text
            )

            button.setObjectName(
                "filterButton"
            )

            button.clicked.connect(
                lambda checked=False, filter_key=key:
                    self.set_filter(
                        filter_key
                    )
            )

            filter_layout.addWidget(
                button,
                1,
            )

            self.filter_buttons[key] = (
                button
            )

        content_layout.addWidget(
            filter_frame
        )

        self.scroll = QScrollArea()

        self.scroll.setWidgetResizable(
            True
        )

        self.scroll.setFrameShape(
            QFrame.NoFrame
        )

        self.library_container = QWidget()

        self.library_layout = QVBoxLayout(
            self.library_container
        )

        self.library_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.empty_label = QLabel()

        self.empty_label.setAlignment(
            Qt.AlignCenter
        )

        self.empty_label.setObjectName(
            "emptyLabel"
        )

        self.library_layout.addWidget(
            self.empty_label,
            1,
        )

        self.grid_widget = QWidget()

        self.grid = QGridLayout(
            self.grid_widget
        )

        self.grid.setContentsMargins(
            8,
            10,
            8,
            10,
        )

        self.grid.setAlignment(
            Qt.AlignTop
            | Qt.AlignLeft
        )

        self.grid.setHorizontalSpacing(
            20
        )

        self.grid.setVerticalSpacing(
            20
        )

        self.library_layout.addWidget(
            self.grid_widget
        )

        self.scroll.setWidget(
            self.library_container
        )

        content_layout.addWidget(
            self.scroll,
            1,
        )

        main.addWidget(
            content,
            1,
        )

        self.apply_styles()

    def toggle_sidebar(self):
        if self.sidebar_open:
            self.sidebar.hide()
            self.menu_button.show()
        else:
            self.sidebar.show()
            self.menu_button.hide()

        self.sidebar_open = (
            not self.sidebar_open
        )

    def set_filter(
        self,
        filter_name,
    ):
        self.current_filter = (
            filter_name
        )

        titles = {
            "all": "Mi biblioteca",
            "continue": "Continuar",
            "favorite": "Favoritos",
            "reading": "Leyendo",
            "finished": "Finalizados",
        }

        self.page_title.setText(
            titles.get(
                filter_name,
                "Mi biblioteca",
            )
        )

        self.refresh_library()

    def open_settings(self):
        dialog = SettingsDialog(
            self.database,
            self,
        )

        dialog.exec()

        self.refresh_library()

    def open_manga(
        self,
        manga_id,
    ):
        dialog = MangaDetails(
            self.database,
            manga_id,
            self,
        )

        dialog.exec()

        self.refresh_library()

    def network_placeholder(self):
        QMessageBox.information(
            self,
            "Red local",
            (
                "La biblioteca por red local está reservada "
                "para la siguiente etapa."
            ),
        )

    def refresh_library(self):
        while self.grid.count():
            item = self.grid.takeAt(
                0
            )

            widget = item.widget()

            if widget:
                widget.deleteLater()

        search = (
            self.search
            .text()
            .lower()
            .strip()
        )

        cards = []

        if (
            self.current_filter
            == "continue"
        ):
            rows = (
                self.database
                .get_continue_manga()
            )

            for row in rows:
                manga = row[:8]
                chapter_title = row[8]

                if (
                    search
                    and search
                    not in manga[1].lower()
                ):
                    continue

                cards.append(
                    (
                        manga,
                        chapter_title,
                    )
                )

        else:
            mangas = (
                self.database
                .get_manga()
            )

            for manga in mangas:
                title = manga[1]
                favorite = bool(
                    manga[6]
                )
                reading_state = (
                    manga[7]
                )

                if (
                    search
                    and search
                    not in title.lower()
                ):
                    continue

                if (
                    self.current_filter
                    == "all"
                ):
                    cards.append(
                        (
                            manga,
                            None,
                        )
                    )
                    continue

                if (
                    self.current_filter
                    == "favorite"
                ):
                    if (
                        favorite
                        and reading_state
                        != "Finalizado"
                    ):
                        cards.append(
                            (
                                manga,
                                None,
                            )
                        )
                    continue

                if (
                    self.current_filter
                    == "reading"
                ):
                    if (
                        reading_state
                        == "Leyendo"
                    ):
                        cards.append(
                            (
                                manga,
                                None,
                            )
                        )
                    continue

                if (
                    self.current_filter
                    == "finished"
                ):
                    if (
                        reading_state
                        == "Finalizado"
                    ):
                        cards.append(
                            (
                                manga,
                                None,
                            )
                        )
                    continue

        if not cards:
            messages = {
                "all":
                    "Todavía no tienes mangas en tu biblioteca.",

                "continue":
                    "No tienes mangas pendientes para continuar.",

                "favorite":
                    "Todavía no tienes mangas favoritos.",

                "reading":
                    "No tienes mangas marcados como Leyendo.",

                "finished":
                    "No tienes mangas finalizados.",
            }

            self.empty_label.setText(
                messages.get(
                    self.current_filter,
                    "",
                )
            )

            self.empty_label.show()

            self.grid_widget.hide()

            return

        self.empty_label.hide()

        self.grid_widget.show()

        columns = 5

        for index, (
            manga,
            continue_label,
        ) in enumerate(cards):

            card = MangaCard(
                manga,
                self.open_manga,
                continue_label,
            )

            self.grid.addWidget(
                card,
                index // columns,
                index % columns,
            )

    def apply_styles(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #151519;
            }

            QWidget {
                color: #eeeeee;
                font-size: 14px;
            }

            #sidebar {
                background-color: #1d1d23;
                border-right: 1px solid #2c2c34;
            }

            #logo {
                font-size: 19px;
                font-weight: bold;
            }

            #smallTitle {
                color: #8f8f9b;
                font-weight: bold;
                font-size: 12px;
            }

            #pageTitle {
                font-size: 27px;
                font-weight: bold;
            }

            QPushButton {
                border: none;
                border-radius: 8px;
                padding: 10px 12px;
                background-color: transparent;
                text-align: left;
            }

            QPushButton:hover {
                background-color: #292931;
            }

            QLineEdit {
                background-color: #202027;
                border: 1px solid #34343d;
                border-radius: 8px;
                padding: 10px;
            }

            QLineEdit:focus {
                border: 1px solid #6d5dfc;
            }

            #filterBar {
                background-color: #19191e;
                border: 1px solid #292932;
                border-radius: 10px;
            }

            #filterButton {
                text-align: center;
                font-weight: bold;
                padding: 14px;
            }

            #filterButton:hover {
                background-color: #292931;
            }

            #mangaCard {
                background-color: #1c1c22;
                border: 1px solid #292932;
                border-radius: 10px;
            }

            #mangaCard:hover {
                border: 1px solid #555566;
            }

            #cover {
                background-color: #292930;
                border-radius: 8px;
                color: #8b8b96;
            }

            #mangaTitle {
                font-weight: bold;
            }

            #continueLabel {
                color: #8f83ff;
                font-weight: bold;
                font-size: 13px;
            }

            #emptyLabel {
                color: #9999a5;
                font-size: 16px;
            }

            QScrollArea {
                background-color: transparent;
            }
        """)


# ============================================================
# INICIAR
# ============================================================

if __name__ == "__main__":
    app = QApplication(
        sys.argv
    )

    # Identidad de la aplicación para KDE / Plasma / Wayland.
    # Debe coincidir con manga-reader.desktop.
    app.setApplicationName(
        "manga-reader"
    )

    app.setApplicationDisplayName(
        "Manga Reader"
    )

    app.setDesktopFileName(
        "manga-reader"
    )

    # En el paquete el icono se instala junto al código.
    local_icon = (
        Path(__file__).resolve().parent
        / "manga-reader-cat.png"
    )

    system_icon = Path(
        "/usr/share/icons/hicolor/"
        "256x256/apps/"
        "manga-reader-cat.png"
    )

    icon_path = (
        local_icon
        if local_icon.exists()
        else system_icon
    )

    if icon_path.exists():
        app.setWindowIcon(
            QIcon(str(icon_path))
        )

    window = MangaReader()

    if icon_path.exists():
        window.setWindowIcon(
            QIcon(str(icon_path))
        )

    window.show()

    sys.exit(
        app.exec()
    )
