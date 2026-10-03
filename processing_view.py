"""Lightweight processing screen, mounted only while a media job is active."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QLabel, QPlainTextEdit, QProgressBar, QPushButton, QVBoxLayout, QWidget,
)


class EncodingView(QWidget):
    def __init__(self, parent, cancel_callback, return_callback):
        super().__init__(parent)
        self._return_callback = return_callback
        self.active = True
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.addStretch()
        box = QFrame()
        box.setObjectName("card")
        box.setMaximumWidth(520)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(14)
        self.title = QLabel()
        self.title.setObjectName("title")
        layout.addWidget(self.title)
        self.description = QLabel()
        self.description.setObjectName("muted")
        self.description.setWordWrap(True)
        layout.addWidget(self.description)
        self.percent = QLabel("0%")
        layout.addWidget(self.percent)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        layout.addWidget(self.bar)
        self.details_button = QPushButton()
        self.details_button.clicked.connect(self._toggle_details)
        self.details_button.hide()
        layout.addWidget(self.details_button)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setMaximumHeight(110)
        self.details.hide()
        layout.addWidget(self.details)
        self.action = QPushButton()
        self.action.clicked.connect(cancel_callback)
        layout.addWidget(self.action)
        outer.addWidget(box, alignment=Qt.AlignmentFlag.AlignHCenter)
        outer.addStretch()

    def _toggle_details(self):
        self.details.setVisible(not self.details.isVisible())

    def finish(self, text, action_text):
        self.active = False
        self.description.setText(text)
        self.action.setText(action_text)
        self.action.clicked.disconnect()
        self.action.clicked.connect(self._return_callback)
