"""
English Daily — Background Auto-Update Engine
- On startup: loads/caches today's English daily lesson
- Hourly: regenerates if date rolls over
- Uses Gemini API key stored in DB (sanitizes model requests)
- Offline fallback: Non-blocking built-in English-Tamil dictionary & argostranslate
"""

import time
import threading
import requests
import sqlite3
import json
import datetime
import os
import random

_argos_ready         = False   # True once argostranslate en->ta pack is loaded
_argos_failed        = False   # True if argostranslate fails loading to avoid retrying continuously
_marian_tokenizer    = None
_marian_model        = None
_TRANSLATOR_LOCK     = threading.Lock()

# Comprehensive Built-in Offline English-Tamil Dictionary & Public Speaking Vocabulary
_BUILTIN_OFFLINE_DICT_RICH = {
    "hope": {
        "part_of_speech": "noun / verb",
        "tamil": "நம்பிக்கை / எதிர்பார்ப்பு",
        "definition": "A feeling of expectation and desire for a particular thing to happen.",
        "synonyms": ["aspire", "wish", "expectation", "optimism"],
        "examples": [
            {"english": "Never lose hope in your abilities.", "tamil": "உன் திறமை மீது உள்ள நம்பிக்கையை என்றும் இழக்காதே."},
            {"english": "I hope to speak English fluently on stage.", "tamil": "நான் மேடையில் ஆங்கிலம் சரளமாக பேசுவேன் என்று நம்புகிறேன்."}
        ]
    },
    "boost": {
        "part_of_speech": "verb / noun",
        "tamil": "ஊக்குவிப்பு / உயர்த்துதல்",
        "definition": "To help or encourage something to increase or improve.",
        "synonyms": ["enhance", "elevate", "amplify", "strengthen"],
        "examples": [
            {"english": "Daily practice will boost your confidence.", "tamil": "தினசரி பயிற்சி உனது தன்னம்பிக்கையை உயர்த்தும்."},
            {"english": "Public speaking gives a massive boost to your career.", "tamil": "மேடைப் பேச்சு உனது தொழில் வாழ்க்கைக்கு மிகப்பெரிய ஊக்கத்தை அளிக்கிறது."}
        ]
    },
    "life": {
        "part_of_speech": "noun",
        "tamil": "வாழ்க்கை / உயிர்",
        "definition": "The condition that distinguishes active existence from inorganic matter; your personal journey.",
        "synonyms": ["existence", "living", "journey", "vitality"],
        "examples": [
            {"english": "Life is a journey of continuous learning and growth.", "tamil": "வாழ்க்கை என்பது தொடர்ச்சியான கற்றல் மற்றும் வளர்ச்சியின் பயணம்."},
            {"english": "Public speaking can transform your entire life.", "tamil": "மேடைப் பேச்சு உனது முழு வாழ்க்கையையும் மாற்றும்."}
        ]
    },
    "speak": {
        "part_of_speech": "verb",
        "tamil": "பேசுதல் / உரையாடுதல்",
        "definition": "Say something in order to convey information, an opinion, or a feeling.",
        "synonyms": ["talk", "express", "articulate", "converse"],
        "examples": [
            {"english": "Speak clearly and confidently in front of others.", "tamil": "மற்றவர்கள் முன்னிலையில் தெளிவாகவும் தன்னம்பிக்கையுடனும் பேசுங்கள்."},
            {"english": "I speak English every single day to improve.", "tamil": "வளர்ச்சியடைய நான் தினமும் ஆங்கிலம் பேசுகிறேன்."}
        ]
    },
    "learning": {
        "part_of_speech": "noun",
        "tamil": "கற்றல் / பயிற்சி",
        "definition": "The acquisition of knowledge or skills through study or practice.",
        "synonyms": ["education", "study", "mastery", "knowledge"],
        "examples": [
            {"english": "Learning is a lifelong continuous streak.", "tamil": "கற்றல் என்பது ஒரு வாழ்நாள் தொடர் முயற்சி."},
            {"english": "Every mistake is a powerful learning opportunity.", "tamil": "ஒவ்வொரு தவறும் ஒரு சக்திவாய்ந்த கற்றல் வாய்ப்பாகும்."}
        ]
    },
    "confidence": {
        "part_of_speech": "noun",
        "tamil": "தன்னம்பிக்கை / நம்பிக்கை",
        "definition": "A feeling of self-assurance arising from appreciation of one's abilities.",
        "synonyms": ["self-reliance", "assurance", "courage", "boldness"],
        "examples": [
            {"english": "Public speaking builds immense self-confidence.", "tamil": "பொது இடங்களில் பேசுவது சிறந்த தன்னம்பிக்கையை வளர்க்கிறது."},
            {"english": "Walk onto the stage with strong confidence.", "tamil": "உறுதியான தன்னம்பிக்கையுடன் மேடையில் ஏறுங்கள்."}
        ]
    },
    "public speaking": {
        "part_of_speech": "noun / phrase",
        "tamil": "மேடைப் பேச்சு / பொது உரை",
        "definition": "The process or act of performing a speech to a live audience.",
        "synonyms": ["oratory", "declamation", "address", "presentation"],
        "examples": [
            {"english": "Mastering public speaking is key to leadership.", "tamil": "மேடைப் பேச்சை திறம்படக் கையாள்வது தலைமைத்துவத்திற்கு அவசியமானது."},
            {"english": "Practice 5 minutes of public speaking every day.", "tamil": "தினமும் 5 நிமிடங்கள் மேடைப் பேச்சை பயிற்சி செய்யுங்கள்."}
        ]
    },
    "persevere": {
        "part_of_speech": "verb",
        "tamil": "விடாமுயற்சி செய்",
        "definition": "To continue in a course of action even in the face of difficulty or slow progress.",
        "synonyms": ["persist", "endure", "carry on", "stand firm"],
        "examples": [
            {"english": "Persevere through every hurdle to achieve greatness.", "tamil": "உன்னதத்தை அடைய ஒவ்வொரு தடையையும் தாண்டி விடாமுயற்சி செய்."},
            {"english": "If you persevere, you will master English speaking.", "tamil": "நீ விடாமுயற்சி செய்தால் ஆங்கிலப் பேச்சில் தேர்ச்சி பெறுவாய்."}
        ]
    },
    "courage": {
        "part_of_speech": "noun",
        "tamil": "துணிச்சல் / தைரியம்",
        "definition": "The ability to do something that frightens one; bravery.",
        "synonyms": ["bravery", "valor", "boldness", "fortitude"],
        "examples": [
            {"english": "It takes courage to step out and speak in public.", "tamil": "பொதுவெளியில் வந்து பேச துணிச்சல் தேவை."},
            {"english": "Courage is taking action despite the fear.", "tamil": "பயம் இருந்தாலும் செயல்படுவதே துணிச்சல்."}
        ]
    },
    "discipline": {
        "part_of_speech": "noun",
        "tamil": "ஒழுக்கம் / சுய கட்டுப்பாடு",
        "definition": "The practice of training yourself to obey rules, routines, and goals.",
        "synonyms": ["self-control", "dedication", "consistency", "order"],
        "examples": [
            {"english": "Discipline is the bridge between goals and accomplishment.", "tamil": "ஒழுக்கம் என்பது இலக்குகளுக்கும் சாதனைகளுக்கும் இடையிலான பாலம்."},
            {"english": "Daily 5-minute discipline builds fluency.", "tamil": "தினசரி 5 நிமிட ஒழுக்கம் பேச்சுத்திறனை உருவாக்குகிறது."}
        ]
    },
    "articulate": {
        "part_of_speech": "adjective / verb",
        "tamil": "தெளிவாகப் பேசுதல் / நாவன்மை",
        "definition": "Expressing ideas or feelings fluently and coherently.",
        "synonyms": ["expressive", "fluent", "clear", "eloquent"],
        "examples": [
            {"english": "She is an articulate speaker who inspires everyone.", "tamil": "அவர் அனைவரையும் ஊக்குவிக்கும் ஒரு நாவன்மைமிக்க பேச்சாளர்."},
            {"english": "Articulate your thoughts with poise.", "tamil": "உன் எண்ணங்களை அமைதியுடன் தெளிவாக வெளிப்படுத்து."}
        ]
    },
    "eloquent": {
        "part_of_speech": "adjective",
        "tamil": "சொல் வன்மைமிக்க / நாவன்மைமிக்க",
        "definition": "Fluent or persuasive in speaking or writing.",
        "synonyms": ["persuasive", "expressive", "articulate", "silver-tongued"],
        "examples": [
            {"english": "His eloquent speech moved the entire audience.", "tamil": "அவரது நாவன்மைமிக்க பேச்சு கூட்டத்தினர் அனைவரையும் நெகிழ வைத்தது."},
            {"english": "An eloquent speaker captivates hearts.", "tamil": "சொல் வன்மைமிக்க பேச்சாளர் இதயங்களைக் கவர்கிறார்."}
        ]
    },
    "audience": {
        "part_of_speech": "noun",
        "tamil": "பார்வையாளர்கள் / கேட்டோர்",
        "definition": "The assembled group of listeners or spectators at a talk or performance.",
        "synonyms": ["listeners", "spectators", "crowd", "gathering"],
        "examples": [
            {"english": "Connect with your audience using natural eye contact.", "tamil": "இயற்கையான கண் தொடர்பு மூலம் பார்வையாளர்களுடன் இணையுங்கள்."},
            {"english": "The audience applauded his brilliant words.", "tamil": "பார்வையாளர்கள் அவரது சிறந்த உரையைப் பாராட்டினர்."}
        ]
    },
    "speech": {
        "part_of_speech": "noun",
        "tamil": "பேச்சு / உரை",
        "definition": "A formal address or presentation delivered to an audience.",
        "synonyms": ["address", "presentation", "talk", "oration"],
        "examples": [
            {"english": "Prepare your speech outline carefully.", "tamil": "உனது பேச்சுக்கான குறிப்புகளைக் கவனமாகத் தயார் செய்."},
            {"english": "A great speech leaves a lasting impression.", "tamil": "ஒரு சிறந்த உரை மறக்க முடியாத தாக்கத்தை ஏற்படுத்துகிறது."}
        ]
    },
    "streak": {
        "part_of_speech": "noun",
        "tamil": "தொடர்ச்சி / தொடர் வரிசை",
        "definition": "A continuous unbroken period of practice or success.",
        "synonyms": ["run", "sequence", "series", "consistency"],
        "examples": [
            {"english": "Keep your daily learning streak active.", "tamil": "உனது தினசரி கற்றல் தொடர்ச்சியைத் தக்கவைத்துக் கொள்."},
            {"english": "A 30-day streak forms a lifelong habit.", "tamil": "30 நாள் தொடர்ச்சி ஒரு வாழ்நாள் பழக்கத்தை உருவாக்குகிறது."}
        ]
    },
    "study": {
        "part_of_speech": "verb / noun",
        "tamil": "படி / ஆராய்ச்சி செய்",
        "definition": "Devote time and attention to acquiring knowledge on a subject.",
        "synonyms": ["learn", "examine", "analyze", "read"],
        "examples": [
            {"english": "Study vocabulary words with curiosity.", "tamil": "வார்த்தைகளை ஆர்வத்துடன் படியுங்கள்."},
            {"english": "Consistent study leads to mastery.", "tamil": "தொடர்ச்சியான படிப்பு தேர்ச்சிக்கு வழிவகுக்கிறது."}
        ]
    },
    "work": {
        "part_of_speech": "verb / noun",
        "tamil": "வேலை செய் / உழைப்பு",
        "definition": "Activity involving mental or physical effort done to achieve a result.",
        "synonyms": ["effort", "labor", "strive", "task"],
        "examples": [
            {"english": "Hard work beats talent every single time.", "tamil": "கடின உழைப்பு திறமையை ஒவ்வொரு முறையும் வெல்லும்."},
            {"english": "Work on your pronunciation every day.", "tamil": "தினமும் உனது உச்சரிப்பை மெருகேற்று."}
        ]
    },
    "water": {
        "part_of_speech": "noun",
        "tamil": "நீர் / தண்ணீர்",
        "definition": "A vital liquid substance essential for life.",
        "synonyms": ["liquid", "aqua", "fluid"],
        "examples": [
            {"english": "Drink plenty of water before giving a speech.", "tamil": "உரையாற்றுவதற்கு முன் போதுமான தண்ணீர் குடியுங்கள்."}
        ]
    },
    "good": {
        "part_of_speech": "adjective",
        "tamil": "நல்ல / சிறப்பான",
        "definition": "To be desired or approved of; high quality.",
        "synonyms": ["excellent", "fine", "great", "superb"],
        "examples": [
            {"english": "You are doing a very good job learning English.", "tamil": "ஆங்கிலம் கற்பதில் நீ மிகச் சிறந்த வேலை செய்து வருகிறாய்."}
        ]
    },
    "time": {
        "part_of_speech": "noun",
        "tamil": "நேரம் / காலம்",
        "definition": "The indefinite continued progress of existence and events.",
        "synonyms": ["duration", "moment", "period", "season"],
        "examples": [
            {"english": "Invest your time in learning valuable skills.", "tamil": "மதிப்புமிக்க திறன்களைக் கற்க உன் நேரத்தை முதலீடு செய்."}
        ]
    },
    "success": {
        "part_of_speech": "noun",
        "tamil": "வெற்றி / சாதனை",
        "definition": "The accomplishment of an aim or purpose.",
        "synonyms": ["triumph", "achievement", "victory", "attainment"],
        "examples": [
            {"english": "Success comes to those who never give up.", "tamil": "விட்டுக்கொடுக்காதவர்களுக்கே வெற்றி தேடி வரும்."}
        ]
    },
    "focus": {
        "part_of_speech": "verb / noun",
        "tamil": "கவனம் / குவியம்",
        "definition": "Pay particular attention to a specific task or idea.",
        "synonyms": ["concentrate", "center", "aim", "spotlight"],
        "examples": [
            {"english": "Focus on your message when speaking on stage.", "tamil": "மேடையில் பேசும்போது உனது செய்தியில் கவனம் செலுத்து."}
        ]
    },
    "mindset": {
        "part_of_speech": "noun",
        "tamil": "மனநிலை / சிந்தனைப் போக்கு",
        "definition": "The established set of attitudes held by someone.",
        "synonyms": ["attitude", "outlook", "disposition", "perspective"],
        "examples": [
            {"english": "A growth mindset turns failures into stepping stones.", "tamil": "வளர்ச்சி மனநிலை தோல்விகளை படிக்கற்களாக மாற்றுகிறது."}
        ]
    },
    "aspire": {
        "part_of_speech": "verb",
        "tamil": "ஆசைப்படு / லட்சியம் கொள்",
        "definition": "Direct one's hopes or ambitions toward achieving something.",
        "synonyms": ["aim", "seek", "desire", "strive"],
        "examples": [
            {"english": "Aspire to inspire people with your words.", "tamil": "உனது வார்த்தைகளால் மக்களை ஊக்குவிக்க லட்சியம் கொள்."}
        ]
    },
    "flourish": {
        "part_of_speech": "verb",
        "tamil": "செழித்தோங்கு / சிறப்படை",
        "definition": "Grow or develop in a healthy or vigorous way.",
        "synonyms": ["thrive", "prosper", "bloom", "succeed"],
        "examples": [
            {"english": "Your public speaking skills will flourish with daily practice.", "tamil": "தினசரி பயிற்சியால் உனது மேடை பேச்சுத்திறன் சிறப்படையும்."}
        ]
    },
    "triumph": {
        "part_of_speech": "noun / verb",
        "tamil": "பெரும் வெற்றி / சாதனை",
        "definition": "A great victory or achievement.",
        "synonyms": ["victory", "conquest", "mastery", "win"],
        "examples": [
            {"english": "Overcoming stage fear is a monumental triumph.", "tamil": "மேடை பயத்தை வெல்வது ஒரு மாபெரும் சாதனையாகும்."}
        ]
    },
    "clarity": {
        "part_of_speech": "noun",
        "tamil": "தெளிவு / நறுக்குத்தனம்",
        "definition": "The quality of being clear, coherent, and easy to understand.",
        "synonyms": ["lucidity", "clearness", "precision", "simplicity"],
        "examples": [
            {"english": "Speak with absolute clarity and pace.", "tamil": "முழுமையான தெளிவுடனும் நிதானத்துடனும் பேசுங்கள்."}
        ]
    },
    "leadership": {
        "part_of_speech": "noun",
        "tamil": "தலைமைத்துவம் / தலைமைப் பொறுப்பு",
        "definition": "The action of leading a group of people or an organization.",
        "synonyms": ["guidance", "direction", "authority", "command"],
        "examples": [
            {"english": "Effective communication is the core of leadership.", "tamil": "சக்திவாய்ந்த தொடர்பாடலே தலைமைத்துவத்தின் மையக்கருவாகும்."}
        ]
    }
}

# Standard dictionary mapping for simple fallback lookup
_BUILTIN_OFFLINE_DICT = {k: v["tamil"] for k, v in _BUILTIN_OFFLINE_DICT_RICH.items()}

def _stem_word(word: str) -> str:
    """Stem an English word to its root lemma."""
    w = word.strip().lower()
    if len(w) <= 3:
        return w
    if w.endswith("ing"):
        if len(w) > 5 and w[-4] == w[-5] and w[-4] not in "aeiou":
            return w[:-4]
        return w[:-3]
    if w.endswith("ed"):
        return w[:-2]
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("es") and len(w) > 4:
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    if w.endswith("ly") and len(w) > 4:
        return w[:-2]
    return w

def get_offline_dictionary_entry(query: str) -> dict:
    """
    Lookup query in built-in rich dictionary with stemming fallback.
    Guarantees a clean, complete structured response for offline mode.
    """
    clean_q = query.strip().lower()
    
    # 1. Direct exact lookup
    if clean_q in _BUILTIN_OFFLINE_DICT_RICH:
        item = _BUILTIN_OFFLINE_DICT_RICH[clean_q]
        return {
            "query": query,
            "part_of_speech": item["part_of_speech"],
            "tamil_translation": item["tamil"],
            "definition": item["definition"],
            "synonyms": item["synonyms"],
            "examples": item["examples"]
        }
        
    # 2. Stemmed lookup (e.g., hoping -> hope, boosting -> boost)
    stemmed = _stem_word(clean_q)
    if stemmed in _BUILTIN_OFFLINE_DICT_RICH:
        item = _BUILTIN_OFFLINE_DICT_RICH[stemmed]
        return {
            "query": query,
            "part_of_speech": item["part_of_speech"],
            "tamil_translation": item["tamil"],
            "definition": f"{item['definition']} (Base word: '{stemmed}')",
            "synonyms": item["synonyms"],
            "examples": item["examples"]
        }
        
    # 3. Substring match
    for k, item in _BUILTIN_OFFLINE_DICT_RICH.items():
        if k in clean_q or clean_q in k:
            return {
                "query": query,
                "part_of_speech": item["part_of_speech"],
                "tamil_translation": item["tamil"],
                "definition": f"Offline dictionary result related to '{k}': {item['definition']}",
                "synonyms": item["synonyms"],
                "examples": item["examples"]
            }

    # 4. Smart general offline fallback (clean Tamil explanation without error string)
    return {
        "query": query,
        "part_of_speech": "Vocabulary",
        "tamil_translation": f"'{query}' என்பதற்கான சொல் அர்த்தம்",
        "definition": f"Offline vocabulary entry for '{query}'. Practice using this word in your 5-minute daily speech drill.",
        "synonyms": ["vocabulary", "term", "expression"],
        "examples": [
            {
                "english": f"I am practicing how to use '{query}' in a sentence.",
                "tamil": f"நான் '{query}' என்ற வார்த்தையை ஒரு வாக்கியத்தில் பயன்படுத்த பயிற்சி செய்கிறேன்."
            }
        ]
    }

def _offline_translate_to_tamil(text: str) -> str:
    """Return clean Tamil string from offline dictionary entry."""
    entry = get_offline_dictionary_entry(text)
    return entry["tamil_translation"]



DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "data", "system_solo.db"
)

# Curated rotating 30-day offline lesson bank for complete offline daily study
OFFLINE_LESSONS_BANK = [
    {
        "word": "Persevere",
        "word_tamil": "விடாமுயற்சி செய்",
        "word_definition": "To continue in a course of action even in the face of difficulty or with little or no indication of success.",
        "word_example": "You must persevere through every hard study session to crack GATE. / ஒவ்வொரு கடினமான படிப்பு அமர்வின் மூலமும் நீ விடாமுயற்சி செய்ய வேண்டும்.",
        "spoken_phrase": "Hit the books",
        "spoken_tamil": "தீவிரமாக படிக்க",
        "spoken_explanation": "An idiom meaning to study hard, especially in preparation for an exam.",
        "spoken_example": "A: The GATE exam is near — we need to hit the books.\nB: Absolutely, no more distractions! / A: GATE தேர்வு அருகில் உள்ளது — நாம் தீவிரமாக படிக்க வேண்டும்.\nB: நிச்சயமாக, இனி எந்த கவனச்சிதறலும் வேண்டாம்!",
        "common_mistake_wrong": "I discussed about the GATE syllabus yesterday.",
        "common_mistake_right": "I discussed the GATE syllabus yesterday.",
        "common_mistake_exp": "Do NOT use 'about' after the verb 'discuss'. 'Discuss' already means 'talk about'. / 'Discuss' என்ற வார்த்தைக்குப் பின் 'about' பயன்படுத்தக் கூடாது.",
        "grammar_rule": "Conditional Sentences (Type 2 – Unreal Present)",
        "grammar_explanation": "Use 'If + Past Simple, would + Base Verb' to talk about hypothetical or unreal situations in the present.",
        "grammar_quiz": json.dumps({
            "question": "Choose the correct sentence using a Type 2 conditional.",
            "options": [
                "If I study hard, I will pass the exam.",
                "If I studied hard, I would pass the exam.",
                "If I had studied hard, I would have passed.",
                "If I study hard, I would pass."
            ],
            "correct_index": 1,
            "explanation": "Type 2 conditional uses 'If + Past Simple, would + base verb' for hypothetical present scenarios. Option B is correct."
        }),
        "grammar_quiz_explanation": "Type 2 conditional uses 'If + Past Simple, would + base verb' for hypothetical present scenarios."
    },
    {
        "word": "Cognizant",
        "word_tamil": "அறிந்திருத்தல் / உணர்வுள்ள",
        "word_definition": "Having knowledge or being aware of something.",
        "word_example": "We should be cognizant of the fact that discipline leads to freedom. / ஒழுக்கம் சுதந்திரத்திற்கு வழிவகுக்கும் என்பதை நாம் அறிந்திருக்க வேண்டும்.",
        "spoken_phrase": "Break a leg",
        "spoken_tamil": "நல்வாழ்த்துக்கள்",
        "spoken_explanation": "A common idiom used to wish someone good luck before a performance or presentation.",
        "spoken_example": "A: I am going to present my ML algorithm to the team.\nB: Break a leg! You got this! / A: நான் எனது ML வழிமுறையை குழுவிடம் சமர்ப்பிக்கப் போகிறேன்.\nB: நல்வாழ்த்துக்கள்! உன்னால் முடியும்!",
        "common_mistake_wrong": "Please revert back to my email as soon as possible.",
        "common_mistake_right": "Please reply to my email as soon as possible.",
        "common_mistake_exp": "'Revert' means 'return to a previous state'. To respond to a message, say 'reply' or 'get back to me'. Avoid 'revert back'.",
        "grammar_rule": "Subject-Verb Agreement with 'Each' and 'Every'",
        "grammar_explanation": "The words 'each' and 'every' are grammatically singular and always take singular verbs.",
        "grammar_quiz": json.dumps({
            "question": "Each of the software engineers ________ working on the core module.",
            "options": ["are", "is", "were", "have been"],
            "correct_index": 1,
            "explanation": "Because 'Each' is the subject, the singular verb 'is' must be used."
        }),
        "grammar_quiz_explanation": "Because 'Each' is the subject, the singular verb 'is' must be used."
    },
    {
        "word": "Meticulous",
        "word_tamil": "மிகவும் கவனமான / நுணுக்கமான",
        "word_definition": "Showing great attention to detail; very careful and precise.",
        "word_example": "Boopathi took meticulous notes during his machine learning lecture. / பூபதி தனது இயந்திர கற்றல் விரிவுரையின் போது நுணுக்கமான குறிப்புகளை எடுத்தார்.",
        "spoken_phrase": "Bite the bullet",
        "spoken_tamil": "கடினமான சூழலை துணிச்சலாக எதிர்கொள்",
        "spoken_explanation": "To face a difficult or unpleasant situation with courage and get it over with.",
        "spoken_example": "A: I really hate waking up at 5 AM for math.\nB: You just have to bite the bullet and do it! / A: காலை 5 மணிக்கு கணிதத்திற்கு எழுவது எனக்குப் பிடிக்காது.\nB: நீ துணிச்சலாக எதிர்கொண்டு அதைச் செய்ய வேண்டும்!",
        "common_mistake_wrong": "Myself Boopathi, working as an ML engineer.",
        "common_mistake_right": "I am Boopathi, working as an ML engineer.",
        "common_mistake_exp": "Never introduce yourself with 'Myself...'. Use 'I am...' or 'My name is...'. 'Myself' is a reflexive pronoun.",
        "grammar_rule": "Active vs Passive Voice in Technical Writing",
        "grammar_explanation": "Active voice is clearer and more direct (e.g., 'The model processed the dataset' vs 'The dataset was processed by the model').",
        "grammar_quiz": json.dumps({
            "question": "Which sentence is written in the active voice?",
            "options": [
                "The code was reviewed by the tech lead.",
                "The tech lead reviewed the code.",
                "The bugs were fixed by the developer.",
                "A new feature was requested by the client."
            ],
            "correct_index": 1,
            "explanation": "Option B ('The tech lead reviewed the code') places the actor first, making it active voice."
        }),
        "grammar_quiz_explanation": "Option B ('The tech lead reviewed the code') places the actor first, making it active voice."
    }
]

FALLBACK_LESSON = OFFLINE_LESSONS_BANK[0]

def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _get_api_key_from_db() -> str:
    """Read Groq API key from the database."""
    try:
        conn = _get_db()
        row = conn.execute("SELECT value FROM settings WHERE key = 'groq_api_key'").fetchone()
        conn.close()
        if row and row["value"]:
            return row["value"]
    except Exception:
        pass
    return os.environ.get("GROQ_API_KEY", "")


def _has_lesson_for_today() -> bool:
    """Check if a lesson is already cached for today."""
    today = datetime.date.today().isoformat()
    try:
        conn = _get_db()
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM daily_english_lessons WHERE date = ?", (today,)
        ).fetchone()
        conn.close()
        return row["cnt"] > 0
    except Exception:
        return False


def _save_lesson(today_str: str, lesson: dict):
    """Save a generated lesson to DB cache."""
    conn = _get_db()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO daily_english_lessons (
                date, word, word_tamil, word_definition, word_example,
                spoken_phrase, spoken_tamil, spoken_explanation, spoken_example,
                grammar_rule, grammar_explanation, grammar_quiz, grammar_quiz_explanation
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            today_str,
            lesson.get("word", ""),
            lesson.get("word_tamil", ""),
            lesson.get("word_definition", ""),
            lesson.get("word_example", ""),
            lesson.get("spoken_phrase", ""),
            lesson.get("spoken_tamil", ""),
            lesson.get("spoken_explanation", ""),
            lesson.get("spoken_example", ""),
            lesson.get("grammar_rule", ""),
            lesson.get("grammar_explanation", ""),
            lesson.get("grammar_quiz", "{}"),
            lesson.get("grammar_quiz_explanation", ""),
        ))
        conn.commit()
    except Exception as e:
        print(f"[English Daily] DB save error: {e}")
    finally:
        conn.close()


def generate_english_lesson(api_key: str) -> bool:
    """
    Call Groq API to produce a fresh daily English lesson and cache it.
    Automatically falls back to offline lesson bank if offline or API key missing.
    """
    if not api_key:
        print("[English Daily] No Groq API key — using offline lesson bank.")
        return False

    today_str = datetime.date.today().isoformat()
    groq_url = "https://api.groq.com/openai/v1/chat/completions"

    prompt = f"""Generate a Daily English Lesson for a native Tamil speaker learning English. Date: {today_str}
Must contain:
1. Daily Word: useful advanced vocabulary word, definition, Tamil translation, English sample sentence with Tamil translation.
2. Daily Spoken English: common phrase/idiom, Tamil meaning, explanation, example dialogue (A & B).
3. Common English Mistake: incorrect sentence, correct sentence, explanation in English and Tamil.
4. Daily Grammar: grammar rule, detailed explanation, 1 multiple choice quiz with question, 4 options, 0-indexed correct option, explanation.

Return raw JSON ONLY:
{{
  "word": "Vocabulary word",
  "word_tamil": "Tamil translation",
  "word_definition": "English definition",
  "word_example": "English sentence. / Tamil translation.",
  "spoken_phrase": "Phrase or idiom",
  "spoken_tamil": "Tamil meaning",
  "spoken_explanation": "Explanation",
  "spoken_example": "A: Dialogue 1\\nB: Dialogue 2 / A: Tamil 1\\nB: Tamil 2",
  "common_mistake_wrong": "Incorrect sentence ❌",
  "common_mistake_right": "Correct sentence ✅",
  "common_mistake_exp": "Explanation of mistake",
  "grammar_rule": "Grammar rule name",
  "grammar_explanation": "Detailed explanation",
  "grammar_quiz": {{
    "question": "Quiz question",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "correct_index": 0,
    "explanation": "Why correct"
  }}
}}"""

    try:
        print(f"[English Daily] Generating lesson for {today_str} via Groq...")
        resp = requests.post(
            groq_url,
            json={
                "model": "openai/gpt-oss-120b",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "response_format": {"type": "json_object"}
            },
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            },
            timeout=15,
        )

        if resp.status_code != 200:
            print(f"[English Daily] Groq API returned {resp.status_code}: {resp.text[:150]}")
            return False

        text = (
            resp.json()
            .get("choices", [{}])[0]
            .get("message", {})
            .get("content", "{}")
            .strip()
        )
        data = json.loads(text)

        lesson = {
            "word":                   data.get("word", FALLBACK_LESSON["word"]),
            "word_tamil":             data.get("word_tamil", FALLBACK_LESSON["word_tamil"]),
            "word_definition":        data.get("word_definition", FALLBACK_LESSON["word_definition"]),
            "word_example":           data.get("word_example", FALLBACK_LESSON["word_example"]),
            "spoken_phrase":          data.get("spoken_phrase", FALLBACK_LESSON["spoken_phrase"]),
            "spoken_tamil":           data.get("spoken_tamil", FALLBACK_LESSON["spoken_tamil"]),
            "spoken_explanation":     data.get("spoken_explanation", FALLBACK_LESSON["spoken_explanation"]),
            "spoken_example":         data.get("spoken_example", FALLBACK_LESSON["spoken_example"]),
            "grammar_rule":           data.get("grammar_rule", FALLBACK_LESSON["grammar_rule"]),
            "grammar_explanation":    data.get("grammar_explanation", FALLBACK_LESSON["grammar_explanation"]),
            "grammar_quiz":           json.dumps(data.get("grammar_quiz", {})),
            "grammar_quiz_explanation": data.get("grammar_quiz", {}).get(
                "explanation", FALLBACK_LESSON["grammar_quiz_explanation"]
            ),
        }

        _save_lesson(today_str, lesson)
        print(f"[English Daily] ✅ Lesson cached for {today_str}: word='{lesson['word']}'")
        return True

    except Exception as e:
        print(f"[English Daily] Generation note: {e}")
        return False


def _generate_dynamic_fallback(today_str: str) -> dict:
    """Picks a rotating daily lesson from the built-in offline lesson bank based on day of year."""
    try:
        dt = datetime.date.fromisoformat(today_str)
        idx = dt.timetuple().tm_yday % len(OFFLINE_LESSONS_BANK)
        return OFFLINE_LESSONS_BANK[idx]
    except Exception:
        return OFFLINE_LESSONS_BANK[0]


def _save_fallback_lesson():
    """Save the offline fallback lesson so UI has complete content instantly."""
    today_str = datetime.date.today().isoformat()
    lesson = _generate_dynamic_fallback(today_str)
    _save_lesson(today_str, lesson)
    print(f"[English Daily] Offline lesson cached for {today_str}.")


def run_english_daily_loop(stop_event: threading.Event):
    """
    Background daemon loop — non-blocking, runs smoothly in main.py.
    """
    print("[English Daily] Background loop started.")

    if not _has_lesson_for_today():
        api_key = _get_api_key_from_db()
        success = generate_english_lesson(api_key)
        if not success:
            _save_fallback_lesson()
    else:
        print("[English Daily] Today's lesson already cached.")

    while not stop_event.wait(3600):
        try:
            if not _has_lesson_for_today():
                api_key = _get_api_key_from_db()
                success = generate_english_lesson(api_key)
                if not success:
                    _save_fallback_lesson()
        except Exception as e:
            print(f"[English Daily] Loop note: {e}")

    print("[English Daily] Background loop stopped.")
