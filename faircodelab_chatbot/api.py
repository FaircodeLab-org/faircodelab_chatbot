# File: ~/frappe-bench/apps/faircodelab_chatbot/faircodelab_chatbot/api.py

import frappe
import openai

@frappe.whitelist(allow_guest=True)
def get_bot_response(user_message):
    response = process_message(user_message)
    return response

def process_message(user_message):
    user_message = user_message.lower().strip()

    # Search Knowledge Base
    faq = search_faq(user_message)
    if faq:
        return faq

    # If no match, use GPT to find the most relevant FAQ
    faqs = get_all_faqs()  # Fetch all FAQs from the database
    gpt_answer = get_gpt_interpreted_faq(user_message, faqs)
    return gpt_answer

def search_faq(user_message):
    # Perform a basic search for FAQs (exact match or contains)
    faqs = frappe.get_all('FAQS', fields=['question', 'answer'])
    for faq in faqs:
        if user_message in faq['question'].lower(): # Basic matching
            return faq['answer']
    return None

def get_all_faqs():
    # Fetch all FAQs from the database
    faqs = frappe.get_all('FAQS', fields=['question', 'answer'])
    return [{"question": faq["question"], "answer": faq["answer"]} for faq in faqs]

def get_gpt_interpreted_faq(user_message, faqs):
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

    Company Description:
    {company_description}

    FAQs:
    {faq_prompt}
    """

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=150,
            temperature=0.7,
        )
        return response.choices[0].message['content'].strip()
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "OpenAI API Error")
        return "I'm sorry, I'm having trouble responding right now. Please try again later."