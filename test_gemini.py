
import google.generativeai as genai
import os
from dotenv import load_dotenv
import streamlit as st

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
print(f"Key used: {api_key[:5]}...{api_key[-5:]}")

genai.configure(api_key=api_key)
# model = genai.GenerativeModel('gemini-1.5-pro')
model = genai.GenerativeModel('gemini-1.5-flash')

try:
    response = model.generate_content("Hello")
    print("Gemini Response:", response.text)
except Exception as e:
    print("Gemini Error:", e)
