Python version 3.11 required

create a virtual environment and install the below dependencies in the virtual environment

Dependencies needed :
  pip install fastapi uvicorn python-multipart
  pip install torch
  pip install transformers==4.40.2 sentencepiece accelerate
  pip install openai-whisper
  pip install indic-nlp-library
  
Install ffmpeg <!--visit their website -->
Generate HF_TOKEN by loggin into hugging face -> Settings -> Access Tokens 
After generting the tokens run this command in the terminal:
  huggingface-cli login <!-- This will prompt you to enter your Token generated -->

The model used is a bit heavy (4.5 GB ) and hence may take some time when you first run the application
