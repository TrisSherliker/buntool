#TODO 
##############################################
##  BUGS
##############################################
#- [duplicate logs - session file handler not clearing]

##############################################
##  Possible Technical improvements
##############################################
# - [ ] break up big functions into smaller chunks with isolated responsibilities. candidates: 
#       - count-pages, 
#       - compile LaTeX,
#       - stamping page numbers,
#       - adding annotations
# - [ ] check: sanitsation of filenames problems with multiple . in names. Is the code depending too much on there being an extension to the file?
# - [ ] Add a write metadata function: https://pypdf.readthedocs.io/en/stable/user/metadata.html
# - [ ] Use pdflatex via python not just system calls: https://pypi.org/project/pdflatex/
# - [ ] Debloat. e.g. is it possible to stick to one library rather than mixking between pypdf, pikepdf and pypdftk


##############################################
## Possible feature expansions User and QOL features
##############################################
# - [ ] Make the zip contents more useful files in zip - e.g. the text of index? word format of index?
# - [ ] Save and reload state (take advantage of the zip). 
#       This would require --
#       - [ ] save option state (as json?)
#       - [ ] save csv
#       - [ ] save input files
#       - [ ] allow upload of zip which is then parsed out into options/csv/inputfiles
#       - [ ] the data structure point above will help with this, because then it just becomes a matter of setting variables from the lines of the file.
#   - [ ] Drop down box with pre-filled bundle names, or type your own in.


#import ALL THE PDF LIBRARIES, sigh
import pypdftk
from pypdf import PdfReader, PdfWriter
from pypdf.annotations import Link
from pypdf.generic import Fit
from pikepdf import Pdf, OutlineItem, Dictionary, Name, PdfError
import pdfplumber

import os
import re
import argparse
from werkzeug.utils import secure_filename
import shutil
import subprocess
import csv
import logging
import zipfile
from datetime import datetime


bundle_logger = logging.getLogger('bundle_logger')
session_file_handler = None

def configure_logger(session_id=None, temp_dir="temp"):
    logs_dir = os.path.join("logs")
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    # Configure logging
    global session_file_handler
    global bundle_logger
    bundle_logger = logging.getLogger('bundle_logger')
    bundle_logger.setLevel(logging.DEBUG)
    bundle_logger.propagate = False
    formatter = logging.Formatter('%(asctime)s-%(levelname)s-[BUN]: %(message)s')
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    bundle_logger.addHandler(console_handler)
    if session_id:
        #logs path = buntool_timestamp.log:
        logs_path = os.path.join(logs_dir, f"buntool_{session_id}.log")
        session_file_handler = logging.FileHandler(logs_path)
        session_file_handler.setLevel(logging.DEBUG)
        session_file_handler.setFormatter(formatter)
        bundle_logger.addHandler(session_file_handler)
    return bundle_logger


def remove_session_file_handler():
    global session_file_handler
    if session_file_handler:
        bundle_logger.removeHandler(session_file_handler)
        session_file_handler = None

def sanitise_latex(text):
    replacements = {
        u'_':  u'\\_',
        u'$':  u'\\$',
        u'%':  u'\\%',
        u'#':  u'\\#',
        u'{':  u'\\{',
        u'&':  u'\\&',
        u'}':  u'\\}',
        u'[':  u'{[}',
        u']':  u'{]}',
        u'"':  u"{''}",
        u"|": u'\\textbar{}',
        u'\\': u'\\textbackslash{}',
        u'~':  u'\\textasciitilde{}',
        u'<':  u'\\textless{}',
        u'>':  u'\\textgreater{}',
        u'^':  u'\\textasciicircum{}',
        u'`':  u'{}`',
        u'\n': u'\\\\',
    }

    # Remove emojis and other non-ASCII characters  (ascii list from space  0x20 onwards)
    text = re.sub(r'[^\x20-\x7F]+', '', text)

    #replace awkward ascii characters with LaTeX commands:
    sanitised_text = u''.join(replacements.get(c, c) for c in text)
    bundle_logger.debug(f"[SL].... Sanitised input '{text}' for LaTeX output '{sanitised_text}'")
    return sanitised_text
    
    return text

def load_index_data(csv_index):
    #CSV format: filename, userdefined_title, date, section
    #   for files: [filename, title, date, 0]
    #   for sections: [SECTION, section_name,,1]
    
    index_data = {}
    bundle_logger.debug(f"[LID]Loading index data from {csv_index}")
    with open(csv_index, 'r', newline='') as f:
        reader = csv.reader(f)
        next(reader)  # Skip header row
        nil="0"
        for row in reader:
            if len(row) >= 4:
                filename, userdefined_title, date, section = row
                # Store filename as provided by frontend
                index_data[filename] = (userdefined_title, date, section)
            elif len(row) == 3:
                filename, userdefined_title, date = row
                index_data[filename] = (userdefined_title, date, '')
            else:
                filename, userdefined_title = row
                bundle_logger.debug(f"Reading file entry: |{filename}|")
                index_data[filename] = (userdefined_title, '', '')
    bundle_logger.debug(f"[LID]..Loaded index data with {len(index_data)} entries:")
    for k, v in index_data.items():
        bundle_logger.debug(f"[LID]....Key: |{k}| -> Value: {v}")
    return index_data

def get_pdf_creation_date(file):
    try:
        with Pdf.open(file) as pdf:
            creation_date = pdf.docinfo.get('/CreationDate', None)
            if creation_date:
                # Convert to string if it's a pikepdf.String object
                creation_date_str = str(creation_date)
                # Extract date in the format D:YYYYMMDDHHmmSS
                date_str = creation_date_str[2:10]
                date_obj = datetime.strptime(date_str, '%Y%m%d')
                return date_obj.strftime('%d.%m.%Y')
    except Exception as e:
        bundle_logger.error(f"[GPCD]Error extracting creation date from {file}: {e}")
        creation_date = None
        return None

def merge_pdfs_create_toc_entries(input_files, output_file, index_data):
    pdf = Pdf.new()
    page_count = 0
    toc_entries = []
    tab_count = 1
    section_count = 1
    # Iterate through the lines of index data
    for filename, (title, date, section) in index_data.items():
        if section == "1":
            # Sections are easy
            toc_entries.append((f"SECTION_BREAK_{section_count}", title))
            section_count += 1
        else:
            try:
                # Files are more complex. They require:
                # - Set tab number:
                tab_number = f"{tab_count:03}."
                tab_count += 1
                try:
                    # - Count pages:
                    # Filename just has the base name, but input_files has the full path. Use the full path:
                    this_file_path = None
                    for input_file_path in input_files:
                        if os.path.basename(filename) in input_file_path:
                            if not os.path.exists(input_file_path):
                                bundle_logger.debug(f"[MPCTE]..Error: File {filename} not found at {input_file_path}")
                                break
                            else:
                                bundle_logger.debug(f"[MPCTE]..File {filename} found at {input_file_path}")
                                this_file_path = input_file_path
                            break
                    if not this_file_path:
                        bundle_logger.debug(f"[MPCTE]File {filename} not found in input_files.")
                        continue
                    src = Pdf.open(this_file_path)
                    page_count += len(src.pages)
                    pdf.pages.extend(src.pages)
                    bundle_logger.debug(f"[MPCTE]....added to merged PDF")
                except Exception as e:
                    bundle_logger.debug(f"Error counting pages in {os.path.basename(this_file_path)}: {e}")
                    continue
                # - Add to outline:
                if index_data and os.path.basename(filename) in index_data:
                    bundle_logger.debug(f"[MPCTE]..found index data")
                    title, date, section = index_data[os.path.basename(filename)]
                else:
                    title = os.path.splitext(os.path.basename(filename))[0]
                    date = get_pdf_creation_date(filename)
                    section = None  
                    date = date or "Unknown"
                    bundle_logger.debug(f"[MPCTE]..Not in index. Using alternative data: Title: {title}, Date: {date}")
                bundle_logger.debug(f"[MPCTE]..Adding toc entry: {tab_number}, {title}, {page_count - len(src.pages)}")
                toc_entries.append((tab_number, title, date, page_count-len(src.pages)))
            except Exception as e:
                bundle_logger.debug(f"[MPCTE] Error merging and creating toc entries for {filename}: {e}")
                raise e
                continue
    pdf.save(output_file)
    return toc_entries

def add_bookmarks_to_pdf(pdf_file, output_file, toc_entries, length_of_frontmatter):
    #take the toc_entries and make an outline item for each one, appending it to the bookmarks. Note that the frontmatter will have been added in the meantime, so the pages will need to be adjusted by the length of the frontmatter. 
    with Pdf.open(pdf_file) as pdf:
        with pdf.open_outline() as outline:
            for entry in toc_entries:
                if "SECTION_BREAK" in entry[0]: #ignore section entries
                    continue
                else:
                    tab_number, title, date, page = entry
                    item = OutlineItem(f"{tab_number} {title}", page+length_of_frontmatter)
                    outline.root.append(item)
        pdf.save(output_file)

def merge_frontmatter(input_files, output_file):
    pdf = Pdf.new()
    for input_file in input_files:
        with Pdf.open(input_file) as src:
            pdf.pages.extend(src.pages)
        pdf.save(output_file)
    return output_file

def bookmark_the_index(pdf_file, output_file, coversheet=None):
    with Pdf.open(pdf_file) as pdf:
        with pdf.open_outline() as outline:
            if coversheet:
                #test length of coversheet and set coversheet_length to the number of pages:
                with Pdf.open(coversheet) as coversheet_pdf:
                    coversheet_length = len(coversheet_pdf.pages)
                # Add an outline item for "Index" linking to the first page after the coversheet (it's 0-indexed):
                index_item = OutlineItem("Index", coversheet_length)
                outline.root.insert(0, index_item)
                bundle_logger.debug("[BTI]coversheet is specified, outline item added for index")
            else:
                # Add an outline item for "Index" linking to the first page:
                index_item = OutlineItem("Index", 0)
                outline.root.insert(0, index_item)
                bundle_logger.debug("[BTI]no coversheet specified, outline item added for index")
        pdf.save(output_file)

def create_toc_pdf(toc_entries, casedetails, output_file, confidential=False, date_setting=True, index_font_setting=None, dummy=False, frontmatter_offset=0, length_of_coversheet=0, page_num_alignment=None, page_num_font=None, page_numbering_style=None, footer_prefix=None, main_page_count=0, roman_numbering=False):
    bundle_name = sanitise_latex(casedetails[0])
    bundle_logger.debug(f"[CTP]Creating TOC PDF. Parsing settings:")
    if dummy:
        page_offset = 0
        bundle_logger.debug("[CTP]..This is the first pass dummy TOC")
    else:
        page_offset = frontmatter_offset + 1
        bundle_logger.debug(f"[CTP]..Creating the final TOC. The frontmatter offset is {frontmatter_offset}")


    if date_setting == "hide_date": #if date disabled: keep the column, just make it small and blank out the header
        bundle_logger.debug("[CTP]..Date column disabled")
        date_col_hdr = ""
        date_col_width = "0.3cm"
    elif date_setting == "show_date":
        bundle_logger.debug("[CTP]..Date column enabled")
        date_col_hdr = "Date"
        date_col_width = "3.5cm"
    else:
        bundle_logger.debug("[CTP]..Date setting blank, enabling date column by default.")
        date_col_hdr = "Date"
        date_col_width = "3.5cm"

    if casedetails[1]: 
        claimno_sanitised = sanitise_latex(casedetails[1])
        # claimno_hdr = f"Claim No. {claimno_sanitised}"
        claimno_hdr = claimno_sanitised

        bundle_logger.debug(f"[CTP]..Claim number: {claimno_sanitised}")
    else: 
        claimno_hdr = ""
        bundle_logger.debug("[CTP]..No claim number provided")  
    
    if casedetails[2]:
        casename = sanitise_latex(casedetails[2])
        bundle_logger.debug(f"[CTP]..Case name: {casename}")
    else: 
        casename = ""
        bundle_logger.debug("[CTP]..No case name provided")
    
    index_font_family = None
    if not roman_numbering:
        #parse index font setting
        # set starting page to be one more than the length_of_coversheet
        starting_page = length_of_coversheet + 1
        if index_font_setting == "sans":
            index_font_family = "phv" #LaTeX font family for Helvetica, see https://www.overleaf.com/learn/latex/Font_typefaces#Reference_guide
            bundle_logger.debug("[CTP]..Sans-serif font selected for TOC")
        elif index_font_setting == "serif":
            index_font_family = "ppl" #LaTeX font family for Palatino
            bundle_logger.debug("[CTP]..Serif font selected for TOC")
        elif index_font_setting == "mono":
            index_font_family = "pcr" #LaTeX font family for Courier
            bundle_logger.debug("[CTP]..Monospace font selected for TOC")
        else:
            index_font_family = "" #LaTeX font family for Courier by default
            bundle_logger.debug("[CTP]..No font setting provided, using default font for TOC")

        # parse alignment setting
        if page_num_alignment == "left":
            footer_alignment_setting = r"LO LE"
            bundle_logger.debug("[MPNP]..Left alignment selected for page numbers")
        elif page_num_alignment == "right":
            footer_alignment_setting = r"RO RE"
            bundle_logger.debug("[MPNP]..Right alignment selected for page numbers")
        elif page_num_alignment == "centre":
            footer_alignment_setting = r"CO CE"
            bundle_logger.debug("[MPNP]..Centre alignment selected for page numbers")
        else:
            footer_alignment_setting = r"CO CE"
            bundle_logger.debug("[MPNP]..Defaulting to centre alignment for page numbers")
        
        #parse font setting
        if page_num_font == "sans":
            footer_font = "phv" #LaTeX font family for Helvetica, see https://www.overleaf.com/learn/latex/Font_typefaces#Reference_guide
            bundle_logger.debug("[MPNP]..Sans-serif font selected for page numbers")
        elif page_num_font == "serif":
            footer_font = "ppl" #LaTeX font family for Palatino
            bundle_logger.debug("[MPNP]..Serif font selected for page numbers")
        elif page_num_font == "mono":
            footer_font = "pcr" #LaTeX font family for Courier
            bundle_logger.debug("[MPNP]..Monospace font selected for page numbers")
        else:
            footer_font = "cmr" #LaTeX font family for Courier by default
            bundle_logger.debug("[MPNP]..defaulting to Computer Modern Roman text font for page numbers")
        
        #Allow for pagenumber to be preceded by a bundle tag (e.g. "Bundle A page 1")
        if footer_prefix:
            footer_text = sanitise_latex(footer_prefix.strip() + " ")
            bundle_logger.debug(f"[MPNP]..Prefixing page numbers with '{footer_text}'")
        else: 
            footer_text = ""

        #parse page numbering style and APPEND to the existing text above.
        if page_numbering_style == "x":
            footer_text += r"\thepage"
            bundle_logger.debug("[MPNP]..Page numbering style: x")
        elif page_numbering_style == "x_of_y":
            footer_text += r"\thepage{} of " + str(main_page_count + frontmatter_offset)
            bundle_logger.debug("[MPNP]..Page numbering style: x of y")
        elif page_numbering_style == "page_x":
            footer_text += r"Page \thepage"
            bundle_logger.debug("[MPNP]..Page numbering style: Page x")
        elif page_numbering_style == "page_x_of_y":
            footer_text += r"Page \thepage{} of " + str(main_page_count + frontmatter_offset)
            bundle_logger.debug("[MPNP]..Page numbering style: Page x of y")
        elif page_numbering_style == "x_slash_y":
            footer_text += r"\thepage /" + str(main_page_count + frontmatter_offset)
            bundle_logger.debug("[MPNP]..Page numbering style: x / y")
        else:
            footer_text += r"Page \thepage"
            bundle_logger.debug("[MPNP]..Defaulting to page numbering style: Page x")


    toc_content = r"""
    \documentclass[12pt,a4paper]{article}
    \usepackage{fancyhdr}
    \usepackage{geometry}
    \usepackage{hyperref}
    \usepackage{longtable}
    \usepackage{color, colortbl}
    """
    if confidential:
        toc_content += r"""
        \usepackage{xcolor}
        """
    toc_content += r"""
    \geometry{a4paper, hmargin=2.5cm,vmargin=2cm}
    \definecolor{Gray}{gray}{0.9}"""
    if not roman_numbering:
        toc_content += r"""
        \newcommand{\fontsetting}{\fontfamily{""" + footer_font + r"""}\fontseries{b}\fontsize{18}{22}\selectfont}
        \setcounter{page}{""" + str(starting_page) + r"""}
        \begin{document}
        \pagestyle{fancy}
        \renewcommand{\headrulewidth}{0pt}
        \setlength{\footskip}{20pt}
        \fancyhf{} % to clear the header and the footer simultaneously
        \fancyfoot[""" + footer_alignment_setting + r"""]{\fontsetting """ + footer_text + r"""}
        """
    else: 
        toc_content += r"""
        \begin{document}
        \pagestyle{empty}
        """
    if index_font_family:
        toc_content += r"""
        \fontfamily{""" + index_font_family + r"""}\selectfont
        """
    # toc_content += r"\pagestyle{empty}"
    if claimno_hdr:
        toc_content += r"""
        \hfill\textbf{\normalsize{""" + claimno_hdr + r"""}} \\
        \vspace{-0.5cm}
        """
    if casename:
        toc_content += r"""
        \begin{center}
        \textbf{\large{""" + casename + r"""}} \\
        \end{center}
        """
    if bundle_name:
        toc_content += r"""
        \begin{center}
        \rule{0.5\linewidth}{0.3mm} \\
        \vspace{0.3cm}
        """
        if confidential:
            toc_content += r"""
            \textbf{\large{\textcolor{red}{CONFIDENTIAL}\\ """ + bundle_name.upper() + r"""}} \\
            """
        else:
            toc_content += r"""
            \textbf{\Large{""" + bundle_name.upper() + r"""}} \\
            """
        toc_content += r"""
        \rule{0.5\linewidth}{0.3mm} \\
        \vspace{-0.5cm}
        \end{center}
        """
    toc_content += r"""    
    \def\arraystretch{1.3}
    \begin{longtable}{p{1.2cm} p{10cm} p{""" + date_col_width + r"""} r}
    \hline
    \textbf{Tab} & \textbf{Title} & \textbf{""" + date_col_hdr + r"""} & \textbf{Page} \\
    \hline
    \endfirsthead
    \hline
    \textbf{Tab} & \textbf{Title} & \textbf{""" + date_col_hdr + r"""} & \textbf{Page} \\
    \hline
    \endhead
    \hline
    \endfoot
    \hline
    \endlastfoot
    """
    # toc_entries format:
    #   for files, it's: [tab_number, title, date, page_count]
    #   for sections, it's: [SECTION_BREAK, section_name]

    for entry in toc_entries:
        if "SECTION_BREAK" in entry[0]:
            toc_content += r"\hline \rowcolor{Gray}\multicolumn{4}{l}{\textbf{" + entry[1] + r"}} \\ \hline "
        else:
            tab_number, title, date, page = entry
            sanitised_title = sanitise_latex(title)
            if date_setting == "hide_date":
                sanitised_date = ""
            elif date_setting == "show_date":
                sanitised_date = sanitise_latex(date)
            else:
                sanitised_date = sanitise_latex(date)
            sanitised_tab_number = sanitise_latex(tab_number)
            if dummy:
                page = 999
            else:
                page += page_offset
            toc_content += f"{sanitised_tab_number} & {sanitised_title} & {sanitised_date} & {page} \\\\"
    
    bundle_logger.debug("[CTP]TOC entries added")

    toc_content += r"""
    \end{longtable}
    \newpage
    \pagenumbering{arabic}
    \end{document}
    """
    if dummy:
        toc_tex_path = os.path.join(os.path.dirname(output_file), "dummytoc.tex")
         #basename of specified output file
    else:
        toc_tex_path = os.path.join(os.path.dirname(output_file), "toc.tex")
        jobname = "toc"
    with open(toc_tex_path, "w") as f:
        f.write(toc_content)
    if os.path.exists(toc_tex_path):
        bundle_logger.debug(f"[CTP]TOC content written to file: {toc_tex_path}")
    else:
        bundle_logger.error(f"[CTP]Error writing TOC content to file: {toc_tex_path}")
        return     
    #TODO: PYTHONISE THIS COMMAND
    jobname = os.path.basename(output_file).split(".")[0]
    result = os.system(f"pdflatex -output-directory {os.path.dirname(output_file)} -jobname={jobname} {toc_tex_path} > /dev/null")
    if result != 0:
        bundle_logger.error(f"[CTP]..pdflatex command failed with error code {result}")
    else:
        bundle_logger.debug("[CTP]..pdflatex command succeeded.")

    #shutil.move(os.path.join(os.path.dirname(output_file), output_file), output_file)
    bundle_logger.debug(f"[CTP]TOC PDF saved to {output_file}")

def make_page_numbers_pdf(
        page_numbers_pdf_path, 
        page_numbers_tex_path, 
        main_page_count,
        length_of_frontmatter_offset=0, 
        page_num_alignment=None, 
        page_num_font=None, 
        page_numbering_style=None, 
        footer_prefix=None
    ):
    bundle_logger.debug("[MPNP]Creating page numbers PDF. Parsing settings:")
    starting_page = length_of_frontmatter_offset + 1
    if length_of_frontmatter_offset:
        bundle_logger.debug(f"[MPNP]..frontmatter offset: {length_of_frontmatter_offset}")
    else:
        bundle_logger.debug("[MPNP]..no frontmatter offset.")
    # parse alignment setting
    if page_num_alignment == "left":
        footer_alignment_setting = r"LO LE"
        bundle_logger.debug("[MPNP]..Left alignment selected for page numbers")
    elif page_num_alignment == "right":
        footer_alignment_setting = r"RO RE"
        bundle_logger.debug("[MPNP]..Right alignment selected for page numbers")
    elif page_num_alignment == "centre":
        footer_alignment_setting = r"CO CE"
        bundle_logger.debug("[MPNP]..Centre alignment selected for page numbers")
    else:
        footer_alignment_setting = r"CO CE"
        bundle_logger.debug("[MPNP]..Defaulting to centre alignment for page numbers")
    
    #parse font setting
    if page_num_font == "sans":
        footer_font = "phv" #LaTeX font family for Helvetica, see https://www.overleaf.com/learn/latex/Font_typefaces#Reference_guide
        bundle_logger.debug("[MPNP]..Sans-serif font selected for page numbers")
    elif page_num_font == "serif":
        footer_font = "ppl" #LaTeX font family for Palatino
        bundle_logger.debug("[MPNP]..Serif font selected for page numbers")
    elif page_num_font == "mono":
        footer_font = "pcr" #LaTeX font family for Courier
        bundle_logger.debug("[MPNP]..Monospace font selected for page numbers")
    else:
        footer_font = "cmr" #LaTeX font family for Courier by default
        bundle_logger.debug("[MPNP]..defaulting to Computer Modern Roman text font for page numbers")
    
    #Allow for pagenumber to be preceded by a bundle tag (e.g. "Bundle A page 1")
    if footer_prefix:
        footer_text = sanitise_latex(footer_prefix.strip() + " ")
        bundle_logger.debug(f"[MPNP]..Prefixing page numbers with '{footer_text}'")
    else: 
        footer_text = ""

    #parse page numbering style and APPEND to the existing text above.
    if page_numbering_style == "x":
        footer_text += r"\thepage"
        bundle_logger.debug("[MPNP]..Page numbering style: x")
    elif page_numbering_style == "x_of_y":
        footer_text += r"\thepage{} of " + str(main_page_count + length_of_frontmatter_offset)
        bundle_logger.debug("[MPNP]..Page numbering style: x of y")
    elif page_numbering_style == "page_x":
        footer_text += r"Page \thepage"
        bundle_logger.debug("[MPNP]..Page numbering style: Page x")
    elif page_numbering_style == "page_x_of_y":
        footer_text += r"Page \thepage{} of " + str(main_page_count + length_of_frontmatter_offset)
        bundle_logger.debug("[MPNP]..Page numbering style: Page x of y")
    elif page_numbering_style == "x_slash_y":
        footer_text += r"\thepage /" + str(main_page_count + length_of_frontmatter_offset)
        bundle_logger.debug("[MPNP]..Page numbering style: x / y")
    else:
        footer_text += r"Page \thepage"
        bundle_logger.debug("[MPNP]..Defaulting to page numbering style: Page x")

    page_number_footer_tex = ""

    # Create LaTeX file for page numbers
    page_number_footer_tex += r"""
        \documentclass[12pt,a4paper]{article}
        \usepackage{fancyhdr}
        \usepackage{multido}
        \usepackage[hmargin=.8cm,vmargin=1.1cm,nohead,nofoot,twoside]{geometry}
        \newcommand{\fontsetting}{\fontfamily{""" + footer_font + r"""}\fontseries{b}\fontsize{18}{22}\selectfont}
        \setcounter{page}{""" + str(starting_page) + r"""}
        \begin{document}
        \pagestyle{fancy}
        \renewcommand{\headrulewidth}{0pt}
        \setlength{\footskip}{20pt}
        \fancyhf{} % to clear the header and the footer simultaneously
        \fancyfoot[""" + footer_alignment_setting + r"""]{\fontsetting """ + footer_text + r"""}
        \multido{}{""" + str(main_page_count) + r"""}{\vphantom{x}\newpage}
        \end{document}
        """

    with open(page_numbers_tex_path, "w") as f:
        f.write(page_number_footer_tex)
    bundle_logger.debug(f"[MPNP]Page numbers content written to file: {page_numbers_tex_path}")

    # Compile LaTeX file to PDF
    result = os.system(f"pdflatex -output-directory {os.path.dirname(page_numbers_pdf_path)} {page_numbers_tex_path} > /dev/null")
    if result != 0:
        bundle_logger.error(f"[MPNP]pdflatex command failed with error code {result}")
    else:
        bundle_logger.debug(f"[MPNP]pdflatex command succeeded. Page numbers PDF saved to {page_numbers_pdf_path}")
    return page_numbers_pdf_path

def paginate_pdf(input_file, output_file, frontmatter_offset, page_num_alignment=None, page_num_font=None, page_numbering_style=None, footer_prefix=None):
    bundle_logger.debug("[PP]Paginate PDF function beginning")
    main_page_count = 0
    try:
        tocsrc = Pdf.open(input_file)
        main_page_count += len(tocsrc.pages)
        bundle_logger.debug(f"[PP]..Main PDF opened with {main_page_count} pages")
    except Exception as e:
        bundle_logger.error(f"[PP]..Error counting pages in TOC: {e}")
        raise e
        return
    page_numbers_tex_path = os.path.join(os.path.dirname(output_file), "pageNumbers.tex")
    page_numbers_pdf_path = os.path.join(os.path.dirname(output_file), "pageNumbers.pdf")
    page_numbers_pdf_output = make_page_numbers_pdf(     # Create LaTeX file for page numbers
                                page_numbers_pdf_path, 
                                page_numbers_tex_path, 
                                main_page_count,
                                frontmatter_offset, 
                                page_num_alignment, 
                                page_num_font, 
                                page_numbering_style, 
                                footer_prefix)
    if os.path.exists(page_numbers_pdf_output):    # Add page numbers to the PDF
        try:
            pypdftk.stamp(input_file, page_numbers_pdf_path, output_file)
            bundle_logger.debug(f"[PP]..Page numbers PDF stamped to {output_file}")
        except subprocess.CalledProcessError as e:
            bundle_logger.error(f"[PP]..Error stamping page numbers onto PDF: {e}")
            return
    else: 
        bundle_logger.error("[PP]Error creating page numbers PDF: see pdftex temporary logs in temp folder.")
    return main_page_count

def add_roman_labels(pdf_file, length_of_frontmatter, output_file):
    bundle_logger.debug(f"[APL]Adding page labels to PDF {pdf_file}")
    with Pdf.open(pdf_file) as pdf:
        nums = [
            0, Dictionary(S=Name.r),  # lowercase Roman starting at first page of bundle
            length_of_frontmatter, Dictionary(S=Name.D)   # Decimal starting at page 1 after frontmatter
        ]

        pdf.Root.PageLabels = Dictionary(Nums=nums)
        pdf.save(output_file)
    


def process_csv_index(csv_index): #This is a stub of a not-well-implemented idea (passing csv info as a string argument.)
    index_data = {}
    current_section = None
    reader = csv.DictReader(csv_index.splitlines())
    
    for row in reader:
        if (row['Type'] == 'File') and (row['Filename'] not in index_data):
            index_data[row['Filename']] = (row['Title'], row['Date'], row['Section'])
    
    return index_data

def transform_coordinates(coords, page_height):
    """Transform coordinates from top-left to bottom-left origin system"""
    x1, y1, x2, y2 = coords
    # Flip the y coordinates by subtracting from page height
    new_y1 = page_height - y2  # Note: we swap y1 and y2 here
    new_y2 = page_height - y1
    return (x1, new_y1, x2, new_y2)

def add_annotations_with_transform(pdf_file, list_of_annotation_coords, output_file):
    reader = PdfReader(pdf_file)
    writer = PdfWriter()
    
    # Copy all pages to the writer
    for page in reader.pages:
        writer.add_page(page)
    
    # navigate the treacherous PDF coordinate system
    for annotation in list_of_annotation_coords:
        toc_page = annotation['toc_page']
        coords = annotation['coords']
        destination_page = annotation['destination_page']
        
        # Get the page height for coordinate transformation
        page = reader.pages[toc_page]
        page_height = float(page.mediabox.height)
        
        # Transform the coordinates
        transformed_coords = transform_coordinates(coords, page_height)
        
        try:
            # Create link annotation with transformed coordinates
            link = Link(
                rect=transformed_coords,
                target_page_index=destination_page,
                fit=Fit("/FitH")
            )
            writer.add_annotation(page_number=toc_page, annotation=link)
            
            # # Create highlight annotation with transformed coordinates
            # quad_points = [
            #     transformed_coords[0], transformed_coords[3],  # x1, y1 (top left)
            #     transformed_coords[2], transformed_coords[3],  # x2, y1 (top right)
            #     transformed_coords[0], transformed_coords[1],  # x1, y2 (bottom left)
            #     transformed_coords[2], transformed_coords[1]   # x2, y2 (bottom right)
            # ]
            bundle_logger.debug(f"[AAWT]Added annotations on TOC page {toc_page} to destination pg index {destination_page}")
            
        except Exception as e:
            bundle_logger.error(f"[AAWT]Failed to add annotations on TOC page {toc_page}: {e}")
            raise e
    
    # Write the output file
    with open(output_file, "wb") as output:
        writer.write(output)

def add_hyperlinks(
        pdf_file, 
        output_file, 
        length_of_coversheet, 
        length_of_frontmatter, 
        toc_entries, 
        date_setting="show_date",
        roman_page_labels=False
    ):
    #This starts by finding the text to link to, and recording its position and the data that will need to be written into the PDF
    # It then passes off to the annotation writer. 

    bundle_logger.debug(f"[HYP]Starting hyperlink addition")
    scraped_pages_text = []
    list_of_annotation_coords = []
    longtitle = 0
    
    # Step 1: Extract text and coordinates from TOC
    with pdfplumber.open(pdf_file) as pdf:
        for idx in range(length_of_coversheet, length_of_frontmatter):
            current_page = pdf.pages[idx]
            bundle_logger.debug(f"[HYP]..Processing page {idx} for TOC text extraction")
            #scraped_toc_text = current_page.extract_words(keep_blank_chars=True, use_text_flow=True)
            scraped_toc_text = current_page.extract_text_lines()            
            scraped_pages_text.append(scraped_toc_text)
    # Step 2: Match TOC entries to text and get coordinates
    for entry in toc_entries:  # toc_entries format: [tab_number, title, date, page_count]
        matched_this_entry_flag = False
        bundle_logger.debug(f"[HYP]..Processing TOC entry: {entry}")
        #if it's a section break, skip this part
        if "SECTION_BREAK" in entry[0]:
            continue
        tab_key = re.escape(entry[0].replace(" ", ""))
        if len(entry[1]) > 30: #More than 50 chars is liable to line-break, 
            ##in which case it won't be matched in the extracted lines from the pdf:
            ##we are searching against naively-extracted text not accounting for tabular layout.
            ##Choose 30 chr (much shorter than 50) so we don't need to worry about end-of-line hyphen characters. 
            ##(Actually even without the title the programattically generated tab...page combination 
            ## should be unique enough, but let's include the title anyway to be a bit more robust)
            #
            #In future though, if converting between date formats becomes supported, it might be easier just to 
            # nix the date from this search function.
            longtitle = 1
            title_key = re.escape(entry[1][:29].replace(" ", "")) #if the title is too long, just use the first 30 characters
        else:
            title_key = re.escape(entry[1].replace(" ", ""))
        if roman_page_labels:
            page_key = entry[3] + 1 #no need to escape int
        else:
            page_key = entry[3] + length_of_frontmatter + 1 
        if date_setting == "hide_date": #if date disabled
            if longtitle == 1:
                search_key = re.compile(f"{tab_key}{title_key}.*?{page_key}") # allow for wildcards to match titles fuzzier
                fallback_search_key = re.compile(f"{tab_key}./?{page_key}") # if the title doesn't work for some reason, fall back to the tab and page number
            else:
                search_key = re.compile(f"{tab_key}{title_key}{page_key}")
                fallback_search_key = re.compile(f"{tab_key}{page_key}")
        else:                #If date is enabled
            date_key = re.escape(entry[2].replace(" ", ""))
            if longtitle == 1:
                search_key = re.compile(f"{tab_key}{title_key}.*?{date_key}{page_key}")
                fallback_search_key = re.compile(f"{tab_key}./?{page_key}") 
            else:
                search_key = re.compile(f"{tab_key}{title_key}{date_key}{page_key}")
                fallback_search_key = re.compile(f"{tab_key}{page_key}")
        #    search_key = f"{entry[0]}{entry[1]}{entry[2]}{page_key}" #old format before regex 
        #strip whitespace from search key for easier matching, but preserve punctuation:
        #search_key_for_this_entry = search_key.replace(" ", "") ## old from before regex
        bundle_logger.debug(f"[HYP]....Using search-key regex: '{search_key.pattern}' on TOC pages")
        for page_idx, page_words in enumerate(scraped_pages_text, start=length_of_coversheet):
            for word in page_words:
                current_word = word['text']
                stripped_word = current_word.replace(" ", "")
                #if search_key_for_this_entry in stripped_word: This is the old way, from before using regex
                if search_key.match(stripped_word): #Using regex `.match` instead of `.fullmatch` to avoid df text exraction noise. 
                    matched_this_entry_flag = True
                    bundle_logger.debug(f"[HYP]....found on page {page_idx}")
                    annotation = {
                        'title': entry[1], # title of the TOC entry
                        'toc_page': page_idx,  # 0-based index for TOC page
                    #by inspection, converting from pdfplumber output format to pikepdf input formats:
                    # x0=llx, top=ury, x1=urx, bottom=lly
                    #pikepdf wants them ordered as llx lly urx ury therefore use order: x0, bottom, x1, top ---
                        'coords': (word['x0'], word['bottom'], word['x1'], word['top']),
                        'destination_page': entry[3] + length_of_coversheet + 1 #0-based page entry for main arabic section
                    }
                    list_of_annotation_coords.append(annotation)
                    break
        if not matched_this_entry_flag:    #if the search key isn't found once all words are processed, do the process again with the fallback_search_key:
            bundle_logger.debug(f"[HYP]....search key not found trying fallback search key: '{fallback_search_key}'")
            for page_idx, page_words in enumerate(scraped_pages_text, start=length_of_coversheet):
                for word in page_words:
                    current_word = word['text']
                    stripped_word = current_word.replace(" ", "")
                    if fallback_search_key.match(stripped_word): 
                        matched_this_entry_flag = True
                        bundle_logger.debug(f"[HYP]....fallback search key found on page {page_idx}")
                        annotation = {
                            'title': entry[1],
                            'toc_page': page_idx, 
                            'coords': (word['x0'], word['bottom'], word['x1'], word['top']),
                            'destination_page': entry[3] + length_of_coversheet + 1 
                        }
                        list_of_annotation_coords.append(annotation)
                        break
    
    # Step 3: Add annotations to the PDF
    #for annotation in list_of_annotation_coords:
    add_annotations_with_transform(pdf_file, list_of_annotation_coords, output_file)


class BundleConfig:
    def __init__(self, timestamp, case_details, csv_string, confidential_bool, zip_bool, session_id, user_agent, page_num_align, index_font, footer_font, page_num_style, footer_prefix, date_setting, roman_for_preface):
        self.timestamp = timestamp if timestamp else datetime.now().strftime("%Y-%m-%d-%H%M%S")
        self.case_details = case_details
        self.csv_string = csv_string if csv_string else None
        self.confidential_bool = confidential_bool if confidential_bool else False
        self.zip_bool = zip_bool if zip_bool else True
        self.session_id = session_id if session_id else timestamp
        self.user_agent = user_agent if user_agent else "Unknown"
        self.page_num_align = page_num_align if page_num_align else "centre"
        self.index_font = index_font if index_font else "Default"
        self.footer_font = footer_font if footer_font else "Default"
        self.page_num_style = page_num_style if page_num_style else "page_x_of_y"
        self.footer_prefix = footer_prefix if footer_prefix else ""
        self.date_setting = date_setting if date_setting else "show_date"
        self.roman_for_preface = roman_for_preface if roman_for_preface else False

def create_bundle(input_files, output_file, coversheet, index_file, bundle_config):

# development setting:
    BUNTOOL_VERSION = "2025-01-13"

    #initial file handling
    temp_dir = os.path.join(os.getcwd(), "tempfiles", bundle_config.session_id)
    os.makedirs(temp_dir, exist_ok=True)
    output_file = secure_filename(output_file)
    tmp_output_file = os.path.join(temp_dir, output_file)
    coversheet_path = os.path.join(temp_dir, coversheet) if coversheet else None
    list_of_temp_files = []
    
    # set up logging using configure_logger function
    bundle_logger = configure_logger(bundle_config.session_id, temp_dir)
    bundle_logger.info(f"[CB]THIS IS BUNTOOL VERSION {BUNTOOL_VERSION}")
    bundle_logger.info(f"[CB]Temp directory created at {temp_dir}.")


    bundle_logger.info(f"*****New session: {bundle_config.session_id} called create_bundle*****")
    bundle_logger.info(f"{bundle_config.session_id} has the USER AGENT: {bundle_config.user_agent}")
    bundle_logger.info(f"Bundle creation called with {len(input_files)} input files and output file {output_file}")
    bundle_logger.debug(f"[CB]create_bundle received the following arguments:")
    bundle_logger.debug(f"[CB]....input_files: {input_files}")
    bundle_logger.debug(f"[CB]....output_file: {output_file}")
    bundle_logger.debug(f"[CB]....coversheet: {coversheet}") 
    bundle_logger.debug(f"[CB]....index_file: {index_file}")
    bundle_logger.debug(f"[CB]....bundle_config: {bundle_config.__dict__}")

    #of those files specified in the arguments, add to temp list:
    list_of_temp_files.append(coversheet_path) if coversheet_path else None
    list_of_temp_files.append(index_file) if index_file else None
    list_of_temp_files.extend(input_files)

    try:
        # Process index data:
        # First, save the CSV index string to a temporary file if index data provided as a string
        if not index_file:
            if bundle_config.csv_string:
                index_file_path = os.path.join(temp_dir, "index.csv")
                with open(index_file_path, 'w') as f:
                    f.write(bundle_config.csv_string)
                index_file = index_file_path
                bundle_logger.info(f"[CB]Index data from string input saved to {index_file}")

        if index_file: #this is a file handler. The main way to pass an index.
            bundle_logger.debug(f"[CB]Calling load_index_data [LI] with index_file: {index_file}")
            index_data = load_index_data(index_file)
        else:
            index_data = None
            bundle_logger.info(f"[CB]No index data provided.")

        # Merge PDFs using provided unique filenames
        merged_file = os.path.join(temp_dir, "TEMP01_mainpages.pdf")
        bundle_logger.debug(f"[CB]Calling merge_pdfs_create_toc_entries [MP] with arguments:")
        bundle_logger.debug(f"[CB]....input_files: {input_files}")
        bundle_logger.debug(f"[CB]....merged_file: {merged_file}")
        bundle_logger.debug(f"[CB]....index_data: {index_data}")
        try:
            toc_entries = merge_pdfs_create_toc_entries(input_files, merged_file, index_data)
        except Exception as e:
            bundle_logger.error(f"[CB]Error while merging pdf files: {e}")
            raise e
        if not os.path.exists(merged_file):
            bundle_logger.info(f"[CB]Merging file unsuccessful: cannot locate expected ouput {merged_file}.")
            return
        else:
            bundle_logger.info(f"[CB]Merged PDF created at {merged_file}")
            list_of_temp_files.append(merged_file)

        # Find length of frontmatter to allow for pagination from page 1 (no roman numbering)
        if coversheet and os.path.exists(coversheet_path):
            with Pdf.open (coversheet_path) as coversheet_pdf:
                length_of_coversheet = len(coversheet_pdf.pages)
        else:
            length_of_coversheet = 0

        #First pass to create a dummy TOC to find the length of the frontmatter:
        if not bundle_config.roman_for_preface:
            bundle_logger.debug(f"[CB]Creating dummy TOC PDF to find length of frontmatter")
            try: 
                dummy_toc_pdf_path = os.path.join( temp_dir, "TEMP02_dummy_toc.pdf")
                create_toc_pdf( #DUMMY TOC
                    toc_entries,
                    bundle_config.case_details,
                    dummy_toc_pdf_path,
                    bundle_config.confidential_bool,
                    bundle_config.date_setting,
                    bundle_config.index_font,
                    True, #now make sure the page num align settings etc which it expects are passed:
                    0,
                    0,
                    bundle_config.page_num_align,
                    bundle_config.footer_font,
                    bundle_config.page_num_style,
                    bundle_config.footer_prefix             
                    )
            except Exception as e:
                bundle_logger.error(f"[CB]Error during first pass TOC creation: {e}")
                raise e
            if not os.path.exists(dummy_toc_pdf_path):
                bundle_logger.error(f"[CB]First pass TOC file unsuccessful: cannot locate expected ouput {dummy_toc_pdf_path}.")
                return
            else:
                bundle_logger.info(f"[CB]dummy TOC PDF created at {dummy_toc_pdf_path}")
                list_of_temp_files.append(dummy_toc_pdf_path)
                # also append the various latex outputs: TEMP02_dummy_toc.out, .aux (keep only the .log):
                list_of_temp_files.append(os.path.join(temp_dir, "TEMP02_dummy_toc.out"))
                list_of_temp_files.append(os.path.join(temp_dir, "TEMP02_dummy_toc.aux"))
                #also the dummy toc tex file:
                list_of_temp_files.append(os.path.join(temp_dir, "dummytoc.tex"))
                #find length of dummy TOC:
                with Pdf.open(dummy_toc_pdf_path) as dummytocpdf:
                    length_of_dummy_toc = len(dummytocpdf.pages)
                    expected_length_of_frontmatter = length_of_coversheet + length_of_dummy_toc
        else:
            expected_length_of_frontmatter = length_of_coversheet


        # Paginate the merged main files of the PDF
        merged_paginated_no_toc = os.path.join(temp_dir, "TEMP03_paginated_mainpages.pdf")
        bundle_logger.debug(f"[CB]Calling paginate_pdf [PP] with arguments:")
        bundle_logger.debug(f"[CB]....merged_file: {merged_file}")
        bundle_logger.debug(f"[CB]....merged_paginated_no_toc: {merged_paginated_no_toc}")
        bundle_logger.debug(f"[CB]....page_num_alignment: {bundle_config.page_num_align}")
        bundle_logger.debug(f"[CB]....page_num_font: {bundle_config.footer_font}")
        bundle_logger.debug(f"[CB]....page_numbering_style: {bundle_config.page_num_style}")
        bundle_logger.debug(f"[CB]....footer_prefix: {bundle_config.footer_prefix}")
        try:
            main_page_count = paginate_pdf(
                merged_file, 
                merged_paginated_no_toc,
                expected_length_of_frontmatter,
                bundle_config.page_num_align, 
                bundle_config.footer_font, 
                bundle_config.page_num_style, 
                bundle_config.footer_prefix,
            )
        except Exception as e:
            bundle_logger.error(f"[CB]..Error during paginate_pdf: {e}")
        if not os.path.exists(merged_paginated_no_toc):
            bundle_logger.error(f"[CB]..Paginating file unsuccessful: cannot locate expected ouput {merged_paginated_no_toc}.")
            return
        else:
            bundle_logger.info(f"[CB]..Merged PDF paginated at {merged_paginated_no_toc}")
            list_of_temp_files.append(merged_paginated_no_toc)
            # also pageNumbers.aux   pageNumbers.pdf  pageNumbers.tex (keep only the .log):
            list_of_temp_files.append(os.path.join(temp_dir, "pageNumbers.aux"))
            list_of_temp_files.append(os.path.join(temp_dir, "pageNumbers.pdf"))
            list_of_temp_files.append(os.path.join(temp_dir, "pageNumbers.tex"))


        # Now, create TOC PDF For real:
        toc_file_path = os.path.join(temp_dir, "index.pdf")
        bundle_logger.debug(f"[CB]Calling create_toc_pdf [CT] - final version -  with arguments:")
        bundle_logger.debug(f"[CB]....toc_entries: {toc_entries}")
        bundle_logger.debug(f"[CB]....casedetails: {bundle_config.case_details}")
        bundle_logger.debug(f"[CB]....toc_file_path: {toc_file_path}")
        bundle_logger.debug(f"[CB]....confidential: {bundle_config.confidential_bool}")
        bundle_logger.debug(f"[CB]....date_setting: {bundle_config.date_setting}")
        bundle_logger.debug(f"[CB]....index_font: {bundle_config.index_font}")
        bundle_logger.debug(f"[CB]....dummy: False")
        bundle_logger.debug(f"[CB]....length_of_frontmatter: {expected_length_of_frontmatter}")
        create_toc_pdf( #FINAL TOC
            toc_entries, 
            bundle_config.case_details, 
            toc_file_path, 
            bundle_config.confidential_bool, 
            bundle_config.date_setting, 
            bundle_config.index_font,
            False,
            expected_length_of_frontmatter,
            length_of_coversheet,
            bundle_config.page_num_align,
            bundle_config.footer_font,
            bundle_config.page_num_style,
            bundle_config.footer_prefix,
            main_page_count,
            bundle_config.roman_for_preface
        )
        if not os.path.exists(toc_file_path):
            bundle_logger.error(f"[CB]..Creating TOC file unsuccessful: cannot locate expected ouput {toc_file_path}.")
            return
        else:
            bundle_logger.info(f"[CB]..TOC PDF created at {os.path.basename(toc_file_path)}")
            list_of_temp_files.append(toc_file_path)
            # also append the various latex outputs: TEMP02_dummy_toc.out, .log, .aux:
            list_of_temp_files.append(os.path.join(temp_dir, "index.out"))
            list_of_temp_files.append(os.path.join(temp_dir, "index.log"))
            list_of_temp_files.append(os.path.join(temp_dir, "index.aux"))
            #also the toc tex file:
            list_of_temp_files.append(os.path.join(temp_dir, "toc.tex"))

        
        # Handle frontmatter
            frontmatter = os.path.join(temp_dir, "TEMP00-coversheet-plus-toc.pdf")
        if coversheet:
            if os.path.exists(coversheet_path):
                frontmatterfiles = [coversheet_path, toc_file_path]
                bundle_logger.debug(f"[CB]Coversheet specified. Calling merge_frontmatter [MF] with arguments:")
                bundle_logger.debug(f"[CB]....frontmatterfiles: {frontmatterfiles}")
                bundle_logger.debug(f"[CB]....frontmatter: {frontmatter}")
                frontmatter_path = merge_frontmatter(frontmatterfiles, frontmatter)
                if not os.path.exists(frontmatter_path):
                    bundle_logger.error(f"[CB]..Merging frontmatter unsuccessful: cannot locate expected ouput {frontmatter_path}.")
                    return
                else:
                    bundle_logger.info(f"[CB]..Frontmatter created at {os.path.basename(frontmatter_path)}")
            else: 
                bundle_logger.error(f"[CB]..Coversheet specified but not found at {coversheet_path}.")
                return
        else:
            frontmatter_path = toc_file_path
            bundle_logger.info(f"[CB]No coversheet specified. TOC is the only frontmatter.")

        #check the frontmatter now generated matches the length that was expected from the dummy:
        
        with Pdf.open(frontmatter_path) as frontmatter_pdf:
            length_of_frontmatter = len(frontmatter_pdf.pages)
            bundle_logger.debug(f"[CB]Frontmatter length is {length_of_frontmatter} pages.")
            if not bundle_config.roman_for_preface:
                if length_of_frontmatter != expected_length_of_frontmatter:
                    bundle_logger.error(f"[CB]..Frontmatter length mismatch: expected {length_of_dummy_toc} pages, got {length_of_frontmatter}.")
                    return
                else:
                    bundle_logger.info(f"[CB]..Frontmatter length matches expected {length_of_dummy_toc} pages.")

        # Merge frontmatter with main docs (previously merged) PDFs
        merged_file_with_frontmatter = os.path.join(temp_dir, "TEMP04-all_pages.pdf")
        bundle_logger.debug(f"[CB]..Calling pypdftk.concat with arguments:")
        bundle_logger.debug(f"[CB]....flie1: {frontmatter_path}")
        bundle_logger.debug(f"[CB]....file2: {merged_paginated_no_toc}")
        bundle_logger.debug(f"[CB]....out_file: {merged_file_with_frontmatter}")
        pypdftk.concat([frontmatter_path, merged_paginated_no_toc], merged_file_with_frontmatter)
        if not os.path.exists(merged_file_with_frontmatter):
            bundle_logger.error(f"[CB]..Merging frontmatter with main docs unsuccessful: cannot locate expected ouput {merged_file_with_frontmatter}.")
            return
        else:
            bundle_logger.info(f"[CB]..Frontmatter merged with main docs at {merged_file_with_frontmatter}")
            list_of_temp_files.append(merged_file_with_frontmatter)

        #add clickable hyperlinks to TOC page
        bundle_logger.debug(f"[[CB]Beginning hyperlinking process")

        #find length of coversheet and frontmatter to pass to hyperlinking function:
        hyperlinked_file = os.path.join(temp_dir, "TEMP05-hyperlinked.pdf")
        bundle_logger.debug(f"[CB]..Calling add_hyperlinks [AH] with arguments:")
        bundle_logger.debug(f"[CB]......merged_file_with_frontmatter: {merged_file_with_frontmatter}")
        bundle_logger.debug(f"[CB]......hyperlinked_file: {hyperlinked_file}")
        bundle_logger.debug(f"[CB]......length_of_coversheet: {length_of_coversheet}")
        bundle_logger.debug(f"[CB]......length_of_frontmatter: {length_of_frontmatter}")
        bundle_logger.debug(f"[CB]......toc_entries: {toc_entries}")
        bundle_logger.debug(f"[CB]......date_setting: {bundle_config.date_setting}")
        bundle_logger.debug(f"[CB]......roman_for_preface: {bundle_config.roman_for_preface}")
        try:
            add_hyperlinks(
                merged_file_with_frontmatter, 
                hyperlinked_file, 
                length_of_coversheet, 
                length_of_frontmatter, 
                toc_entries, 
                bundle_config.date_setting,
                bundle_config.roman_for_preface
            )
        except Exception as e:
            bundle_logger.error(f"[CB]..Error during add_hyperlinks: {e}")
            raise e
        if not os.path.exists(hyperlinked_file):
            bundle_logger.error(f"[CB]..Hyperlinking file unsuccessful: cannot locate expected ouput {hyperlinked_file}.")
            return
        else:
            bundle_logger.info(f"[CB]..Hyperlinked PDF created at {hyperlinked_file}")
            list_of_temp_files.append(hyperlinked_file)

        # Add pdf bookmarks (outline items) to the PDF outline:
        main_bookmarked_file = os.path.join(temp_dir, "TEMP06_main_bookmarks.pdf")
        bundle_logger.debug(f"[CB]Calling add_bookmarks_to_pdf [AB] with arguments:")
        bundle_logger.debug(f"[CB]....hyperlinked_file: {hyperlinked_file}")
        bundle_logger.debug(f"[CB]....main_bookmarked_file: {main_bookmarked_file}")
        bundle_logger.debug(f"[CB]....toc_entries: {toc_entries}")
        bundle_logger.debug(f"[CB]....length_of_frontmatter: {length_of_frontmatter}")
        try:
            add_bookmarks_to_pdf(
                hyperlinked_file, 
                main_bookmarked_file, 
                toc_entries, 
                length_of_frontmatter
            )
        except Exception as e:
            bundle_logger.error(f"[CB]..Error during add_bookmarks_to_pdf: {e}")
            raise e
        if not os.path.exists(main_bookmarked_file):
            bundle_logger.error(f"[CB]..Bookmarking file unsuccessful: cannot locate expected ouput {main_bookmarked_file}.")
            return
        else:
            bundle_logger.info(f"[CB]..Bookmarked PDF created at {main_bookmarked_file}")
            list_of_temp_files.append(main_bookmarked_file)

        # Add pdf bookmark (outline item) for the TOC
        index_bookmarked_file = os.path.join(temp_dir, "TEMP07_all_bookmarks.pdf")
        bundle_logger.debug(f"[CB]Calling bookmark_the_index [BI] with arguments:")
        bundle_logger.debug(f"[CB]....main_bookmarked_file: {main_bookmarked_file}")
        bundle_logger.debug(f"[CB]....index_bookmarked_file: {index_bookmarked_file}")
        bundle_logger.debug(f"[CB]....coversheet_path: {coversheet_path}")
        try:
            bookmark_the_index(
                main_bookmarked_file, 
                index_bookmarked_file, 
                coversheet_path
            )
        except Exception as e:
            bundle_logger.error(f"[CB]..Error during bookmark_the_index: {e}")
            raise e
        if not os.path.exists(index_bookmarked_file):
            bundle_logger.error(f"[CB]..Bookmarking index file unsuccessful: cannot locate expected ouput {index_bookmarked_file}.")
            return
        else:
            bundle_logger.info(f"[CB]..Index bookmarked PDF created at {index_bookmarked_file}")
            list_of_temp_files.append(index_bookmarked_file)

        if bundle_config.roman_for_preface:
        # This function changes the page labels so that the frontmatter is 
        ##paginated as a roman numbering preface (i, ii etc) 
        ##and the main part of the bundle is paginated beginning
        ## at page 1, the first page after the frontmatter. 
            bundle_logger.debug(f"[CB]Calling add_roman_labels [APL] with arguments:")
            bundle_logger.debug(f"[CB]....index_bookmarked_file: {index_bookmarked_file}")
            bundle_logger.debug(f"[CB]....frontmatter_path: {frontmatter_path}")
            bundle_logger.debug(f"[CB]....tmp_output_file: {tmp_output_file}")
            try:
                add_roman_labels(
                    index_bookmarked_file, 
                    length_of_frontmatter, 
                    tmp_output_file
                    )
            except Exception as e:
                bundle_logger.error(f"[CB]..Error during add_roman_labels: {e}")
                raise e
            if not os.path.exists(tmp_output_file):
                bundle_logger.error(f"[CB]..Adding page labels unsuccessful: cannot locate expected ouput {tmp_output_file}.")
                return
            else:
                bundle_logger.info(f"[CB]..Page labels added to PDF saved to {tmp_output_file}")
        else: 
            #if no roman numbering is requested, just copy the file to the final output location:
            shutil.copyfile(index_bookmarked_file, tmp_output_file)

        bundle_logger.info(f"[CB]Completed bundle creation. output written to: {tmp_output_file}")

    except Exception as e:
        bundle_logger.error(f"[CB]Error during create_bundle: {e}")
        raise e

    finally:
        # Create zip file if requested:
        zip_filepath = None
        if bundle_config.zip_bool:
            zip_timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            if not bundle_config.case_details[0]:
                bundletitleforfilename = "Bundle"
            else:
                bundletitleforfilename = bundle_config.case_details[0]
            bundle_logger.debug(f"[CB]Calling create_zip_file [CZF] with arguments:")
            bundle_logger.debug(f"[CB]....bundletitleforfilename: {bundletitleforfilename}")
            bundle_logger.debug(f"[CB]....casedetails: {bundle_config.case_details}")
            bundle_logger.debug(f"[CB]....zip_timestamp: {zip_timestamp}")
            bundle_logger.debug(f"[CB]....input_files: {input_files}")
            bundle_logger.debug(f"[CB]....index_file: {index_file}")
            bundle_logger.debug(f"[CB]....toc_file_path: {toc_file_path}")
            bundle_logger.debug(f"[CB]....coversheet_path: {coversheet_path}")
            bundle_logger.debug(f"[CB]....temp_dir: {temp_dir}")
            bundle_logger.debug(f"[CB]....tmp_output_file: {tmp_output_file}")
            
            try:
                zip_filepath = create_zip_file(
                    bundletitleforfilename, 
                    bundle_config.case_details[2], 
                    zip_timestamp, 
                    input_files, 
                    index_file, 
                    toc_file_path, 
                    coversheet_path, 
                    temp_dir, 
                    tmp_output_file
                )
            except Exception as e:
                bundle_logger.error(f"[CB]..Error during create_zip_file: {e}")
                raise e
            if not os.path.exists(zip_filepath):
                bundle_logger.error(f"[CB]..Creating zip file unsuccessful: cannot locate expected ouput {zip_filepath}.")
                return
            else:
                bundle_logger.info(f"[CB]..Zip file created at {os.path.basename(zip_filepath)}")
        
        
        # Clean up temporary files
        bundle_logger.debug(f"[CB]Cleaning up temporary files:")
        for file in list_of_temp_files:
            if os.path.exists(file):
                bundle_logger.debug(f"[CB]..Deleting: {file}")
                try:
                    os.remove(file)
                    bundle_logger.debug(f"[CB]....deleted.")
                except Exception as e:
                    bundle_logger.info(f"[CB]....Info: could not delete temporary file {file}. Error: {e}")
            else: 
                bundle_logger.info(f"[CB]....Info: Temporary file {file} does not exist, nothing to clean up.")
            list_of_temp_files.remove(file)

        # Remove the handler to prevent duplicate logs
        remove_session_file_handler()
    return tmp_output_file, zip_filepath

def create_zip_file(
    bundle_title, 
    case_name, 
    timestamp, 
    input_files, 
    csv_path, 
    toc_path, 
    coversheet_path, 
    temp_dir, 
    tmp_output_file
    ):

    zip_filename = secure_filename(f"{bundle_title}{case_name}-Files-{timestamp}.zip")
    int_zip_filepath = os.path.join(temp_dir, zip_filename)
    bundle_logger.debug(f"[CZF]Creating zip file at {int_zip_filepath}")

    with zipfile.ZipFile(int_zip_filepath, 'w') as zipf:
    # Add input files to a subdirectory
        for file in input_files:
            zipf.write(file, os.path.join('input_files', os.path.basename(file)))
        # Add CSV index to the root directory
        if csv_path:
            zipf.write(csv_path, os.path.basename(csv_path))
        # Add TOC to the root directory
        if toc_path:
            zipf.write(toc_path, os.path.basename(toc_path))
        # Add coversheet to the root directory
        if coversheet_path:
            zipf.write(coversheet_path, os.path.basename(coversheet_path))
        # Add outputfile (whole bundle) to the root directory
        if tmp_output_file:
            zipf.write(tmp_output_file, os.path.basename(tmp_output_file))
    return int_zip_filepath


def main():
    parser = argparse.ArgumentParser(description="Merge PDFs with bookmarks and optional coversheet.")
    parser.add_argument("input_files", nargs="+", help="Input PDF files")
    parser.add_argument("-o", "--output_file", help="Output PDF file", default=None)
    parser.add_argument("-b", "--bundlename", help="Title of the bundle", default="Bundle")
    parser.add_argument("-c", "--casename", help="Name of case e.g. Smith v Jones & ors", default="")
    parser.add_argument("-n", "--claimno", help="Claim number",default="")
    parser.add_argument("-coversheet", help="Optional coversheet PDF file", default=None)
    parser.add_argument("-index", help="Optional CSV file with predefined index data", default=None)
    parser.add_argument("-csv_index", help="CSV index data as a string", default=None)
    parser.add_argument("-zip", help="Flag to indicate if a zip file should be created", action="store_true", default=False)    
    parser.add_argument("-confidential", help="Flag to indicate if bundle is confidential", action="store_true", default=False)
    args = parser.parse_args()

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    input_files = args.input_files
    output_file = secure_filename(args.output_file) if args.output_file else secure_filename(f"{args.bundlename}-{timestamp}.pdf")
    coversheet = args.coversheet
    index_file = args.index
    casedetails=[args.bundlename, args.claimno, args.casename]
    csv_index = args.csv_index
    confidential_bool = args.confidential
    zip_bool = args.zip if args.zip else False

    
    create_bundle(
        input_files, 
        output_file, 
        coversheet, 
        csv_index, 
        casedetails, 
        index_file, 
        confidential_bool, 
        zip_bool)

if __name__ == "__main__":
    main()