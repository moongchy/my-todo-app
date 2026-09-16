import sys
import json
import os
from datetime import datetime, timedelta
from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from PyQt6.QtGui import QFont
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
        meta_size = max(8, int(10 * self.scale_factor))
        self.setStyleSheet("background: transparent; border-bottom: 0.5px solid #E5E5EA;")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 6, 4, 6)
        layout.setSpacing(int(8 * self.scale_factor))

        # 6. 아이폰 메모 스타일 사각 체크박스
        self.chk = QCheckBox()
        self.chk.setChecked(self.data.get("completed", False))
        chk_wh = int(18 * self.scale_factor)
        self.chk.setStyleSheet(f"""
            QCheckBox::indicator {{
                width: {chk_wh}px; height: {chk_wh}px;
                border: 1.5px solid #C7C7CC; border-radius: 4px; background: #FFFFFF;
            }}
            QCheckBox::indicator:checked {{
                background-color: #E5A100; border-color: #E5A100;
            }}
        """)
        self.chk.toggled.connect(self.on_toggle)
        layout.addWidget(self.chk)

        # 4 & 5. 줄노트 스타일 텍스트 상시 수정
        self.line_edit = QLineEdit(self.data.get("text", ""))
        self.line_edit.setFrame(False)
        self.line_edit.setFont(QFont("Apple SD Gothic Neo", f_size))
        self.line_edit.setStyleSheet("background: transparent; border: none; padding: 2px 0;")
        self.line_edit.textChanged.connect(self.on_text_change)
        layout.addWidget(self.line_edit, stretch=1)

        # 5 & 7. 오른쪽 2줄 일시 (모듈 커스텀 반영)
        self.time_label = QLabel()
        self.time_label.setFont(QFont("Apple SD Gothic Neo", meta_size))
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.time_label.setStyleSheet("color: #8E8E93; background: transparent;")
        layout.addWidget(self.time_label)

        # 행 삭제 버튼
        self.btn_del = QPushButton("✕")
        self.btn_del.setFixedSize(int(20 * self.scale_factor), int(20 * self.scale_factor))
        self.btn_del.setStyleSheet("QPushButton { border: none; color: #C7C7CC; font-weight: bold; background: transparent; } QPushButton:hover { color: #FF3B30; }")
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
        font.setStrikeOut(self.data.get("completed", False))  # 8. 취소선
        self.line_edit.setFont(font)
        if self.data.get("completed", False):
            self.line_edit.setStyleSheet("color: #8E8E93; background: transparent; border: none;")
        else:
            if self.data.get("is_tag_header", False):
                font.setBold(True)
                self.line_edit.setFont(font)
                self.line_edit.setStyleSheet("color: #1C1C1E; background: transparent; font-weight: bold; border: none;")
            else:
                self.line_edit.setStyleSheet("color: #1C1C1E; background: transparent; border: none;")

    def update_time_display(self):
        # 2 & 7. 등록 및 완료 날짜 커스텀 렌더링
        mode = self.settings.get("datetime_mode", "both")  # both, date_only, time_only, none
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
        self.setFixedSize(300, 260)
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
        # 1. 윈도우 기본 제목창 및 테두리 제거 (Frameless)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(560, 760)

    def build_ui(self):
        # 메인 둥근 배경 컨테이너
        self.main_container = QFrame(self)
        self.main_container.setObjectName("MainContainer")
        
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(self.main_container)

        self.root_layout = QVBoxLayout(self.main_container)
        self.root_layout.setContentsMargins(18, 14, 18, 16)
        self.root_layout.setSpacing(10)

        # 1. 미니멀 커스텀 타이틀바 (마우스로 창 이동 가능)
        self.header_bar = QHBoxLayout()
        self.lbl_title = QLabel("할 일 및 노트")
        self.lbl_title.setStyleSheet("font-weight: bold; color: #1C1C1E;")
        self.header_bar.addWidget(self.lbl_title)
        self.header_bar.addStretch()

        # 2. 커스텀 설정 버튼
        self.btn_settings = QPushButton("커스텀")
        self.btn_settings.setStyleSheet("QPushButton { border: 1px solid #D1D1D6; border-radius: 6px; padding: 3px 8px; font-size: 11px; background: white; } QPushButton:hover { background: #F2F2F7; }")
        self.btn_settings.clicked.connect(self.open_settings)
        self.header_bar.addWidget(self.btn_settings)

        # 9. 전체 크기 배율 드롭다운 (창 크기 제외 UI 스케일링)
        self.scale_combo = QComboBox()
        self.scale_combo.addItems(["80%", "90%", "100%", "110%", "125%", "150%"])
        self.scale_combo.setCurrentText(f"{int(self.scale_factor * 100)}%")
        self.scale_combo.setStyleSheet("QComboBox { border: 1px solid #D1D1D6; border-radius: 6px; padding: 2px 6px; font-size: 11px; background: white; }")
        self.scale_combo.currentTextChanged.connect(self.on_scale_change)
        self.header_bar.addWidget(self.scale_combo)

        # 미니멀 윈도우 조작 버튼 (최소화, 닫기)
        btn_min = QPushButton("—")
        btn_min.setFixedSize(24, 24)
        btn_min.setStyleSheet("QPushButton { border: none; background: transparent; font-size: 11px; } QPushButton:hover { background: #E5E5EA; border-radius: 12px; }")
        btn_min.clicked.connect(self.showMinimized)
        self.header_bar.addWidget(btn_min)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(24, 24)
        btn_close.setStyleSheet("QPushButton { border: none; background: transparent; font-size: 12px; } QPushButton:hover { background: #FF3B30; color: white; border-radius: 12px; }")
        btn_close.clicked.connect(self.close)
        self.header_bar.addWidget(btn_close)

        self.root_layout.addLayout(self.header_bar)

        # 10. 파스텔 태그 바 모듈
        self.tag_scroll = QScrollArea()
        self.tag_scroll.setWidgetResizable(True)
        self.tag_scroll.setFixedHeight(38)
        self.tag_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.tag_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tag_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.tag_widget = QWidget()
        self.tag_layout = QHBoxLayout(self.tag_widget)
        self.tag_layout.setContentsMargins(0, 2, 0, 2)
        self.tag_layout.setSpacing(6)
        self.tag_scroll.setWidget(self.tag_widget)
        self.root_layout.addWidget(self.tag_scroll)
        self.render_tags()

        # 4. 아이폰 메모 스타일 줄노트 영역 (상단 2/3)
        self.task_scroll = QScrollArea()
        self.task_scroll.setWidgetResizable(True)
        self.task_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.task_scroll.setObjectName("CustomScroll")
        
        self.task_container = QWidget()
        self.task_layout = QVBoxLayout(self.task_container)
        self.task_layout.setContentsMargins(0, 0, 8, 0)
        self.task_layout.setSpacing(0)
        self.task_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.task_scroll.setWidget(self.task_container)
        self.root_layout.addWidget(self.task_scroll, stretch=2)

        # 다음 줄 클릭/입력용 빈 노트 유도 줄
        self.new_line_edit = QLineEdit()
        self.new_line_edit.setPlaceholderText("+ 다음 줄을 눌러 새 숙제 작성...")
        self.new_line_edit.setFrame(False)
        self.new_line_edit.returnPressed.connect(self.commit_new_task)
        self.root_layout.addWidget(self.new_line_edit)

        # 3. 하단 1/3 일상 메모장
        self.memo_frame = QFrame()
        self.memo_frame.setStyleSheet("background: #FAF8F2; border: 1px solid #EAE5D9; border-radius: 12px; padding: 6px;")
        memo_inner_layout = QVBoxLayout(self.memo_frame)
        memo_inner_layout.setContentsMargins(6, 6, 6, 6)

        lbl_memo_title = QLabel("일상 메모장")
        lbl_memo_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #8E8E93;")
        memo_inner_layout.addWidget(lbl_memo_title)

        self.txt_memo = QTextEdit()
        self.txt_memo.setFrameShape(QFrame.Shape.NoFrame)
        self.txt_memo.setStyleSheet("background: transparent; font-family: 'Apple SD Gothic Neo', sans-serif;")
        self.txt_memo.setPlainText(self.memo_text)
        self.txt_memo.textChanged.connect(self.on_memo_change)
        memo_inner_layout.addWidget(self.txt_memo)

        self.root_layout.addWidget(self.memo_frame, stretch=1)

        self.refresh_task_list()
        self.apply_module_visibility()

    # 마우스 드래그로 무테두리 창 이동
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

    # 태그 바 렌더링
    def render_tags(self):
        while self.tag_layout.count():
            item = self.tag_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        for idx, tag_text in enumerate(self.tags):
            bg_c, fg_c = PASTEL_COLORS[idx % len(PASTEL_COLORS)]
            tag_box = QFrame()
            tag_box.setStyleSheet(f"background-color: {bg_c}; border-radius: 12px; padding: 2px 8px;")
            tb_layout = QHBoxLayout(tag_box)
            tb_layout.setContentsMargins(4, 2, 4, 2)
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

        # 새 태그 추가 버튼 (+)
        btn_add_tag = QPushButton("+ 태그")
        btn_add_tag.setStyleSheet("border: 1px dashed #C7C7CC; border-radius: 12px; padding: 2px 10px; font-size: 11px; color: #8E8E93; background: white;")
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

        # 4. 하루 지난 항목 자동 보관 처리
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
        self.main_container.setStyleSheet(f"""
            #MainContainer {{
                background-color: #FFFFFF;
                border-radius: 16px;
                border: 1px solid #D1D1D6;
            }}
            #CustomScroll QScrollBar:vertical {{
                border: none;
                background: transparent;
                width: {int(5 * s)}px;
                margin: 0px;
            }}
            #CustomScroll QScrollBar::handle:vertical {{
                background: #C7C7CC;
                min-height: 20px;
                border-radius: {int(2.5 * s)}px;
            }}
            #CustomScroll QScrollBar::add-line:vertical, #CustomScroll QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)
        self.lbl_title.setFont(QFont("Apple SD Gothic Neo", int(14 * s)))
        self.new_line_edit.setFont(QFont("Apple SD Gothic Neo", f_main))
        self.new_line_edit.setStyleSheet(f"border-bottom: 1px dashed #D1D1D6; padding: {int(6 * s)}px 2px; color: #8E8E93; background: transparent;")
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