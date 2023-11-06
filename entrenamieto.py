
from llama_index import SimpleDirectoryReader, GPTVectorStoreIndex, LLMPredictor, ServiceContext
from llama_index import StorageContext, load_index_from_storage
from langchain import OpenAI
import os
import openai


os.environ['OPENAI_API_KEY'] = 'aqui colocar el token de openai'
openai.api_key = "aqui colocar el token de openai"

def construct_index(directory_path):

    num_outputs = 512
    llm_predictor = LLMPredictor(llm=OpenAI(temperature=0.7, model_name="text-davinci-003", max_tokens=num_outputs))
    service_context = ServiceContext.from_defaults(llm_predictor=llm_predictor)
    
    docs = SimpleDirectoryReader(directory_path).load_data()

    index = GPTVectorStoreIndex.from_documents(docs, service_context = service_context )

    index.storage_context.persist(persist_dir="uteq_data")

    return index


index = construct_index("docs")
