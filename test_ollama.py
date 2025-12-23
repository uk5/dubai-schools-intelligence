
import ollama

try:
    response = ollama.chat(model='llama3.1:8b', messages=[
        {'role': 'user', 'content': 'Hello'},
    ])
    print("Ollama Response:", response['message']['content'])
except Exception as e:
    print("Ollama Error:", e)
