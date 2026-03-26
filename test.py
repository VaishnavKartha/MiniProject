from sarvamai import SarvamAI
import base64
client = SarvamAI(
    api_subscription_key="sk_092rcpnr_8R9SRob6txoUGJXvwnmbZ2kE"
)

# Select a specific speaker
response = client.text_to_speech.convert(
    text="Hello, how are you today?",
    target_language_code="en-IN",
    model="bulbul:v3",
    speaker="priya"  # Options: aditya, ritu, priya, neha, rahul, pooja, rohan, simran, kavya, amit, dev, ishita, shreya, ratan, varun, manan, sumit, roopa, kabir, aayan, shubh, ashutosh, advait, amelia, sophia, anand, tanya, tarun, sunny, mani, gokul, vijay, shruti, suhani, mohit, kavitha, rehan, soham, rupali
)

audio_bytes = base64.b64decode(response.audios[0])
with open("output.wav", "wb") as f:
    f.write(audio_bytes)

print("Saved to output.wav")