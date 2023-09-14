import argparse
import io
import os
import speech_recognition as sr
import whisper
import torch
import re
from time import sleep
from pythonosc import udp_client
from tkinter.messagebox import showinfo
from gensim.models import KeyedVectors
from datetime import datetime, timedelta
from queue import Queue
from tempfile import NamedTemporaryFile
from time import sleep
from sys import platform

#Configuration
corpus_model = KeyedVectors.load('Models\Fullcorpus.bin')
IP = '10.12.181.191'
PORT1 = 7002    # 5 words to send
PORT2 = 8002    #Size of 5 worlds according to the correlation number
PORT3 = 9002    #list of the selected words by user

#Parser argument for whisper
parserWhisper = argparse.ArgumentParser()
parserWhisper.add_argument("--model", default="base", help="Model to use",
                        choices=["tiny", "base", "small", "medium", "large"])
parserWhisper.add_argument("--non_english", action='store_true',
                        help="Don't use the english model.")
parserWhisper.add_argument("--energy_threshold", default=1000,
                        help="Energy level for mic to detect.", type=int)
parserWhisper.add_argument("--record_timeout", default=1,
                        help="How real time the recording is in seconds.", type=float)
parserWhisper.add_argument("--phrase_timeout", default=0.1,
                        help="How much empty space between recordings before we "
                             "consider it a new line in the transcription.", type=float)  
argsWhisper = parserWhisper.parse_args()

#Parser argument for OSC with th 5 words
parserOSCwords = argparse.ArgumentParser()
parserOSCwords.add_argument("--ip", default=IP, help="The ip of the OSC server")
parserOSCwords.add_argument("--port", type=str, default=PORT1, help="The port the OSC server is listening ON")
argsOSCwords = parserOSCwords.parse_args()

#Parser argument for OSC with the size of the 5 words
parserOSCsize = argparse.ArgumentParser()
parserOSCsize.add_argument("--ip", default=IP, help="The ip of the OSC server")
parserOSCsize.add_argument("--port", type=str, default=PORT2, help="The port the OSC server is listening ON")
argsOSCsize = parserOSCsize.parse_args()

#Parser argument for OSC with selected words by user
parserOSCselectwords = argparse.ArgumentParser()
parserOSCselectwords.add_argument("--ip", default=IP, help="The ip of the OSC server")
parserOSCselectwords.add_argument("--port", type=str, default=PORT3, help="The port the OSC server is listening ON")
argsOSCselectwords = parserOSCselectwords.parse_args()

data_queue = Queue()
last_sample = bytes()
phrase_time = None
recorder = sr.Recognizer()
recorder.energy_threshold = argsWhisper.energy_threshold
recorder.dynamic_energy_threshold =False
source = sr.Microphone(sample_rate=16000)

#Load model
model = argsWhisper.model
if argsWhisper.model != "large" and not argsWhisper.non_english:
    model = model + ".en"
audio_model = whisper.load_model(model)
record_timeout = argsWhisper.record_timeout
phrase_timeout = argsWhisper.phrase_timeout
temp_file = NamedTemporaryFile().name
transcription = ['']
selectedlist = []

with source:
    recorder.adjust_for_ambient_noise(source)

def record_callback(_, audio:sr.AudioData) -> None:
        """
        Threaded callback function to recieve audio data when recordings finish.
        audio: An AudioData containing the recorded bytes.
        """
        # Grab the raw bytes and push it into the thread safe queue.
        data = audio.get_raw_data()
        data_queue.put(data)

    # Create a background thread that will pass us raw audio bytes.
    # We could do this manually but SpeechRecognizer provides a nice helper.
recorder.listen_in_background(source, record_callback, phrase_time_limit=record_timeout)

    # Cue the user that we're ready to go.
print("Model loaded.\n")

def osc_words(words,numbers):
    client = udp_client.SimpleUDPClient(argsOSCwords.ip,argsOSCwords.port)
    client.send_message("/word1",words[0])
    client.send_message("/word2",words[1])
    client.send_message("/word3",words[2])
    client.send_message("/word4",words[3])
    client.send_message("/word5",words[4])

    client = udp_client.SimpleUDPClient(argsOSCsize.ip, argsOSCsize.port)
    client.send_message("/size0", numbers[0])
    client.send_message("/size1", numbers[1])
    client.send_message("/size2", numbers[2])
    client.send_message("/size3", numbers[3])
    client.send_message("/size4", numbers[4])

def osc_selected(word):
    client = udp_client.SimpleUDPClient(argsOSCselectwords.ip, argsOSCselectwords.port)
    client.send_message("/word1", word)

def test_w2v(emotion,n):
    math_result = corpus_model.most_similar(positive=emotion,topn=n)
    w_vals = [v[0] for v in math_result]
    n_vals = [v[1] for v in math_result]
    return w_vals, n_vals

def repeated(words,lista):
    for i in range(2):
        try: 
            indx = lista.index(words[i])
            print(indx)
            lista[indx] = newwords[2]
        except ValueError:
            print("Ok")

emotion = input('Enter the emotion: ')
print(emotion + ' is the selected emotion.')

[words, numbers] = test_w2v(emotion,5)

print(words)
print(numbers)

osc_words(words,numbers)

while True:
        try:
            now = datetime.utcnow()
            # Pull raw recorded audio from the queue.
            if not data_queue.empty():
                phrase_complete = False
                # If enough time has passed between recordings, consider the phrase complete.
                # Clear the current working audio buffer to start over with the new data.
                if phrase_time and now - phrase_time > timedelta(seconds=phrase_timeout):
                    last_sample = bytes()
                    phrase_complete = True
                # This is the last time we received new audio data from the queue.
                phrase_time = now

                # Concatenate our current audio data with the latest audio data.
                while not data_queue.empty():
                    data = data_queue.get()
                    last_sample += data

                # Use AudioData to convert the raw data to wav data.
                audio_data = sr.AudioData(last_sample, source.SAMPLE_RATE, source.SAMPLE_WIDTH)
                wav_data = io.BytesIO(audio_data.get_wav_data())

                # Write wav data to the temporary file as bytes.
                with open(temp_file, 'w+b') as f:
                    f.write(wav_data.read())

                # Read the transcription.
                result = audio_model.transcribe(temp_file, fp16=torch.cuda.is_available())
                text = result['text'].strip()
                
                text = re.sub(r'[^\w\s]','',text)
                text=text.lower()
            
                try:
                    id=words.index(text)
                    try:
                         [newwords,newnumbers]=test_w2v(text,3)
                         repeated(newwords,words)
                         if id == 4:
                            idplus = id-1
                         else:
                            idplus = 4
                            
                         words[id] = newwords[0]
                         numbers[id] = newnumbers[0]
                         words[idplus] = newwords[1]
                         numbers[idplus] = newnumbers[1]
                         osc_words(words,numbers)
                         osc_selected(text)
                         selectedlist.append(text)
                         
                    except KeyError:
                        print(text + 'is not present in vocabulary')
                    
                except ValueError:
                    print(text + ' is not in the list')
                  
                # If we detected a pause between recordings, add a new item to our transcripion.
                # Otherwise edit the existing one.
                if phrase_complete:
                    transcription.append(text)
                else:
                    transcription[-1] = text

                # Clear the console to reprint the updated transcription.
                #os.system('cls' if os.name=='nt' else 'clear')
                #for line in transcription:
                #    print(line)
                # Flush stdout.
                #print('', end='', flush=True)

                # Infinite loops are bad for processors, must sleep.
                sleep(0.5)
        except KeyboardInterrupt:
            break

print("\n\nTranscription:")
for line in transcription:
    print(line)

print("\n\nSelected words:")
print(selectedlist)

