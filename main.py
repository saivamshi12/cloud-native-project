import os
import json
from flask import Flask, redirect, request, render_template
from google.cloud import storage, secretmanager
import google.generativeai as genai
import re
from io import BytesIO

app = Flask(__name__)

# Bucket setup
bucket_name = 'cnd_bucket'
storage_client = storage.Client()
bucket = storage_client.bucket(bucket_name)

# Create local dir (if needed)
os.makedirs('files', exist_ok=True)

def get_gemini_api_key():
    client = secretmanager.SecretManagerServiceClient()
    secret_name = f"projects/846599288582/secrets/GEMINI_API_KEY/versions/latest"
    response = client.access_secret_version(name=secret_name)
    return response.payload.data.decode("UTF-8")

# Configure Gemini
# genai.configure(api_key=get_gemini_api_key())
print(get_gemini_api_key())
import json
import re


def generate_caption_description(image_bytes):
    api_key = get_gemini_api_key()
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    image_blob = {"mime_type": "image/jpeg", "data": image_bytes}

    prompt = (
        "Analyze the image and generate a clear title and description.\n\n"
        "Strictly respond in this JSON format:\n"
        "{\n"
        '  "title": "A short, engaging title",\n'
        '  "description": "2-3 sentences describing the image"\n'
        "}\n"
        "No extra text, no markdown, no formatting."
    )

    response = model.generate_content([image_blob, prompt])

    if response and hasattr(response, 'text'):
        response_text = response.text.strip()

        # Remove triple backticks if present
        response_text = re.sub(r"^```json\n|\n```$", "", response_text)

        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            print("Error parsing JSON:", response_text)  # Debugging
            return {"title": "No title generated", "description": "No description generated"}
    
    return {"title": "No title generated", "description": "No description generated"}


def upload_blob(file_obj, blob_name):
    blob = bucket.blob(blob_name)
    blob.upload_from_file(file_obj)

def upload_json(data, blob_name):
    blob = bucket.blob(blob_name)
    blob.upload_from_string(json.dumps(data, indent=4), content_type='application/json')

def list_images():
    blobs = bucket.list_blobs()
    files = []
    for blob in blobs:
        if blob.name.lower().endswith(('.jpg', '.jpeg', '.png')):
            json_blob = f"{os.path.splitext(blob.name)[0]}.json"
            try:
                caption_blob = bucket.blob(json_blob)
                caption = json.loads(caption_blob.download_as_string())
            except:
                caption = {"title": "N/A", "description": "N/A"}

            files.append({
                "name": blob.name,
                "title": caption.get("title", "N/A"),
                "description": caption.get("description", "N/A")
            })
    return sorted(files, key=lambda x: x['name'], reverse=True)

@app.route('/')
def index():
    return render_template('index.html', files=list_images())

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files['form_file']
    filename = file.filename
    image_bytes = file.read()

    # Generate title/desc
    caption_data = generate_caption_description(image_bytes)

    # Upload image
    file.seek(0)
    upload_blob(file, filename)

    # Upload JSON
    json_filename = f"{os.path.splitext(filename)[0]}.json"
    upload_json(caption_data, json_filename)

    return redirect('/')

@app.route('/files/<filename>')
def get_file(filename):
    blob = bucket.blob(filename)
    file_stream = BytesIO()
    blob.download_to_file(file_stream)
    file_stream.seek(0)

    return app.response_class(file_stream.read(), mimetype='image/jpeg')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)