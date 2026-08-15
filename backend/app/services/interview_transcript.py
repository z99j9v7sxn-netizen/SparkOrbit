"""讯飞 IAT wpgs 动态修正：按句序号 sn 组装全量字幕。

讯飞 dwa=wpgs 语义：
- 每帧带 sn（句子序号）
- pgs=apd：把本帧文本写入 sn
- pgs=rpl：先按 rg（sn 闭区间）删除旧句，再写入本帧 sn
"""
from __future__ import annotations


class TranscriptAssembler:
    def __init__(self) -> None:
        self._segments: dict[int, str] = {}

    def reset(self) -> None:
        self._segments = {}

    @property
    def text(self) -> str:
        return "".join(self._segments[k] for k in sorted(self._segments))

    @property
    def words(self) -> list[str]:
        return list(self.text)

    def push(self, sn: int, words: list[str], pgs: str = "", rg: list[int] | None = None) -> str:
        incoming = "".join(w for w in (words or []) if w)
        mode = (pgs or "").strip().lower()
        if mode == "rpl" and rg and len(rg) >= 2:
            start = int(rg[0])
            end = int(rg[1])
            for i in range(min(start, end), max(start, end) + 1):
                self._segments.pop(i, None)
        if sn or incoming:
            self._segments[int(sn)] = incoming
        return self.text

    def push_text(self, text: str) -> str:
        """文本兜底：整段覆盖当前结果。"""
        self._segments = {1: str(text or "").strip()}
        return self.text
