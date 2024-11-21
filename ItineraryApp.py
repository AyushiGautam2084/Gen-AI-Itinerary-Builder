import openai
import streamlit as st
from dotenv import load_dotenv
import os
import wikipediaapi
from geopy.geocoders import Nominatim
import spacy
import re

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
nlp = spacy.load("en_core_web_sm")
user_agent = "TravelItineraryApp/1.0 (your_email@gmail.com)"
wiki_wiki = wikipediaapi.Wikipedia(language='en', user_agent=user_agent)
geolocator = Nominatim(user_agent="TravelItineraryApp")

st.markdown(
    """
    <style>
    body {
        font-family: 'Helvetica', sans-serif;
    }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("AI Travel Itinerary Builder Chat")
st.write("Chat with the AI to plan your personalized travel itinerary with detailed references and time-wise format!")

if "initialized" not in st.session_state:
    st.session_state["initialized"] = True
    st.session_state.messages = [{
        "role": "assistant",
        "content": "Welcome to the AI Itinerary Builder! Please tell me your preferred location and trip duration (e.g., 'Japan for 7 days').\n\nMoreover, you can customize your trip further by mentioning any of the following keywords:\n\n- Adventure\n- Historic\n- Foodie\n- Pilgrimage\n- Kid-friendly\n- Senior Citizen friendly\n- Solo\n- Budget-friendly"
    }]
    st.session_state.preferences = []
    st.session_state.finalized_preferences = False
    st.session_state.location_duration = ""
    st.session_state.itinerary_generated = False
    st.session_state.additional_requests = []
    st.session_state.itinerary_content = ""

def display_chat():
    for message in st.session_state.messages:
        if message["role"] == "user":
            st.chat_message("user").markdown(message["content"])
        else:
            st.chat_message("assistant").markdown(message["content"])

def generate_itinerary():
    location_duration = st.session_state.location_duration
    preferences = st.session_state.preferences
    try:
        days_allocation = extract_city_allocations(location_duration)
        itinerary_prompt = f"Create a detailed day-by-day travel itinerary for a {location_duration} with preferences: {', '.join(preferences)}. Each day should be split into Morning, Afternoon, Evening, and Night activities, and provide detailed suggestions for each timeframe."
        if days_allocation:
            itinerary_prompt += f" Ensure the itinerary respects the following allocations: {', '.join([f'{days} days in {city}' for city, days in days_allocation.items()])}."

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=st.session_state.messages + [{"role": "user", "content": itinerary_prompt}]
        )

        ai_message = response['choices'][0]['message']['content'].strip()

        formatted_message = re.sub(r'(Day \d+:)', r'\n\1\n', ai_message)
        formatted_message = re.sub(r'(Morning|Afternoon|Evening|Night):', r'\n\1:\n', formatted_message)
        formatted_message = re.sub(r'^\s-\s', '\n- ', formatted_message, flags=re.MULTILINE)

        if not st.session_state.itinerary_generated:
            enriched_itinerary = formatted_message + "\n\n**Additional Links for Reference:**\n"
            enriched_itinerary += fetch_wikipedia_links(formatted_message)
            st.session_state.itinerary_content = enriched_itinerary
            st.session_state.messages.append({"role": "assistant", "content": enriched_itinerary})
            st.session_state.itinerary_generated = True
    except Exception as e:
        st.error(f"An error occurred while generating the itinerary: {e}")

def extract_city_allocations(user_input):
    allocations = {}
    input_words = user_input.split()
    for i in range(len(input_words)):
        if input_words[i].isdigit() and i + 2 < len(input_words) and input_words[i + 1].lower() == "days" and input_words[i + 2].lower() == "in":
            days = int(input_words[i])
            city = input_words[i + 3].capitalize()
            allocations[city] = days
    return allocations

def fetch_wikipedia_links(itinerary_text):
    doc = nlp(itinerary_text)
    unique_entities = set([ent.text for ent in doc.ents if ent.label_ == "GPE" or ent.label_ == "LOC"])
    links = ""
    for entity in unique_entities:
        page = wiki_wiki.page(entity)
        if page.exists():
            links += f"- [{entity}]({page.fullurl})\n"
    return links if links else "No additional links found."

def process_follow_up_request(prompt):
    st.session_state.messages.append({"role": "user", "content": prompt})

    add_days_match = re.search(r'\badd\s+(\d+)\s+days\b', prompt.lower())
    reduce_days_match = re.search(r'\breduce\s+the duration by\s+(\d+)\s+days\b', prompt.lower())

    if add_days_match:
        number_of_days = add_days_match.group(1)
        action = "add"
    elif reduce_days_match:
        number_of_days = reduce_days_match.group(1)
        action = "reduce"
    else:
        number_of_days = None
        action = None

    try:
        if action == "add":
            detailed_prompt = (
                f"Please expand on the existing itinerary and integrate {number_of_days} more days into the trip, "
                "including relevant destinations, activities, meals, and notable sites. Provide more details and include "
                "references where appropriate."
            )
        elif action == "reduce":
            detailed_prompt = (
                f"Please shorten the existing itinerary by removing {number_of_days} days. Ensure that the most important "
                "activities and destinations are retained, and provide more details for the remaining days with relevant references."
            )
        else:
            detailed_prompt = prompt

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=st.session_state.messages + [{"role": "user", "content": detailed_prompt}]
        )

        ai_message = response['choices'][0]['message']['content'].strip()

        formatted_followup_message = re.sub(r'(Day \d+:)', r'\n\1\n', ai_message)
        formatted_followup_message = re.sub(r'(Morning|Afternoon|Evening|Night):', r'\n\1:\n', formatted_followup_message)
        formatted_followup_message = re.sub(r'^\s-\s', '\n- ', formatted_followup_message, flags=re.MULTILINE)

        if not any(ai_message == msg["content"] for msg in st.session_state.messages if msg["role"] == "assistant"):
            st.session_state.itinerary_content += "\n\n" + formatted_followup_message
            st.session_state.messages.append({"role": "assistant", "content": formatted_followup_message})

    except Exception as e:
        st.error(f"An error occurred while processing the follow-up request: {e}")

if not st.session_state.location_duration:
    if prompt := st.chat_input("Enter your preferred location and trip duration (e.g., 'Japan for 7 days'):"):
        st.session_state.location_duration = prompt
        st.session_state.messages.append({"role": "user", "content": prompt})
        preferences_list = ["adventure", "historic", "foodie", "pilgrimage", "kid-friendly", "senior citizen friendly", "solo", "budget-friendly"]
        st.session_state.preferences = [word.strip().capitalize() for word in preferences_list if word in prompt.lower()]
        generate_itinerary()
else:
    if prompt := st.chat_input("Ask about your travel plans, preferences, or a destination!"):
        process_follow_up_request(prompt)

display_chat()
