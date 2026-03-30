import json
import re
from groq import Groq
from app.config import settings

client = Groq(api_key=settings.GROQ_API_KEY)

SYSTEM_PROMPT = """You are Solace, a warm and caring conversational companion.

## MOST IMPORTANT RULE — MIRROR THE USER'S WORDS:
Pick up the EXACT words, phrases, or feelings the user used and reflect them back naturally in your reply.
Examples:
- User says "nearly 2 days lonely ya feel pannren" → Reply uses "2 days", "lonely" — "2 days loneliness is really heavy to carry alone..."
- User says "work stress ah thandavama aadum" → Reply uses "work stress", "thandavam" naturally
- User says "numb ah iruku, enna feel pannanum nu theriyala" → Reply uses "numb" — "that numb feeling where you don't even know what to feel..."
- User says "i feel so tired of everything" → Reply uses "tired of everything" — "when everything feels exhausting like that..."
Never use generic phrases like "I understand" or "that sounds tough" alone — always anchor to their specific words.

## Other rules:
- Respond to EVERYTHING — casual, emotional, serious, random, even one-word messages
- Short messages like "please", "pls", "hello", "?" — these mean the user needs you, always respond warmly
- Never give empty or silent response — always reply
- 2-4 sentences, warm, like a caring close friend texting back
- Validate first, advice only when they ask or it feels right
- Occasional emojis (💙 🌿 ✨) — not every sentence
- Reply in the SAME language/mix the user writes in (Tanglish, Tamil, English, Hindi etc.)
- If crisis signals ("want to die", "end my life", "kill myself", "no reason to live", self-harm) → reply with warmth AND set crisis=true
- Detect mood in one word: lonely, anxious, sad, angry, hopeless, numb, overwhelmed, calm, happy, grieving, frustrated, exhausted, neutral, stressed

ALWAYS return valid JSON — no markdown, no extra text:
{"reply": "your response here", "mood": "one_word_mood", "crisis": false}"""

FALLBACK_REPLIES = [
    {"reply": "I'm here with you. It sounds like you've been carrying a lot lately — want to tell me more? 💙", "mood": "unknown", "crisis": False},
    {"reply": "That sounds really tough. I'm listening — what's been going on? 🌿", "mood": "unknown", "crisis": False},
    {"reply": "I hear you. Sometimes just saying it out loud helps. I'm here. 💙", "mood": "unknown", "crisis": False},
]
_fallback_index = 0


async def get_ai_reply(
    user_message: str,
    conversation_history: list[dict]
) -> dict:
    """
    Call Groq API. Returns clean { reply, mood, crisis }.
    Never raises — always returns a usable response.
    """
    global _fallback_index
    messages = conversation_history[-20:]

    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                max_tokens=600,
                temperature=0.7 if attempt == 0 else 0.5,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    *messages,
                    {"role": "user", "content": user_message},
                ],
            )

            choice = response.choices[0]

            # Groq content filter blocked response
            if choice.finish_reason == "content_filter":
                print(f"[AI] Content filtered for: {user_message[:50]}")
                fb = FALLBACK_REPLIES[_fallback_index % len(FALLBACK_REPLIES)]
                _fallback_index += 1
                return fb

            raw = choice.message.content
            if not raw or not raw.strip():
                print(f"[AI] Empty response attempt {attempt+1}")
                continue

            raw = raw.strip()
            raw = re.sub(r"^```json\s*", "", raw)
            raw = re.sub(r"```\s*$", "", raw).strip()

            # Pure JSON
            if raw.startswith("{"):
                try:
                    parsed = json.loads(raw)
                    return {
                        "reply":  str(parsed.get("reply") or "I'm here with you. 💙"),
                        "mood":   parsed.get("mood", "unknown"),
                        "crisis": bool(parsed.get("crisis", False)),
                    }
                except json.JSONDecodeError:
                    pass

            # Text + JSON appended
            json_match = re.search(r'\s*(\{"reply"[\s\S]*\})\s*$', raw)
            if json_match:
                text_before = raw[:json_match.start()].strip()
                try:
                    json_part = json.loads(json_match.group(1))
                    reply_text = text_before if text_before else str(json_part.get("reply", ""))
                    return {
                        "reply":  reply_text or "I'm here with you. 💙",
                        "mood":   json_part.get("mood", "unknown"),
                        "crisis": bool(json_part.get("crisis", False)),
                    }
                except Exception:
                    if text_before:
                        return {"reply": text_before, "mood": "unknown", "crisis": False}

            # Plain text (model ignored JSON instruction)
            if len(raw) > 10:
                return {"reply": raw, "mood": "unknown", "crisis": False}

        except Exception as e:
            err_str = str(e).lower()
            print(f"[AI Error attempt {attempt+1}] {e}")
            if "rate_limit" in err_str or "429" in err_str:
                import asyncio
                await asyncio.sleep(2)
                continue
            break

    # All attempts failed
    fb = FALLBACK_REPLIES[_fallback_index % len(FALLBACK_REPLIES)]
    _fallback_index += 1
    return fb


async def generate_mood_insight(mood_history: list[dict]) -> str:
    """Generate AI insight from mood history."""
    if not mood_history:
        return "Start logging your mood daily to get personalised insights. 💙"

    history_text = "\n".join(
        [f"- {m['date']}: {m['mood']} (score {m['score']}/10) — {m.get('note','')}"
         for m in mood_history[-14:]]
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=300,
            messages=[
                {"role": "system", "content": "You are a warm, empathetic mental health AI."},
                {
                    "role": "user",
                    "content": (
                        f"Here is a user's mood log:\n{history_text}\n\n"
                        "Write 2-3 sentences of empathetic insight about their emotional patterns. "
                        "Mention best days, challenging times, one gentle suggestion. "
                        "Warm tone, not clinical. Return only the insight text, no JSON."
                    )
                }
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[Mood Insight Error] {e}")
        return "Keep logging your mood — patterns will emerge over time. You're doing great. 💙"


async def check_crisis_in_text(text: str) -> bool:
    """Quick crisis check without full AI call."""
    CRISIS_KEYWORDS = [
        "want to die", "end my life", "kill myself", "suicidal", "no reason to live",
        "want to disappear", "better off dead", "can't go on", "ending it all",
        "self harm", "hurt myself", "உயிரை மாய்த்துக்க", "சாக வேண்டும்",
    ]
    lower = text.lower()
    return any(kw in lower for kw in CRISIS_KEYWORDS)