# buntool

Automatically make court bundles in seconds.

[buntool.sherliker.net](https://buntool.sherliker.net)

# Usage

Tested only on Ubuntu. To self-host:

```
python3 -m venv venv
. venv/bin/activate
pip install -r requirements.txt
apt install -y pdflatex pdftk-java
python3 app.py
```

Then visit 0.0.0.0:7001 in your browser.

# Licences

This is currently licensed under the same licence as pdfTK server, which is a GPL licence:  GNU General Public License Version 2
Since my preference is towards more permissive licensing, I am working on removing pdfTK as a dependency. 

BunTool uses third-party software including: 
- pyPDF: https://github.com/py-pdf/pypdf/blob/main/LICENSE (MIT)
- pike PDF:https://github.com/pikepdf/pikepdf/blob/main/LICENSE.txt (Mozilla v.2.0)
- pdfLaTeX: https://ctan.org/pkg/pdftex
- pdfplumber: https://github.com/jsvine/pdfplumber/blob/stable/LICENSE.txt
- (in development) python-docx: https://github.com/python-openxml/python-docx/blob/master/LICENSE
