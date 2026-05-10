ARCHIVED Python implementation of BunTool. For its more private, better-featured and actively maintained successor, go to https://github.com/TrisSherliker/buntool-website-git

# BunTool
<p align="center">
  <img src="static/buntool.webp" width="300" style="center">
</p>

Automatically make court bundles in seconds.  Check out the main instance: [buntool.co.uk](https://buntool.co.uk)

Takes input PDF files; generates index data; outputs a merged PDF with index, hyperlinks, bookmarks and page numbers according to your chosen settings.

Output Bundles comply with the requirements of the English Courts, and are also useful for a range of other applications. 

# Usage and installation

This is configured for self-hosting, which is what these isntructions are for.


```bash
# 1. Create the virtual environment (a hidden folder named .venv)
python3 -m venv .venv

# 2. Activate the virtual environment
source .venv/bin/activate

# 3. Install the required packages
pip install -r requirements.txt
```
## Copy fonts to fonts directory

Buntool uses the font Charter, a popular style of font for legal documents. The four `.ttf` files need to be added to ReportLab's fonts folder:

```bash
# This command copies the fonts into your virtual environment.
# The python* wildcard makes it work for any version of Python 3 
cp static/Charter*.ttf ./venv/lib/python*/site-packages/reportlab/fonts/
```

## Ready to bake

Now you can start the server:
```bash
python app.py
```
Then visit `http://127.0.0.1:7001` in your browser.

# Copyright and License

Copyright © Tristan Sherliker and contributors to BunTool

Licensed under the Mozilla Public License, version 2.0.
