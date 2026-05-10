"""
スケジュールデータモデル
- 物理教室番号への変換
- 時間帯への変換
- 日付・教室・時間帯でのルックアップ構造を構築
"""
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, time
from typing import Optional

from csv_loader import LessonRecord


@dataclass
class SlotEntry:
    """1コマ分のデータ"""
    room: int
    time_slot: str
    level: str
    subject: str
    instructor: str
    classroom_code: str


# date → room → time_slot → list[SlotEntry]
ScheduleMap = dict[date, dict[int, dict[str, list[SlotEntry]]]]


def build_schedule(records: list[LessonRecord], settings: dict) -> ScheduleMap:
    classroom_map: dict[str, int] = settings.get("classroom_mapping", {})
    slot_map: dict[str, str] = settings.get("time_slot_by_start", {})

    unknown_classrooms: set[str] = set()
    unknown_times: set[str] = set()

    schedule: ScheduleMap = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for rec in records:
        room = classroom_map.get(rec.classroom_code)
        if room is None:
            unknown_classrooms.add(rec.classroom_code)
            continue

        time_key = rec.start_time.strftime("%H:%M")
        time_slot = slot_map.get(time_key)
        if time_slot is None:
            unknown_times.add(f"{rec.date} {time_key}")
            continue

        entry = SlotEntry(
            room=room,
            time_slot=time_slot,
            level=rec.level,
            subject=rec.subject,
            instructor=_short_name(rec.instructor_name),
            classroom_code=rec.classroom_code,
        )
        schedule[rec.date][room][time_slot].append(entry)

    if unknown_classrooms:
        print(f"[警告] settings.jsonに未登録の教室コード: {unknown_classrooms}")
    if unknown_times:
        print(f"[警告] settings.jsonに未登録の開始時刻: {unknown_times}")

    return dict(schedule)


def _short_name(name: str) -> str:
    """「川畑　享稔」→「川畑」（姓のみ）"""
    return name.split()[0] if name else ""


def get_entry_label(entries: list[SlotEntry]) -> str:
    """複数エントリを1セルのテキストにまとめる（合同クラス対応）"""
    parts = []
    for e in entries:
        parts.append(f"{e.subject}\n{e.instructor}")
    return "\n／\n".join(parts)
