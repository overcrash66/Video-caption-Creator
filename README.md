# Video caption Creator

Video caption Creator: is a Python program that uses an SRT file to generate a videos with captions.
It support generating speech / audio from SRT files
It also support merging and sync video with audio 

### Captivating captions

`Video caption Creator` supports SRT file with embed html style to be able to create "captivating" captions,
 which means that you can produce captions that highlight

Overall the following options are available when it comes to styling the captions:

- Choose the caption font; custom font, style, size, color ..

[![VcC](https://img.youtube.com/vi/rjFq3P9vhHs/0.jpg)](https://www.youtube.com/watch?v=rjFq3P9vhHs)

### Installation

* Clone or download this repository

* Install Python version >= 3.10

* Install `ffmpeg` [for your platform](https://ffmpeg.org/download.html)

* Create a vitrual env:

```
py -3.10 -m venv venv
```

```
venv\Scripts\activate
```

* Install Python dependencies: `pip install -r requirements.txt`

If you like to use torch with cuda:

```
pip uninstall torch torchaudio
pip install torch==2.5.1+cu118 torchaudio==2.5.1+cu118 --index-url https://download.pytorch.org/whl/cu118
```

### GUI usage

You can run the GUI with `python main.py`.

![flowchart](image/flowchart.png)
![Demo](image/App.png)

## Unit Tests

Install tesseract

```
https://github.com/UB-Mannheim/tesseract/wiki
```

Install unit tests requirements

```
pip install test-requirements.txt
```

Run tests

```
python run-tests.py
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.