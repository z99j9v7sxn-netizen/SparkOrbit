from app.agents.tools.intent import classify_companion_intent


def test_intent_path():
    assert classify_companion_intent("帮我做一份学习路径") == "path"


def test_intent_deck():
    assert classify_companion_intent("生成闪卡和课件") == "deck"


def test_intent_quiz():
    assert classify_companion_intent("来几道练习题") == "quiz"


def test_intent_resource():
    assert classify_companion_intent("生成讲义和思维导图") == "resource"


def test_intent_feynman_hint():
    assert classify_companion_intent("随便说说", mode_hint="feynman") == "feynman"


def test_intent_companion_emotion():
    assert classify_companion_intent("好累啊压力好大") == "companion"


def test_intent_default_chat():
    assert classify_companion_intent("链表和数组有什么区别？") == "chat"
