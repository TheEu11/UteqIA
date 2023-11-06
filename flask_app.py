import os
import io
import requests
from flask import Flask, jsonify, request
from flask import make_response, flash, url_for
from llama_index import SimpleDirectoryReader, GPTVectorStoreIndex, LLMPredictor, Document, ServiceContext, StorageContext, load_index_from_storage
from flask_cors import CORS
import openai
from langchain import OpenAI

import pydub
import requests
import soundfile as sf
import speech_recognition as sr

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = './webapi/uploads'
ALLOWED_EXTENSIONS = {'mp3','mp4','mpeg','mpga','m4a','wav','webm'}
app.config['MAX_CONTENT_LENGTH'] = 1 * 1000 * 1000

index_name = "./web/saved_index"

openai.api_key = "aqui colocar el token de open ai"
os.environ['OPENAI_API_KEY'] = "aqui colocar el token de open ai"

whatsapp_token = "aqui colocar el token de whatsapp"

@app.route("/")
def home():
    return "Hello, World 2"

@app.route("/webhook", methods=["POST", "GET"])
def webhook():
    if request.method == "GET":
        return verify(request)
    elif request.method == "POST":
        if not validate_request_format(request):
              return jsonify({"status": "error", "message": "Error Estructura Respuesta Whatsapp API"}), 500

        body = request.get_json()
        whatsapp_message(body)
        return "POST"


def verify(request):
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode and token:
        if mode == "subscribe" and token == "UTEQ":
            app.logger.info('%s logged in successfully', challenge)
            return challenge, 200
        else:
            app.logger.info('Verification failed')
            return jsonify({"status": "error", "message": "Verification failed"}), 403
    else:
        app.logger.info('Missing parameters')
        return jsonify({"status": "error", "message": "Missing parameters"}), 400


def validate_request_format(request):
    body = request.get_json()
    try:
        if body.get("object"):
            if (body.get("entry")
                and body["entry"][0].get("changes")
                and body["entry"][0]["changes"][0].get("value")
                and body["entry"][0]["changes"][0]["value"].get("messages")
                and body["entry"][0]["changes"][0]["value"]["messages"][0]):
                return True
            else:
                return False
        else:
            return False

    except Exception:
       return False

def whatsapp_message(body):
    message_body=""
    message = body["entry"][0]["changes"][0]["value"]["messages"][0]
    if message["type"] == "text":
        message_body = message["text"]["body"]
    elif message["type"] == "audio":
        audio_id = message["audio"]["id"]
        message_body =  convierte_audio_to_text(audio_id)

    response = ask_model(message_body)
    send_whatsapp_message(body, response)

def ask_model(question):
    if os.path.exists(index_name):
        llm_predictor = LLMPredictor(llm=OpenAI(temperature=0.7, model_name="gpt-3.5-turbo", max_tokens=1012))
        service_context = ServiceContext.from_defaults(llm_predictor=llm_predictor)
        index = load_index_from_storage(StorageContext.from_defaults(persist_dir=index_name), service_context=service_context)
        response = index.as_query_engine().query(question)
        return str(response)
    else:
        return ""

def send_whatsapp_message(body, message):
    value = body["entry"][0]["changes"][0]["value"]
    phone_number_id = value["metadata"]["phone_number_id"]
    from_number = value["messages"][0]["from"]
    headers = {
        "Authorization": f"Bearer {whatsapp_token}",
        "Content-Type": "application/json",
    }
    url = "https://graph.facebook.com/v17.0/" + phone_number_id + "/messages"
    data = {
        "messaging_product": "whatsapp",
        "to": from_number,
        "type": "text",
        "text": {"body": message},
    }
    response = requests.post(url, json=data, headers=headers)
    response.raise_for_status()

def do_ask(question):
    response = ask_model(question)
    if not response == "":
        response_json= {
        	"pregunta": question,
        	"respuesta": response
	    }
        return make_response(jsonify(response_json)), 200
    else:
        return make_response("No Hay índices", 400)

@app.route("/query", methods=["GET"])
def query_index():
    query_text = request.args.get("pregunta", None)
    if query_text is None:
        return "No hay pregunta", 400
    return do_ask(query_text)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/queryaudio', methods=['POST'])
def query_audio():
    if 'file' not in request.files:
        return "No hay fichero", 400
    file = request.files['file']
    if file.filename == '':
        return "No hay fichero", 400
    if not allowed_file(file.filename):
        return "Extensión NO Válida " + file.filename, 400

    audio_file = io.BytesIO(file.read())
    audio_file.name=file.filename
    transcript = openai.Audio.transcribe(model="whisper-1", file=audio_file, language="es")
    if transcript['text'] is None:
        return "No hay texto en la tradución", 400
    else:
        return do_ask(transcript['text'])

def get_media_url(media_id):
    headers = {"Authorization": f"Bearer {whatsapp_token}",}
    url = f"https://graph.facebook.com/v17.0/{media_id}/"
    response = requests.get(url, headers=headers)
    return response.json()["url"]


def download_media_file(media_url):
    headers = {"Authorization": f"Bearer {whatsapp_token}",}
    response = requests.get(media_url, headers=headers)
    return response.content


def convert_audio_bytes(audio_bytes):
    ogg_audio = pydub.AudioSegment.from_ogg(io.BytesIO(audio_bytes))
    ogg_audio = ogg_audio.set_sample_width(4)
    wav_bytes = ogg_audio.export(format="wav").read()
    audio_data, sample_rate = sf.read(io.BytesIO(wav_bytes), dtype="int32")
    sample_width = audio_data.dtype.itemsize
    audio = sr.AudioData(audio_data, sample_rate, sample_width)
    return audio


def recognize_audio(audio_bytes):
    recognizer = sr.Recognizer()
    audio_text = recognizer.recognize_google(audio_bytes, language="es-EC")
    return audio_text


def convierte_audio_to_text(audio_id):
    audio_url = get_media_url(audio_id)
    audio_bytes = download_media_file(audio_url)
    audio_data = convert_audio_bytes(audio_bytes)
    return recognize_audio(audio_data)


key = "6090975472:AAGEOgbN5jCiHuCPIpS53Rn_tfHgw61Vm8E"
api_telegram_url = f'https://api.telegram.org/bot{key}/'

def sendmessage_telegram(chatid, msgtext):
    payload = {
        "text": msgtext,
        "chat_id":chatid
        }
    resp = requests.get(api_telegram_url + "sendMessage",params=payload)

def convierte_audio_to_text_telegram(audio_id):
    url = api_telegram_url + f"getFile?file_id={audio_id}"
    telegram_filepath =  requests.get(url).json()['result']['file_path']
    audio_url =f'https://api.telegram.org/file/bot{key}/{telegram_filepath}'
    response = requests.get(audio_url)
    if response.headers.get('content-type') == 'application/json':
        respJson=response.json()
        app.logger.info('Error Code %s Descripcion %s',respJson['error_code'],respJson['description'])
        return ""
    else:
        audio_bytes = response.content
        audio_data = convert_audio_bytes(audio_bytes)
        return recognize_audio(audio_data)


@app.route("/webhook_telegram",methods=["POST","GET"])
def webhook_telegram():
    if(request.method == "POST"):
        resp = request.get_json()
        app.logger.info('%s response',resp)
        sendername = resp["message"]["from"]["first_name"] + " " + resp["message"]["from"]["last_name"]
        chatid = resp["message"]["chat"]["id"]
        msgtext=""

        if 'entities' in resp["message"]:
            comando = resp["message"]["text"]
            if comando == '/start':
                mensaje=f'Bienvenido {sendername} al chatbot de la UTEQ.'
                mensaje=mensaje+'He sido entrenado para contestar las preguntas más frecuentes sobre trámites académicos e información institucional de la Universidad Técnica Estatal de Quevedo UTEQ'
                sendmessage_telegram(chatid,mensaje)
                send_photo(chatid, open('web/botuteq.jpeg', 'rb'))
            else:
                sendmessage_telegram(chatid,'No reconozco el comando')
        else:
            if 'voice' in resp["message"]:
                msgtext = convierte_audio_to_text_telegram(resp['message']['voice']['file_id'])
            else:
                msgtext = resp["message"]["text"]

            if msgtext!="":
                respuesta = ask_model(msgtext)
                sendmessage_telegram(chatid, respuesta)
            else:
                 sendmessage_telegram(chatid, "Error al procesar Mensaje")

        #send_photo(chatid, open('web/logoUTEQ.png', 'rb'))
    return "Done"

@app.route("/setwebhook_telegram/")
def setwebhook_Telegram():
    url = "https://uteqia.pythonanywhere.com/webhook_telegram"
    s = requests.get(api_telegram_url + f"setWebhook?url={url}")
    if s:
        return "yes"
    else:
        return "fail"

def send_photo(chat_id, file_opened):
    method = ""
    params = {'chat_id': chat_id}
    files = {'photo': file_opened}
    resp = requests.post(api_telegram_url + 'sendPhoto', params, files=files)
    return resp



if __name__ == "__main__":
    #initialize_index("data")
    app.run(host="0.0.0.0", port=5601)

