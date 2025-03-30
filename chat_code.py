from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from models import ChatHistory

load_dotenv()

model = ChatGoogleGenerativeAI(model='gemini-1.5-pro')

def get_chat_response(query, user_id):
    if user_id == "":
        response = model.invoke(query)
    else:
        chat_history = ChatHistory.query.filter_by(user_id=user_id).order_by(ChatHistory.timestamp).all() 
        chat_data = [{"message": chat.message, "response": chat.response, "timestamp": chat.timestamp} for chat in chat_history]
        messages = []
        for chat in chat_data:
            messages.append(HumanMessage(content=chat['message']))
            messages.append(AIMessage(content=chat['response']))
        messages.append(HumanMessage(content=query))
        response = model.invoke(messages)
        messages = []
    return response.content