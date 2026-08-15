"""Track B：花名册 CSV / 成绩导出 / 衰减阶段解析冒烟。"""

from app.services.memory_decay import _stages_from_days
from app.services.teacher_extras import gradebook_to_csv, parse_roster_csv


def test_parse_roster_csv_with_header():
    raw = "username,display_name,password\ns01,Alice,pass123\ns02,Bob,\n"
    rows = parse_roster_csv(raw)
    assert len(rows) == 2
    assert rows[0] == {"username": "s01", "display_name": "Alice", "password": "pass123"}
    assert rows[1]["password"] == "123456"
    assert rows[1]["display_name"] == "Bob"


def test_parse_roster_csv_chinese_header():
    raw = "学号,姓名\n2026001,王小明\n"
    rows = parse_roster_csv(raw.encode("utf-8-sig"))
    assert rows == [{"username": "2026001", "display_name": "王小明", "password": "123456"}]


def test_gradebook_to_csv_bom():
    text = gradebook_to_csv(
        [
            {
                "display_name": "张,三",
                "username": "zhang",
                "mastery_rate": 88,
                "quiz_accuracy": 70,
                "assignment_avg": None,
                "lit_count": 4,
                "total_planets": 10,
                "user_id": "u1",
            }
        ]
    )
    assert text.startswith("\ufeff")
    assert '"张,三"' in text
    assert "4/10" in text


def test_decay_stages_monotonic():
    stages = _stages_from_days({"fading": 10, "meteor": 5, "dim": 6})
    assert stages[0][0] == 10
    assert stages[1][0] > stages[0][0]
    assert stages[2][0] > stages[1][0]
