"""
事務局ツール - Streamlit Webアプリ版
社内LAN経由でブラウザからアクセスして使用する。
"""
import calendar as _cal
import os
import sys
import tempfile
from datetime import date, datetime, time

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(__file__))

from csv_loader import LessonRecord, load_csvs, load_settings
from kanzu_generator import generate_kanzu
from kyoshitu_generator import generate_kyoshitu
from schedule_builder import build_schedule

BASE_DIR   = os.path.dirname(os.path.dirname(__file__))
CONFIG_DIR = os.path.join(BASE_DIR, "config")

LEVEL_OPTIONS = ["上級", "初級", ""]

COLUMN_CONFIG = {
    "日付":     st.column_config.DateColumn("日付", format="YYYY/MM/DD", required=True),
    "開始時刻": st.column_config.TextColumn("開始時刻", help="例：13:00", required=True),
    "終了時刻": st.column_config.TextColumn("終了時刻", help="例：15:20"),
    "教室コード": st.column_config.TextColumn("教室コード", help="例：102初級全日"),
    "科目":     st.column_config.TextColumn("科目", help="例：一般知能"),
    "レベル":   st.column_config.SelectboxColumn("レベル", options=LEVEL_OPTIONS),
    "講師名":   st.column_config.TextColumn("講師名"),
}

EMPTY_COLUMNS = ["日付", "開始時刻", "終了時刻", "教室コード", "科目", "レベル", "講師名"]


def _date_input_ja(label: str, key: str, default: date, sync_to: str = None) -> date:
    """カレンダー選択 + 年・月・日の数字入力（連動）。sync_toを指定すると変更時に終了日へ自動コピー。"""
    y_key, m_key, d_key, p_key = f"{key}_y", f"{key}_m", f"{key}_d", f"{key}_p"

    if y_key not in st.session_state:
        st.session_state[y_key] = default.year
        st.session_state[m_key] = default.month
        st.session_state[d_key] = default.day

    def _push_to_end():
        if sync_to:
            y = int(st.session_state[y_key])
            m = int(st.session_state[m_key])
            d = min(int(st.session_state[d_key]), _cal.monthrange(y, m)[1])
            st.session_state[f"{sync_to}_y"] = y
            st.session_state[f"{sync_to}_m"] = m
            st.session_state[f"{sync_to}_d"] = d
            st.session_state[f"{sync_to}_p"] = date(y, m, d)

    def _sync_calendar():
        picked = st.session_state[p_key]
        st.session_state[y_key] = picked.year
        st.session_state[m_key] = picked.month
        st.session_state[d_key] = picked.day
        _push_to_end()

    st.write(f"**{label}**")
    y0 = int(st.session_state[y_key])
    m0 = int(st.session_state[m_key])
    d0 = min(int(st.session_state[d_key]), _cal.monthrange(y0, m0)[1])
    st.date_input("", value=date(y0, m0, d0), key=p_key, on_change=_sync_calendar,
                  label_visibility="collapsed", format="YYYY/MM/DD")

    c1, c2, c3 = st.columns([3, 2, 2])
    with c1:
        st.number_input("年", 2020, 2035, step=1, key=y_key, on_change=_push_to_end)
    with c2:
        st.number_input("月", 1, 12, step=1, key=m_key, on_change=_push_to_end)
    with c3:
        max_d = _cal.monthrange(int(st.session_state[y_key]), int(st.session_state[m_key]))[1]
        if int(st.session_state[d_key]) > max_d:
            st.session_state[d_key] = max_d
        st.number_input("日", 1, max_d, step=1, key=d_key, on_change=_push_to_end)

    return date(
        int(st.session_state[y_key]),
        int(st.session_state[m_key]),
        min(int(st.session_state[d_key]), max_d),
    )


def _empty_df() -> pd.DataFrame:
    return pd.DataFrame(columns=EMPTY_COLUMNS)


def _records_to_df(records: list[LessonRecord]) -> pd.DataFrame:
    rows = [
        {
            "日付":       r.date,
            "開始時刻":   r.start_time.strftime("%H:%M"),
            "終了時刻":   r.end_time.strftime("%H:%M"),
            "教室コード": r.classroom_code,
            "科目":       r.subject,
            "レベル":     r.level,
            "講師名":     r.instructor_name,
        }
        for r in records
    ]
    return pd.DataFrame(rows, columns=EMPTY_COLUMNS)


def _df_to_records(df: pd.DataFrame) -> list[LessonRecord]:
    records = []
    for _, row in df.iterrows():
        try:
            d_val = row["日付"]
            if pd.isna(d_val) or str(d_val).strip() == "":
                continue
            d = d_val if isinstance(d_val, date) else datetime.strptime(str(d_val).strip()[:10], "%Y-%m-%d").date()
            st_t = datetime.strptime(str(row["開始時刻"]).strip(), "%H:%M").time()
            et_t = datetime.strptime(str(row["終了時刻"]).strip(), "%H:%M").time()
        except Exception:
            continue

        rec = LessonRecord(
            date=d,
            start_time=st_t,
            end_time=et_t,
            classroom_code=str(row["教室コード"]).strip(),
            subject_raw=str(row["科目"]).strip(),
            instructor_name=str(row["講師名"]).strip(),
            instructor_code="",
        )
        rec.level   = str(row["レベル"]).strip() if not pd.isna(row["レベル"]) else ""
        rec.subject = str(row["科目"]).strip()
        records.append(rec)
    return records


def _kyoshitu_bytes(schedule, settings, start: date, end: date) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        path = generate_kyoshitu(schedule, settings, start, end, tmp)
        with open(path, "rb") as f:
            return f.read()


def _kanzu_bytes(schedule, settings, s: date, e: date, label: str) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        path = generate_kanzu(schedule, settings, s, e, tmp, label)
        with open(path, "rb") as f:
            return f.read()


def _merge_df(existing: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    combined = pd.concat([existing, new], ignore_index=True)
    return combined.drop_duplicates(
        subset=["日付", "開始時刻", "終了時刻", "教室コード", "講師名"]
    ).reset_index(drop=True)


# ──────────────────────────────────────────────
# メイン
# ──────────────────────────────────────────────

def _check_password() -> bool:
    """パスワード保護。secrets.toml未設定時（ローカル起動）はスキップ。"""
    try:
        required = st.secrets["password"]
    except (KeyError, FileNotFoundError):
        return True  # ローカル開発時はパスワード不要

    if st.session_state.get("authenticated"):
        return True

    st.title("事務局ツール")
    pw = st.text_input("パスワード", type="password", placeholder="パスワードを入力してください")
    if st.button("ログイン", type="primary"):
        if pw == required:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("パスワードが違います")
    return False


def main():
    st.set_page_config(page_title="事務局ツール", layout="wide")

    if not _check_password():
        st.stop()

    st.title("事務局ツール　スケジュール自動生成")

    settings = load_settings(CONFIG_DIR)

    if "df" not in st.session_state:
        st.session_state.df = _empty_df()

    tab1, tab2, tab3 = st.tabs(["① データ管理", "② 教室案内表", "③ 鳥瞰図"])

    # ══════════════════════════════════════════
    # タブ① データ管理
    # ══════════════════════════════════════════
    with tab1:
        st.subheader("CSVファイルを取り込む")
        uploaded = st.file_uploader(
            "CSVファイルを選択（複数可）",
            type=["csv"],
            accept_multiple_files=True,
            key="csv_uploader",
        )

        col_btn, col_clear, _ = st.columns([1, 1, 6])
        with col_btn:
            if st.button("取り込む", type="primary", disabled=not uploaded):
                with tempfile.TemporaryDirectory() as tmp:
                    paths = []
                    for uf in uploaded:
                        p = os.path.join(tmp, uf.name)
                        with open(p, "wb") as fw:
                            fw.write(uf.getvalue())
                        paths.append(p)
                    try:
                        records = load_csvs(paths, settings)
                        new_df  = _records_to_df(records)
                        st.session_state.df = _merge_df(st.session_state.df, new_df)
                        st.success(f"{len(records)} 件を読み込みました（合計 {len(st.session_state.df)} 件）")
                    except Exception as ex:
                        st.error(str(ex))

        with col_clear:
            if st.button("全クリア"):
                st.session_state.df = _empty_df()
                st.rerun()

        st.divider()
        st.subheader("レッスンデータ（直接編集・行追加・削除も可）")

        edited = st.data_editor(
            st.session_state.df,
            column_config=COLUMN_CONFIG,
            num_rows="dynamic",
            use_container_width=True,
            key="editor",
        )
        st.session_state.df = edited
        st.caption(f"合計 {len(edited)} 件")

    # ══════════════════════════════════════════
    # タブ② 教室案内表
    # ══════════════════════════════════════════
    with tab2:
        st.subheader("教室案内表を生成")
        c1, c2 = st.columns(2)
        with c1:
            kyoshitu_start = _date_input_ja("開始日", "kyoshitu_start", date.today(), sync_to="kyoshitu_end")
        with c2:
            kyoshitu_end = _date_input_ja("終了日", "kyoshitu_end", date.today())

        if st.button("教室案内表を生成", type="primary", key="gen_kyoshitu"):
            if kyoshitu_start > kyoshitu_end:
                st.error("開始日が終了日より後になっています。")
            else:
                records = _df_to_records(st.session_state.df)
                if not records:
                    st.warning("データがありません。先にCSVを取り込むか、データを入力してください。")
                else:
                    with st.spinner("生成中..."):
                        schedule = build_schedule(records, settings)
                        data = _kyoshitu_bytes(schedule, settings, kyoshitu_start, kyoshitu_end)
                    label = f"{kyoshitu_start.strftime('%Y.%m.%d')}-{kyoshitu_end.strftime('%m.%d')}"
                    fname = f"教室案内表_{label}.xlsx"
                    st.download_button(
                        label=f"📥 {fname} をダウンロード",
                        data=data,
                        file_name=fname,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )

    # ══════════════════════════════════════════
    # タブ③ 鳥瞰図
    # ══════════════════════════════════════════
    with tab3:
        st.subheader("鳥瞰図を生成")
        c1, c2 = st.columns(2)
        with c1:
            start_d = _date_input_ja("開始日", "kanzu_start", date.today(), sync_to="kanzu_end")
        with c2:
            end_d = _date_input_ja("終了日", "kanzu_end", date.today())

        if st.button("鳥瞰図を生成", type="primary", key="gen_kanzu"):
            if start_d > end_d:
                st.error("開始日が終了日より後になっています。")
            else:
                records = _df_to_records(st.session_state.df)
                if not records:
                    st.warning("データがありません。先にCSVを取り込むか、データを入力してください。")
                else:
                    with st.spinner("生成中..."):
                        schedule = build_schedule(records, settings)
                        label = f"{start_d.strftime('%Y.%m')}-{end_d.strftime('%m月')}"
                        data = _kanzu_bytes(schedule, settings, start_d, end_d, label)
                    fname = f"鳥瞰図_{label}.xlsx"
                    st.download_button(
                        label=f"📥 {fname} をダウンロード",
                        data=data,
                        file_name=fname,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )


if __name__ == "__main__":
    main()
