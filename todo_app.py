import sys
import json
import os
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import ttk, messagebox

DATA_FILE = "tasks_data.json"

class TodoApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Todo & Notes")
        self.geometry("640x720")
        self.configure(bg="#F2F2F7")

        self.tasks = []
        self.log_memo = ""
        self.load_data()

        self.setup_ui()
        self.refresh_task_lists()

    def setup_ui(self):
        # 상단 탭 스타일
        style = ttk.Style()
        style.theme_use("default")
        style.configure("TNotebook", background="#F2F2F7", borderwidth=0)
        style.configure("TNotebook.Tab", background="#E3E3E8", padding=[15, 6], font=("Apple SD Gothic Neo", 10, "bold"))
        style.map("TNotebook.Tab", background=[("selected", "#FFFFFF")])

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=16, pady=16)

        # 탭 1: 할 일 목록
        self.tab_active = tk.Frame(self.notebook, bg="#F2F2F7")
        self.notebook.add(self.tab_active, text="할 일 목록")
        self.build_active_tab()

        # 탭 2: 완료된 숙제 보관함
        self.tab_archive = tk.Frame(self.notebook, bg="#F2F2F7")
        self.notebook.add(self.tab_archive, text="완료된 숙제함")
        self.build_archive_tab()

        # 탭 3: 로그 메모장
        self.tab_memo = tk.Frame(self.notebook, bg="#F2F2F7")
        self.notebook.add(self.tab_memo, text="로그 메모장")
        self.build_memo_tab()

    # --- 탭 1: 활성 할 일 화면 ---
    def build_active_tab(self):
        # 상단 입력 바
        input_frame = tk.Frame(self.tab_active, bg="#FFFFFF", padx=10, pady=8)
        input_frame.pack(fill="x", pady=(0, 10))

        self.entry_task = tk.Entry(input_frame, font=("Apple SD Gothic Neo", 12), relief="flat", bg="#FFFFFF")
        self.entry_task.pack(side="left", fill="x", expand=True, padx=(5, 10))
        self.entry_task.bind("<Return>", lambda e: self.add_task())

        btn_add = tk.Button(input_frame, text="등록", bg="#E5A100", fg="#FFFFFF", relief="flat",
                            font=("Apple SD Gothic Neo", 10, "bold"), padx=12, pady=4,
                            cursor="hand2", command=self.add_task)
        btn_add.pack(side="right")

        # 스크롤 가능한 리스트 프레임
        self.active_scroll_frame = self.create_scrollable_container(self.tab_active)

    # --- 탭 2: 보관함 화면 ---
    def build_archive_tab(self):
        self.archive_scroll_frame = self.create_scrollable_container(self.tab_archive)

    # --- 탭 3: 로그 메모장 화면 ---
    def build_memo_tab(self):
        memo_frame = tk.Frame(self.tab_memo, bg="#FFFFFF", padx=12, pady=12)
        memo_frame.pack(fill="both", expand=True)

        self.txt_memo = tk.Text(memo_frame, font=("Apple SD Gothic Neo", 11), relief="flat", wrap="word", bg="#FFFFFF")
        self.txt_memo.pack(fill="both", expand=True)
        self.txt_memo.insert("1.0", self.log_memo)
        self.txt_memo.bind("<KeyRelease>", self.save_memo)

    def create_scrollable_container(self, parent):
        canvas = tk.Canvas(parent, bg="#F2F2F7", highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#F2F2F7")

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=600)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        return scrollable_frame

    # --- 데이터 처리 로직 ---
    def add_task(self):
        text = self.entry_task.get().strip()
        if not text:
            return
        
        task = {
            "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
            "text": text,
            "completed": False,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "completed_at": None
        }
        self.tasks.insert(0, task)
        self.entry_task.delete(0, tk.END)
        self.save_data()
        self.refresh_task_lists()

    def toggle_task(self, task):
        task["completed"] = not task["completed"]
        if task["completed"]:
            task["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        else:
            task["completed_at"] = None
        self.save_data()
        self.refresh_task_lists()

    def update_task_text(self, task, new_text):
        if task["text"] != new_text:
            task["text"] = new_text
            self.save_data()

    def delete_task(self, task_id):
        self.tasks = [t for t in self.tasks if t["id"] != task_id]
        self.save_data()
        self.refresh_task_lists()

    def refresh_task_lists(self):
        for widget in self.active_scroll_frame.winfo_children():
            widget.destroy()
        for widget in self.archive_scroll_frame.winfo_children():
            widget.destroy()

        now = datetime.now()
        one_day = timedelta(days=1)

        active_count = 0
        archive_count = 0

        for task in self.tasks:
            is_done = task["completed"]
            completed_time = None
            if is_done and task.get("completed_at"):
                completed_time = datetime.strptime(task["completed_at"], "%Y-%m-%d %H:%M")

            # 24시간 경과 판정: 완료된 후 하루가 지나면 아카이브(보관함)
            is_archived = is_done and completed_time and (now - completed_time > one_day)

            target_frame = self.archive_scroll_frame if is_archived else self.active_scroll_frame
            if is_archived:
                archive_count += 1
            else:
                active_count += 1

            self.render_task_item(target_frame, task)

        if active_count == 0:
            tk.Label(self.active_scroll_frame, text="할 일이 없습니다.", bg="#F2F2F7", fg="#8E8E93").pack(pady=20)
        if archive_count == 0:
            tk.Label(self.archive_scroll_frame, text="완료 후 하루가 지난 숙제가 보관됩니다.", bg="#F2F2F7", fg="#8E8E93").pack(pady=20)

    def render_task_item(self, parent, task):
        item = tk.Frame(parent, bg="#FFFFFF", padx=10, pady=8)
        item.pack(fill="x", pady=4, padx=2)

        # 동그라미 체크 토글 버튼 (아이폰 메모 체크박스 대용)
        check_symbol = "●" if task["completed"] else "○"
        check_fg = "#E5A100" if task["completed"] else "#C7C7CC"
        btn_chk = tk.Button(item, text=check_symbol, font=("Arial", 14), fg=check_fg,
                            relief="flat", bg="#FFFFFF", bd=0, cursor="hand2",
                            command=lambda t=task: self.toggle_task(t))
        btn_chk.pack(side="left", padx=(0, 8))

        # 본문 및 메타데이터 컨테이너
        center = tk.Frame(item, bg="#FFFFFF")
        center.pack(side="left", fill="x", expand=True)

        # 상시 수정 가능한 Entry (아이폰 메모처럼 즉시 편집 가능)
        entry_text = tk.Entry(center, font=("Apple SD Gothic Neo", 11), relief="flat", bg="#FFFFFF")
        entry_text.insert(0, task["text"])
        entry_text.pack(fill="x")

        # 완료 시 회색 글자 및 취소선 효과 대신 색상 흐림 처리
        if task["completed"]:
            entry_text.configure(fg="#8E8E93")
        else:
            entry_text.configure(fg="#1C1C1E")

        # 수정 후 포커스 빠질 때 자동 저장
        entry_text.bind("<FocusOut>", lambda e, t=task, ent=entry_text: self.update_task_text(t, ent.get()))

        # 등록/완료 일시 표시
        meta_str = f"등록: {task['created_at']}"
        if task.get("completed_at"):
            meta_str += f" | 완료: {task['completed_at']}"
        lbl_meta = tk.Label(center, text=meta_str, font=("Apple SD Gothic Neo", 8), fg="#8E8E93", bg="#FFFFFF", anchor="w")
        lbl_meta.pack(fill="x")

        # 삭제 버튼
        btn_del = tk.Button(item, text="✕", font=("Arial", 9), fg="#FF3B30", relief="flat",
                            bg="#FFFFFF", bd=0, cursor="hand2",
                            command=lambda tid=task["id"]: self.delete_task(tid))
        btn_del.pack(side="right", padx=(8, 0))

    def save_memo(self, event=None):
        self.log_memo = self.txt_memo.get("1.0", tk.END)
        self.save_data()

    def load_data(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.tasks = data.get("tasks", [])
                    self.log_memo = data.get("memo", "")
            except Exception:
                self.tasks = []
                self.log_memo = ""

    def save_data(self):
        data = {
            "tasks": self.tasks,
            "memo": self.log_memo
        }
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    app = TodoApp()
    app.mainloop()