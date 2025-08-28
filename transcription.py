import tkinter as tk
from tkinter import filedialog, scrolledtext
from PIL import Image, ImageTk
import io
import os
import time
from google.cloud import speech
from google.cloud import storage
from pydub import AudioSegment
from moviepy.editor import VideoFileClip
from tkinter import messagebox
import threading
from tkinter import font
def convert_video_to_audio(video_path, output_format="wav"):
    """Converts a video file to an audio file and returns the audio file path."""
    try:
        video = VideoFileClip(video_path)
        if not video.audio:
            messagebox.showerror("Error", f"No audio stream found in the video file.")
            return None
        
        audio_path = f"{os.path.splitext(video_path)[0]}.{output_format}"
        video.audio.write_audiofile(audio_path)
        video.close()  # Release resources
        return audio_path
    except Exception as e:
        messagebox.showerror("Error", f"Failed to transcribe audio: {str(e)}")
        return None

def convert_to_mono(input_file, output_file):
    """Converts a stereo audio file to mono."""
    audio = AudioSegment.from_wav(input_file)
    audio = audio.set_channels(1)
    audio.export(output_file, format="wav")

def get_audio_properties_gcs(gcs_uri):
    """Retrieves audio properties (sample rate, encoding) from a GCS URI."""
    storage_client = storage.Client()
    bucket_name = gcs_uri.split('/')[2]
    blob_name = '/'.join(gcs_uri.split('/')[3:])
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob_content = blob.download_as_bytes()
    audio = AudioSegment.from_file(io.BytesIO(blob_content))
    sample_rate = audio.frame_rate
    num_channels = audio.channels
    sample_width = audio.sample_width
    if sample_width == 1:
        encoding = speech.RecognitionConfig.AudioEncoding.LINEAR16 if num_channels == 1 else speech.RecognitionConfig.AudioEncoding.LINEAR16
    elif sample_width == 2:
        encoding = speech.RecognitionConfig.AudioEncoding.LINEAR16
    elif sample_width == 4:
        encoding = speech.RecognitionConfig.AudioEncoding.LINEAR32
    else:
        encoding = speech.RecognitionConfig.AudioEncoding.ENCODING_UNSPECIFIED
    return sample_rate, encoding

def transcribe_gcs(gcs_uri: str, language_code: str = "bn-BD"):
    """Asynchronously transcribes audio from a Google Cloud Storage URI."""
    client = speech.SpeechClient()
    try:
        sample_rate_hertz, encoding = get_audio_properties_gcs(gcs_uri)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to transcribe audio: {str(e)}")
        
        return
    try:
        audio = speech.RecognitionAudio(uri=gcs_uri)
        config = speech.RecognitionConfig(
            encoding=encoding,
            sample_rate_hertz=sample_rate_hertz,
            language_code=language_code,
        )
        operation = client.long_running_recognize(config=config, audio=audio)
        print("Waiting for operation to complete...")
        # Set the timeout to 60 minutes (3600 seconds)
        response = operation.result(timeout=3600)
        transcript = ''
        for result in response.results:
            alternative = result.alternatives[0]
            transcript += alternative.transcript
            # transcript += f"Confidence: {alternative.confidence}"
            # print(f"Transcript: {alternative.transcript}")
            # print(f"Confidence: {alternative.confidence}")
        return transcript
    except Exception as e:
        messagebox.showerror("Error", f"Failed to transcribe audio: {str(e)}")
        return 
def upload_blob(bucket_name, source_file_name, destination_blob_name):
    """Uploads a file to the bucket."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)
    blob.upload_from_filename(source_file_name)
    print(f"File {source_file_name} uploaded to {destination_blob_name}.")

def process(json_key_path, bucket_name, input_file, destination_blob_name):
    """Uploads audio, transcribes it, and cleans up."""
    
    def run_process():
        try:
            # Disable button and show "Processing..."
            upload_button.config(state=tk.DISABLED, text="Processing...")

            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = json_key_path
            output_file = f"{os.getcwd()}/{int(time.time())}_mono.wav"

            # Convert to mono
            convert_to_mono(input_file, output_file)

            # Upload file to GCS
            upload_blob(bucket_name, output_file, destination_blob_name)

            # Transcribe audio
            gcs_uri = f"gs://{bucket_name}/{destination_blob_name}"
            transcribe = transcribe_gcs(gcs_uri)

            # Delete the uploaded blob
            storage_client = storage.Client()
            bucket = storage_client.bucket(bucket_name)
            blob = bucket.blob(destination_blob_name)
            blob.delete()

            # Remove temporary file
            os.remove(output_file)
            print(f"Blob {destination_blob_name} deleted.")

            # Show transcription result in GUI
            result_text.delete("1.0", tk.END)
            result_text.insert(tk.END, transcribe)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to transcribe audio: {str(e)}")

        finally:
            # Re-enable the button after processing
            upload_button.config(state=tk.NORMAL, text="Upload & Transcribe")
    threading.Thread(target=run_process, daemon=True).start()
def process_file():
    # Placeholder for your upload and transcription logic
    # You'll integrate your existing transcription code here
    file_path = filedialog.askopenfilename(filetypes=[("Audio/Video Files", "*.wav;*.mp3;*.mp4")])
    if not file_path:
        return

    if file_path.endswith((".mp4", ".mkv", ".avi")):
        file_path = convert_video_to_audio(file_path)
        if not file_path:
            return
    if file_path:
        json_key_path = f"{os.getcwd()}/auth.json"
        print(json_key_path)
        bucket_name = "bdr-commission"
        input_file = file_path
        destination_blob_name = "temp_audio.wav"
        process(json_key_path, bucket_name, input_file, destination_blob_name)
        

def copy_text():
    # Placeholder for copying text to clipboard
    text_to_copy = result_text.get(1.0, tk.END)
    root.clipboard_clear()
    root.clipboard_append(text_to_copy)

# Main Window
root = tk.Tk()
root.title("Audio/Video Transcription App")
root.geometry("500x850")
# Load the image using Pillow
logo = Image.open(f"{os.getcwd()}/cover-bn.png")

# Resize the image (adjust the size as needed)
logo = logo.resize((500, 100))  # Resize to 500x100

# Convert the image to a Tkinter-compatible format
logo = ImageTk.PhotoImage(logo)

# Create a Label widget with the image and place it at the top center
logo_label = tk.Label(root, image=logo)
logo_label.place(relx=0.5, rely=0, anchor='n')  # Place the logo at the top center

# Right Side Content
content_frame = tk.Frame(root)
content_frame.pack(side=tk.RIGHT, padx=10, pady=105, fill=tk.BOTH, expand=True)

# Upload & Transcribe Button
upload_button = tk.Button(content_frame, text="Upload & Transcribe", command=process_file, bg="orange", fg="black", padx=20, pady=10)
upload_button.pack(pady=10)

bangla_font = ("SolaimanLipi", 14)  # Use an installed Bangla font  # You can change to "SolaimanLipi", "Vrinda", etc.
# Text Output Area (ScrolledText for scrolling)
result_text = scrolledtext.ScrolledText(content_frame, wrap=tk.WORD, font=bangla_font, width=10, height=5)  # Smaller height
result_text.pack(pady=0, fill=tk.BOTH, expand=True)

# Copy Text Button
copy_button = tk.Button(content_frame, text="Copy Text", command=copy_text, bg="green", fg="white", padx=10, pady=5)
copy_button.pack(pady=10)

root.mainloop()