from app.services.interview_scoring import analyze_prosody, fuse_scores
from app.services.interview_transcript import TranscriptAssembler


def test_fuse_scores_three_modalities():
    fused, degraded = fuse_scores(80, 60, 40)
    assert degraded == []
    # 80*0.70 + 60*0.15 + 40*0.15 = 56+9+6 = 71
    assert fused == 71.0


def test_fuse_scores_missing_visual_normalizes():
    fused, degraded = fuse_scores(80, 60, None)
    assert degraded == ["visual"]
    # remaining weights 0.70+0.15=0.85 → 80*0.70/0.85 + 60*0.15/0.85
    expected = round(80 * (0.70 / 0.85) + 60 * (0.15 / 0.85), 1)
    assert fused == expected


def test_fuse_scores_semantic_only():
    fused, degraded = fuse_scores(90, None, None)
    assert set(degraded) == {"prosody", "visual"}
    assert fused == 90.0


def test_fuse_scores_all_missing():
    fused, degraded = fuse_scores(None, None, None)
    assert fused == 0.0
    assert set(degraded) == {"semantic", "prosody", "visual"}


def test_analyze_prosody_short_answer():
    result = analyze_prosody(transcript="嗯", duration_sec=2.0, silence_sec=0.5)
    assert result["score"] < 70
    assert result["filler_count"] >= 1


def test_analyze_prosody_natural_speech():
    text = "我在这个项目里负责接口设计和数据库索引优化，把查询耗时从八百毫秒降到一百毫秒。"
    result = analyze_prosody(transcript=text, duration_sec=8.0, silence_sec=0.6)
    assert result["char_count"] > 20
    assert result["score"] >= 70


def test_wpgs_append_then_replace():
    asm = TranscriptAssembler()
    asm.push(1, ["今", "天"], "apd", None)
    asm.push(2, ["天", "气"], "apd", None)
    assert asm.text == "今天天气"
    # rpl rg 是 sn 闭区间：替换 sn=2
    asm.push(2, ["很", "好"], "rpl", [2, 2])
    assert asm.text == "今天很好"


def test_wpgs_replace_from_start():
    asm = TranscriptAssembler()
    asm.push(1, ["我", "是", "学", "生"], "apd", None)
    asm.push(1, ["我", "是", "候", "选", "人"], "rpl", [1, 1])
    assert asm.text == "我是候选人"


def test_wpgs_replace_multi_sentence():
    asm = TranscriptAssembler()
    asm.push(1, ["盒子", "有"], "apd", None)
    asm.push(2, ["四", "层"], "apd", None)
    asm.push(3, ["结", "构"], "apd", None)
    assert asm.text == "盒子有四层结构"
    asm.push(2, ["内", "容"], "rpl", [2, 3])
    assert asm.text == "盒子有内容"
