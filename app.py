import os
import requests
import json
import gradio as gr
from typing import TypedDict, Annotated, List
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage
from langchain_community.vectorstores import FAISS
from langgraph.graph import StateGraph, END
import operator
from dotenv import load_dotenv

# load .env environment file
load_dotenv(override=True)

API_GATEWAY_URL = os.getenv("API_GATEWAY_URL")
os.environ["GEMINI_API_KEY"] = os.getenv("GEMINI_API_KEY")

# Langgraph state definition
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    user_query: str
    retrieved_schema: str
    sql_query: str
    query_result: str
    error: str
    retry_count: int

schema_docs = [
    "Table: database.table. Columns: guid (string),",
    "Data Dictionary: table schema",
]

embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
vector_store = FAISS.from_texts(schema_docs, embedding=embeddings)
retriever = vector_store.as_retriever(search_kwargs={"k": 2})

def retrieve_schema(state: AgentState):
    """
    Fetch relevant schema information based on user query.
    """
    docs = retriever.get_relevant_documents(state['user_query'])
    context = "\n".join([d.page_content for d in docs])
    return {"retrieved_schema": context}


def should_retry(state: AgentState):
    """
    Check if we need to loop back.
    """
    if state['error']:
        if state['retry_count'] < 3:
            print(f"Error detected: {state['error']}. Retrying ({state['retry_count']}/3)...")
            return "retry"
        else:
            print("Max retries reached.")
            return "give_up"
    return "success"

def summarize_results(state: AgentState):
    """
    Summarize the data for the user.
    """
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.5)
    
    data_result = state['query_result']
        
    prompt = f"""The user asked: "{state['user_query']}"
    The database returned this raw JSON data:
    {data_result}
    Please provide a concise, human-readable answer summarizing these results. 
    If the data is a table, briefly describe the key insights.
    """
    
    response = llm.invoke([HumanMessage(content=prompt)])
    return {"Summarized Results": [AIMessage(content=response.content)]}

def execute_query(state: AgentState):
    """
    Call AWS API Gateway which internally calls Lambda and Athena.
    """
    print(f"Executing Query on AWS: {state['sql_query']} ---")
    try:
        response = requests.post(
            API_GATEWAY_URL, 
            json={"sql_query": state['sql_query']},
            timeout=60
        )
        response_data = response.json()
        if response.status_code == 200:
            return {"query_result": json.dumps(response_data.get('data', [])), "error": None}
        else:
            error_msg = response_data.get('error', 'Unknown AWS Error')
            return {"error": error_msg, "query_result": None}           
    except Exception as e:
        return {"error": f"Network/Client Error: {str(e)}", "query_result": None}

def generate_sql(state: AgentState):
    """
    Generate SQL based on input + schema + previous errors.
    """
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
    system_prompt = f"""You are an expert AWS Athena SQL Data Analyst.
    Your goal is to write syntactically correct SQL queries for Amazon Athena.
    Schema Context:
    {state['retrieved_schema']}
    Instructions:
    1. Output ONLY the SQL query. No markdown, no backticks, no explanations.
    2. If there is an error in the previous attempt, fix it based on the error message provided.
    """
    messages = [SystemMessage(content=system_prompt)] + state['messages']
    
    if state.get('error'):
        messages.append(HumanMessage(content=f"Previous query failed with error: {state['error']}. Please fix the SQL."))

    response = llm.invoke(messages)
    sql = response.content.strip().replace("```sql", "").replace("```", "")
    return {"sql_query": sql, "messages": [AIMessage(content=sql)]}


# Build Graph
workflow = StateGraph(AgentState)

workflow.add_node("retrieve_schema", retrieve_schema)
workflow.add_node("generate_sql", generate_sql)
workflow.add_node("execute_query", execute_query)
workflow.add_node("summarize", summarize_results)

workflow.set_entry_point("retrieve_schema")
workflow.add_edge("retrieve_schema", "generate_sql")
workflow.add_edge("generate_sql", "execute_query")

# Conditional Routing
workflow.add_conditional_edges(
    "execute_query",
    should_retry,
    {
        "retry": "generate_sql",
        "success": "summarize",
        "give_up": "summarize"
    }
)

workflow.add_edge("summarize", END)

app_graph = workflow.compile()



def chat_interface(user_input, history):
    """
    Gradio Callback function
    """
    inputs = {
        "user_query": user_input,
        "messages": [HumanMessage(content=user_input)],
        "retry_count": 0,
        "error": None,
        "chat_history": history
    }
    
    final_response = "Processing..."
    
    # Run the Graph
    try:
        final_state = app_graph.invoke(inputs)
        final_response = final_state['messages'][-1].content

        if final_state.get('error') and final_state['retry_count'] >= 3:
            final_response += f"\n\n(Technical Detail: Query failed after retries: {final_state['error']})"
    except Exception as e:
        final_response = f"System Error: {str(e)}"

    return final_response

def heading_style_1(text: str):
    return f"<span style='font-size: 2.5rem;font-weight: 900;color: #2c3e50;margin-bottom: 1rem;text-align: center;line-height: 1.2;'>{text}</span>"

def heading_style_2(text: str):
    return f"<span style='font-size: 1rem;font-weight: 300;color: #2c3e81;margin-bottom: 1rem;text-align: center;'>{text}</span>"


with gr.Blocks() as ui_interface:
    gr.Markdown(heading_style_1("AI Driven Data Lake Query System"))
    gr.Markdown(heading_style_2("Describe your data request in plain English. The Agent will query Athena and self-correct if error occurs in generated sql query."))
    
    with gr.Row():
        with gr.Column(scale=4):
             chatbot = gr.ChatInterface(
                fn=chat_interface
            )

if __name__ == "__main__":
    custom_css = """
    #component-0 {height: 100vh;}
    .chat-window {font-family: 'Roboto Mono', monospace;}
    footer {
        display: none !important;
    }
    """
    ui_interface.launch(theme=gr.themes.Soft(), css=custom_css)
