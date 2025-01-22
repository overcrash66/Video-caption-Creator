# Video caption Creator

Video caption Creator is a Python program that uses an audio and an SRT file to generate a videos with captions.

### Captivating captions

`Video caption Creator` supports SRT file with embed html style to be able to create "captivating" captions,
 which means that you can produce captions that highlight

Overall the following options are available when it comes to styling the captions:

- Choose the caption font size
- Choose the caption font color
- Choose the caption font family

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

### GUI usage

You can run the GUI with `python main.py`.

![Demo](image/App.png)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.