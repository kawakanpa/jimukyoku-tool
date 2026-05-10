"""
事務局ツール - メイン画面
tkinterによるシンプルGUI
"""
import os
import sys
import tkinter as tk
from datetime import date
from tkinter import filedialog, messagebox, ttk

# srcフォルダをパスに追加
sys.path.insert(0, os.path.dirname(__file__))

from csv_loader import load_csvs, load_settings
from kanzu_generator import generate_kanzu
from kyoshitu_generator import generate_kyoshitu
from schedule_builder import build_schedule

BASE_DIR    = os.path.dirname(os.path.dirname(__file__))
CONFIG_DIR  = os.path.join(BASE_DIR, "config")
INPUT_DIR   = os.path.join(BASE_DIR, "data", "input")
OUT_KANZU   = os.path.join(BASE_DIR, "data", "output", "鳥瞰図")
OUT_KYOSHITU = os.path.join(BASE_DIR, "data", "output", "教室案内表")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("事務局ツール - スケジュール自動生成")
        self.resizable(False, False)
        self.settings = load_settings(CONFIG_DIR)
        self._csv_paths: list[str] = []
        self._build_ui()

    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}

        # ── CSVファイル選択 ──
        frm_csv = ttk.LabelFrame(self, text="① CSVファイル（複数選択可）")
        frm_csv.grid(row=0, column=0, columnspan=2, sticky="ew", **pad)

        self.csv_listbox = tk.Listbox(frm_csv, height=5, width=60)
        self.csv_listbox.pack(side="left", fill="both", expand=True, padx=4, pady=4)

        frm_btns = ttk.Frame(frm_csv)
        frm_btns.pack(side="left", padx=4)
        ttk.Button(frm_btns, text="追加", command=self._add_csv).pack(fill="x", pady=2)
        ttk.Button(frm_btns, text="削除", command=self._remove_csv).pack(fill="x", pady=2)
        ttk.Button(frm_btns, text="全削除", command=self._clear_csv).pack(fill="x", pady=2)

        # ── 出力設定 ──
        frm_out = ttk.LabelFrame(self, text="② 出力設定")
        frm_out.grid(row=1, column=0, columnspan=2, sticky="ew", **pad)

        # 教室案内表：年月
        ttk.Label(frm_out, text="教室案内表の年:").grid(row=0, column=0, sticky="e", padx=4, pady=3)
        self.var_year = tk.StringVar(value=str(date.today().year))
        ttk.Entry(frm_out, textvariable=self.var_year, width=6).grid(row=0, column=1, sticky="w")

        ttk.Label(frm_out, text="月:").grid(row=0, column=2, sticky="e", padx=4)
        self.var_month = tk.StringVar(value=str(date.today().month))
        ttk.Entry(frm_out, textvariable=self.var_month, width=4).grid(row=0, column=3, sticky="w")

        # 鳥瞰図：開始〜終了
        ttk.Label(frm_out, text="鳥瞰図 開始日(YYYY/MM/DD):").grid(row=1, column=0, sticky="e", padx=4, pady=3)
        self.var_start = tk.StringVar()
        ttk.Entry(frm_out, textvariable=self.var_start, width=14).grid(row=1, column=1, columnspan=2, sticky="w")

        ttk.Label(frm_out, text="終了日:").grid(row=1, column=3, sticky="e", padx=4)
        self.var_end = tk.StringVar()
        ttk.Entry(frm_out, textvariable=self.var_end, width=14).grid(row=1, column=4, sticky="w")

        # 生成チェック
        self.var_do_kyoshitu = tk.BooleanVar(value=True)
        self.var_do_kanzu    = tk.BooleanVar(value=True)
        ttk.Checkbutton(frm_out, text="教室案内表を生成", variable=self.var_do_kyoshitu).grid(
            row=2, column=0, columnspan=2, sticky="w", padx=4, pady=2)
        ttk.Checkbutton(frm_out, text="鳥瞰図を生成", variable=self.var_do_kanzu).grid(
            row=2, column=2, columnspan=2, sticky="w", padx=4, pady=2)

        # ── 実行ボタン ──
        ttk.Button(self, text="▶ 生成実行", command=self._run,
                   style="Accent.TButton").grid(row=2, column=0, columnspan=2, pady=10)

        # ── ログ表示 ──
        frm_log = ttk.LabelFrame(self, text="ログ")
        frm_log.grid(row=3, column=0, columnspan=2, sticky="ew", **pad)
        self.log_text = tk.Text(frm_log, height=8, width=72, state="disabled")
        self.log_text.pack(fill="both", padx=4, pady=4)

    def _add_csv(self):
        files = filedialog.askopenfilenames(
            title="CSVファイルを選択",
            initialdir=INPUT_DIR,
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        for f in files:
            if f not in self._csv_paths:
                self._csv_paths.append(f)
                self.csv_listbox.insert("end", os.path.basename(f))

    def _remove_csv(self):
        sel = self.csv_listbox.curselection()
        for i in reversed(sel):
            self.csv_listbox.delete(i)
            self._csv_paths.pop(i)

    def _clear_csv(self):
        self.csv_listbox.delete(0, "end")
        self._csv_paths.clear()

    def _log(self, msg: str):
        self.log_text.config(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")
        self.update_idletasks()

    def _run(self):
        if not self._csv_paths:
            messagebox.showwarning("警告", "CSVファイルを選択してください。")
            return

        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

        try:
            self._log("CSV読み込み中...")
            records = load_csvs(self._csv_paths, self.settings)
            self._log(f"  → {len(records)}件のレッスンを読み込みました")

            self._log("スケジュール構築中...")
            schedule = build_schedule(records, self.settings)

            results = []

            if self.var_do_kyoshitu.get():
                year  = int(self.var_year.get())
                month = int(self.var_month.get())
                self._log(f"教室案内表生成中（{year}年{month}月）...")
                out = generate_kyoshitu(schedule, self.settings, year, month, OUT_KYOSHITU)
                self._log(f"  → 保存: {out}")
                results.append(out)

            if self.var_do_kanzu.get():
                from datetime import datetime
                s = datetime.strptime(self.var_start.get().strip(), "%Y/%m/%d").date()
                e = datetime.strptime(self.var_end.get().strip(), "%Y/%m/%d").date()
                label = f"{s.strftime('%Y.%m')}-{e.strftime('%m月')}"
                self._log(f"鳥瞰図生成中（{s}〜{e}）...")
                out = generate_kanzu(schedule, self.settings, s, e, OUT_KANZU, label)
                self._log(f"  → 保存: {out}")
                results.append(out)

            self._log("✓ 完了しました。")
            if messagebox.askyesno("完了", "生成が完了しました。\n出力フォルダを開きますか？"):
                os.startfile(os.path.dirname(results[0]))

        except ValueError as e:
            messagebox.showerror("入力エラー", str(e))
            self._log(f"[エラー] {e}")
        except Exception as e:
            messagebox.showerror("エラー", str(e))
            self._log(f"[エラー] {e}")
            import traceback
            self._log(traceback.format_exc())


if __name__ == "__main__":
    app = App()
    app.mainloop()
