import csv
import html
import random
from pathlib import Path

import streamlit as st

# -----------------------------------------------------------------------------
# Application configuration
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="TOGAF Exam Simulator",
    page_icon="🎓",
    layout="centered",
    initial_sidebar_state="expanded",
)

APP_DIR = Path(__file__).resolve().parent
QUESTION_BANK_FILE = APP_DIR / "Togaf_Questions_Bank.csv"
QUESTION_COUNTS = (5, 10, 20, 40)

# -----------------------------------------------------------------------------
# Styling
# -----------------------------------------------------------------------------
st.markdown(
    """
    <style>
        :root {
            --navy: #102A43;
            --blue: #1864AB;
            --teal: #0B7285;
            --green: #2F9E44;
            --red: #C92A2A;
            --ink: #243B53;
            --muted: #627D98;
            --surface: #F7FAFC;
            --line: #D9E2EC;
        }
        .stApp {
            background: linear-gradient(180deg, #F4F8FC 0%, #FFFFFF 42%);
        }
        .block-container {
            max-width: 920px;
            padding-top: 1.6rem;
            padding-bottom: 3rem;
        }
        .hero {
            padding: 1.45rem 1.55rem;
            border-radius: 22px;
            background: linear-gradient(135deg, #102A43 0%, #1864AB 58%, #0B7285 100%);
            color: white;
            margin-bottom: 1.25rem;
        }
        .hero h1 {
            margin: 0 0 .35rem 0;
            font-size: clamp(1.85rem, 4vw, 2.65rem);
            line-height: 1.1;
            letter-spacing: -.025em;
        }
        .hero p { margin: 0; opacity: .9; }
        .question-card, .result-card, .start-card {
            background: #FFFFFF;
            border: 1px solid var(--line);
            border-radius: 18px;
            padding: 1.25rem 1.35rem;
            margin: .8rem 0 1rem 0;
        }
        .eyebrow {
            color: var(--blue);
            font-size: .78rem;
            font-weight: 750;
            letter-spacing: .08em;
            text-transform: uppercase;
            margin-bottom: .45rem;
        }
        .question-text {
            color: var(--ink);
            font-size: 1.16rem;
            font-weight: 700;
            line-height: 1.5;
        }
        .score-ring {
            width: 150px;
            height: 150px;
            border-radius: 50%;
            display: grid;
            place-items: center;
            margin: .45rem auto 1rem auto;
            color: white;
            background: linear-gradient(145deg, #1864AB, #0B7285);
        }
        .score-ring strong { font-size: 2rem; }
        .score-ring span { display: block; font-size: .75rem; opacity: .88; }
        .correct-label { color: var(--green); font-weight: 750; }
        .wrong-label { color: var(--red); font-weight: 750; }
        .muted { color: var(--muted); }
        div[data-testid="stButton"] > button {
            border-radius: 12px;
            min-height: 2.8rem;
            font-weight: 700;
        }
        div[role="radiogroup"] label {
            background: #FFFFFF;
            border: 1px solid var(--line);
            border-radius: 12px;
            padding: .65rem .75rem;
            margin: .18rem 0;
        }
        [data-testid="stMetric"] {
            background: white;
            border: 1px solid var(--line);
            padding: .75rem;
            border-radius: 14px;
        }
        footer { visibility: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)


def clean_text(value: str) -> str:
    """Clean spacing and common encoding artefacts without changing meaning."""
    value = (value or "").strip()
    replacements = {
        "â€œ": "“", "â€": "”", "â€™": "’", "â€“": "–", "â€”": "—",
        "\u00a0": " ", "\\_": "_",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    return " ".join(value.split())


def strip_option_prefix(value: str, letter: str) -> str:
    """Remove prefixes such as 'A)', 'A.', or 'A)' from option text."""
    text = clean_text(value)
    for prefix in (f"{letter})", f"{letter}.", f"{letter}:"):
        if text.upper().startswith(prefix.upper()):
            return text[len(prefix):].strip()
    return text


@st.cache_data(show_spinner=False)
def load_question_bank(path_string: str) -> tuple[list[dict], list[str]]:
    """
    Load the supplied eight-column CSV:
    ID, Question, A, B, C, D, E, CorrectAnswer

    A ninth column is supported as an optional Explanation field.
    """
    path = Path(path_string)
    if not path.exists():
        raise FileNotFoundError(
            f"Question bank not found: {path.name}. Keep it in the same folder as this app."
        )

    questions: list[dict] = []
    warnings: list[str] = []
    seen_signatures: set[tuple[str, tuple[str, ...]]] = set()

    with path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.reader(source)
        for line_number, row in enumerate(reader, start=1):
            if not row or not any(cell.strip() for cell in row):
                continue

            # Optional header support.
            if line_number == 1 and clean_text(row[0]).lower() in {"id", "number", "question_id"}:
                continue

            if len(row) < 8:
                warnings.append(f"Line {line_number} was skipped because it has fewer than 8 columns.")
                continue

            question_text = clean_text(row[1])
            answer_letter = clean_text(row[7]).upper()[:1]
            options = []
            for offset, letter in enumerate("ABCDE", start=2):
                option_text = strip_option_prefix(row[offset], letter)
                if option_text:
                    options.append({"letter": letter, "text": option_text})

            available_letters = {option["letter"] for option in options}
            if not question_text or answer_letter not in available_letters:
                warnings.append(
                    f"Line {line_number} was skipped because its question or correct answer is invalid."
                )
                continue

            signature = (question_text.casefold(), tuple(o["text"].casefold() for o in options))
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)

            explanation = clean_text(row[8]) if len(row) > 8 else ""
            questions.append(
                {
                    "id": clean_text(row[0]) or str(line_number),
                    "question": question_text,
                    "options": options,
                    "correct": answer_letter,
                    "explanation": explanation,
                }
            )

    if not questions:
        raise ValueError("No valid questions were found in the question bank.")
    return questions, warnings


def initialise_state() -> None:
    defaults = {
        "screen": "start",
        "quiz": [],
        "question_index": 0,
        "answers": {},
        "quiz_size": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def start_quiz(size: int, bank: list[dict]) -> None:
    st.session_state.quiz_size = size
    st.session_state.quiz = random.sample(bank, k=size)
    st.session_state.question_index = 0
    st.session_state.answers = {}
    st.session_state.screen = "quiz"
    st.rerun()


def reset_to_start() -> None:
    st.session_state.screen = "start"
    st.session_state.quiz = []
    st.session_state.question_index = 0
    st.session_state.answers = {}
    st.session_state.quiz_size = None
    st.rerun()


def option_text(question: dict, letter: str | None) -> str:
    if not letter:
        return "Not answered"
    lookup = {item["letter"]: item["text"] for item in question["options"]}
    return f"{letter}) {lookup.get(letter, 'Answer text unavailable')}"


initialise_state()

st.markdown(
    """
    <section class="hero">
      <h1>TOGAF Exam Simulator</h1>
      <p>Focused practice, immediate scoring and a clear answer review.</p>
    </section>
    """,
    unsafe_allow_html=True,
)

try:
    question_bank, data_warnings = load_question_bank(str(QUESTION_BANK_FILE))
except (FileNotFoundError, ValueError) as exc:
    st.error(str(exc))
    st.info("Upload the Python file and Togaf_Questions_Bank.csv into the same website folder.")
    st.stop()

with st.sidebar:
    st.subheader("Exam simulator")
    st.caption("Unofficial study tool")
    st.metric("Questions available", len(question_bank))
    if st.session_state.screen == "quiz":
        answered = len(st.session_state.answers)
        total = len(st.session_state.quiz)
        st.metric("Answered", f"{answered} / {total}")
        st.progress(answered / total if total else 0)
        if st.button("End this test", use_container_width=True):
            reset_to_start()
    elif st.session_state.screen == "results":
        total = len(st.session_state.quiz)
        correct = sum(
            st.session_state.answers.get(i) == q["correct"]
            for i, q in enumerate(st.session_state.quiz)
        )
        st.metric("Latest score", f"{correct} / {total}")
    if data_warnings:
        with st.expander("Question-bank checks"):
            st.write(f"{len(data_warnings)} row(s) were skipped.")
            for warning in data_warnings[:10]:
                st.caption(warning)


if st.session_state.screen == "start":
    st.markdown(
        """
        <div class="start-card">
          <div class="eyebrow">Create a new practice test</div>
          <div class="question-text">How many questions would you like to try?</div>
          <p class="muted">Each test is selected randomly from the supplied question bank.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    columns = st.columns(4)
    for column, size in zip(columns, QUESTION_COUNTS):
        with column:
            if st.button(str(size), key=f"start_{size}", use_container_width=True, type="primary"):
                if size > len(question_bank):
                    st.error(f"The question bank contains only {len(question_bank)} valid questions.")
                else:
                    start_quiz(size, question_bank)

    st.caption("Questions are not shown as official or endorsed examination content.")


elif st.session_state.screen == "quiz":
    quiz = st.session_state.quiz
    index = st.session_state.question_index
    question = quiz[index]
    total = len(quiz)

    st.progress((index + 1) / total, text=f"Question {index + 1} of {total}")
    st.markdown(
        f"""
        <div class="question-card">
          <div class="eyebrow">Question {index + 1} of {total}</div>
          <div class="question-text">{html.escape(question['question'])}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    available_letters = [item["letter"] for item in question["options"]]
    current_answer = st.session_state.answers.get(index)
    default_index = available_letters.index(current_answer) if current_answer in available_letters else None
    labels = {item["letter"]: f"{item['letter']}) {item['text']}" for item in question["options"]}

    selected = st.radio(
        "Select one answer",
        options=available_letters,
        index=default_index,
        format_func=lambda letter: labels[letter],
        key=f"answer_widget_{index}",
        label_visibility="collapsed",
    )

    back_col, spacer, next_col = st.columns([1, 1.5, 1.25])
    with back_col:
        if index > 0 and st.button("← Previous", use_container_width=True):
            if selected:
                st.session_state.answers[index] = selected
            st.session_state.question_index -= 1
            st.rerun()
    with next_col:
        button_text = "Finish test" if index == total - 1 else "Next question →"
        if st.button(button_text, type="primary", use_container_width=True, disabled=selected is None):
            st.session_state.answers[index] = selected
            if index == total - 1:
                st.session_state.screen = "results"
            else:
                st.session_state.question_index += 1
            st.rerun()

    if selected is None:
        st.caption("Choose an answer to continue.")


elif st.session_state.screen == "results":
    quiz = st.session_state.quiz
    answers = st.session_state.answers
    total = len(quiz)
    correct_count = sum(answers.get(i) == q["correct"] for i, q in enumerate(quiz))
    wrong_count = total - correct_count
    score = round((correct_count / total) * 100) if total else 0

    st.markdown(
        f"""
        <div class="score-ring">
          <div><strong>{score}%</strong><span>FINAL SCORE</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    metric_1, metric_2, metric_3 = st.columns(3)
    metric_1.metric("Correct", correct_count)
    metric_2.metric("Incorrect", wrong_count)
    metric_3.metric("Total", total)

    if score >= 80:
        st.success("Strong result. Review the details below to reinforce your knowledge.")
    elif score >= 60:
        st.info("Good progress. Focus your next review on the questions you missed.")
    else:
        st.warning("Keep practising. Use the answer review below to target the main gaps.")

    st.subheader("Answer review")
    review_filter = st.radio(
        "Show",
        ["All questions", "Incorrect only", "Correct only"],
        horizontal=True,
        label_visibility="collapsed",
    )

    for i, question in enumerate(quiz):
        user_answer = answers.get(i)
        is_correct = user_answer == question["correct"]
        if review_filter == "Incorrect only" and is_correct:
            continue
        if review_filter == "Correct only" and not is_correct:
            continue

        status_icon = "✅" if is_correct else "❌"
        status_text = "Correct" if is_correct else "Incorrect"
        with st.expander(f"{status_icon} Question {i + 1}: {status_text}", expanded=not is_correct):
            st.markdown(f"**{question['question']}**")
            st.write(f"**Your answer:** {option_text(question, user_answer)}")
            st.write(f"**Correct answer:** {option_text(question, question['correct'])}")
            if question["explanation"]:
                st.info(f"Explanation: {question['explanation']}")
            else:
                st.caption(
                    "No explanation is stored for this question. Add an optional ninth CSV column "
                    "to display a detailed explanation here."
                )

    st.divider()
    st.subheader("Would you like to generate a new test?")
    new_col, same_col = st.columns(2)
    with new_col:
        if st.button("Choose a new test length", type="primary", use_container_width=True):
            reset_to_start()
    with same_col:
        if st.button("New random test, same length", use_container_width=True):
            start_quiz(st.session_state.quiz_size, question_bank)
