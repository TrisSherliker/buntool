# BunTool
<p align="center">
  <img src="static/buntool.webp" width="300" style="center">
</p>  

Automatically make court bundles in seconds.  Check out the main instance: [buntool.co.uk](https://buntool.co.uk)

Takes input PDF files; generates index data; outputs a merged PDF with index, hyperlinks, bookmarks and page numbers according to your chosen settings.

Output Bundles comply with the requirements of the English Courts, and are also useful for a range of other applications. 


# Usage and installation

This is configured for self-hosting, which is what these isntructions are for.

It can also be deployed to an AWS Lambda with zappa, if desired.

## Installation

```
python3 -m venv venv
. venv/bin/activate
pip install -r requirements.txt
apt install -y pdflatex pdftk-java
python3 app.py
```

## Copy fonts to fonts directory

Buntool uses the font Charter, a popular style of font for legal documents. The four `.ttf` files need to be added to ReportLab's fonts folder:

```
cp ./static/Charter*.ttf ./venv/lib/python3.12/site-packages/reportlab/fonts/
```

## Ready to bake

Now you can visit `0.0.0.0:7001` in your browser.

# License

Licensed under the Mozilla Public License, version 2.0.