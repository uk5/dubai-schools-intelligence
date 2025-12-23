
import os
import pandas as pd
import google.generativeai as genai
from dotenv import load_dotenv
import ollama

load_dotenv()

class SchoolAgent:
    def __init__(self, data_path):
        """Initialize the RAG agent with both Gemini and Ollama support."""
        self.df = pd.read_excel(data_path)
        
        # Try to get API key from Streamlit secrets first (for cloud), then from .env (for local)
        api_key = None
        
        # First try Streamlit secrets (cloud deployment)
        try:
            import streamlit as st
            if hasattr(st, 'secrets'):
                api_key = st.secrets.get("GEMINI_API_KEY")
        except Exception as e:
            pass
        
        # Fallback to environment variables (local development)
        if not api_key:
            api_key = os.getenv("GEMINI_API_KEY")
        
        # Configure Gemini with the API key
        if api_key:
            genai.configure(api_key=api_key)
            self.gemini_model = genai.GenerativeModel('gemini-1.5-pro')
        else:
            self.gemini_model = None
            print("⚠️ Warning: Gemini API key not found. AI chat will not work.")
        
    def search_schools(self, query, filters=None):
        """
        Base tool for searching schools based on criteria.
        """
        temp_df = self.df.copy()
        
        if filters:
            for col, val in filters.items():
                if col in temp_df.columns:
                    if isinstance(val, list):
                        temp_df = temp_df[temp_df[col].isin(val)]
                    else:
                        temp_df = temp_df[temp_df[col] == val]
        
        # Simple logical search for now, can be expanded with FAISS
        # We will use the dataframe for answering direct data questions
        return temp_df.head(10).to_dict(orient='records')

    def ask(self, user_query, context_df=None):
        # Format the context data clearly for the LLM
        context_text = "No relevant schools found."
        if context_df is not None and not context_df.empty:
            # Only send key details to keep context light and relevant
            cols_to_send = ['name', 'curriculum', 'overall_rating', 'location']
            available_cols = [c for c in cols_to_send if c in context_df.columns]
            context_text = context_df[available_cols].to_string(index=False)

        system_prompt = f"""
        You are the Dubai School Expert Bot. 
        Your ONLY source of truth is the provided context data below.
        DO NOT use outside information about schools. DO NOT hallucinate.
        If a school is not in the data, tell the user you don't have information about it in the current dataset.
        
        Context Data (Filtered Schools):
        {context_text}
        
        Always be helpful, professional, and guide the user based on the context ratings, fees, and location.
        """
        
        # Try Gemini first if available
        if self.gemini_model:
            try:
                print(f"[DEBUG] Attempting Gemini API call...")
                response = self.gemini_model.generate_content(system_prompt + "\nUser Question: " + user_query)
                print(f"[DEBUG] Gemini response received!")
                return response.text
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                print(f"[ERROR] Gemini API failed: {e}")
                print(f"[ERROR] Full traceback: {error_details}")
                # Return the error so user can see what's wrong
                return f"⚠️ Gemini API Error: {str(e)}\n\nThis usually means the API key is invalid or there's a connectivity issue. Please double-check the GEMINI_API_KEY in Streamlit Cloud Secrets."
        else:
            return "⚠️ Gemini model not initialized. Please check that GEMINI_API_KEY is configured in Streamlit Cloud Secrets."

# Sample usage logic for testing
if __name__ == "__main__":
    agent = SchoolAgent("data/dxb_schools_v0.1.xlsx")
    print(agent.ask("What are some high rated schools in Dubai?"))
