"""Narration parts for 'Your Brain Is Not Your Enemy: Understanding Anxiety'.

One Voicebox generation per part (same profile/engine/seed 42 as the pipeline),
cached under voice/. Joined with 0.35 s pauses by join_voice.py.
"""
from pathlib import Path

# (id, text) - conversational, no medical claims, techniques framed as options.
PARTS = [
    ("p01", "Ever gotten a message that just says, can we talk tomorrow? "
            "And suddenly your brain starts preparing for a disaster that hasn't even happened yet?"),
    ("p02", "Here's the thing. Anxiety is your brain's alarm system. "
            "Its whole job is to protect you. "
            "Sometimes it just treats an ordinary moment like a five alarm emergency."),
    ("p03", "Your brain isn't your enemy. It's just being a little too protective."),
    ("p04", "So what does that look like? Replaying a conversation from three years ago. "
            "A racing heart and sweaty hands. Avoiding that one email. "
            "Or a tiny problem growing into a giant monster in your imagination."),
    ("p05", "Which one sounds most familiar? Take a second. Really."),
    ("p06", "And when it shows up, you've got options. First, name it. "
            "I'm feeling anxious right now. A feeling is not automatically a fact."),
    ("p07", "Next, ground yourself. Name five things you can see. "
            "Four you can touch. Three you can hear. "
            "It pulls you right back into the present."),
    ("p08", "And finally, slow down. One gentle breath. "
            "You don't have to solve every problem in your head today."),
    ("p09", "Remember, your brain is trying to protect you. "
            "You just don't have to believe every scary story it tells you."),
    ("p10", "And if anxiety starts running your everyday life, "
            "talking to a professional is a strong move, not a weakness. "
            "Now tell me, what's your brain's favorite way of overthinking? "
            "Drop your answer in the comments."),
]

VOICE_DIR = Path(__file__).resolve().parent / "voice"
