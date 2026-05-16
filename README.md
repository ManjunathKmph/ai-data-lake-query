# AI Driven Data Lake Query System

Architecture for querying an AWS Data Lake (S3 + Athena) using LLMs and RAG, with validation and self-correction for safe, accurate execution.

![alt text](./AI_Driven_Data_Query_Arch.png)

## Overview
- Natural language → validated SQL routed to Athena via Lambda.
- RAG enriches prompts with schema/data dictionary embeddings from a vector DB.
- Self-correction loop iterates on invalid queries until they pass checks or fail out.
- Gradio chat UI fronts the workflow; API Gateway returns final results.

## Components
1) **User & Gradio UI Chat**  
   Conversational UI where users submit questions; main entry point to the flow.

2) **AI LangGraph Agent Framework**  
   Orchestrates steps across RAG, LLMs, validation, and AWS execution.

3) **RAG Module**  
   Retrieves schema/data dictionary context from the vector DB to ground LLM outputs.

4) **Vector Database (embeddings)**  
   Stores embeddings of tables, columns, and descriptions; powers fast, relevant retrieval.

5) **Large Language Model (LLM)**  
   Generates SQL from the user prompt plus RAG context; also used for summarization and refinement.

6) **Query Validation & Routing**  
   Screens for security, cost, and syntax issues; routes valid queries to Lambda or to self-correction.

7) **Self-Correction Loop**  
   Uses rejection reasons + summarization to iteratively improve invalid queries.

8) **AWS Lambda (boto3)**  
   Executes validated queries against Athena; handles async execution and mediation.

9) **AWS Athena**  
   Runs SQL directly over S3 data; returns result sets upstream.

10) **Data Lake (Amazon S3)**  
    Source of truth storing raw/processed data (Parquet/CSV/JSON).

11) **AWS API Gateway & Final Answer**  
    Gateway secures/mediates responses; final answer is returned to the user via the chat UI.


## Pre-requisites

- Install python version >= 3.11
- Install uv package manager using the url - `https://docs.astral.sh/uv/getting-started/installation/`

## Following are the steps to run the script

- Clone the repository (`git clone https://source.corp.lookout.com/data/ai-data-lake-query.git`).
- Run the command to install the dependent packages and it creates a virtual environment -  `uv pip install -r requirements.txt`.
- Run the command to run application - `uv run app.py`, this command will generate http local url to acces the chat interface.
