# File: ~/frappe-bench/apps/faircodelab_chatbot/faircodelab_chatbot/api.py

import frappe
import openai
import json
import re
from difflib import SequenceMatcher

DEFAULT_OPENAI_CHAT_MODEL = "gpt-5.6-terra"
DEFAULT_OPENAI_MAX_COMPLETION_TOKENS = 700
DEFAULT_OPENAI_RETRY_MAX_COMPLETION_TOKENS = 1200
LOCAL_FAQ_MATCH_THRESHOLD = 0.64
CHAT_HISTORY_LIMIT = 8
LOCAL_FAQ_STOP_WORDS = {
    "a",
    "about",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "can",
    "could",
    "describe",
    "do",
    "does",
    "for",
    "from",
    "give",
    "how",
    "i",
    "in",
    "is",
    "it",
    "list",
    "me",
    "of",
    "on",
    "or",
    "our",
    "please",
    "show",
    "should",
    "tell",
    "the",
    "to",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
    "would",
    "you",
    "your",
}
LOCAL_FAQ_LOW_SIGNAL_TOKENS = {
    "chatbot",
    "company",
    "faircode",
    "faircodelab",
    "lab",
    "organic",
    "planton",
    "uganda",
}
LOCAL_FAQ_TOKEN_ALIASES = {
    "ceo": {"chief", "executive", "officer"},
    "md": {"managing", "director"},
}
CONTEXTUAL_STATEMENT_STARTS = (
    "also ",
    "and ",
    "but ",
    "he ",
    "her ",
    "his ",
    "it ",
    "my ",
    "no ",
    "she ",
    "that ",
    "their ",
    "there ",
    "they ",
    "this ",
    "we ",
    "yes ",
)
FAQ_QUERY_STARTS = (
    "can ",
    "could ",
    "describe ",
    "do ",
    "does ",
    "explain ",
    "give ",
    "how ",
    "is ",
    "list ",
    "show ",
    "tell ",
    "what ",
    "when ",
    "where ",
    "which ",
    "who ",
    "why ",
)


def normalize_faq_text(text):
    text = str(text or "").casefold()
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def get_meaningful_tokens(normalized_text):
    return {
        token
        for token in normalized_text.split()
        if len(token) > 1 and token not in LOCAL_FAQ_STOP_WORDS
    }


def get_match_tokens(normalized_text):
    return get_meaningful_tokens(normalized_text) - LOCAL_FAQ_LOW_SIGNAL_TOKENS


def expand_match_tokens(tokens):
    expanded = set(tokens)
    for token in tokens:
        expanded.update(LOCAL_FAQ_TOKEN_ALIASES.get(token, set()))
    return expanded


def has_company_name(normalized_text):
    return (
        "faircodelab" in normalized_text
        or "faircode lab" in normalized_text
        or "planton" in normalized_text
        or "uganda" in normalized_text
    )


def is_company_overview_query(user_norm, user_match_tokens):
    if not has_company_name(user_norm) or user_match_tokens:
        return False

    return (
        user_norm in ("faircodelab", "faircode lab", "planton", "planton organic uganda")
        or user_norm.startswith("what is faircodelab")
        or user_norm.startswith("what is faircode lab")
        or user_norm.startswith("what is planton")
        or user_norm.startswith("what does faircodelab")
        or user_norm.startswith("what does faircode lab")
        or user_norm.startswith("what does planton")
        or user_norm.startswith("tell me about faircodelab")
        or user_norm.startswith("tell me about faircode lab")
        or user_norm.startswith("tell me about planton")
        or user_norm.startswith("describe faircodelab")
        or user_norm.startswith("describe faircode lab")
        or user_norm.startswith("describe planton")
        or user_norm.startswith("about faircodelab")
        or user_norm.startswith("about faircode lab")
        or user_norm.startswith("about planton")
    )


def is_company_overview_question(question_norm):
    return has_company_name(question_norm) and not get_match_tokens(question_norm)


def should_try_local_faq_fallback(user_norm):
    if not user_norm:
        return False

    if user_norm.startswith(CONTEXTUAL_STATEMENT_STARTS):
        return False

    if "?" in user_norm or user_norm.startswith(FAQ_QUERY_STARTS):
        return True

    return len(get_match_tokens(user_norm)) >= 2


def score_faq_match(user_norm, user_tokens, question_norm):
    if not user_norm or not question_norm:
        return 0

    if user_norm == question_norm:
        return 1

    user_match_tokens = user_tokens - LOCAL_FAQ_LOW_SIGNAL_TOKENS
    question_tokens = get_meaningful_tokens(question_norm)
    question_match_tokens = question_tokens - LOCAL_FAQ_LOW_SIGNAL_TOKENS
    expanded_user_match_tokens = expand_match_tokens(user_match_tokens)
    expanded_question_match_tokens = expand_match_tokens(question_match_tokens)

    if not user_match_tokens:
        if is_company_overview_query(user_norm, user_match_tokens) and is_company_overview_question(question_norm):
            return 0.95
        return 0

    score = 0
    if user_norm in question_norm or question_norm in user_norm:
        smaller_token_count = min(len(user_tokens), len(question_tokens))
        smaller_match_token_count = min(len(expanded_user_match_tokens), len(expanded_question_match_tokens))
        if smaller_token_count >= 2 and smaller_match_token_count >= 1:
            score = max(score, 0.92)

    if expanded_user_match_tokens and expanded_question_match_tokens:
        common_tokens = expanded_user_match_tokens.intersection(expanded_question_match_tokens)
        if common_tokens:
            coverage = len(common_tokens) / len(expanded_user_match_tokens)
            precision = len(common_tokens) / len(expanded_question_match_tokens)
            token_score = (coverage * 0.78) + (precision * 0.22)

            if len(user_match_tokens) == 1:
                token_score = min(token_score, 0.62)

            score = max(score, token_score)
            score = max(score, SequenceMatcher(None, user_norm, question_norm).ratio())

    return score


def get_no_faq_match_message():
    return (
        "I'm sorry, I couldn't find a matching answer in our FAQ. "
        "Please try rephrasing your question or contact our team for more details."
    )


def get_openai_chat_model():
    return frappe.conf.get("faircodelab_chatbot_chat_model") or DEFAULT_OPENAI_CHAT_MODEL


def get_int_config(key, default, min_value=None, max_value=None):
    try:
        value = int(frappe.conf.get(key) or default)
    except Exception:
        return default

    if min_value is not None:
        value = max(value, min_value)
    if max_value is not None:
        value = min(value, max_value)
    return value


def get_openai_max_completion_tokens():
    return get_int_config(
        "faircodelab_chatbot_chat_max_completion_tokens",
        DEFAULT_OPENAI_MAX_COMPLETION_TOKENS,
        min_value=200,
        max_value=4000,
    )


def get_openai_retry_max_completion_tokens(first_limit):
    configured_retry_limit = get_int_config(
        "faircodelab_chatbot_chat_retry_max_completion_tokens",
        DEFAULT_OPENAI_RETRY_MAX_COMPLETION_TOKENS,
        min_value=first_limit,
        max_value=6000,
    )
    return max(first_limit * 2, configured_retry_limit)


def get_recent_chat_messages(chat_history):
    if isinstance(chat_history, str):
        try:
            chat_history = json.loads(chat_history)
        except Exception:
            frappe.logger().debug("Ignoring FairCodeLab chatbot chat history payload.")
            return []

    if not isinstance(chat_history, list):
        return []

    messages = []
    for item in chat_history[-CHAT_HISTORY_LIMIT:]:
        if not isinstance(item, dict):
            continue

        role = item.get("role")
        content = str(item.get("content") or "").strip()
        if role not in ("user", "assistant") or not content:
            continue

        messages.append({
            "role": role,
            "content": content[:600],
        })

    return messages

@frappe.whitelist(allow_guest=True)
def get_bot_response(user_message, chat_history=None):
    response = process_message(user_message, chat_history=chat_history)
    return response

def process_message(user_message, chat_history=None):
    user_message = (user_message or "").strip()
    if not user_message:
        return "Please enter a question so I can help you."

    # Search Knowledge Base
    faq = search_faq(user_message)
    if faq:
        return faq

    faq = search_faq_fallback(user_message)
    if faq:
        return faq

    # If no match, use GPT to interpret the available FAQs and company info.
    faqs = get_all_faqs()  # Fetch all FAQs from the database
    gpt_answer = get_gpt_interpreted_faq(user_message, faqs, chat_history=chat_history)
    return gpt_answer

def search_faq(user_message):
    user_norm = normalize_faq_text(user_message)
    faqs = frappe.get_all('FAQS', fields=['question', 'answer'])
    for faq in faqs:
        if user_norm == normalize_faq_text(faq.get('question')):
            return faq['answer']
    return None

def search_faq_fallback(user_message):
    user_norm = normalize_faq_text(user_message)
    user_tokens = get_meaningful_tokens(user_norm)
    if not should_try_local_faq_fallback(user_norm):
        return None

    faqs = frappe.get_all('FAQS', fields=['question', 'answer'])
    best_answer = None
    best_score = 0

    for faq in faqs:
        question_norm = normalize_faq_text(faq.get('question'))
        score = score_faq_match(user_norm, user_tokens, question_norm)

        if score == 1:
            return faq.get('answer')

        if score > best_score:
            best_score = score
            best_answer = faq.get('answer')

    if best_score >= LOCAL_FAQ_MATCH_THRESHOLD:
        frappe.logger().debug(f"Local FAQ fallback matched with score {best_score:.2f}")
        return best_answer

    frappe.logger().debug(f"Local FAQ fallback found no match. Best score: {best_score:.2f}")
    return None

def get_all_faqs():
    # Fetch all FAQs from the database
    faqs = frappe.get_all('FAQS', fields=['question', 'answer'])
    return [{"question": faq["question"], "answer": faq["answer"]} for faq in faqs]

def get_gpt_interpreted_faq(user_message, faqs, chat_history=None):
    openai_api_key = frappe.conf.get("openai_api_key")
    if not openai_api_key:
        frappe.log_error("OpenAI API key not found in site config.", "Chatbot Error")
        return "I'm sorry, I cannot process your request at the moment."

    openai.api_key = openai_api_key

    # Prepare the GPT prompt with all FAQs
    faq_prompt = "\n".join([f"Q: {faq['question']}\nA: {faq['answer']}" for faq in faqs])

    # Incorporate company description, vision, and mission into the system prompt
    company_description = """
    Planton Organic Uganda is a team of committed and experienced professionals with decades of expertise in the global Fairtrade and Organic sectors. Our journey has taken us across continents, where we have successfully established producer organizations that empower smallholder farmers and promote sustainable practices. Our work is rooted in creating resilient and transparent supply chains, supporting communities, and fostering sustainable growth.

    Vision:
    To empower small-scale farmers in Uganda by creating a sustainable agricultural ecosystem that enhances their livelihoods, respects the environment, and values local cultures, creating high-quality, traceable organic products for global markets.

    Mission:
    Our mission is to drive economic growth and environmental stewardship among Uganda's smallholder farmers through sustainable agricultural practices, fair partnerships, and technological innovations like the Hubtrace app for traceability. We are committed to respecting local cultural values, advancing organic farming techniques, and providing quality organic products with transparency and integrity.
    """

    system_prompt = f"""
    You are a helpful assistant for Planton Organic Uganda. Use the following information to answer the user's questions in a clear and friendly manner.
    If the user's question is conversational or not covered by the FAQs, answer naturally and honestly. For example, if you do not know a personal detail such as the user's name, say that you do not know it yet and invite them to tell you.
    Use the recent conversation to understand follow-up messages and pronouns, but do not invent private facts beyond what the user has told you.
    For leadership, staff, roles, ownership, contact details, prices, certifications, and other factual company details, answer only from the provided company description, FAQs, or recent conversation. If the information is not provided there, say that you do not have verified information about it.
    Do not mention that no FAQ match was found unless the user specifically asks about the FAQ.

    Company Description:
    {company_description}

    FAQs:
    {faq_prompt}
    """

    messages = [
        {"role": "system", "content": system_prompt.strip()},
        *get_recent_chat_messages(chat_history),
        {"role": "user", "content": user_message.strip()},
    ]

    try:
        max_completion_tokens = get_openai_max_completion_tokens()
        response = openai.ChatCompletion.create(
            model=get_openai_chat_model(),
            messages=messages,
            max_completion_tokens=max_completion_tokens,
        )
        choice = response.choices[0]
        content = (choice.message.get('content') or "").strip()
        if content:
            return content

        retry_max_completion_tokens = get_openai_retry_max_completion_tokens(max_completion_tokens)
        frappe.logger().warning(
            "OpenAI returned an empty FairCodeLab chatbot response. "
            f"finish_reason={getattr(choice, 'finish_reason', None)}, "
            f"retrying with max_completion_tokens={retry_max_completion_tokens}."
        )

        response = openai.ChatCompletion.create(
            model=get_openai_chat_model(),
            messages=messages,
            max_completion_tokens=retry_max_completion_tokens,
        )
        choice = response.choices[0]
        content = (choice.message.get('content') or "").strip()
        if content:
            return content

        frappe.log_error(
            f"OpenAI returned an empty response after retry. finish_reason={getattr(choice, 'finish_reason', None)}",
            "Chatbot Empty Response",
        )
        return "I'm sorry, I couldn't generate a response just now. Please try again in a moment."
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "OpenAI API Error")
        return get_no_faq_match_message()
