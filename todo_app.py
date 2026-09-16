import sys
import json
import os
from datetime import datetime, timedelta
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QPainter, QColor, QPen
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QTextEdit, QScrollArea, QFrame, QComboBox, 
    QDialog, QCheckBox, QMessageBox, QPushButton
)

DATA_FILE = "tasks_data.json"
PASTEL_COLORS = [
    ("#E58A73", "#FFFFFF"), ("#C6A97D", "#FFFFFF"), ("#6FDE81", "#1C1C1E"),
    ("#C6A8D6", "#1C1C1E"), ("#97CCE3", "#1C1C1E"), ("#72BFE8", "#FFFFFF"),
    ("#E364E0", "#FFFFFF"), ("#EADB68", "#1C1C1E")
]

# 클래식 리갈 패드(노란 줄노트 + 좌측 빨간 이중선) 배경 위젯
class LegalPadBackground(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("LegalPad")

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # 1. 전체 따뜻한 노란 메모지 배경
        painter.fillRect(self.rect(), QColor("#FFF9A6"))

        w = self.width()
        h = self.height()

        # 2. 청록색 가로 줄노트 (28px 간격)
        pen_line = QPen(QColor("#7BD1B8"), 1)
        painter.setPen(pen_line)
        line_spacing = 32
        for y in range(50, h, line_spacing):
            painter.drawLine(0, y, w, y)

        # 3. 좌측 세로 빨간색 이중 마진선
        pen_red = QPen(QColor("#E8706D"), 1.2)
        painter.setPen(pen_red)
        margin_x = 42
        painter.drawLine(margin_x, 0, margin_x, h)
        painter.drawLine(margin_x + 3, 0, margin_x + 3, h)


class CustomTaskRow(QFrame):
    changed = pyqtSignal()
    delete_requested = pyqtSignal(object)

    def __init__(self, data, scale_factor, settings, parent=None):
        super().__init__(parent)
        self.data = data
        self.scale_factor = scale_factor
        self.settings = settings
        self.init_ui()

    def init_ui(self):
        f_size = max(10, int(13 * self.scale_factor))
        meta_size = max(8, int(9 * self.scale_factor))
        
        # 줄노트 청록 가로선과 어우러지게 투명 처리
        self.setStyleSheet("background: transparent;")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 2, 8, 2)
        layout.setSpacing(int(8 * self.scale_factor))

        # 체크박스 (아이폰 사각 체크)
        self.chk = QCheckBox()
        self.chk.setChecked(self.data.get("completed", False))
        chk_wh = int(17 * self.scale_factor)
        self.chk.setStyleSheet(f"""
            QCheckBox::indicator {{
                width: {chk_wh}px; height: {chk_wh}px;
                border: 1.5px solid #8E8E93; border-radius: 3px; background: #FFFFFF;
            }}
            QCheckBox::indicator:checked {{
                background-color: #E5A100; border-color: #E5A100;
            }}
        """)
        self.chk.toggled.connect(self.on_toggle)
        layout.addWidget(self.chk)

        # 줄노트 본문 상시 수정
        self.line_edit = QLineEdit(self.data.get("text", ""))
        self.line_edit.setFrame(False)
        self.line_edit.setFont(QFont("Apple SD Gothic Neo", f_size))
        self.line_edit.setStyleSheet("background: transparent; border: none; padding: 2px 0;")
        self.line_edit.textChanged.connect(self.on_text_change)
        layout.addWidget(self.line_edit, stretch=1)

        # 오른쪽 2줄 날짜/시간
        self.time_label = QLabel()
        self.time_label.setFont(QFont("Apple SD Gothic Neo", meta_size))
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.time_label.setStyleSheet("color: #7A7A7E; background: transparent;")
        layout.addWidget(self.time_label)

        # 삭제 버튼
        self.btn_del = QPushButton("✕")
        self.btn_del.setFixedSize(int(18 * self.scale_factor), int(18 * self.scale_factor))
        self.btn_del.setStyleSheet("QPushButton { border: none; color: #B0B0B5; font-weight: bold; background: transparent; } QPushButton:hover { color: #FF3B30; }")
        self.btn_del.clicked.connect(lambda: self.delete_requested.emit(self))
        layout.addWidget(self.btn_del)

        self.update_style()
        self.update_time_display()

    def on_toggle(self, checked):
        self.data["completed"] = checked
        if checked:
            self.data["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        else:
            self.data["completed_at"] = None
        self.update_style()
        self.update_time_display()
        self.changed.emit()

    def on_text_change(self, text):
        self.data["text"] = text
        self.changed.emit()

    def update_style(self):
        font = self.line_edit.font()
        font.setStrikeOut(self.data.get("completed", False))
        self.line_edit.setFont(font)
        if self.data.get("completed", False):
            self.line_edit.setStyleSheet("color: #9E9E9E; background: transparent; border: none;")
        else:
            if self.data.get("is_tag_header", False):
                font.setBold(True)
                self.line_edit.setFont(font)
                self.line_edit.setStyleSheet("color: #222222; background: transparent; font-weight: bold; border: none;")
            else:
                self.line_edit.setStyleSheet("color: #222222; background: transparent; border: none;")

    def update_time_display(self):
        mode = self.settings.get("datetime_mode", "both")
        if mode == "none":
            self.time_label.setText("")
            return

        def fmt(dt_str):
            if not dt_str: return ""
            try:
                dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
                if mode == "date_only": return dt.strftime("%Y.%m.%d")
                if mode == "time_only": return dt.strftime("%H:%M")
                return dt.strftime("%y.%m.%d %H:%M")
            except:
                return dt_str

        lines = []
        c_str = fmt(self.data.get("created_at"))
        if c_str: lines.append(f"등록: {c_str}")
        if self.data.get("completed_at"):
            d_str = fmt(self.data.get("completed_at"))
            lines.append(f"완료: {d_str}")

        self.time_label.setText("\n".join(lines))


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("커스텀 모듈 설정")
        self.setFixedSize(300, 240)
        self.settings = settings
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self.chk_tag = QCheckBox("상단 파스텔 태그바 표시")
        self.chk_tag.setChecked(self.settings.get("show_tags", True))
        layout.addWidget(self.chk_tag)

        self.chk_memo = QCheckBox("하단 일상 메모장(1/3) 표시")
        self.chk_memo.setChecked(self.settings.get("show_memo", True))
        layout.addWidget(self.chk_memo)

        layout.addWidget(QLabel("우측 일시 표시 형식:"))
        self.combo_dt = QComboBox()
        self.combo_dt.addItems(["날짜+시간 모두 표시", "날짜만 표시", "시간만 표시", "표시 안 함"])
        mode_map = {"both": 0, "date_only": 1, "time_only": 2, "none": 3}
        self.combo_dt.setCurrentIndex(mode_map.get(self.settings.get("datetime_mode", "both"), 0))
        layout.addWidget(self.combo_dt)

        btn_save = QPushButton("적용 완료")
        btn_save.setStyleSheet("background: #E5A100; color: white; border-radius: 6px; padding: 8px; font-weight: bold;")
        btn_save.clicked.connect(self.save_and_close)
        layout.addWidget(btn_save)

    def save_and_close(self):
        self.settings["show_tags"] = self.chk_tag.isChecked()
        self.settings["show_memo"] = self.chk_memo.isChecked()
        rev_map = {0: "both", 1: "date_only", 2: "time_only", 3: "none"}
        self.settings["datetime_mode"] = rev_map[self.combo_dt.currentIndex()]
        self.accept()


class ModernTodoApp(QWidget):
    def __init__(self):
        super().__init__()
        self.old_pos = None
        self.scale_factor = 1.0
        self.load_data()
        self.init_frameless_window()
        self.build_ui()
        self.apply_scale_factor()

    def init_frameless_window(self):
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(560, 780)

    def build_ui(self):
        # 짤의 리갈 패드 배경 적용
        self.main_container = LegalPadBackground(self)
        self.main_container.setStyleSheet("border-radius: 14px; border: 1px solid #D6CE9A;")
        
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(self.main_container)

        self.root_layout = QVBoxLayout(self.main_container)
        self.root_layout.setContentsMargins(16, 12, 16, 16)
        self.root_layout.setSpacing(8)

        # 미니멀 상단바 (창 이동용)
        self.header_bar = QHBoxLayout()
        self.lbl_title = QLabel("📝 메모 숙제장")
        self.lbl_title.setStyleSheet("font-weight: bold; color: #3A382A; background: transparent;")
        self.header_bar.addWidget(self.lbl_title)
        self.header_bar.addStretch()

        self.btn_settings = QPushButton("커스텀")
        self.btn_settings.setStyleSheet("QPushButton { border: 1px solid #C4BC87; border-radius: 5px; padding: 3px 8px; font-size: 11px; background: #FFFDF0; } QPushButton:hover { background: #FFFFFF; }")
        self.btn_settings.clicked.connect(self.open_settings)
        self.header_bar.addWidget(self.btn_settings)

        self.scale_combo = QComboBox()
        self.scale_combo.addItems(["80%", "90%", "100%", "110%", "125%", "150%"])
        self.scale_combo.setCurrentText(f"{int(self.scale_factor * 100)}%")
        self.scale_combo.setStyleSheet("QComboBox { border: 1px solid #C4BC87; border-radius: 5px; padding: 2px 5px; font-size: 11px; background: #FFFDF0; }")
        self.scale_combo.currentTextChanged.connect(self.on_scale_change)
        self.header_bar.addWidget(self.scale_combo)

        btn_min = QPushButton("—")
        btn_min.setFixedSize(22, 22)
        btn_min.setStyleSheet("QPushButton { border: none; background: transparent; font-size: 11px; } QPushButton:hover { background: #EAE3AB; border-radius: 11px; }")
        btn_min.clicked.connect(self.showMinimized)
        self.header_bar.addWidget(btn_min)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(22, 22)
        btn_close.setStyleSheet("QPushButton { border: none; background: transparent; font-size: 12px; } QPushButton:hover { background: #FF3B30; color: white; border-radius: 11px; }")
        btn_close.clicked.connect(self.close)
        self.header_bar.addWidget(btn_close)

        self.root_layout.addLayout(self.header_bar)

        # 파스텔 태그 바
        self.tag_scroll = QScrollArea()
        self.tag_scroll.setWidgetResizable(True)
        self.tag_scroll.setFixedHeight(36)
        self.tag_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.tag_scroll.setStyleSheet("background: transparent;")
        self.tag_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tag_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.tag_widget = QWidget()
        self.tag_widget.setStyleSheet("background: transparent;")
        self.tag_layout = QHBoxLayout(self.tag_widget)
        self.tag_layout.setContentsMargins(0, 0, 0, 0)
        self.tag_layout.setSpacing(6)
        self.tag_scroll.setWidget(self.tag_widget)
        self.root_layout.addWidget(self.tag_scroll)
        self.render_tags()

        # 줄노트 할 일 영역 (상단 2/3)
        self.task_scroll = QScrollArea()
        self.task_scroll.setWidgetResizable(True)
        self.task_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.task_scroll.setStyleSheet("background: transparent;")
        
        self.task_container = QWidget()
        self.task_container.setStyleSheet("background: transparent;")
        self.task_layout = QVBoxLayout(self.task_container)
        self.task_layout.setContentsMargins(0, 0, 4, 0)
        self.task_layout.setSpacing(0)
        self.task_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.task_scroll.setWidget(self.task_container)
        self.root_layout.addWidget(self.task_scroll, stretch=2)

        # 다음 줄 클릭 입력창
        self.new_line_edit = QLineEdit()
        self.new_line_edit.setPlaceholderText("+ 다음 줄을 눌러 새 숙제 작성...")
        self.new_line_edit.setFrame(False)
        self.new_line_edit.returnPressed.connect(self.commit_new_task)
        self.root_layout.addWidget(self.new_line_edit)

        # 하단 1/3 일상 메모장
        self.memo_frame = QFrame()
        self.memo_frame.setStyleSheet("background: rgba(255, 255, 255, 0.45); border: 1px solid #D6CE9A; border-radius: 10px; padding: 4px;")
        memo_inner_layout = QVBoxLayout(self.memo_frame)
        memo_inner_layout.setContentsMargins(6, 6, 6, 6)

        lbl_memo_title = QLabel("자유 메모")
        lbl_memo_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #7A7246; background: transparent;")
        memo_inner_layout.addWidget(lbl_memo_title)

        self.txt_memo = QTextEdit()
        self.txt_memo.setFrameShape(QFrame.Shape.NoFrame)
        self.txt_memo.setStyleSheet("background: transparent; font-family: 'Apple SD Gothic Neo', sans-serif; color: #222222;")
        self.txt_memo.setPlainText(self.memo_text)
        self.txt_memo.textChanged.connect(self.on_memo_change)
        memo_inner_layout.addWidget(self.txt_memo)

        self.root_layout.addWidget(self.memo_frame, stretch=1)

        self.refresh_task_list()
        self.apply_module_visibility()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() < 40:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.pos() + delta)
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.old_pos = None

    def render_tags(self):
        while self.tag_layout.count():
            item = self.tag_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        for idx, tag_text in enumerate(self.tags):
            bg_c, fg_c = PASTEL_COLORS[idx % len(PASTEL_COLORS)]
            tag_box = QFrame()
            tag_box.setStyleSheet(f"background-color: {bg_c}; border-radius: 11px; padding: 1px 6px;")
            tb_layout = QHBoxLayout(tag_box)
            tb_layout.setContentsMargins(4, 1, 4, 1)
            tb_layout.setSpacing(4)

            btn_tag = QPushButton(f"#{tag_text}")
            btn_tag.setStyleSheet(f"border: none; color: {fg_c}; font-weight: bold; font-size: 11px; background: transparent;")
            btn_tag.clicked.connect(lambda _, t=tag_text: self.insert_tag_header(t))
            tb_layout.addWidget(btn_tag)

            btn_x = QPushButton("✕")
            btn_x.setStyleSheet(f"border: none; color: {fg_c}; font-size: 10px; background: transparent;")
            btn_x.clicked.connect(lambda _, t=tag_text: self.confirm_delete_tag(t))
            tb_layout.addWidget(btn_x)

            self.tag_layout.addWidget(tag_box)

        btn_add_tag = QPushButton("+ 태그")
        btn_add_tag.setStyleSheet("border: 1px dashed #A69E68; border-radius: 11px; padding: 1px 8px; font-size: 11px; color: #5C5528; background: #FFFEEA;")
        btn_add_tag.clicked.connect(self.prompt_new_tag)
        self.tag_layout.addWidget(btn_add_tag)
        self.tag_layout.addStretch()

    def insert_tag_header(self, tag_name):
        new_row = {
            "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
            "text": f"[{tag_name}] ",
            "completed": False,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "completed_at": None,
            "is_tag_header": True
        }
        self.tasks.insert(0, new_row)
        self.save_data()
        self.refresh_task_list()

    def prompt_new_tag(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("새 태그 등록")
        l = QVBoxLayout(dlg)
        inp = QLineEdit()
        inp.setPlaceholderText("태그명을 입력하세요")
        l.addWidget(inp)
        btn = QPushButton("추가")
        btn.clicked.connect(lambda: dlg.accept())
        l.addWidget(btn)
        if dlg.exec() and inp.text().strip():
            self.tags.append(inp.text().strip().replace("#", ""))
            self.save_data()
            self.render_tags()

    def confirm_delete_tag(self, tag_name):
        reply = QMessageBox.question(self, "태그 삭제", f"'{tag_name}' 태그를 삭제하시겠습니까?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.tags = [t for t in self.tags if t != tag_name]
            self.save_data()
            self.render_tags()

    def commit_new_task(self):
        text = self.new_line_edit.text().strip()
        if not text: return
        self.tasks.append({
            "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
            "text": text,
            "completed": False,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "completed_at": None
        })
        self.new_line_edit.clear()
        self.save_data()
        self.refresh_task_list()

    def refresh_task_list(self):
        while self.task_layout.count():
            item = self.task_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        now = datetime.now()
        filtered = []
        for t in self.tasks:
            if t.get("completed") and t.get("completed_at"):
                c_time = datetime.strptime(t["completed_at"], "%Y-%m-%d %H:%M")
                if now - c_time > timedelta(days=1):
                    continue
            filtered.append(t)

        for t_data in filtered:
            row = CustomTaskRow(t_data, self.scale_factor, self.settings)
            row.changed.connect(self.save_data)
            row.delete_requested.connect(self.remove_task_row)
            self.task_layout.addWidget(row)

    def remove_task_row(self, row_widget):
        self.tasks = [t for t in self.tasks if t["id"] != row_widget.data["id"]]
        self.save_data()
        self.refresh_task_list()

    def on_memo_change(self):
        self.memo_text = self.txt_memo.toPlainText()
        self.save_data()

    def on_scale_change(self, text):
        val = int(text.replace("%", "")) / 100.0
        self.scale_factor = val
        self.apply_scale_factor()
        self.refresh_task_list()

    def apply_scale_factor(self):
        s = self.scale_factor
        f_main = max(11, int(13 * s))
        self.lbl_title.setFont(QFont("Apple SD Gothic Neo", int(14 * s)))
        self.new_line_edit.setFont(QFont("Apple SD Gothic Neo", f_main))
        self.new_line_edit.setStyleSheet(f"border-bottom: 1px dashed #A69E68; padding: {int(5 * s)}px 2px; color: #6E6738; background: transparent;")
        self.txt_memo.setFont(QFont("Apple SD Gothic Neo", f_main))

    def open_settings(self):
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec():
            self.apply_module_visibility()
            self.save_data()
            self.refresh_task_list()

    def apply_module_visibility(self):
        self.tag_scroll.setVisible(self.settings.get("show_tags", True))
        self.memo_frame.setVisible(self.settings.get("show_memo", True))

    def load_data(self):
        self.tasks = []
        self.tags = ["코지몬", "피치몬", "제우스", "숙제의 바다", "잘 모르는 피치몬", "잘하네", "약올리는 코지몬", "대단하십니다"]
        self.memo_text = ""
        self.settings = {"show_tags": True, "show_memo": True, "datetime_mode": "both"}

        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    self.tasks = d.get("tasks", [])
                    self.tags = d.get("tags", self.tags)
                    self.memo_text = d.get("memo", "")
                    self.settings = d.get("settings", self.settings)
            except:
                pass

    def save_data(self):
        d = {
            "tasks": self.tasks,
            "tags": self.tags,
            "memo": self.memo_text,
            "settings": self.settings
        }
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ModernTodoApp()
    window.show()
    sys.exit(app.exec())