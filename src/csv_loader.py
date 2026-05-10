"""
CSVファイル読み込みモジュール
- CP932エンコード対応
- 「レッスン」以外（出講不可・要調整）を自動除外
- 複数ファイルの統合
"""
import csv
import json
import os
import re
from dataclasses import dataclass, field
from datetime import date, time, datetime
from pathlib import Path
from typing import Optional


@dataclass
class LessonRecord:
    date: date
    start_time: time
    end_time: time
    classroom_code: str
    subject_raw: str
    instructor_name: str
    instructor_code: str
    level: str = ""
    subject: str = ""

    def __post_init__(self):
        self.level, self.subject = _parse_subject(self.subject_raw)


def _parse_subject(raw: str) -> tuple[str, str]:
    """
    "b 一般知能(120)" → ("初級", "一般知能")
    "a 法律入門(行政法)(120)" → ("上級", "法律入門(行政法)")
    """
    raw = raw.strip()
    level_map = {"a": "上級", "b": "初級"}

    m = re.match(r'^([ab])\s+(.+?)(?:\(\d+\))?\s*$', raw)
    if m:
        level = level_map.get(m.group(1), m.group(1))
        subject = m.group(2).strip()
        return level, subject

    return "", raw


def load_csvs(paths: list[str], settings: dict) -> list[LessonRecord]:
    """
    複数CSVを読み込んで統合し、レッスンのみ返す。
    paths: CSVファイルパスのリスト
    """
    filter_cfg = settings.get("lesson_filter", {})
    allowed_code = filter_cfg.get("business_code", "")
    allowed_type = filter_cfg.get("business_type", "レッスン")
    encoding = settings.get("encoding", "cp932")

    seen: set[tuple] = set()
    records: list[LessonRecord] = []
    for path in paths:
        for rec in _load_one(path, encoding, allowed_code, allowed_type):
            key = (rec.date, rec.start_time, rec.end_time,
                   rec.classroom_code, rec.instructor_code)
            if key not in seen:
                seen.add(key)
                records.append(rec)

    records.sort(key=lambda r: (r.date, r.start_time))
    return records


def _load_one(path: str, encoding: str, allowed_code: str, allowed_type: str) -> list[LessonRecord]:
    records = []
    with open(path, encoding=encoding, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = row.get("講師業務コード", "").strip()
            btype = row.get("講師業務", "").strip()
            if code != allowed_code or btype != allowed_type:
                continue

            classroom = row.get("教室", "").strip()
            if not classroom:
                continue

            try:
                d = datetime.strptime(row["開始日"].strip(), "%Y/%m/%d").date()
                st = datetime.strptime(row["開始時刻"].strip(), "%H:%M").time()
                et = datetime.strptime(row["終了時刻"].strip(), "%H:%M").time()
            except (ValueError, KeyError):
                continue

            rec = LessonRecord(
                date=d,
                start_time=st,
                end_time=et,
                classroom_code=classroom,
                subject_raw=row.get("スケジュール内容", "").strip(),
                instructor_name=row.get("講師名", "").strip(),
                instructor_code=row.get("講師コード", "").strip(),
            )
            records.append(rec)
    return records


def load_settings(config_dir: str) -> dict:
    path = os.path.join(config_dir, "settings.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)
