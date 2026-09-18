import sys
import json
import os
import ctypes
from datetime import datetime, timedelta
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QSize, QPointF, QEvent, QTimer
from PyQt6.QtGui import QFont, QPainter, QColor, QPen, QPixmap, QIcon, QResizeEvent, QTextCursor, QTextBlockFormat, QPolygonF
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QTextEdit, QScrollArea, QFrame, QComboBox, 
    QPushButton, QStackedWidget, QSizeGrip, QLayout, QSpacerItem, QSizePolicy
)

try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('mycompany.mytodo.legalpad.1')
except Exception:
    pass

DATA_FILE = "tasks_data.json"
# 리걸노트의 실제 줄 간격을 기준으로 잡습니다.
# QWidget의 실제 높이는 정수 픽셀이지만 배경선과 전체 행 배치는
# 소수점 피치를 기준으로 누적 반올림하여 화면에서 자연스럽게 맞춥니다.
GRID_PITCH = 43.75
LINE_HEIGHT = round(GRID_PITCH)
MARGIN_RED_X = 96
SCROLLBAR_GUTTER = 4
TITLE_FONT_PX = 40


def grid_pos(index):
    """소수점 그리드 피치를 화면 픽셀 좌표로 누적 반올림합니다."""
    return round(index * GRID_PITCH)


def grid_row_height(index):
    """각 행이 43/44px로 분산되도록 누적 반올림한 실제 높이입니다."""
    return max(1, grid_pos(index + 1) - grid_pos(index))
NEON_TEXT_COLORS = ["#55FF88", "#FFA940", "#FFF730", "#5CE1E6", "#FF69B4", "#B388FF"]
TEXT_COLOR = "#4F4A35"
MODULE_ACTIVE_HIGHLIGHT = "#79A7C2"
MODULE_INACTIVE_HIGHLIGHT = "#C86F6A"
META_ACTIVE_BG = "#DAE2AE"
META_INACTIVE_BG = "#F1D697"


def blend_hex(fg_hex, bg_hex="#FFFEBE", alpha=150):
    """QSS rgba 파싱에 의존하지 않고 같은 시각적 혼합색을 계산합니다."""
    fg = QColor(fg_hex)
    bg = QColor(bg_hex)
    a = max(0, min(255, int(alpha))) / 255.0
    r = round(fg.red() * a + bg.red() * (1.0 - a))
    g = round(fg.green() * a + bg.green() * (1.0 - a))
    b = round(fg.blue() * a + bg.blue() * (1.0 - a))
    return f"#{r:02X}{g:02X}{b:02X}"

def app_font(pixel_size, weight=QFont.Weight.Normal, ui_scale=True):
    """앱 글꼴 생성기.

    Qt의 pixel-size 폰트는 pointSize()가 -1이 될 수 있습니다. 일부 스타일/배율
    경로가 그 값을 다시 point size로 사용하면 QFont 경고가 발생할 수 있으므로
    여기서는 유효한 point size만 사용합니다. 일반 UI 글자는 1.2배 확대하고
    메인 타이틀처럼 고정 크기가 필요한 곳은 ui_scale=False로 호출합니다.
    """
    px = float(pixel_size) * (1.2 if ui_scale else 1.0)
    font = QFont()
    try:
        font.setFamilies(["Malgun Gothic", "Noto Sans KR", "Dotum", "sans-serif"])
    except AttributeError:
        font.setFamily("Malgun Gothic")
    # 96 DPI 기준 px -> pt. 항상 양수라 pointSize()/pointSizeF()가 -1이 되지 않습니다.
    font.setPointSizeF(max(1.0, px * 0.75))
    font.setWeight(weight)
    return font

def meta_font_metrics_width(font, text):
    from PyQt6.QtGui import QFontMetrics
    return QFontMetrics(font).horizontalAdvance(text)

def create_legal_pad_icon():
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor("#FFFEBE"))
    p = QPainter(pixmap)
    p.setPen(QPen(QColor("#9FC6C1"), 2))
    p.drawLine(0, 20, 64, 20); p.drawLine(0, 36, 64, 36); p.drawLine(0, 52, 64, 52)
    p.setPen(QPen(QColor("#D12F28"), 2))
    p.drawLine(18, 0, 18, 64); p.drawLine(21, 0, 21, 64)
    p.end()
    return QIcon(pixmap)

class SimplePencilButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(20, 20)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.is_edit_mode = False

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if self.is_edit_mode:
            p.setPen(QPen(QColor("#FF3B30"), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(4, 10, 8, 14)
            p.drawLine(8, 14, 16, 5)
            return
        pen_color = QColor("#4F4A35") if self.underMouse() else QColor("#4F4A35")
        p.setPen(QPen(pen_color, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(3, 17, 17, 17)
        p.setPen(QPen(pen_color, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        pencil_poly = QPolygonF([QPointF(4.5, 13.5), QPointF(4.5, 10.5), QPointF(12.5, 2.5), QPointF(15.5, 5.5), QPointF(7.5, 13.5)])
        p.drawPolygon(pencil_poly)
        p.drawLine(QPointF(6, 12), QPointF(14, 4))

class DottedSizeGrip(QSizeGrip):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self.setStyleSheet("background: transparent;")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#4F4A35"))
        for x, y in [(11, 3), (7, 7), (11, 7), (3, 11), (7, 11), (11, 11)]:
            p.drawRect(x, y, 2, 2)

class TagFlowLayout(QLayout):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setContentsMargins(0, 0, 0, 0)
        self.item_list = []

    def __del__(self):
        while self.item_list: self.item_list.pop()
    def addItem(self, item): self.item_list.append(item)
    def count(self): return len(self.item_list)
    def itemAt(self, index): return self.item_list[index] if 0 <= index < len(self.item_list) else None
    def takeAt(self, index): return self.item_list.pop(index) if 0 <= index < len(self.item_list) else None
    def hasHeightForWidth(self): return True
    def heightForWidth(self, width): return self.do_layout(QRect(0, 0, width, 0), True)
    def setGeometry(self, rect):
        super().setGeometry(rect)
        self.do_layout(rect, False)
    def sizeHint(self): return self.minimumSize()
    def minimumSize(self):
        s = QSize()
        for i in self.item_list: s = s.expandedTo(i.minimumSize())
        return s

    def do_layout(self, rect, test_only):
        x, y = rect.x(), rect.y()
        line_idx, spacing = 0, 6
        for item in self.item_list:
            w, h = item.sizeHint().width(), item.sizeHint().height()
            if x + w > rect.right() and x > rect.x():
                x = rect.x()
                line_idx += 1
                y = rect.y() + grid_pos(line_idx)
            if not test_only:
                item.setGeometry(QRect(x, y + (LINE_HEIGHT - h) // 2, w, h))
            x += w + spacing
        return grid_pos(line_idx + 1)

class LegalPadBackground(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.fillRect(self.rect(), QColor("#FFFEBE"))
        w, h = self.width(), self.height()
        p.setPen(QPen(QColor("#9FC6C1"), 1))
        line_index = 2
        while grid_pos(line_index) < h:
            y = float(grid_pos(line_index))
            p.drawLine(QPointF(0.0, y), QPointF(float(w), y))
            line_index += 1
        # 사용자가 원하는 authentic legal-pad 인상: 얇은 red margin 두 줄을 유지합니다.
        p.setPen(QPen(QColor("#D12F28"), 1.0))
        p.drawLine(MARGIN_RED_X, 0, MARGIN_RED_X, h)
        p.drawLine(MARGIN_RED_X + 4, 0, MARGIN_RED_X + 4, h)

class NoteTaskRow(QFrame):
    changed = pyqtSignal()
    text_changed = pyqtSignal()
    delete_requested = pyqtSignal(object)

    def __init__(self, data, scale_factor, settings, parent=None):
        super().__init__(parent)
        self.data = data
        self.scale_factor = scale_factor
        self.settings = settings
        self.setMinimumHeight(1)
        self.init_ui()

    def init_ui(self):
        s = self.scale_factor
        self.setStyleSheet("background: transparent; border: none;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 10, 0)
        layout.setSpacing(int(8 * s))

        self.chk = QPushButton()
        self.update_chk_icon()
        self.chk.setFixedSize(int(16 * s), int(16 * s))
        self.chk.clicked.connect(self.toggle_complete)
        layout.addWidget(self.chk)

        self.edit = QLineEdit(self.data.get("text", ""))
        self.edit.setFrame(False)
        self.edit.setFont(app_font(max(12, int(15 * s))))
        # 필드보다 긴 숙제는 기본 표시가 뒷부분으로 밀리지 않게 앞에서 시작합니다.
        self.edit.setCursorPosition(0)
        self.edit.textChanged.connect(self.on_text_change)
        layout.addWidget(self.edit, stretch=1)

        self.time_box = QFrame()
        self.time_box.setFixedWidth(int(135 * s))
        self.time_box.setStyleSheet("background: transparent; border: none;")
        time_lay = QVBoxLayout(self.time_box)
        time_lay.setContentsMargins(0, 0, 0, 0)
        time_lay.setSpacing(0)

        meta_font = app_font(max(8, int(9.5 * s)))
        self.lbl_created = QLabel()
        self.lbl_created.setFont(meta_font)
        self.lbl_created.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_created.setStyleSheet("color: #4F4A35; background: transparent;")
        time_lay.addWidget(self.lbl_created)

        self.lbl_completed = QLabel()
        self.lbl_completed.setFont(meta_font)
        compact_meta_h = max(12, self.lbl_created.fontMetrics().height() - 2)
        self.lbl_created.setFixedHeight(compact_meta_h)
        self.lbl_completed.setFixedHeight(compact_meta_h)
        self.lbl_completed.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_completed.setStyleSheet("color: #4F4A35; background: transparent;")
        time_lay.addWidget(self.lbl_completed)
        layout.addWidget(self.time_box)

        self.btn_del = QPushButton("×")
        self.btn_del.setFixedSize(int(24 * s), int(24 * s))
        self.btn_del.setFont(app_font(20, QFont.Weight.Normal))
        self.btn_del.setStyleSheet(f"QPushButton {{ border: none; color: {TEXT_COLOR}; background: transparent; font-weight: normal; }} QPushButton:hover {{ color: {MODULE_INACTIVE_HIGHLIGHT}; }}")
        self.btn_del.clicked.connect(lambda: self.delete_requested.emit(self))
        layout.addWidget(self.btn_del, alignment=Qt.AlignmentFlag.AlignVCenter)

        self.update_appearance()
        self.update_time_label()

    def update_chk_icon(self):
        """작고 각진 네이티브 버튼형 체크박스. 배율에 따라 크기만 기존 방식대로 조정합니다."""
        done = self.data.get("completed", False)
        s = self.scale_factor
        check_px = max(8, int(10 * s))
        self.chk.setFont(app_font(check_px, QFont.Weight.Bold))
        if done:
            self.chk.setStyleSheet(
                "QPushButton { border: 1px solid #4F4A35; border-radius: 0px; "
                f"background-color: #4F4A35; color: #FFFFFF; "
                "font-weight: bold; padding: 0px; margin: 0px; }"
            )
            self.chk.setText("✓")
        else:
            self.chk.setStyleSheet(
                "QPushButton { border: 1px solid #4F4A35; border-radius: 0px; "
                "background-color: transparent; padding: 0px; margin: 0px; } "
                "QPushButton:hover { background-color: transparent; }"
            )
            self.chk.setText("")

    def toggle_complete(self):
        done = not self.data.get("completed", False)
        self.data["completed"] = done
        self.data["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M") if done else None
        self.update_chk_icon()
        self.update_appearance()
        self.update_time_label()
        self.changed.emit()

    def on_text_change(self, text):
        # 입력 중에는 저장만 합니다. 행 재생성을 막아 한글 IME 조합을 보존합니다.
        self.data["text"] = text
        self.text_changed.emit()

    def update_appearance(self):
        done = self.data.get("completed", False)
        s = self.scale_factor
        weight = QFont.Weight.Bold if self.data.get("is_tag_header", False) else QFont.Weight.Normal
        font = app_font(max(12, int(15 * s)), weight)
        font.setStrikeOut(done)
        self.edit.setFont(font)
        self.edit.setStyleSheet(f"color: {'#918B78' if done else TEXT_COLOR}; background: transparent; border: none;")

    def update_time_label(self):
        c_str = self.data.get("created_at")
        c_parts = []
        if c_str:
            try:
                dt_c = datetime.strptime(c_str, "%Y-%m-%d %H:%M")
                if self.settings.get("show_created_date", True): c_parts.append(dt_c.strftime("%m.%d"))
                if self.settings.get("show_created_time", True): c_parts.append(dt_c.strftime("%H:%M"))
            except Exception: pass
        self.lbl_created.setText(f"등록: {' '.join(c_parts)}" if c_parts else "")

        d_str = self.data.get("completed_at")
        d_parts = []
        if d_str:
            try:
                dt_d = datetime.strptime(d_str, "%Y-%m-%d %H:%M")
                if self.settings.get("show_completed_date", True): d_parts.append(dt_d.strftime("%m.%d"))
                if self.settings.get("show_completed_time", True): d_parts.append(dt_d.strftime("%H:%M"))
            except Exception: pass
        
        # 완료되지 않은 숙제라도 빈칸(공백)을 유지하여 레이아웃 밀림 방지
        if d_parts:
            self.lbl_completed.setText(f"완료: {' '.join(d_parts)}")
        else:
            self.lbl_completed.setText(" " if self.data.get("completed", False) else "")

# 커스텀 미리보기 행
class PreviewMetaLine(QWidget):
    """메타데이터 한 줄을 하나의 텍스트 캔버스로 직접 그립니다.

    등록/날짜/시간은 별도 QLabel/QPushButton이 아닙니다. 실제 숙제와 같은
    폰트 메트릭과 공백을 사용해 한 줄로 그리며 클릭 판정만 글자 영역별로 합니다.
    """
    clicked = pyqtSignal(str)

    def __init__(self, prefix, date_text, time_text, prefix_target, date_target, time_target, parent=None):
        super().__init__(parent)
        self.prefix = prefix
        self.date_text = date_text
        self.time_text = time_text
        self.targets = (prefix_target, date_target, time_target)
        self.states = (True, True, True)
        self._hit_rects = []
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

    def set_states(self, prefix_active, date_active, time_active):
        self.states = (bool(prefix_active), bool(date_active), bool(time_active))
        self.update()

    def sizeHint(self):
        fm = self.fontMetrics()
        text = f"{self.prefix} {self.date_text} {self.time_text}"
        return QSize(max(1, fm.horizontalAdvance(text)), max(12, fm.height() - 2))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setFont(self.font())
        fm = self.fontMetrics()
        space = fm.horizontalAdvance(" ")
        pieces = (self.prefix, self.date_text, self.time_text)
        widths = [fm.horizontalAdvance(t) for t in pieces]
        total = sum(widths) + space * 2
        x = self.width() - total
        baseline = (self.height() - fm.height()) // 2 + fm.ascent()
        self._hit_rects = []
        for i, (text, width, active) in enumerate(zip(pieces, widths, self.states)):
            rect = QRect(x, 0, width, self.height())
            p.fillRect(rect, QColor(META_ACTIVE_BG if active else META_INACTIVE_BG))
            p.setPen(QColor(TEXT_COLOR))
            p.drawText(x, baseline, text)
            self._hit_rects.append((rect, self.targets[i]))
            x += width + (space if i < 2 else 0)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            for rect, target in self._hit_rects:
                if rect.contains(pos):
                    self.clicked.emit(target)
                    event.accept()
                    return
        super().mousePressEvent(event)


class VirtualCustomTaskRow(QFrame):
    """실제 숙제 행과 같은 우측 규격을 쓰는 커스텀 미리보기."""
    def __init__(self, settings, scale_factor, on_setting_changed, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.scale_factor = scale_factor
        self.on_setting_changed = on_setting_changed
        self.setMinimumHeight(1)
        self.init_ui()

    def init_ui(self):
        s = self.scale_factor
        self.setStyleSheet("background: transparent; border: none;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 10, 0)
        layout.setSpacing(int(8 * s))

        self.lbl_chk = QLabel("✓")
        self.lbl_chk.setFixedSize(int(16 * s), int(16 * s))
        self.lbl_chk.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_chk)

        self.lbl_title = QLabel("커스텀 미리보기 숙제")
        layout.addWidget(self.lbl_title, stretch=1)

        self.time_box = QFrame()
        self.time_box.setFixedWidth(int(135 * s))
        self.time_box.setStyleSheet("background: transparent; border: none;")
        self.time_layout = QVBoxLayout(self.time_box)
        self.time_layout.setContentsMargins(0, 0, 0, 0)
        self.time_layout.setSpacing(0)

        self.created_line = PreviewMetaLine("등록:", "09.17", "10:30", "created_all", "created_date", "created_time", self.time_box)
        self.completed_line = PreviewMetaLine("완료:", "09.17", "15:45", "completed_all", "completed_date", "completed_time", self.time_box)
        self.created_line.clicked.connect(self.toggle_part)
        self.completed_line.clicked.connect(self.toggle_part)
        self.time_layout.addStretch(1)
        self.time_layout.addWidget(self.created_line)
        self.time_layout.addWidget(self.completed_line)
        self.time_layout.addStretch(1)
        layout.addWidget(self.time_box)

        self.trailing_spacer = QSpacerItem(int(24 * s) + SCROLLBAR_GUTTER, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        layout.addSpacerItem(self.trailing_spacer)
        self.update_styles()

    def set_scale(self, s):
        self.scale_factor = s
        self.layout().setSpacing(int(8 * s))
        self.lbl_chk.setFixedSize(int(16 * s), int(16 * s))
        self.time_box.setFixedWidth(int(135 * s))
        self._update_trailing_spacer()
        self.update_styles()

    def set_scrollbar_width(self, width):
        self._update_trailing_spacer()

    def _update_trailing_spacer(self):
        delete_width = int(24 * self.scale_factor)
        self.trailing_spacer.changeSize(delete_width + SCROLLBAR_GUTTER, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        self.layout().invalidate()

    def adjust_trailing_spacer(self, delta):
        current = self.trailing_spacer.sizeHint().width()
        self.trailing_spacer.changeSize(max(0, current + int(delta)), 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        self.layout().invalidate()
        self.updateGeometry()

    def toggle_part(self, target):
        if target == "created_all":
            both = self.settings.get("show_created_date", True) and self.settings.get("show_created_time", True)
            self.settings["show_created_date"] = not both
            self.settings["show_created_time"] = not both
        elif target == "created_date":
            self.settings["show_created_date"] = not self.settings.get("show_created_date", True)
        elif target == "created_time":
            self.settings["show_created_time"] = not self.settings.get("show_created_time", True)
        elif target == "completed_all":
            both = self.settings.get("show_completed_date", True) and self.settings.get("show_completed_time", True)
            self.settings["show_completed_date"] = not both
            self.settings["show_completed_time"] = not both
        elif target == "completed_date":
            self.settings["show_completed_date"] = not self.settings.get("show_completed_date", True)
        elif target == "completed_time":
            self.settings["show_completed_time"] = not self.settings.get("show_completed_time", True)
        self.update_styles()
        self.on_setting_changed()

    def update_styles(self):
        s = self.scale_factor
        self.lbl_chk.setFont(app_font(max(8, int(10 * s)), QFont.Weight.Bold))
        self.lbl_chk.setStyleSheet(
            f"background-color: {TEXT_COLOR}; color: #FFFFFF; border: 1px solid {TEXT_COLOR}; "
            "border-radius: 0px; font-weight: bold;"
        )
        self.lbl_title.setFont(app_font(max(12, int(15 * s))))
        self.lbl_title.setStyleSheet(f"color: {TEXT_COLOR}; font-weight: bold; background: transparent;")
        meta_font = app_font(max(8, int(9.5 * s)))
        self.created_line.setFont(meta_font)
        self.completed_line.setFont(meta_font)
        row_h = max(12, self.created_line.fontMetrics().height() - 2)
        self.created_line.setFixedHeight(row_h)
        self.completed_line.setFixedHeight(row_h)
        self.created_line.set_states(
            self.settings.get("show_created_date", True) or self.settings.get("show_created_time", True),
            self.settings.get("show_created_date", True),
            self.settings.get("show_created_time", True),
        )
        self.completed_line.set_states(
            self.settings.get("show_completed_date", True) or self.settings.get("show_completed_time", True),
            self.settings.get("show_completed_date", True),
            self.settings.get("show_completed_time", True),
        )


class GridScrollArea(QScrollArea):
    """소수점 리걸노트 피치를 실제 스크롤 위치에도 적용합니다."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._snapping = False
        self.verticalScrollBar().valueChanged.connect(self._snap_value)

    def _snap_value(self, value):
        if self._snapping:
            return
        target_index = max(0, round(value / GRID_PITCH))
        target = grid_pos(target_index)
        target = max(self.verticalScrollBar().minimum(),
                     min(target, self.verticalScrollBar().maximum()))
        if target != value:
            self._snapping = True
            self.verticalScrollBar().setValue(target)
            self._snapping = False

    def wheelEvent(self, event):
        # 기본 휠 이동 후 valueChanged에서 가장 가까운 노트 줄로 정렬합니다.
        super().wheelEvent(event)
        self._snap_value(self.verticalScrollBar().value())

class ModernTodoApp(QWidget):
    def __init__(self):
        super().__init__()
        self.old_pos = None
        self.scale_factor = 1.0
        self.is_custom_mode = False
        self.is_tag_edit_mode = False
        self.memo_text = ""
        self.setWindowTitle("나만의 숙제")
        self.setWindowIcon(create_legal_pad_icon())
        self.load_data()
        # UI 배율은 데이터와 함께 저장하고 다음 실행 때 복원합니다.
        self.scale_factor = float(self.settings.get("ui_scale", 1.0))
        if self.scale_factor not in (1.0, 1.1, 1.25, 1.5):
            self.scale_factor = 1.0
        self.init_window()
        self.build_ui()
        self.apply_scale()
        self.update_minimum_width()
        QTimer.singleShot(0, self._startup_geometry_sync)

    def init_window(self):
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(660, 880)
        self.update_minimum_width()

    # 커스텀 미리보기 제목 + 메타데이터가 잘리지 않는 실제 최소 폭을 계산합니다.
    def update_minimum_width(self):
        s = self.scale_factor
        if hasattr(self, "virtual_row"):
            title_w = self.virtual_row.lbl_title.fontMetrics().horizontalAdvance("커스텀 미리보기 숙제")
            check_w = int(16 * s)
            time_w = int(135 * s)
            delete_w = int(24 * s)
            spacing = int(8 * s)
            row_margins = 10
            outer_margins = MARGIN_RED_X + 16 + 16
            # 체크-제목-시간-삭제 영역 사이 spacing 3개 + 고정 scrollbar gutter.
            min_w = outer_margins + check_w + title_w + time_w + delete_w + SCROLLBAR_GUTTER + spacing * 3 + row_margins + 24
        else:
            min_w = MARGIN_RED_X + int(360 * s)
        self.setMinimumWidth(max(550, int(min_w)))
        self.setMinimumHeight(grid_pos(10))

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self.sync_grid()
        # resize 도중에는 Qt가 이전 child geometry를 잠깐 유지할 수 있습니다.
        # 현재 event가 끝난 뒤 한 번만 레이아웃을 확정해 겹침 잔상을 줄입니다.
        QTimer.singleShot(0, self._settle_layout_geometry)
        if hasattr(self, "tag_bar_frame"):
            QTimer.singleShot(0, self.refresh_tag_geometry)

    def showEvent(self, event):
        super().showEvent(event)
        # 저장된 배율로 처음 열 때는 실제 행/스크롤바 geometry가 show 이전에는
        # 아직 확정되지 않습니다. 첫 paint 이후 실제 좌표를 기준으로 재동기화합니다.
        QTimer.singleShot(0, self._startup_geometry_sync)
        QTimer.singleShot(40, self._startup_geometry_sync)

    def _startup_geometry_sync(self):
        self._settle_layout_geometry()
        if hasattr(self, "virtual_row"):
            self.sync_preview_time_alignment()

    def _settle_layout_geometry(self):
        # 그리드 계산값은 바꾸지 않고 이미 계산된 Qt 레이아웃 geometry만 확정합니다.
        for layout in (getattr(self, "root_layout", None), getattr(self, "task_layout", None)):
            if layout is not None:
                layout.activate()
        if hasattr(self, "task_list_widget"):
            self.task_list_widget.updateGeometry()
            self.task_list_widget.update()
        if hasattr(self, "scroll"):
            self.scroll.viewport().update()
        if hasattr(self, "virtual_row"):
            self.sync_preview_time_alignment()

    def sync_grid(self):
        h = self.height()
        # 하단 여백도 같은 소수점 그리드에 맞춰 누적 반올림합니다.
        base = grid_pos(2)
        remainder = (h - base) % GRID_PITCH
        offset = round((remainder + 26) % GRID_PITCH)
        self.bottom_spacer.changeSize(10, offset, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.root_layout.invalidate()
        self.main_bg.update()

    def build_ui(self):
        self.main_bg = LegalPadBackground(self)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.main_bg)

        self.root_layout = QVBoxLayout(self.main_bg)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)

        # 상단 헤더
        self.header_frame = QFrame()
        self.header_frame.setFixedHeight(grid_pos(2))
        h_layout = QVBoxLayout(self.header_frame)
        h_layout.setContentsMargins(0, 4, 18, 0)
        h_layout.setSpacing(0)

        ctrl_bar = QHBoxLayout()
        ctrl_bar.setSpacing(10)
        ctrl_bar.addStretch()

        self.btn_archive_toggle = QPushButton("완료한 숙제")
        self.btn_archive_toggle.setFont(app_font(11))
        self.btn_archive_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_archive_toggle.setStyleSheet("QPushButton { border: 1px solid #C4BC87; border-radius: 4px; padding: 4px 8px; background: transparent; color: #4F4A35; }")
        self.btn_archive_toggle.clicked.connect(self.toggle_archive_view)
        ctrl_bar.addWidget(self.btn_archive_toggle)

        self.btn_custom = QPushButton("커스텀")
        self.btn_custom.setFont(app_font(11))
        self.btn_custom.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_custom.setStyleSheet("QPushButton { border: 1px solid #C4BC87; border-radius: 4px; padding: 4px 8px; background: transparent; color: #4F4A35; }")
        self.btn_custom.clicked.connect(self.toggle_custom_mode)
        ctrl_bar.addWidget(self.btn_custom)

        self.scale_combo = QComboBox()
        self.scale_combo.setFont(app_font(11))
        self.scale_combo.addItems(["100%", "110%", "125%", "150%"])
        self.scale_combo.setCurrentText(f"{int(self.scale_factor * 100)}%")
        self.scale_combo.setStyleSheet("QComboBox { border: 1px solid #C4BC87; border-radius: 4px; padding: 2px 6px; padding-right: 6px; background: transparent; color: #4F4A35; font-weight: bold; } QComboBox::drop-down { border: none; width: 0px; } QComboBox::down-arrow { image: none; width: 0px; height: 0px; } QComboBox QAbstractItemView { background-color: #FFFDF0; color: #4F4A35; border: 1px solid #C4BC87; }")
        self.scale_combo.currentTextChanged.connect(self.on_scale_change)
        ctrl_bar.addWidget(self.scale_combo)

        btn_min = QPushButton("—")
        btn_min.setFixedSize(20, 20)
        btn_min.setStyleSheet("border: none; background: transparent; font-weight: bold; color: #4F4A35;")
        btn_min.clicked.connect(self.showMinimized)
        ctrl_bar.addWidget(btn_min)

        self.btn_close = QPushButton("×")
        self.btn_close.setFixedSize(int(24 * self.scale_factor), int(24 * self.scale_factor))
        self.btn_close.setFont(app_font(20, QFont.Weight.Normal))
        self.btn_close.setStyleSheet(f"QPushButton {{ border: none; background: transparent; font-weight: normal; color: {TEXT_COLOR}; }} QPushButton:hover {{ color: {MODULE_INACTIVE_HIGHLIGHT}; }}")
        self.btn_close.clicked.connect(self.close)
        ctrl_bar.addWidget(self.btn_close)
        h_layout.addLayout(ctrl_bar)

        title_bar = QHBoxLayout()
        title_bar.setContentsMargins(MARGIN_RED_X + 16, 0, 0, 2)
        self.lbl_main_title = QLabel("나만의 숙제")
        self.lbl_main_title.setFont(app_font(TITLE_FONT_PX, QFont.Weight.Black, ui_scale=False))
        self.lbl_main_title.setStyleSheet("color: #4F4A35; background: transparent; text-decoration: underline;")
        self.lbl_main_title.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft)
        title_bar.addWidget(self.lbl_main_title)
        title_bar.addStretch()
        h_layout.addLayout(title_bar)
        self.root_layout.addWidget(self.header_frame)

        self.stacked_widget = QStackedWidget()
        self.root_layout.addWidget(self.stacked_widget)

        # 메인 페이지
        self.page_main = QWidget()
        page_main_layout = QVBoxLayout(self.page_main)
        page_main_layout.setContentsMargins(0, 0, 0, 0)
        page_main_layout.setSpacing(0)

        # 태그 프레임
        self.tag_wrapper = QFrame()
        tw_lay = QHBoxLayout(self.tag_wrapper)
        # 수정 버튼 중심을 숙제 삭제 × 중심과 같은 X축에 둡니다.
        tw_lay.setContentsMargins(MARGIN_RED_X + 16, 0, 32, 0)
        tw_lay.setSpacing(8)

        self.tag_bar_frame = QFrame()
        self.tag_flow_layout = TagFlowLayout(self.tag_bar_frame)
        self.tag_bar_frame.setLayout(self.tag_flow_layout)
        tw_lay.addWidget(self.tag_bar_frame, stretch=1)

        self.btn_tag_edit = SimplePencilButton()
        self.btn_tag_edit.clicked.connect(self.toggle_tag_edit_mode)
        # 태그가 여러 줄이어도 수정 버튼은 첫 번째 ruling 한 칸의 중앙에 고정합니다.
        self.tag_edit_slot = QFrame()
        self.tag_edit_slot.setFixedSize(20, grid_row_height(0))
        self.tag_edit_slot.setStyleSheet("background: transparent; border: none;")
        edit_slot_lay = QVBoxLayout(self.tag_edit_slot)
        edit_slot_lay.setContentsMargins(0, 0, 0, 0)
        edit_slot_lay.setSpacing(0)
        edit_slot_lay.addWidget(self.btn_tag_edit, alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        tw_lay.addWidget(self.tag_edit_slot, alignment=Qt.AlignmentFlag.AlignTop)

        page_main_layout.addWidget(self.tag_wrapper)
        self.render_tags()

        # 커스텀 미리보기
        self.virtual_row_wrapper = QFrame()
        vr_lay = QVBoxLayout(self.virtual_row_wrapper)
        vr_lay.setContentsMargins(MARGIN_RED_X + 16, 0, 16, 0)
        vr_lay.setSpacing(0)
        self.virtual_row = VirtualCustomTaskRow(self.settings, self.scale_factor, self.refresh_task_list)
        self.virtual_row.setFixedHeight(grid_row_height(0))
        vr_lay.addWidget(self.virtual_row)
        self.virtual_row_wrapper.setVisible(False)
        page_main_layout.addWidget(self.virtual_row_wrapper)

        # 숙제 영역
        self.scroll_wrapper = QFrame()
        sw_lay = QVBoxLayout(self.scroll_wrapper)
        sw_lay.setContentsMargins(0, 0, 16, 0)
        sw_lay.setSpacing(0)

        self.scroll = GridScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet("QScrollArea { background: transparent; border: none; } QScrollBar:vertical { border: none; background: transparent; width: 4px; } QScrollBar::handle:vertical { background: #BBB37E; border-radius: 2px; }")
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.verticalScrollBar().setSingleStep(round(GRID_PITCH))
        self.scroll.verticalScrollBar().rangeChanged.connect(self.sync_preview_time_alignment)

        self.task_list_widget = QWidget()
        self.task_list_widget.setStyleSheet("background: transparent;")
        self.task_layout = QVBoxLayout(self.task_list_widget)
        self.task_layout.setContentsMargins(MARGIN_RED_X + 16, 0, 0, 0)
        self.task_layout.setSpacing(0)
        self.task_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll.setWidget(self.task_list_widget)
        sw_lay.addWidget(self.scroll)
        page_main_layout.addWidget(self.scroll_wrapper, stretch=1)

        # 자유 메모장
        self.memo_wrapper = QFrame()
        mw_lay = QVBoxLayout(self.memo_wrapper)
        mw_lay.setContentsMargins(MARGIN_RED_X + 16, 0, 16, 0)
        mw_lay.setSpacing(0)

        self.memo_frame = QFrame()

        memo_lay = QVBoxLayout(self.memo_frame)
        memo_lay.setContentsMargins(0, 0, 0, 0)
        memo_lay.setSpacing(0)

        self.memo_title_box = QFrame()
        self.memo_title_box.setFixedHeight(grid_row_height(0))
        self.memo_title_box.setStyleSheet("background: transparent; border: none;")
        mt_lay = QHBoxLayout(self.memo_title_box)
        mt_lay.setContentsMargins(0, 0, 0, 0)
        self.lbl_memo_title = QLabel("자유 메모")
        self.lbl_memo_title.setStyleSheet("font-weight: bold; color: #4F4A35; text-decoration: underline; background: transparent;")
        self.lbl_memo_title.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        mt_lay.addWidget(self.lbl_memo_title)
        memo_lay.addWidget(self.memo_title_box)

        self.txt_memo = QTextEdit()
        self.txt_memo.setFrameShape(QFrame.Shape.NoFrame)
        self.txt_memo.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.txt_memo.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.txt_memo.verticalScrollBar().setSingleStep(round(GRID_PITCH))
        self.txt_memo.document().setDocumentMargin(0)
        self.txt_memo.setStyleSheet("""
            QTextEdit {
                background: transparent; border: none; color: #4F4A35;
                padding: 0px; margin: 0px;
            }
            QScrollBar:vertical { border: none; background: transparent; width: 4px; }
            QScrollBar::handle:vertical { background: #BBB37E; border-radius: 2px; }
        """)
        self.txt_memo.setPlainText(self.memo_text)
        self.txt_memo.textChanged.connect(self.on_memo_change)
        memo_lay.addWidget(self.txt_memo)

        mw_lay.addWidget(self.memo_frame)
        page_main_layout.addWidget(self.memo_wrapper)

        # 커스텀 모드에서는 하이라이트 영역의 자식 위젯까지 클릭을 모듈 토글로 받습니다.
        # 태그 수정 버튼만 본래 편집 기능을 보존합니다.
        self._install_module_click_filter(self.tag_wrapper, "show_tags", exclusions=(self.btn_tag_edit,))
        self._install_module_click_filter(self.memo_wrapper, "show_memo")

        self.stacked_widget.addWidget(self.page_main)

        # 완료한 숙제 페이지
        self.page_archive = QWidget()
        page_archive_layout = QVBoxLayout(self.page_archive)
        page_archive_layout.setContentsMargins(0, 0, 0, 0)

        self.archive_scroll = GridScrollArea()
        self.archive_scroll.setWidgetResizable(True)
        self.archive_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.archive_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; } QScrollBar:vertical { border: none; background: transparent; width: 4px; } QScrollBar::handle:vertical { background: #BBB37E; border-radius: 2px; }")
        self.archive_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.archive_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.archive_scroll.verticalScrollBar().setSingleStep(round(GRID_PITCH))

        self.archive_container = QWidget()
        self.archive_container.setStyleSheet("background: transparent;")
        self.archive_layout = QVBoxLayout(self.archive_container)
        self.archive_layout.setContentsMargins(0, 0, 16, 0)
        self.archive_layout.setSpacing(0)
        self.archive_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.archive_scroll.setWidget(self.archive_container)
        page_archive_layout.addWidget(self.archive_scroll)
        self.stacked_widget.addWidget(self.page_archive)

        self.bottom_spacer = QSpacerItem(10, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.root_layout.addSpacerItem(self.bottom_spacer)

        bottom_bar = QHBoxLayout()
        bottom_bar.setContentsMargins(0, 0, 3, 3)
        bottom_bar.addStretch()
        bottom_bar.addWidget(DottedSizeGrip(self))
        self.root_layout.addLayout(bottom_bar)

        self.update_memo_height()
        self.refresh_task_list()
        self.apply_visibility()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() < LINE_HEIGHT * 2:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.pos() + delta)
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event): self.old_pos = None

    def toggle_tag_edit_mode(self):
        self.is_tag_edit_mode = not self.is_tag_edit_mode
        self.btn_tag_edit.is_edit_mode = self.is_tag_edit_mode
        self.btn_tag_edit.update()
        self.render_tags()

    def render_tags(self):
        while self.tag_flow_layout.count():
            i = self.tag_flow_layout.takeAt(0)
            if i.widget(): i.widget().deleteLater()

        s = self.scale_factor
        f_size = max(11, int(13 * s))

        for idx, tag_text in enumerate(self.tags):
            hl = NEON_TEXT_COLORS[idx % len(NEON_TEXT_COLORS)]
            hl_bg = blend_hex(hl)
            btn = QPushButton(tag_text)
            btn.setFont(app_font(f_size))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)

            if self.is_tag_edit_mode:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {hl_bg}; border: none; border-radius: 3px;
                        color: #4F4A35; padding: 2px 6px;
                    }}
                    QPushButton:hover {{
                        background-color: #E6B2AD; color: #4F4A35;
                    }}
                """)
                btn.clicked.connect(lambda _, t=tag_text: self.quick_delete_tag(t))
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {hl_bg}; border: none; border-radius: 3px;
                        color: #4F4A35; padding: 2px 6px;
                    }}
                """)
                btn.clicked.connect(lambda _, t=tag_text: self.insert_tag_to_top(t))

            self.tag_flow_layout.addWidget(btn)
            btn.setProperty("custom_module_key", "show_tags")
            btn.installEventFilter(self)

        self.new_tag_input = QLineEdit()
        self.new_tag_input.setPlaceholderText("+ 자주하는 숙제")
        self.new_tag_input.setFont(app_font(f_size))
        self.new_tag_input.setStyleSheet("border: 1px dashed #4F4A35; border-radius: 4px; padding: 2px 8px; background: transparent; color: #4F4A35;")
        self.new_tag_input.returnPressed.connect(self.add_tag_from_input)
        self.new_tag_input.textChanged.connect(self.adjust_new_tag_width)
        self.new_tag_input.setMinimumWidth(1)
        self.adjust_new_tag_width()
        self.tag_flow_layout.addWidget(self.new_tag_input)
        self.new_tag_input.setProperty("custom_module_key", "show_tags")
        self.new_tag_input.installEventFilter(self)
        # render 직후 기존 높이가 남아 첫 줄만 보이는 문제를 다음 event loop에서 재계산합니다.
        QTimer.singleShot(0, self.refresh_tag_geometry)

    def refresh_tag_geometry(self):
        if not hasattr(self, "tag_bar_frame"):
            return
        width = self.tag_bar_frame.width()
        if width <= 0:
            width = max(1, self.tag_wrapper.width() - (MARGIN_RED_X + 16) - 16 - 28)
        height = max(grid_row_height(0), self.tag_flow_layout.heightForWidth(width))
        self.tag_bar_frame.setFixedHeight(height)
        self.tag_wrapper.setFixedHeight(height)
        self.tag_flow_layout.invalidate()
        self.tag_bar_frame.updateGeometry()
        self.tag_wrapper.updateGeometry()
        if hasattr(self, "page_main"):
            self.page_main.updateGeometry()

    def adjust_new_tag_width(self):
        txt = self.new_tag_input.text() or self.new_tag_input.placeholderText()
        fm = self.new_tag_input.fontMetrics()
        # 입력 문자열 전체가 보이도록 내용과 함께 필드가 자랍니다.
        self.new_tag_input.setFixedWidth(max(1, fm.horizontalAdvance(txt) + fm.horizontalAdvance("가") + 24))
        QTimer.singleShot(0, self.refresh_tag_geometry)

    def add_tag_from_input(self):
        t = self.new_tag_input.text().strip().replace("#", "")
        if t and t not in self.tags:
            self.tags.append(t)
            self.save_data()
            self.render_tags()
            self.sync_grid()

    def insert_tag_to_top(self, tag_name):
        self.tasks.insert(0, {
            "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
            "text": f"{tag_name} ",
            "completed": False,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "completed_at": None,
            "is_tag_header": True
        })
        self.save_data()
        self.refresh_task_list()

    def quick_delete_tag(self, tag_name):
        self.tags = [t for t in self.tags if t != tag_name]
        self.save_data()
        self.render_tags()
        self.sync_grid()

    def refresh_task_list(self):
        while self.task_layout.count():
            item = self.task_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        now = datetime.now()
        active_list, archive_list = [], []
        for t in self.tasks:
            if t.get("completed") and t.get("completed_at"):
                try:
                    ct = datetime.strptime(t["completed_at"], "%Y-%m-%d %H:%M")
                    if now - ct > timedelta(days=1): archive_list.append(t)
                    else: active_list.append(t)
                except Exception: active_list.append(t)
            else:
                active_list.append(t)

        for idx, t_data in enumerate(active_list):
            row = NoteTaskRow(t_data, self.scale_factor, self.settings)
            row.setFixedHeight(grid_row_height(idx))
            row.changed.connect(self.on_task_row_changed)
            row.text_changed.connect(self.on_task_text_changed)
            row.delete_requested.connect(self.remove_task_row)
            self.task_layout.addWidget(row)

        self.add_inline_input_row(row_index=len(active_list))
        self.render_archive_page(archive_list)
        if hasattr(self, "virtual_row") and self.virtual_row.isVisible():
            QTimer.singleShot(0, self.sync_preview_time_alignment)

    def on_task_row_changed(self):
        self.save_data()
        self.refresh_task_list()

    def on_task_text_changed(self):
        self.save_data()

    def add_inline_input_row(self, row_index=0):
        s = self.scale_factor
        f = QFrame()
        f.setFixedHeight(grid_row_height(row_index))
        f.setStyleSheet("background: transparent; border: none;")
        lay = QHBoxLayout(f)
        lay.setContentsMargins(0, 0, 10, 0)
        lay.setSpacing(int(8 * s))

        chk = QLabel()
        chk.setFixedSize(int(16 * s), int(16 * s))
        chk.setStyleSheet("border: 1px solid #4F4A35; border-radius: 0px; background: transparent;")
        lay.addWidget(chk)

        edit = QLineEdit()
        edit.setFrame(False)
        edit.setFont(app_font(max(12, int(15 * s))))
        edit.setPlaceholderText("새로운 숙제를 추가하세요")
        edit.setStyleSheet("color: #4F4A35; background: transparent; border: none;")
        edit.returnPressed.connect(lambda: self.commit_inline_task(edit))
        lay.addWidget(edit, stretch=1)
        self.task_layout.addWidget(f)

    def commit_inline_task(self, edit_widget):
        txt = edit_widget.text().strip()
        if not txt: return
        self.tasks.append({
            "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
            "text": txt,
            "completed": False,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "completed_at": None
        })
        self.save_data()
        self.refresh_task_list()
        QApplication.processEvents()
        vbar = self.scroll.verticalScrollBar()
        vbar.setValue(vbar.maximum())

    def remove_task_row(self, row_widget):
        self.tasks = [t for t in self.tasks if t["id"] != row_widget.data["id"]]
        self.save_data()
        self.refresh_task_list()

    def render_archive_page(self, archive_items):
        while self.archive_layout.count():
            item = self.archive_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        s = self.scale_factor
        f_size = max(11, int(14 * s))
        for idx, t in enumerate(archive_items):
            row = QFrame()
            row.setFixedHeight(grid_row_height(idx))
            row.setStyleSheet("background: transparent;")
            lay = QHBoxLayout(row)
            lay.setContentsMargins(0, 0, 10, 0)
            lay.setSpacing(0)

            dt_str = ""
            if t.get("completed_at"):
                try: dt_str = datetime.strptime(t["completed_at"], "%Y-%m-%d %H:%M").strftime("%m.%d")
                except Exception: pass

            lbl_date = QLabel(dt_str)
            lbl_date.setFixedWidth(MARGIN_RED_X - 6)
            lbl_date.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            lbl_date.setFont(app_font(max(1, int(11 * s)), QFont.Weight.Bold))
            lbl_date.setStyleSheet("color: #E8706D; background: transparent; padding-right: 8px;")
            lay.addWidget(lbl_date)

            lbl_content = QLineEdit(t.get("text", ""))
            lbl_content.setFrame(False)
            lbl_content.setFont(app_font(f_size))
            lbl_content.setReadOnly(True)
            lbl_content.setStyleSheet("color: #918B78; text-decoration: line-through; background: transparent; padding-left: 20px;")
            lay.addWidget(lbl_content, stretch=1)

            lbl_time = QLabel(t["completed_at"].split(" ")[-1] if t.get("completed_at") else "")
            lbl_time.setFont(app_font(max(1, int(10 * s))))
            lbl_time.setStyleSheet("color: #918B78;")
            lay.addWidget(lbl_time)
            self.archive_layout.addWidget(row)

    def toggle_archive_view(self):
        if self.stacked_widget.currentIndex() == 0:
            self.stacked_widget.setCurrentIndex(1)
            self.btn_archive_toggle.setText("숙제 목록으로")
            self.lbl_main_title.setText("완료한 숙제")
        else:
            self.stacked_widget.setCurrentIndex(0)
            self.btn_archive_toggle.setText("완료한 숙제")
            self.lbl_main_title.setText("나만의 숙제")

    def toggle_custom_mode(self):
        self.is_custom_mode = not self.is_custom_mode
        if self.is_custom_mode:
            self.btn_custom.setText("커스텀 완료 ✓")
            self.btn_custom.setStyleSheet("background: #79A7C2; color: #FFFFFF; font-weight: bold; border-radius: 4px; padding: 4px 10px; border: none;")
            self.virtual_row_wrapper.setVisible(True)
            self.tag_wrapper.setVisible(True)
            self.memo_wrapper.setVisible(True)
            self.update_custom_mode_styles()
        else:
            self.btn_custom.setText("커스텀")
            self.btn_custom.setStyleSheet("background: #FFFDF0; border: 1px solid #C4BC87; border-radius: 4px; padding: 4px 8px; color: #4F4A35;")
            self.virtual_row_wrapper.setVisible(False)
            self.apply_visibility()
            self.save_data()
            self.refresh_task_list()

    def _install_module_click_filter(self, root, key, exclusions=()):
        root.setProperty("custom_module_key", key)
        root.installEventFilter(self)
        for child in root.findChildren(QWidget):
            if child in exclusions:
                continue
            child.setProperty("custom_module_key", key)
            child.installEventFilter(self)

    def eventFilter(self, obj, event):
        if self.is_custom_mode and event.type() == QEvent.Type.MouseButtonPress:
            key = obj.property("custom_module_key") if isinstance(obj, QWidget) else None
            if key and event.button() == Qt.MouseButton.LeftButton:
                self.settings[key] = not self.settings.get(key, True)
                self.update_custom_mode_styles()
                return True
        return super().eventFilter(obj, event)

    def on_module_click(self, key, widget):
        if not self.is_custom_mode:
            return
        self.settings[key] = not self.settings.get(key, True)
        self.update_custom_mode_styles()

    def update_custom_mode_styles(self):
        tag_active = self.settings.get("show_tags", True)
        # 이 두 색은 커스텀 모드 영역 하이라이트 전용입니다. 실제 alpha로 칠해
        # 뒤의 legal-pad ruling이 비치도록 합니다.
        tag_rgb = (121, 167, 194) if tag_active else (200, 111, 106)
        self.tag_wrapper.setStyleSheet(
            f"background-color: rgba({tag_rgb[0]}, {tag_rgb[1]}, {tag_rgb[2]}, 118); border-radius: 4px;"
        )
        self.tag_bar_frame.setStyleSheet("background: transparent; border: none;")
        self.btn_tag_edit.setStyleSheet("background: transparent; border: none;")

        memo_active = self.settings.get("show_memo", True)
        memo_rgb = (121, 167, 194) if memo_active else (200, 111, 106)
        self.memo_wrapper.setStyleSheet(
            f"background-color: rgba({memo_rgb[0]}, {memo_rgb[1]}, {memo_rgb[2]}, 118); border-radius: 4px;"
        )
        self.memo_frame.setStyleSheet("background: transparent; border: none;")
        self.memo_title_box.setStyleSheet("background: transparent; border: none;")
        self.lbl_memo_title.setStyleSheet("font-weight: bold; color: #4F4A35; text-decoration: underline; background: transparent;")

    def apply_visibility(self):
        self.tag_wrapper.setStyleSheet("background: transparent; border: none;")
        self.tag_bar_frame.setStyleSheet("background: transparent; border: none;")
        self.memo_wrapper.setStyleSheet("background: transparent; border: none;")
        self.memo_frame.setStyleSheet("background: transparent; border: none;")
        self.memo_title_box.setStyleSheet("background: transparent; border: none;")
        self.lbl_memo_title.setStyleSheet("font-weight: bold; color: #4F4A35; background: transparent; text-decoration: underline;")
        self.tag_wrapper.setVisible(self.settings.get("show_tags", True))
        self.memo_wrapper.setVisible(self.settings.get("show_memo", True))
        self.sync_grid()

    def on_memo_change(self):
        self.memo_text = self.txt_memo.toPlainText()
        self.update_memo_height()
        self.save_data()

    def update_memo_height(self):
        lines_count = len(self.memo_text.split("\n"))
        edit_lines = max(1, min(4, lines_count))
        self.memo_frame.setFixedHeight(grid_pos(1 + edit_lines))
        self.txt_memo.setFixedHeight(grid_pos(edit_lines))
        self.apply_memo_line_spacing()
        self.sync_grid()

    def apply_memo_line_spacing(self):
        try:
            self.txt_memo.blockSignals(True)
            cursor = self.txt_memo.textCursor()
            cursor.select(QTextCursor.SelectionType.Document)
            fmt = QTextBlockFormat()
            fmt.setLineHeight(float(GRID_PITCH), QTextBlockFormat.LineHeightTypes.FixedHeight.value)
            cursor.mergeBlockFormat(fmt)
            self.txt_memo.blockSignals(False)
        except Exception:
            self.txt_memo.blockSignals(False)

    def sync_preview_time_alignment(self, *_):
        """미리보기 time_box를 실제 숙제 time_box의 화면 X좌표에 맞춥니다.

        고정 4px 추정치가 아니라 현재 렌더링된 실제 행의 geometry를 측정하므로
        배율과 스크롤바 상태가 바뀌어도 같은 X축을 사용합니다.
        """
        if not hasattr(self, "virtual_row"):
            return
        self.virtual_row.set_scrollbar_width(SCROLLBAR_GUTTER)
        actual_row = None
        for i in range(self.task_layout.count()):
            w = self.task_layout.itemAt(i).widget()
            if isinstance(w, NoteTaskRow):
                actual_row = w
                break
        if actual_row is None or not actual_row.isVisible() or not self.virtual_row.isVisible():
            return
        actual_x = actual_row.time_box.mapToGlobal(actual_row.time_box.rect().topRight()).x()
        preview_x = self.virtual_row.time_box.mapToGlobal(self.virtual_row.time_box.rect().topRight()).x()
        delta = preview_x - actual_x
        if delta:
            self.virtual_row.adjust_trailing_spacer(delta)

    def on_scale_change(self, text):
        self.scale_factor = int(text.replace("%", "")) / 100.0
        self.settings["ui_scale"] = self.scale_factor
        self.save_data()
        self.apply_scale()
        self.render_tags()
        self.virtual_row.set_scale(self.scale_factor)
        self.update_minimum_width()
        self.refresh_task_list()
        self.sync_preview_time_alignment()

    def apply_scale(self):
        s = self.scale_factor
        if hasattr(self, "btn_close"):
            close_px = max(24, int(24 * s))
            self.btn_close.setFixedSize(close_px, close_px)
            self.btn_close.setFont(app_font(20, QFont.Weight.Normal))
        f_main = max(12, int(15 * s))
        self.lbl_memo_title.setFont(app_font(max(18, int(22 * s)), QFont.Weight.Bold))
        self.txt_memo.setFont(app_font(f_main))
        self.apply_memo_line_spacing()

    def load_data(self):
        self.tasks = []
        self.tags = []
        self.memo_text = ""
        self.settings = {
            "show_tags": True, "show_memo": True,
            "show_created_date": True, "show_created_time": True,
            "show_completed_date": True, "show_completed_time": True,
            "ui_scale": 1.0
        }
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    self.tasks = d.get("tasks", [])
                    self.tags = d.get("tags", self.tags)
                    self.memo_text = d.get("memo_text", "")
                    self.settings = d.get("settings", self.settings)
            except Exception: pass

    def save_data(self):
        d = {"tasks": self.tasks, "tags": self.tags, "memo_text": self.memo_text, "settings": self.settings}
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = ModernTodoApp()
    win.show()
    sys.exit(app.exec())