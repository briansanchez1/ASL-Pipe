# ASL-Pipe
ASL recognition using Google's MediaPipe

Senior Project - Brian Sanchez and Eric Thompson

Things to note: We ran python 3.10.16. We got this to work on two machines, but we have had a lot of issues with package version and mismatches. This is mostly to due with tensorflow and mediapipe (model maker). For that, we omitted mediapipe mm, since there is no use for it when running the actual program. There is no reason it shouldn't work on more recent version of python, but we recommend versions 3.10-3.12, since those are the versions we tested briefly.

1. Open a terminal
2. Run "pip install -r requirements.txt" 
3. Once everything is done installing, run the main.py file however you like (python main.py)
4. Wait for everything to initialize, it could take up to a minute for some users. In our testing it sometimes took long and sometimes was quick
5. Starting finger spelling
