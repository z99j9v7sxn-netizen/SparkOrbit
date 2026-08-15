"""多语种口语与听力训练智能体。"""
from __future__ import annotations

from app.schemas.extras import OralPracticeIn, OralPracticeOut
from app.services.audio_preprocess import convert_to_pcm16k
from app.services.asr_service import transcribe_pcm
from app.services.cantonese_ai_service import cantonese_score_pronunciation, cantonese_stt
from app.services.ise_service import evaluate_pronunciation
from app.services.llm import extract_json, llm_chat


CABIN_PROMPTS = {
    "cet4-speaking": "你是大学英语四级口语考官。使用难度适中的英语提问，并用中文简短点评。",
    "cet6-speaking": "你是大学英语六级口语考官。使用较正式的英语追问观点，并用中文简短点评。",
    "ielts-speaking": "你是雅思口语考官。按 IELTS Speaking 的方式自然追问，并用中文简短点评。",
    "daily-english": "你是友好的英语会话教练。围绕生活情景进行自然英语对话，并用中文简短点评。",
    "cet4-listening": "你是大学英语四级听力训练教练。用英语给出简短听力材料或问题，并用中文判分订正。",
    "cantonese": "你是粤语学习教练。优先使用粤语口语与繁体字回复，并用简体中文解释用词和发音。",
}

ENGLISH_CABINS = {"cet4-speaking", "cet6-speaking", "ielts-speaking", "daily-english", "cet4-listening"}


async def oral_practice(req: OralPracticeIn, audio_url: str = "") -> OralPracticeOut:
    cabin_prompt = CABIN_PROMPTS.get(req.cabin, CABIN_PROMPTS["daily-english"])
    system = (
        f"{cabin_prompt}"
        "每轮回复应简短，适合直接语音朗读。严格返回 JSON："
        '{"reply":"教练回复或下一题","feedback":"对用户回答的语法、表达和内容点评",'
        '"score":80,"next_prompt":"建议用户下一步回答的问题"}。'
        "若无法合理评分，score 返回 null。"
    )
    raw = await llm_chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": f"训练模式：{req.mode}\n学习者转写内容：{req.message}"},
        ],
        temperature=0.55,
        response_json=True,
    )
    data = extract_json(raw or "")
    if not data:
        return OralPracticeOut(
            reply="I heard you. Please expand your answer with one reason and one example.",
            feedback="当前智能教练服务未配置，已进入基础对话模式。可以继续用语音回答。",
            score=None,
            next_prompt="Could you give one example?",
            audio_url=audio_url,
        )
    score_value = data.get("score")
    score = max(0, min(100, int(score_value))) if isinstance(score_value, (int, float)) else None
    return OralPracticeOut(
        reply=str(data.get("reply") or data.get("next_prompt") or "Please continue."),
        feedback=str(data.get("feedback") or ""),
        score=score,
        next_prompt=str(data.get("next_prompt") or ""),
        audio_url=audio_url,
    )


def _is_english_cabin(cabin: str) -> bool:
    return cabin in ENGLISH_CABINS or cabin.startswith("english")


async def _run_pronunciation_pipeline(
    cabin: str,
    audio_bytes: bytes,
    filename: str,
    content_type: str,
    transcript_hint: str = "",
    ref_text_hint: str = "",
) -> tuple[str, dict | None]:
    transcript = (transcript_hint or "").strip()
    pronunciation: dict | None = None
    pcm = convert_to_pcm16k(audio_bytes, filename, content_type)

    if cabin == "cantonese":
        ref_text = (ref_text_hint or "").strip()
        scored = False

        if ref_text:
            pronunciation = await cantonese_score_pronunciation(
                audio_bytes, ref_text, filename, content_type, language="cantonese"
            )
            scored = pronunciation is not None
            if pronunciation:
                if not transcript:
                    transcript = str(
                        pronunciation.get("transcribed_text")
                        or pronunciation.get("transcribed_jyutping")
                        or ""
                    ).strip()

        if not transcript:
            transcript = await cantonese_stt(audio_bytes, filename, content_type)

        if not scored and (ref_text or transcript):
            score_ref = ref_text or transcript
            pronunciation = await cantonese_score_pronunciation(
                audio_bytes, score_ref, filename, content_type, language="cantonese"
            )
            if pronunciation and not transcript:
                transcript = str(
                    pronunciation.get("transcribed_text")
                    or pronunciation.get("transcribed_jyutping")
                    or ""
                ).strip()

        if not transcript and pcm:
            transcript = await transcribe_pcm(pcm, "zh_cn")

        return transcript, pronunciation

    is_en = _is_english_cabin(cabin)
    if not transcript and pcm:
        transcript = await transcribe_pcm(pcm, "en_us" if is_en else "zh_cn")
    ref_text = (ref_text_hint or transcript).strip()
    if pcm and ref_text:
        pronunciation = await evaluate_pronunciation(pcm, ref_text, lang="en" if is_en else "cn")
    return transcript, pronunciation


async def oral_practice_with_audio(
    cabin: str,
    mode: str,
    duration_sec: int,
    audio_url: str,
    audio_bytes: bytes = b"",
    audio_filename: str = "oral.webm",
    audio_content_type: str = "",
    transcript: str = "",
    ref_text: str = "",
) -> OralPracticeOut:
    """用户上传原声录音：后端转写 + 声学评测 + LLM 综合点评。"""
    cabin_prompt = CABIN_PROMPTS.get(cabin, CABIN_PROMPTS["daily-english"])
    clean_transcript, pronunciation = await _run_pronunciation_pipeline(
        cabin,
        audio_bytes,
        audio_filename,
        audio_content_type,
        transcript_hint=transcript,
        ref_text_hint=ref_text,
    )

    if clean_transcript or pronunciation:
        pron_block = ""
        if pronunciation:
            parts = []
            if pronunciation.get("total") is not None:
                parts.append(f"总分 {pronunciation['total']}")
            if pronunciation.get("accuracy") is not None:
                parts.append(f"准确度 {pronunciation['accuracy']}")
            if pronunciation.get("fluency") is not None:
                parts.append(f"流利度 {pronunciation['fluency']}")
            if pronunciation.get("integrity") is not None:
                parts.append(f"完整度 {pronunciation['integrity']}")
            pron_block = "声学评测：" + "，".join(parts) + "。"

        system = (
            f"{cabin_prompt}"
            "用户上传了原声录音，系统已完成语音转写与发音声学评测。"
            "请结合转写文本与声学分数，给出具体的发音、用词与表达改进建议，并继续自然出题。"
            "粤语舱请兼顾粤语口语习惯与声调。每轮回复应简短，适合朗读。"
            "严格返回 JSON："
            '{"reply":"教练回复或下一题","feedback":"综合声学分数与转写的点评与改进建议",'
            '"score":80,"next_prompt":"下一步建议"}。'
            "score 为 0-100 整数，可参考声学总分；若无法合理评分则返回 null。"
        )
        user_msg = (
            f"训练模式：{mode}\n舱位：{cabin}\n录音时长约 {max(0, duration_sec)} 秒\n"
            f"{pron_block}\n语音转写：{clean_transcript or '（空）'}\n请点评并继续出题。"
        )
    else:
        system = (
            f"{cabin_prompt}"
            "用户刚刚上传了一段原声录音，但本轮未能完成语音转写或发音评测（多为服务处理失败）。"
            "你必须：1）确认已收到录音；2）不要编造具体词句，不要归咎于用户录音不清或背景杂音；"
            "3）说明可能是服务暂不可用，建议稍后重试；4）可继续出下一题。"
            "严格返回 JSON："
            '{"reply":"教练回复或下一题","feedback":"说明服务处理失败、建议重试",'
            '"score":null,"next_prompt":"下一步建议"}。'
        )
        user_msg = (
            f"训练模式：{mode}\n舱位：{cabin}\n用户提交了一段时长约 {max(0, duration_sec)} 秒的录音"
            f"（文件：{audio_url}）。转写/评测失败，请确认并继续。"
        )

    raw = await llm_chat(
        [
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.55,
        response_json=True,
    )
    data = extract_json(raw or "")
    acoustic_score = pronunciation.get("total") if pronunciation else None

    if not data:
        is_cantonese = cabin == "cantonese"
        if clean_transcript or pronunciation:
            reply = (
                f"收到你嘅錄音：「{clean_transcript[:80]}」。我哋繼續下一題。"
                if is_cantonese
                else f"Got your recording: “{clean_transcript[:80]}”. Let's continue."
            )
            fb_parts = []
            if pronunciation and pronunciation.get("total") is not None:
                fb_parts.append(f"发音总分约 {pronunciation['total']} 分")
            if clean_transcript:
                fb_parts.append("可对照转写自查用词与语法")
            return OralPracticeOut(
                reply=reply,
                feedback="；".join(fb_parts) or "录音已收到。",
                score=acoustic_score if isinstance(acoustic_score, int) else None,
                next_prompt="",
                audio_url=audio_url,
                transcript=clean_transcript,
                pronunciation=pronunciation,
            )
        reply = (
            f"收到你約 {duration_sec} 秒嘅錄音。今次服務處理失敗，請稍後再試。"
            if is_cantonese
            else f"Got your {duration_sec}s recording. Service processing failed — please try again."
        )
        return OralPracticeOut(
            reply=reply,
            feedback="语音转写或评测服务暂不可用，请稍后重试；并非录音质量问题。",
            score=None,
            next_prompt="",
            audio_url=audio_url,
            transcript=clean_transcript,
            pronunciation=pronunciation,
        )

    score_value = data.get("score")
    if isinstance(score_value, (int, float)):
        score = max(0, min(100, int(score_value)))
    elif isinstance(acoustic_score, int):
        score = acoustic_score
    else:
        score = None

    return OralPracticeOut(
        reply=str(data.get("reply") or "录音已收到，我们继续下一题。"),
        feedback=str(data.get("feedback") or "录音已保存，可回放自查。"),
        score=score,
        next_prompt=str(data.get("next_prompt") or ""),
        audio_url=audio_url,
        transcript=clean_transcript,
        pronunciation=pronunciation,
    )
