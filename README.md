# ASL-Pipe

ASL recognition using Google's MediaPipe

Senior Project - Brian Sanchez and Eric Thompson

Things to note: We ran Python 3.10.16 on macOS and Python 3.9.13 on Windows. For macOS, there is no reason it shouldn't
work on more recent versions of Python, but we recommend versions 3.10-3.12, since those are the versions we tested
briefly. For Windows, Python 3.9 is required, as some packages do not function on newer versions. We got this to work
on two machines, but we have had a lot of issues with package version and mismatches. This is mostly due to tensorflow
and mediapipe model maker.

# Building

On macOS:

1. Install Python 3.10.16
2. Open a terminal in the project directory
3. Run `pip install -r requirements.txt`
4. Once everything is done installing, run the `main.py` file however you like (e.g., run `python main.py` in the terminal)
5. Wait for everything to initialize, it could take up to a minute for some users. In our testing it sometimes took long and sometimes was quick
6. Start finger spelling

On Windows:

1. Install Python 3.9.13
2. Run `setup.bat`
3. Once everything is done installing, run the `main.py` file however you like (e.g., run `py main.py` in command prompt)
4. Wait for everything to initialize, it could take up to a minute for some users. In our testing it sometimes took long and sometimes was quick
5. Start finger spelling
