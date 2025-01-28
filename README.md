# buntool

Automatically make court bundles in seconds.

[buntool.co.uk](https://buntool.co.uk)

# Usage

Tested only on Ubuntu, and suitable for AWS Lambda deployment via Zappa. To self-host:

```
python3 -m venv venv
. venv/bin/activate
pip install -r requirements.txt
apt install -y pdflatex pdftk-java
python3 app.py
```

Then visit 0.0.0.0:7001 in your browser.

# Licences

MIT.

BunTool uses third-party software including: 
- pyPDF: https://github.com/py-pdf/pypdf/blob/main/LICENSE (MIT)
- pike PDF:https://github.com/pikepdf/pikepdf/blob/main/LICENSE.txt (Mozilla v.2.0)
- pdfLaTeX: https://ctan.org/pkg/pdftex (actually not used, but stubs of code remain)
- pdfplumber: https://github.com/jsvine/pdfplumber/blob/stable/LICENSE.txt
- python-docx: https://github.com/python-openxml/python-docx/blob/master/LICENSE
