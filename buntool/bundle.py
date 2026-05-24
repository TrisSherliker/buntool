# TODO
##############################################
##  BUGS
##############################################
# GENERAL
# - [x] make sure temp files delete
# - [x] add cron job to server to cleanup every few mins
# - [x] draft docx indexing
# - [x] responsive index overflows at some breakpoints
# - [ ] Possible niggle: handling of filenames with multiple `.` characters in names, or none of them. Is the code depending too much on there being
# an extension to the file at all?
##############################################
##  ROADMAP
##############################################
# Technical improvements
#   - [ ] General error handling in functions of app.py (file saving, dir creation, csv reading/writing)
#   - [ ] Validation of all strings passed through frontend
#   - [ ] validation of csv data passed from frontend, check headers and columns.
# Features
#   - [ ] Add ability to offset page numbers (start at N)
#   - [ ] Convenience for sections: Add section header, spawn upload area for that section, helps to organise files
#   - [ ] Add a write-metadata function: https://pypdf.readthedocs.io/en/stable/user/metadata.html
#   - [ ] ability to reload state (via zip import).
#       This would require --
#       - [ ] save option state (as json?)
#       - [ ] save csv
#       - [ ] save input files
#       - [ ] allow upload of zip which is then parsed out into options/csv/inputfiles
#       - [ ] the data structure point above will help with this, because then it just becomes a matter of setting variables from the lines of the
# file.
# PDF manipulation
import argparse
import csv
import functools
import gc
import io
import logging
import os

# General
import re
import textwrap
import threading
import zipfile
from collections.abc import Sequence
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from datetime import datetime
from itertools import count, groupby
from pathlib import Path
from typing import Any, Literal, NamedTuple, cast

import pdfplumber

from buntool.toc_detector import ParseTocLineReturn, TOCDetector

try:
    from memory_profiler import profile  # type: ignore
except ImportError:

    def profile(func):
        return func


# reportlab stuff
import reportlab.rl_config
from colorlog import ColoredFormatter
from pdfplumber.page import Page as PlumberPage
from pdfplumber.pdf import PDF
from pikepdf import Array, Dictionary, Name, OutlineItem, Pdf, Rectangle
from pikepdf._core import Page
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, StyleSheet1, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    Flowable,
    PageBreak,
    Paragraph,  # Already imported
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.rl_config import defaultPageSize
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

# custom
from buntool.bundle_config import BundleConfig, BundleConfigParams
from buntool.headers import HEADERS
from buntool.makedocxindex import DocxConfig, create_toc_docx
from buntool.textwrap_custom import dedent_and_log

# Set globals
PAGE_WIDTH = defaultPageSize[0]  # reportlab page sizes used in more than one function

# Constants
MIN_CSV_COLUMNS_WITH_SECTION = 4
MIN_CSV_COLUMNS_NO_SECTION = 3
MIN_TOC_ENTRY_FIELDS = 3
LINK_OFFSET_MIN = -5
LINK_OFFSET_MAX = 50
LINK_MATCH_TOLERANCE = 2
PAGE_NUMBER_INDEX = 3

CPU_COUNT = os.cpu_count()

bundle_logger = logging.getLogger("bundle_logger")

thread_local = threading.local()


def init_worker(counter):
    """Initializer for ThreadPoolExecutor workers to assign a unique ID."""
    thread_local.worker_id = next(counter)


class ThreadIdFormatter(ColoredFormatter):
    """A custom logger formatter to automatically add a worker thread ID to log messages."""

    def __init__(self, fmt=None, datefmt=None, style: Literal["%", "{", "$"] = "%", log_colors=None, reset=True):
        super().__init__(fmt, datefmt, style, log_colors, reset)

    def format(self, record):
        # If the log record is from a worker thread, prepend its ID.
        # First, let the parent ColoredFormatter format the record, including colors.
        formatted_message = super().format(record)
        # Then, if a worker ID exists, prepend it to the already formatted message.
        if hasattr(thread_local, "worker_id"):
            return f"[🧵-{thread_local.worker_id}] {formatted_message}"
        return formatted_message


def configure_logger(bundle_config: BundleConfig, session_id=None):
    """Configure a logger for the bundling process.

    where session_id is an 8-digit hex number.
    Since the temp files are deleted in production,
    logs are to be stored in a seprate file /tmp/logs.
    """
    # Suppress noisy warnings from pdfminer, which is used by pdfplumber
    logging.getLogger("pdfminer.pdfinterp").setLevel(logging.ERROR)
    logging.getLogger("pdfminer.pdfpage").setLevel(logging.ERROR)
    logging.getLogger("pdfminer.pdffont").setLevel(logging.ERROR)

    logs_dir = bundle_config.logs_dir if bundle_config else "logs"

    if not Path(logs_dir).exists():
        Path(logs_dir).mkdir(parents=True)
    # Configure logging
    logger = logging.getLogger("bundle_logger")

    # Clear existing handlers to prevent duplicate logs on subsequent runs
    if bundle_logger.hasHandlers():
        for handler in bundle_logger.handlers:
            handler.close()
        bundle_logger.handlers.clear()

    bundle_logger.setLevel(logging.DEBUG)
    bundle_logger.propagate = False
    # Use the new custom formatter
    log_colors_config = {"DEBUG": "cyan", "INFO": "green", "WARNING": "yellow", "ERROR": "red", "CRITICAL": "red,bg_white"}

    # Formatter for file output (no colors)
    file_formatter = ThreadIdFormatter("%(asctime)s-%(levelname)s-[BUN]: %(message)s")
    # Formatter for console output (with colors)
    console_formatter = ThreadIdFormatter(
        "%(log_color)s%(asctime)s - %(levelname)s - [BUN]: %(message)s%(reset)s",
        log_colors=log_colors_config,
    )
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    bundle_logger.addHandler(console_handler)

    if not session_id:
        session_id = datetime.now().strftime("%Y%m%d%H%M%S")  # fallback
    # logs path = buntool_timestamp.log:
    logs_path = Path(logs_dir) / f"buntool_{session_id}.log"
    session_file_handler = logging.FileHandler(logs_path)
    session_file_handler.setLevel(logging.DEBUG)  # Set level for file handler
    session_file_handler.setFormatter(file_formatter)  # Use the file formatter
    logger.addHandler(session_file_handler)
    return bundle_logger


def parse_the_date(date, bundle_config):
    """Take a date input in YYYY-MM-DD format and format it.

    formats it according to user preferences from the following
    styles depending on state of date_setting:
    - YYYY-MM-DD
    - DD-MM-YYYY
    - MM-DD-YYYY
    - uk_longdate
    - us_longdate
    - uk_abbreviated_date
    - us_abbreviated_date
    or if setting is hide_date, don't do anything
    """
    if bundle_config.date_setting == "hide_date":
        return ""
    # check if date matches the expected format
    if not re.match(r"\d{4}-\d{2}-\d{2}", date):
        bundle_logger.error(f"[PTD] Error: Date does not match expected format: {date}")
        return date
    try:
        parsed_date = datetime.strptime(date, "%Y-%m-%d")

        formats = {
            "YYYY-MM-DD": "%Y-%m-%d",
            "DD-MM-YYYY": "%d/%m/%Y",
            "MM-DD-YYYY": "%m/%d/%Y",
            "uk_longdate": "%d %B %Y",
            "us_longdate": "%B %d, %Y",
            "uk_abbreviated_date": "%d %b %Y",
            "us_abbreviated_date": "%b %d, %Y",
        }

        return parsed_date.strftime(formats[bundle_config.date_setting])
    except KeyError:
        bundle_logger.exception(f"[PTD] Error: Unknown date setting: {bundle_config.date_setting}")
        return date


def load_index_data(csv_index, bundle_config):
    """Ingest a CSV of table-of-contents entries and return a dictionary.

    a dictionary of the data (in the create bundle function, saved as
    index_data). The resulting dictionary is the template for the whole
    bundle creation.
    The CSV is typically generated by the frontend and is expected to be
    properly formatted as follows:
        Headings:
                filename, userdefined_title, date, section
                where 'section' is a section-marker flag.
        for normal input files:
                [filename, title, date, 0]
        for section breaks:
                [SECTION, section_name,,1]
    There are some fallbacks in place in case the data is missing, but
     this should not happen. They are there mainly for testing purposes
     when using the code via CLI.
    """
    index_data = {}
    bundle_logger.debug(f"[LID]Loading index data from {csv_index}")
    with Path(csv_index).open(newline="") as f:
        reader = csv.reader(f)
        next(reader)  # Skip header row
        for row in reader:
            if len(row) >= MIN_CSV_COLUMNS_WITH_SECTION:
                filename, userdefined_title, raw_date, section = row
                formatted_date = parse_the_date(raw_date, bundle_config)
                # Store filename as provided by frontend
                index_data[filename] = (userdefined_title, formatted_date, section)
            elif len(row) >= MIN_CSV_COLUMNS_NO_SECTION:
                filename, userdefined_title, raw_date = row
                formatted_date = parse_the_date(raw_date, bundle_config)
                index_data[filename] = (userdefined_title, formatted_date, "")
            else:
                filename, userdefined_title = row
                bundle_logger.debug(f"Reading file entry: |{filename}|")
                index_data[filename] = (userdefined_title, "", "")
    bundle_logger.debug(f"[LID]..Loaded index data with {len(index_data)} entries:")
    for k, v in index_data.items():
        bundle_logger.debug(f"[LID]....Key: |{k}| -> Value: {v}")
    return index_data


def get_pdf_creation_date(pdf: Pdf):
    """Extracts the creation date from a PDF file.

    This is purely a fallback function in case the
    user-supplied (or frontend-supplied) information is missing a date.
    """
    try:
        creation_date = pdf.docinfo.get("/CreationDate")
        if creation_date:
            # Convert to string if it's a pikepdf.String object
            creation_date_str = str(creation_date)
            # Extract date in the format D:YYYYMMDDHHmmSS
            date_str = creation_date_str[2:10]
            date_obj = datetime.strptime(date_str, "%Y%m%d")
            return date_obj.strftime("%d.%m.%Y")
    except Exception:
        bundle_logger.exception(f"[GPCD]Error extracting creation date from {pdf.filename}")
        return None


class TocEntryParams(NamedTuple):
    item: tuple
    page_counts: dict
    pdf: Pdf
    tab_counts: count
    section_counts: count


def _generate_toc_entry(toc_entry_params: TocEntryParams) -> tuple | None:
    """Generate a single TOC entry tuple for a given item from the index."""
    item = toc_entry_params.item
    page_counts = toc_entry_params.page_counts
    tab_counts = toc_entry_params.tab_counts
    section_counts = toc_entry_params.section_counts
    pdf = toc_entry_params.pdf

    _, (title, _, section) = item

    if section == "1":
        section_num = next(section_counts)
        return (f"SECTION_BREAK_{section_num}", title)

    # It's a file entry
    tab_number = f"{next(tab_counts):03}."
    current_page_start = page_counts["total"]

    num_pages = len(pdf.pages)
    page_counts["total"] += num_pages

    entry_title = title
    entry_date = item[1][1]  # The formatted date from the index data

    if entry_date == "Unknown":
        entry_date = get_pdf_creation_date(pdf) or "Unknown"

    return (tab_number, entry_title, entry_date, current_page_start)


def _get_page_index_from_dest(pdf: Pdf, dest) -> int:
    """Safely get the page index from a destination."""
    page_to_find = None
    if isinstance(dest, Page):
        page_to_find = dest
    elif isinstance(dest, (list, Array)) and dest:
        page_obj_ref = dest[0]
        # It's most likely a pikepdf.Object representing the page dictionary
        if hasattr(page_obj_ref, "get") and page_obj_ref.get("/Type") == Name.Page:
            page_to_find = Page(page_obj_ref)

    if page_to_find:
        try:
            return pdf.pages.index(page_to_find)
        except ValueError:
            return -1

    if isinstance(dest, int):
        return dest

    return -1


def _extract_links_from_page(src_pdf: Pdf, page_num: int) -> list[tuple[float, int]]:
    """Extract links from a specific page of the PDF."""
    links = []
    try:
        pike_page = src_pdf.pages[page_num - 1]
        annots = pike_page.get("/Annots")
        if not annots:
            return []

        # Ensure annots is treated as iterable (Pylance fix)
        if not isinstance(annots, (list, Array)):
            return []

        page_height = float(pike_page.mediabox[3])

        for annot in cast(list[Dictionary], annots):
            if annot.get("/Subtype") != "/Link":
                continue

            dest = annot.get("/Dest")
            action = annot.get("/A")
            dest_idx = -1

            if dest:
                dest_idx = _get_page_index_from_dest(src_pdf, dest)
            elif action and action.get("/S") == "/GoTo":
                d = action.get("/D")
                if d:
                    dest_idx = _get_page_index_from_dest(src_pdf, d)

            if dest_idx == -1:
                continue

            rect = annot.get("/Rect")
            if not rect:
                continue

            # Calculate center Y (from top)
            center_y = page_height - (float(rect[3]) + float(rect[1])) / 2
            links.append((center_y, dest_idx))

        links.sort(key=lambda x: x[0])
    except Exception:
        bundle_logger.exception(f"Error extracting links from page {page_num}")
    return links


def _resolve_toc_entry_dest(entry: ParseTocLineReturn, page_links: dict[int, list[tuple[float, int]]], state: dict) -> int:
    """Resolve the destination page index for a TOC entry."""
    dest_page_index = -1

    if entry.page is None:
        return -1

    links = page_links.get(entry.toc_page_num, [])
    best_link_idx = -1

    if links:
        if not state["offset_calculated"]:
            for i, (_, l_dest) in enumerate(links):
                diff = l_dest - entry.page
                if LINK_OFFSET_MIN <= diff <= LINK_OFFSET_MAX:
                    state["page_offset"] = diff
                    state["offset_calculated"] = True
                    dest_page_index = l_dest
                    best_link_idx = i
                    break
        else:
            expected_dest = entry.page + state["page_offset"]
            for i, (_, l_dest) in enumerate(links):
                if abs(l_dest - expected_dest) <= LINK_MATCH_TOLERANCE:
                    dest_page_index = l_dest
                    best_link_idx = i
                    break

    if best_link_idx != -1:
        page_links[entry.toc_page_num] = links[best_link_idx + 1 :]

    if dest_page_index == -1:
        dest_page_index = entry.page + state["page_offset"] if entry.page else -1

    return dest_page_index


def generate_bookmarks_from_toc_entries(src_pdf: Pdf, toc_entries: list[ParseTocLineReturn]) -> list[tuple[str, int, int]]:
    """Generate bookmarks from TOC entries, resolving destinations via links."""
    max_src_pages = len(src_pdf.pages)

    # 1. Collect all links from the relevant TOC pages
    toc_pages = sorted({e.toc_page_num for e in toc_entries})
    page_links = {page_num: _extract_links_from_page(src_pdf, page_num) for page_num in toc_pages}

    # 2. Match entries to links
    state = {"page_offset": 0, "offset_calculated": False}

    # bookmarks = []
    # for entry in toc_entries:
    #     dest_page_index = _resolve_toc_entry_dest(entry, page_links, state)
    #     # Clamp to valid range to prevent IndexError later
    #     if dest_page_index >= max_src_pages:
    #         bundle_logger.warning(
    #             f"Bookmark '{entry.title}' points to page {dest_page_index} which is out of bounds (max {max_src_pages})."
    #             f"Treating as section header.")
    #         dest_page_index = -1
    #     bookmarks.append((entry.title, dest_page_index, entry.indent_level))

    bookmarks = [
        (entry.title, dest_page_index, entry.indent_level)
        for entry in toc_entries
        if (dest_page_index := _resolve_toc_entry_dest(entry, page_links, state)) < max_src_pages
    ]

    # 3. Fixup section breaks (dest_page_index == -1)
    # Point them to the destination of the next valid child
    for i in range(len(bookmarks) - 1, -1, -1):
        title, page, level = bookmarks[i]
        if page == -1:
            # Find next item
            next_page = -1
            for j in range(i + 1, len(bookmarks)):
                if bookmarks[j][1] != -1:
                    next_page = bookmarks[j][1]
                    break

            # If still -1 (end of list), use last known good page? Or 0?
            if next_page == -1 and i > 0:
                # Try previous? No, section header should point forward.
                pass

            bookmarks[i] = (title, max(0, next_page), level)

    if bookmarks:
        bundle_logger.info(f"Generated {len(bookmarks)} bookmarks from TOC entries.")
    return bookmarks


def extract_bookmarks(pdf: Pdf, pdf_name_for_logging: str) -> list[tuple[str, int, int]]:
    """Reads a PDF's bookmarks and returns them as a list of (title, page_number, level) tuples."""
    extracted_bookmarks = []
    try:
        if not pdf.Root.get("/Outlines"):
            bundle_logger.debug(f" - No bookmarks found in '{pdf_name_for_logging}'.")
            return []

        def _flatten_bookmarks(items: list[OutlineItem], level=0):
            """A generator to recursively yield all bookmarks as a flat list."""
            for item in items:
                if item.destination is not None:
                    yield item, level
                if item.children:
                    yield from _flatten_bookmarks(item.children, level + 1)

        with pdf.open_outline() as outline:
            extracted_bookmarks = [
                (item.title, page_index, level)
                for item, level in _flatten_bookmarks(outline.root)
                if (page_index := _get_page_index_from_dest(pdf, item.destination)) != -1
            ]

        bundle_logger.info(f"Found {len(extracted_bookmarks)} bookmarks in {pdf_name_for_logging}")
        for title, page, level in extracted_bookmarks:
            bundle_logger.debug(f" - Bookmark '{title}' at level {level} points to page {page}")
    except Exception:
        bundle_logger.exception(f"Error reading bookmarks from {pdf_name_for_logging}")
    return extracted_bookmarks


def is_buntool_bundle(plumber_pdf: PDF, start_page: int = 0) -> int:
    """Checks if a pdfplumber PDF object is a bundle by looking for a TOC."""

    def is_buntool_toc_page(page: PlumberPage) -> bool:
        table = page.extract_table()
        if table and table[0]:
            return table[0][0] == " ".join(HEADERS)
        return False

    toc_pages_number = 0
    for page in plumber_pdf.pages[start_page:]:
        if is_buntool_toc_page(page):
            toc_pages_number += 1
        else:
            break
    return toc_pages_number


@profile
def _process_pdf_file(file_storage: FileStorage) -> dict:  # file_storage is a werkzeug.FileStorage
    """Worker function to process a single PDF file in a thread.

    Opens the file with both pikepdf and pdfplumber to perform all
    necessary analysis and preparation for merging.
    """
    src_pdf = None
    try:
        bundle_logger.debug(f"Processing file {file_storage.filename}")
        # Ensure the stream is at the beginning before reading
        file_storage.stream.seek(0)
        src_pdf = Pdf.open(cast(io.BytesIO, file_storage.stream))
        file_storage.stream.seek(0)  # Rewind again for pdfplumber
        with pdfplumber.open(cast(io.BytesIO, file_storage.stream)) as plumber_pdf:
            sub_bookmarks = extract_bookmarks(src_pdf, cast(str, file_storage.filename))

            toc_page_count = is_buntool_bundle(plumber_pdf)

            # If no bookmarks found, try to detect TOC and generate them
            if toc_page_count == 0 or not sub_bookmarks:
                td = TOCDetector(logger=bundle_logger)
                toc_entries = td.get_full_toc(plumber_pdf)
                if toc_entries:
                    if toc_page_count == 0:
                        toc_page_count = len({e.toc_page_num for e in toc_entries})
                    if not sub_bookmarks:
                        bundle_logger.info(f"Detected {len(toc_entries)} TOC entries. Generating bookmarks.")
                        sub_bookmarks = generate_bookmarks_from_toc_entries(src_pdf, toc_entries)

            is_nested_bundle = toc_page_count

    except Exception as e:
        bundle_logger.exception(f"Error processing file {file_storage.filename}")
        return {"error": str(e), "filename": file_storage.filename}
    else:
        return {
            "is_bundle": is_nested_bundle,
            "sub_bookmarks": sub_bookmarks,
            "filename": file_storage.filename,
        }
    finally:
        if src_pdf:
            src_pdf.close()


@profile
def merge_pdfs_create_toc_entries(input_files: list[FileStorage], index_data: dict):
    """Merge PDFs and create table of contents entries.

    index_data is the roadmap for the bundle creation.
    1. Merge the PDFs in input_files into a single PDF at output_file.
    2. Create a table of contents from the index_data and return it.
    The table of contents is based on the index_data and the structural
    results of merging the files together.
     It outputs a list of tuples, toc_entries each containing:
        - tab number
        - title
        - date
        - page number
    """
    page_counts = {"total": 0}  # Use a mutable dict to track page count across list comprehension
    tab_counts = count(1)
    section_counts = count(1)
    toc_entries = []
    all_sub_bookmarks: list = []
    is_bundle_map = {}  # To store results of is_bundle checks
    filename_to_results = {}
    filename_to_filestorage = {f.filename: f for f in input_files}

    with ThreadPoolExecutor(max_workers=CPU_COUNT, initializer=init_worker, initargs=(count(1),)) as executor:
        # Map filenames from index_data to actual file paths
        files_to_process = {
            file
            for filename in index_data
            if index_data[filename][2] != "1" and (file := next((f for f in input_files if f.filename == filename), None))
        }

        # Submit all PDF processing tasks to the executor
        future_to_file = {executor.submit(_process_pdf_file, file): file for file in files_to_process}

        for future in as_completed(future_to_file):
            result = future.result()
            if "error" not in result:
                filename_to_results[result["filename"]] = result

    # Now, assemble the results sequentially
    final_pdf = Pdf.new()
    for filename, (title, _, section) in index_data.items():
        if section == "1":
            toc_entries.append((f"SECTION_BREAK_{next(section_counts)}", title))
            continue

        result = filename_to_results.get(filename)
        file_storage = filename_to_filestorage.get(filename)

        if not result or not file_storage:
            bundle_logger.warning(f"File {filename} not found or failed to process. Skipping.")
            continue

        # Re-open the PDF just for merging to keep memory usage low
        file_storage.stream.seek(0)
        with Pdf.open(cast(io.BytesIO, file_storage.stream)) as src_pdf:
            entry = _generate_toc_entry(
                TocEntryParams(
                    item=(filename, index_data[filename]), page_counts=page_counts, pdf=src_pdf, tab_counts=tab_counts, section_counts=section_counts
                )
            )
            new_toc_entries = [entry] if entry else []
            toc_entries.extend(new_toc_entries)
            if entry and (result["sub_bookmarks"] or result.get("is_bundle", 0) > 0):
                # Adjust bookmark page numbers with the current offset
                start_page = entry[3]
                adjusted_sub_bookmarks = []
                if result["sub_bookmarks"]:
                    adjusted_sub_bookmarks = [(title, page + start_page, level) for title, page, level in result["sub_bookmarks"]]

                if result.get("is_bundle", 0) > 0:
                    has_index = False
                    if adjusted_sub_bookmarks:
                        first_bm = adjusted_sub_bookmarks[0]
                        if first_bm[1] == start_page and first_bm[0].lower() in ("index", "table of contents", "contents"):
                            has_index = True

                    if not has_index:
                        adjusted_sub_bookmarks.insert(0, ("Index", start_page, 0))

                all_sub_bookmarks.append({"parent_title": entry[1], "tab": entry[0], "bookmarks": adjusted_sub_bookmarks})

            final_pdf.pages.extend(src_pdf.pages)
            is_bundle_map[filename] = result["is_bundle"]

    return final_pdf, toc_entries, all_sub_bookmarks, is_bundle_map, page_counts["total"]


def _create_bookmark_item(entry, destination_page, bundle_config: BundleConfig):
    """Creates a single OutlineItem for a TOC entry based on bookmark settings."""
    tab_number, title, date, _ = entry
    # destination_page is passed in
    setting = bundle_config.bookmark_setting

    if setting == "tab-title":
        label = f"{tab_number} {title}"
    elif setting == "tab-title-date":
        label = f"{tab_number} {title} ({date})"
    elif setting == "tab-title-page":
        label = f"{tab_number} {title} [pg.{1 + destination_page}]"
    elif setting == "tab-title-date-page":
        label = f"{tab_number} {title} ({date}) [pg.{1 + destination_page}]"
    else:
        bundle_logger.error(f"[ABTP]Error: Unknown bookmark_setting: {setting}")
        # Fallback to the default bookmark style
        label = f"{tab_number} {title}"

    return OutlineItem(label, destination_page)


def _add_sub_bookmarks(parent_bookmark: OutlineItem, bookmarks_to_add, length_of_frontmatter, max_pages):
    """Reconstructs and adds a hierarchical group of sub-bookmarks under a parent."""
    level_map = {0: parent_bookmark}
    for title, page_num, level in bookmarks_to_add:
        # The level from the source PDF is 0-based for its own root.
        # We need to add it under the parent_bookmark, so its effective level is level + 1.
        effective_level = level + 1

        # Find the correct parent for the current item's level.
        # The parent is at the preceding level.
        parent_for_current_item = level_map.get(effective_level - 1)

        if parent_for_current_item:
            final_page_num = page_num + length_of_frontmatter
            if final_page_num >= max_pages:
                final_page_num = max_pages - 1
            new_item = OutlineItem(title, final_page_num)
            parent_for_current_item.children.append(new_item)
            # Store this new item in the map at its own level,
            # so it can become a parent for subsequent, more deeply nested items.
            level_map[effective_level] = new_item
        else:
            bundle_logger.warning(f"Could not find parent for sub-bookmark '{title}' at level {level}.")


def _process_all_sub_bookmarks(main_bookmark_map, all_sub_bookmarks, length_of_frontmatter, max_pages):
    """Iterates through all sub-bookmark groups and adds them to the main outline map."""
    if not all_sub_bookmarks:
        return

    bundle_logger.debug(f"Adding {len(all_sub_bookmarks)} sub-bookmarks to the final PDF.")
    for sub_bookmark_group in all_sub_bookmarks:
        parent_title = sub_bookmark_group["parent_title"]
        bookmarks_to_add = sub_bookmark_group["bookmarks"]
        tab = sub_bookmark_group["tab"]

        # Find the parent OutlineItem in the main TOC
        parent_bookmark = main_bookmark_map.get(f"{tab} {parent_title}")
        if parent_bookmark:
            _add_sub_bookmarks(parent_bookmark, bookmarks_to_add, length_of_frontmatter, max_pages)


def add_bookmarks_to_pdf(pdf: Pdf, toc_entries: list, length_of_frontmatter: int, bundle_config: BundleConfig):
    """Add outline entries ('bookmarks') to a PDF for navigation..

    It reads the digested toc_entries and adds an outline item for each.
    Due to loose naming conventions this can be confusing, so to be clear:
    - It does not bookmark the index itself (that's the job of bookmark_the_index).
    - It does not add on-page hyperlinks (that's add_hyperlinks)
    The content of the entry will depend on bookmark_setting from options:
        "tab-title" (default)
        "tab-title-date"
        "tab-title-page"
        "tab-title-date-page
    """
    with pdf.open_outline() as outline:
        max_pages = len(pdf.pages)
        bundle_logger.info(f"[ABTP] Adding bookmarks. PDF has {max_pages} pages. Frontmatter length: {length_of_frontmatter}")
        current_section_bookmark = None
        main_bookmark_map = {}

        for i, entry in enumerate(toc_entries):
            # Skip the header row if it's present in toc_entries
            if "tab" in str(entry[0]).lower() and "title" in str(entry[1]).lower():
                continue

            if "SECTION_BREAK" in entry[0]:
                dest_page = 0
                if i + 1 < len(toc_entries) and len(toc_entries[i + 1]) > PAGE_NUMBER_INDEX:
                    dest_page = toc_entries[i + 1][PAGE_NUMBER_INDEX] + length_of_frontmatter

                if dest_page >= max_pages:
                    bundle_logger.error(f"[ABTP] Section '{entry[1]}' destination {dest_page} exceeds max pages {max_pages}")
                    dest_page = max_pages - 1 if max_pages > 0 else 0

                current_section_bookmark = OutlineItem(entry[1], dest_page)
                outline.root.append(current_section_bookmark)
            else:
                # This is a file entry.
                dest_page = entry[PAGE_NUMBER_INDEX] + length_of_frontmatter
                if dest_page >= max_pages:
                    bundle_logger.error(f"[ABTP] Entry '{entry[1]}' destination {dest_page} exceeds max pages {max_pages}")
                    dest_page = max_pages - 1 if max_pages > 0 else 0

                bookmark_item = _create_bookmark_item(entry, dest_page, bundle_config)
                main_bookmark_map[f"{entry[0]} {entry[1]}"] = bookmark_item
                if current_section_bookmark:
                    current_section_bookmark.children.append(bookmark_item)
                else:
                    outline.root.append(bookmark_item)

        # Now, add the sub-bookmarks under their correct parent in the main TOC
        _process_all_sub_bookmarks(main_bookmark_map, bundle_config.all_sub_bookmarks, length_of_frontmatter, max_pages)


def bookmark_the_index(pdf: Pdf, coversheet_pdf_obj: Pdf | None = None):
    """Adds an outline item for the index to an open PDF object."""
    with pdf.open_outline() as outline:
        coversheet_length = 0
        if coversheet_pdf_obj:
            coversheet_length = len(coversheet_pdf_obj.pages)

        # Add an outline item for "Index" linking to the first page (or after the coversheet).
        index_item = OutlineItem("Index", coversheet_length)
        outline.root.insert(0, index_item)
        log_msg = (
            f"coversheet is specified, outline item added for index at page {coversheet_length}"
            if coversheet_length > 0
            else "no coversheet specified, outline item added for index at page 0"
        )
        bundle_logger.debug(f"[BTI]{log_msg}")


def _get_toc_pdf_styles(date_setting, index_font_setting):
    """Determine styles and column widths for the TOC PDF."""
    if index_font_setting == "serif":
        main_font, bold_font, base_font_size = "Times-Roman", "Times-Bold", 12
    elif index_font_setting == "sans":
        main_font, bold_font, base_font_size = "Helvetica", "Helvetica-Bold", 12
    elif index_font_setting == "mono":
        main_font, bold_font, base_font_size = "Courier", "Courier-Bold", 10
    elif index_font_setting == "traditional":
        main_font, bold_font, base_font_size = "Charter_regular", "Charter_bold", 12
    else:  # default to Helvetica
        main_font, bold_font, base_font_size = "Helvetica", "Helvetica-Bold", 12

    if date_setting == "hide_date":
        date_col_hdr, date_col_width, title_col_width, page_col_width = "", 0, 11.5, 2.5
    elif date_setting in ("YYYY-MM-DD", "DD-MM-YYYY", "MM-DD-YYYY", "uk_abbreviated_date", "us_abbreviated_date"):
        date_col_hdr, date_col_width, title_col_width, page_col_width = "Date", 3.2, 9.8, 1.7
    elif date_setting in ("uk_longdate", "us_longdate"):
        date_col_hdr, date_col_width, title_col_width, page_col_width = "Date", 4.2, 8.8, 1.7
    else:
        date_col_hdr, date_col_width, title_col_width, page_col_width = "Date", 3.5, 9.5, 1.7

    return {
        "main_font": main_font,
        "bold_font": bold_font,
        "base_font_size": base_font_size,
        "date_col_hdr": date_col_hdr,
        "date_col_width": date_col_width,
        "title_col_width": title_col_width,
        "page_col_width": page_col_width,
    }


def _create_header(row_tuple, style_sheet):
    """Creates a single formatted row for the ReportLab table."""
    row = list(row_tuple)
    # It's a regular data row
    return [Paragraph(str(cell), style_sheet["header_style"]) for cell in row]


class CreateReportlabRowParams(NamedTuple):
    row_tuple: tuple
    date_col_hdr: str
    dummy: bool | None
    page_offset: int
    style_sheet: StyleSheet1
    headers: tuple


def _create_reportlab_row(create_reportlab_row_params: CreateReportlabRowParams):
    """Creates a single formatted row for the ReportLab table."""
    (row_tuple, date_col_hdr, dummy, page_offset, style_sheet, headers) = create_reportlab_row_params

    row = list(row_tuple)
    if all(x in row for x in headers):
        row[2] = date_col_hdr
        return [Paragraph(cell, style_sheet["main_style"]) for cell in row]
    if "SECTION_BREAK" in row[0]:
        row[0] = ""
        return [Paragraph(cell, style_sheet["bold_style"]) for cell in row]

    # It's a regular data row
    row[3] = 9999 if dummy else row[3] + page_offset
    return [Paragraph(str(cell), style_sheet["main_style"] if isinstance(cell, str) else style_sheet["main_style_right"]) for cell in row]


class TableDataParams(NamedTuple):
    toc_entries: list[tuple]
    date_col_hdr: str
    dummy: bool | None
    page_offset: int
    style_sheet: StyleSheet1
    bundle_title: str


def _build_reportlab_table_data(table_data_params: TableDataParams):
    """Build the data structure for the ReportLab table."""
    (toc_entries, date_col_hdr, dummy, page_offset, style_sheet, bundle_title) = table_data_params
    list_of_section_breaks = [rowidx for rowidx, current_row_tuple in enumerate(toc_entries) if "SECTION_BREAK" in current_row_tuple[0]]

    header_row = _create_header(HEADERS, style_sheet)
    reportlab_table_data = [
        _create_reportlab_row(CreateReportlabRowParams(row, date_col_hdr, dummy, page_offset, style_sheet, HEADERS)) for row in toc_entries
    ]

    reportlab_table_data.insert(0, header_row)  # Insert header row at the top

    # Adjust section break indices to account for the inserted header row.
    adjusted_section_breaks = [idx + 1 for idx in list_of_section_breaks]
    return reportlab_table_data, adjusted_section_breaks


def _setup_reportlab_styles(main_font: str, bold_font: str, base_font_size: int):
    """Set up ParagraphStyle objects for ReportLab."""
    script_dir = Path(__file__).parent
    static_dir = script_dir / "static"

    # Register non-standard fonts.
    if not pdfmetrics.getFont(main_font):
        pdfmetrics.registerFont(TTFont("Charter_regular", static_dir / "Charter_Regular.ttf"))
        pdfmetrics.registerFont(TTFont("Charter_bold", static_dir / "Charter_Bold.ttf"))
        pdfmetrics.registerFont(TTFont("Charter_italic", static_dir / "Charter_Italic.ttf"))
    reportlab.rl_config.warnOnMissingFontGlyphs = 0

    # Set up stylesheet for the various styles used..
    styleSheet = getSampleStyleSheet()

    header_style = ParagraphStyle(
        "header_style",
        parent=styleSheet["Normal"],
        fontName=bold_font,
        fontSize=base_font_size,
        leading=14,
        alignment=TA_CENTER,
    )
    main_style = ParagraphStyle(
        "main_style",
        parent=styleSheet["Normal"],
        fontName=main_font,
        fontSize=base_font_size,
        leading=14,
    )
    main_style_right = ParagraphStyle(
        "main_style_right",
        parent=styleSheet["Normal"],
        fontName=main_font,
        fontSize=base_font_size,
        leading=14,
        alignment=TA_RIGHT,
    )

    bold_style = ParagraphStyle(
        "bold_style",
        parent=styleSheet["Normal"],
        fontName=bold_font,
        fontSize=base_font_size,
        leading=14,
    )
    claimno_style = ParagraphStyle(
        "claimno_style",
        parent=styleSheet["Normal"],
        fontName=bold_font,
        fontSize=base_font_size,
        leading=14,
        alignment=TA_RIGHT,
    )
    bundle_title_style = ParagraphStyle(
        "bundle_title_style",
        parent=styleSheet["Normal"],
        fontName=bold_font,
        fontSize=base_font_size + 6,
        leading=14,
        alignment=TA_CENTER,
    )
    case_name_style = ParagraphStyle(
        "case_name_style",
        parent=styleSheet["Normal"],
        fontName=bold_font,
        fontSize=base_font_size + 2,
        leading=14,
        alignment=TA_CENTER,
    )

    styles = [
        header_style,
        main_style,
        main_style_right,
        bold_style,
        claimno_style,
        bundle_title_style,
        case_name_style,
        # footer_style,  # Footer style is not used in the TOC PDF
    ]

    for style in styles:
        styleSheet.add(ParagraphStyle(name=style.name, parent=style))

    return styleSheet


def _build_reportlab_doc_header(casedetails: dict, styleSheet: StyleSheet1, confidential: bool) -> list[Table]:
    """Builds the header tables (claim no, case name, bundle title) for the ReportLab TOC."""
    # Claim No table - top right
    claimno_table_data = [
        [Paragraph(casedetails.get("claim_no", ""), styleSheet["claimno_style"])],
    ]
    claimno_table = Table(
        data=claimno_table_data,
        colWidths=PAGE_WIDTH * 0.9,
        rowHeights=1.5 * cm,
    )
    claimno_table.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 50),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
            ]
        )
    )

    # Case name and bundle title table
    if not confidential:
        header_table_data = [
            ["", Paragraph(casedetails.get("case_name", ""), styleSheet["case_name_style"]), ""],
            ["", Paragraph(casedetails.get("bundle_title", ""), styleSheet["bundle_title_style"]), ""],
        ]
    else:
        header_table_data = [
            ["", Paragraph(casedetails.get("case_name", ""), styleSheet["case_name_style"]), ""],
            ["", Paragraph(f'<font color="red">CONFIDENTIAL</font> {casedetails.get("bundle_title", "")}', styleSheet["bundle_title_style"]), ""],
        ]
    header_table = Table(header_table_data, colWidths=[PAGE_WIDTH / 8, PAGE_WIDTH * (6 / 8), PAGE_WIDTH / 8])
    header_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("ALIGN", (2, 0), (2, 0), "RIGHT"),
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("SIZE", (0, 0), (-1, -1), 10),
                ("LINEBELOW", (1, 1), (1, 1), 1, colors.black),
                ("LINEABOVE", (1, 1), (1, 1), 1, colors.black),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
            ]
        )
    )
    return [claimno_table, header_table]


def _build_reportlab_main_table(table_data, list_of_section_breaks, col_widths):
    """Builds and styles the main TOC table for ReportLab."""
    toc_table = Table(table_data, colWidths=col_widths, repeatRows=1, cornerRadii=(5, 5, 0, 0))
    style_commands = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.darkgray),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("LINEBELOW", (0, 0), (-1, 0), 1, colors.black),
        ("ALIGNMENT", (0, 0), (-1, 0), "CENTRE"),
        ("FONTSIZE", (0, 0), (-1, 0), 12),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
        ("LINEBELOW", (0, 1), (-1, -1), 0.3, colors.black),
    ]

    section_styles = [("BACKGROUND", (0, int(row)), (-1, int(row)), colors.lightgrey) for row in list_of_section_breaks]
    style_commands.extend(section_styles)

    toc_table.setStyle(TableStyle(style_commands))
    return toc_table


@profile
def create_toc_pdf_reportlab(toc_entries, bundle_config: BundleConfig, options: dict) -> tuple[io.BytesIO, int]:
    """Generate a table of contents PDF using ReportLab."""
    casedetails = bundle_config.case_details
    styles = _get_toc_pdf_styles(options.get("date_setting"), bundle_config.index_font)
    main_font = styles["main_font"]
    bold_font = styles["bold_font"]
    base_font_size = styles["base_font_size"]
    date_col_hdr = styles["date_col_hdr"]
    date_col_width = styles["date_col_width"]
    title_col_width = styles["title_col_width"]
    page_col_width = styles["page_col_width"]

    page_offset = 1 + (0 if options.get("dummy") else bundle_config.expected_length_of_frontmatter)
    styleSheet = _setup_reportlab_styles(main_font, bold_font, base_font_size)

    buffer = io.BytesIO()
    reportlab_pdf = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=1.5 * cm, leftMargin=1.5 * cm, topMargin=1 * cm, bottomMargin=1.5 * cm)

    # Build header elements
    header_elements = _build_reportlab_doc_header(casedetails, styleSheet, options.get("confidential", False))

    # Build main TOC table
    reportlab_table_data, list_of_section_breaks = _build_reportlab_table_data(
        TableDataParams(toc_entries, date_col_hdr, options.get("dummy"), page_offset, styleSheet, casedetails.get("bundle_title", ""))
    )
    col_widths = [1.3 * cm, title_col_width * cm, date_col_width * cm, page_col_width * cm]
    toc_table = _build_reportlab_main_table(reportlab_table_data, list_of_section_breaks, col_widths)

    # Now, build the pdf:
    elements: Sequence[Flowable] = list(header_elements + [Spacer(1, 1 * cm), toc_table])

    def _get_coversheet_length(coversheet_path: Path) -> int:
        """Safely get the number of pages in a coversheet PDF."""
        if not coversheet_path.exists():
            return 0
        try:
            with Pdf.open(coversheet_path) as coversheet_pdf:
                return len(coversheet_pdf.pages)
        except Exception:
            bundle_logger.exception(f"Could not open coversheet at {coversheet_path} to determine length.")
            return 0

    def _create_toc_footer_config(bundle_config: BundleConfig) -> functools.partial:
        """Creates a partial function for the TOC footer with the correct page offset."""
        length_of_coversheet = _get_coversheet_length(bundle_config.temp_dir / "coversheet.pdf")
        return functools.partial(reportlab_footer_config, bundle_config=bundle_config, page_offset_override=length_of_coversheet)

    if not options.get("roman_numbering"):
        toc_footer_config = _create_toc_footer_config(bundle_config)
        reportlab_pdf.build(elements, onFirstPage=toc_footer_config, onLaterPages=toc_footer_config)
    else:
        reportlab_pdf.build(elements)

    buffer.seek(0)
    return buffer, reportlab_pdf.page


def generate_footer_pages_reportlab(filename, num_pages, bundle_config):
    """Generate a PDF with N blank pages, using onFirstPage and onLaterPages callbacks.

    Args:
        filename (str): The name of the output PDF file.
        num_pages (int): Number of blank pages to create.
        onFirstPage (callable): Callback for the first page.
        onLaterPages (callable): Callback for subsequent pages.
        bundle_config: configuration object.

    """
    bundle_logger.debug(f"[GFP]Generating {num_pages} blank pages in {filename}")
    # Create the document
    # pylint: disable=E1123
    doc = SimpleDocTemplate(
        str(filename),
        pagesize=A4,
    )
    # ReportLab protects against infinite loops by checking whether or not a
    # page has content at build time, and terminates after 10 pages without
    # content. It doesn't count footer content as content. So, it breaks when
    # generating footer-only pages.
    # Workaround: Since reportlab defines 'content' in this sense  as anything
    # which is a flowable, a workaround is to add an invisible flowable to each page.
    annoying_blank_flowable = Paragraph("")

    # Prepare blank pages with PageBreaks
    story: list[Flowable] = [item for _ in range(num_pages) for item in (annoying_blank_flowable, PageBreak())]

    # Build the document with the footer config:
    footer_config_with_bundle = functools.partial(reportlab_footer_config, bundle_config=bundle_config)
    doc.build(story, onFirstPage=footer_config_with_bundle, onLaterPages=footer_config_with_bundle)


def reportlab_footer_config(canvas: Canvas, _doc, bundle_config: BundleConfig, page_offset_override: int | None = None):
    """Configure the footer for ReportLab documents.

    the other reportlab functions during their build process.
    It's not used directly, and since it's internal to ReportLab,
    it's easier to operate on global variables here.
    """
    length_of_frontmatter_offset = page_offset_override if page_offset_override is not None else (bundle_config.expected_length_of_frontmatter or 0)
    total_number_of_pages = bundle_config.total_number_of_pages if bundle_config.total_number_of_pages else 0
    page_num_alignment = bundle_config.page_num_align if bundle_config.page_num_align else None
    page_num_font = bundle_config.footer_font if bundle_config.footer_font else None
    page_numbering_style = bundle_config.page_num_style if bundle_config.page_num_style else None
    footer_prefix = bundle_config.footer_prefix if bundle_config.footer_prefix else ""

    boldness = "bold"

    options = ["serif", "sans", "mono", "traditional", "helvetica"]

    regular = ["Times-Roman", "Helvetica", "Courier", "Charter_regular", "Helvetica"]
    bold = ["Times-Bold", "Helvetica-Bold", "Courier-Bold", "Charter_bold", "Helvetica-Bold"]

    fonts = {
        "options": options,
        "regular": regular,
        "bold": bold,
    }

    canvas.saveState()

    footer_base_font_size = 16
    if page_num_font in fonts["options"]:
        footer_font = fonts[boldness][options.index(page_num_font)]
    else:
        bundle_logger.warning(f"[MPNP]..Unsupported font {page_num_font} for page numbers, defaulting to Times-Roman")
        footer_font = "Times-Roman"
    canvas.setFont(footer_font, footer_base_font_size)

    def _get_page_number_string(style, page_num, offset, total_pages):
        """Get formatted page number string based on style."""
        current_page = page_num + offset

        style_formats = {
            "x": str(current_page),
            "x_of_y": f"{page_num} of {total_pages}",
            "page_x": f"Page {current_page}",
            "page_x_of_y": f"Page {current_page} of {total_pages}",
            "x_slash_y": f"{current_page} / {total_pages}",
        }
        return style_formats.get(style, f"Page {current_page}")

    # Get the page number string
    page_number_str = _get_page_number_string(page_numbering_style, canvas.getPageNumber(), length_of_frontmatter_offset, total_number_of_pages)

    # Build the complete footer data string in one assignment
    footer_data = f"{footer_prefix.strip()} {page_number_str}" if footer_prefix else page_number_str

    # --- Text Stroke/Halo Implementation ---
    canvas.setFont(footer_font, footer_base_font_size)
    text_width = canvas.stringWidth(footer_data, footer_font, footer_base_font_size)

    # Calculate x-coordinate based on alignment
    if page_num_alignment == "right":
        x = PAGE_WIDTH - 50 - text_width  # 50 is right margin
    elif page_num_alignment == "centre":
        x = (PAGE_WIDTH - text_width) / 2
    else:  # Default to left
        x = 50  # 50 is left margin

    y = 1 * cm  # Position from bottom of the page

    # Create a text object for the stroke effect
    text_object = canvas.beginText()
    text_object.setTextOrigin(x, y)
    text_object.setFont(footer_font, footer_base_font_size)

    # 1. Draw the "stroke" (a slightly thicker black outline)
    text_object.setTextRenderMode(2)  # Stroke and Fill
    text_object.setStrokeColor(colors.white, alpha=0.9)
    canvas.setLineWidth(0.35)
    text_object.setFillColor(colors.black, alpha=0.9)  # Transparent fill for stroke effect
    text_object.textLine(footer_data)
    canvas.drawText(text_object)
    canvas.restoreState()


def _perform_overlay(content_pdf: Pdf, footer_pdf: Pdf):
    """Check page counts and overlay footer pages onto content pages."""
    if len(content_pdf.pages) != len(footer_pdf.pages):
        msg = f"Page counts do not match: input={len(content_pdf.pages)} vs page numbers={len(footer_pdf.pages)}"
        bundle_logger.error("[OPN]Error overlaying page numbers")
        raise ValueError(msg)

    for i, content_page in enumerate(content_pdf.pages):
        footer_page = footer_pdf.pages[i]

        # The `overlay` method in pikepdf is powerful. It adds the content
        # of the footer_page as a Form XObject to the content_page.
        content_page.add_overlay(footer_page, None)


def add_footer_to_bundle(content_pdf: Pdf, page_numbers_pdf_path: Path):
    """Overlay a footer PDF onto a content PDF.

    This function operates on an open content_pdf object for efficiency.
    It modifies the content_pdf in place and does not save it.
    """
    try:
        with Pdf.open(page_numbers_pdf_path) as footer_pdf:
            _perform_overlay(content_pdf, footer_pdf)
    except Exception:
        bundle_logger.exception("[OPN]Error overlaying page numbers")
        raise


def pdf_paginator_reportlab(pdf: Pdf, bundle_config: BundleConfig):
    """Paginates an open PDF object in place."""
    bundle_logger.debug("[PPRL]Paginate PDF function beginning (ReporLab version)")
    main_page_count = len(pdf.pages)
    bundle_logger.debug(f"[PPRL]..Main PDF has {main_page_count} pages")

    page_numbers_pdf_path = bundle_config.temp_dir / "pageNumbers.pdf"
    generate_footer_pages_reportlab(page_numbers_pdf_path, main_page_count, bundle_config)

    if Path(page_numbers_pdf_path).exists():
        try:
            add_footer_to_bundle(pdf, page_numbers_pdf_path)
            bundle_logger.debug("[PPRL]Page numbers overlaid on main PDF")
        except Exception:
            bundle_logger.exception("[PPRL]Error overlaying page numbers")
            raise
    else:
        bundle_logger.error("[PPRL]Error creating page numbers PDF!")
    return main_page_count


def add_roman_labels(pdf: Pdf, length_of_frontmatter: int):
    """Adjust page numbering to begin with Roman numerals for the frontmatter."""
    bundle_logger.debug(f"[APL]Adding page labels to PDF {pdf.filename}")
    # Page labels are a list of dictionaries.
    # See PDF 32000-1:2008, 12.4.2 Number Trees
    pdf.Root.PageLabels = Dictionary(Nums=[0, Dictionary(S=Name.r), length_of_frontmatter, Dictionary(S=Name.D, St=1)])


def transform_coordinates(coords, page_height):
    """Transform coordinates from top-left to bottom-left origin system."""
    x1, y1, x2, y2 = coords
    # Flip the y coordinates by subtracting from page height. Ensure consistent types.
    new_y1 = page_height - y2  # Note: we swap y1 and y2 here
    new_y2 = page_height - y1
    return (x1, new_y2, x2, new_y1)


def add_annotations_with_transform(pdf: Pdf, list_of_annotation_coords: list):
    """Write hyperlinks into an open pikepdf.Pdf object."""
    # For efficiency, group annotations by the page they belong to.
    # First, sort the annotations by 'toc_page' index.
    sorted_annotations = sorted(list_of_annotation_coords, key=lambda x: x["toc_page"])

    # Group by 'toc_page' and process each group.
    for toc_page_idx, annotation_group_iter in groupby(sorted_annotations, key=lambda x: x["toc_page"]):
        try:
            toc_page = pdf.pages[toc_page_idx]
            page_height = float(toc_page.mediabox[3])  # Convert Decimal to float for compatibility
            # Convert the groupby iterator to a list to allow multiple uses.
            annotation_group = list(annotation_group_iter)

            # Ensure the Annots array exists on the page
            if "/Annots" not in toc_page:
                toc_page.Annots = Array()

            # Create and append all annotations for this page
            toc_page.Annots.extend(
                [
                    Dictionary(
                        Type=Name.Annot,
                        Subtype=Name.Link,
                        Rect=Rectangle(*transform_coordinates(details["coords"], page_height)),
                        Border=[0, 0, 0],
                        A=Dictionary(S=Name.GoTo, D=[pdf.pages[details["destination_page"]].obj, Name.Fit]),
                    )
                    for details in annotation_group
                ]
            )

            bundle_logger.debug(f"[AAWT]Added {len(annotation_group)} annotations to TOC page {toc_page_idx}")

        except Exception:
            bundle_logger.exception(f"[AAWT]Failed to add annotation on TOC page {toc_page_idx}")
            raise


def get_scraped_pages_text(pdf: PDF, idx: int):
    if idx < 0 or idx >= len(pdf.pages):
        bundle_logger.error(f"[HYP]..IndexError imminent: Requesting page {idx} but PDF has {len(pdf.pages)} pages.")
        return []

    current_page = pdf.pages[idx]
    bundle_logger.debug(f"[HYP]..Processing page {idx} for TOC text extraction")
    return current_page.extract_text_lines()


def _find_match_for_entry(entry, scraped_pages_text, length_of_coversheet, length_of_frontmatter):
    """Find the first matching line in the scraped text for a given TOC entry."""
    tab_to_find = str(entry[0])
    bundle_logger.debug(f"[HYP]....Searching for tab: '{tab_to_find}'")
    for page_idx, page_lines in enumerate(scraped_pages_text, start=length_of_coversheet):
        if not page_lines:
            continue
        for line in page_lines:
            line_text = str(line.get("text", ""))
            if line_text.strip().startswith(tab_to_find):
                dest_page = int(entry[3]) + length_of_frontmatter
                bundle_logger.debug(
                    f"[HYP]......SUCCESS: Found tab '{tab_to_find}' on page {page_idx} in line: '{line_text}'. Calculated Dest Page: {dest_page}"
                )
                return {
                    "title": entry[1],
                    "toc_page": page_idx,
                    "coords": (line["x0"], line["bottom"], line["x1"], line["top"]),
                    "destination_page": dest_page,
                }
    bundle_logger.warning(f"[HYP]......FAILURE: No match found for tab '{tab_to_find}'")
    return None


def _initialize_bundle_creation(bundle_config_data: BundleConfig, output_file, coversheet_file: FileStorage | None, input_files: list[FileStorage]):
    """Initialize variables and logging for bundle creation. Returns a list of initial temp files."""
    BUNTOOL_VERSION = "2025.01.24"

    # various initial file and data handling:
    bundle_config = bundle_config_data
    temp_path = bundle_config.temp_dir
    temp_path.mkdir(parents=True, exist_ok=True)
    tmp_output_file = temp_path / output_file
    coversheet_pdf_obj = Pdf.open(cast(io.BytesIO, coversheet_file.stream)) if coversheet_file else None

    # set up logging using configure_logger function
    bundle_logger = configure_logger(bundle_config, bundle_config.session_id)
    log_msg = f"""
        [CB]THIS IS BUNTOOL VERSION {BUNTOOL_VERSION}
        [CB]Temp directory created at {temp_path.name}.
        *****New session: {bundle_config.session_id} called create_bundle*****
        {bundle_config.session_id} has the USER AGENT: {bundle_config.user_agent}
        Bundle creation called with {len(input_files)} input files and output file {output_file}"""
    bundle_logger.info(textwrap.dedent(log_msg).strip())
    debug_log_msg = f"""
            [CB]create_bundle received the following arguments:
            ....input_files: {[f.filename for f in input_files]}
            ....output_file: {output_file}
            ....coversheet_file: {coversheet_file.filename if coversheet_file else "None"}
            ....bundle_config: {bundle_config.__dict__}"""
    dedent_and_log(bundle_logger, debug_log_msg)

    return bundle_config, temp_path, tmp_output_file, coversheet_pdf_obj


def _process_index_and_merge(
    bundle_config: BundleConfig, index_file, temp_path: Path, input_files: list[FileStorage]
) -> tuple[dict[str, Any] | None, list | None, Pdf | None, int | None, dict[str, int] | None]:
    """Process index data and merge input PDFs. Returns index data, toc entries, and a list of temp files."""
    if not index_file and bundle_config.csv_string:
        index_file_path = temp_path / "index.csv"
        with Path(index_file_path).open("w") as f:
            f.write(bundle_config.csv_string)
        index_file = index_file_path
        bundle_logger.info(f"[CB]Index data from string input saved to {index_file}")

    if index_file:  # this is a file handler. The main way to pass an index.
        bundle_logger.debug(f"[CB]Calling load_index_data [LI] with index_file: {index_file}")
        index_data = load_index_data(index_file, bundle_config)
    else:
        index_data = {}
        bundle_logger.info("[CB]No index data provided.")

    # Merge PDFs using provided unique filenames
    log_msg = f"""
        [CB]Calling merge_pdfs_create_toc_entries [MP] with arguments:
        ....input_files: {[f.filename for f in input_files]}
        ....index_data: {index_data}"""
    dedent_and_log(bundle_logger, log_msg)
    try:
        merged_pdf_obj, toc_entries, all_sub_bookmarks, is_bundle_map, main_page_count = merge_pdfs_create_toc_entries(input_files, index_data)
    except Exception:
        bundle_logger.exception("[CB]Error while merging pdf files")
        raise
    else:
        if not merged_pdf_obj:
            bundle_logger.error("[CB]Merging files unsuccessful: merged PDF object is None.")
            return None, None, None, None, None
    bundle_config.all_sub_bookmarks = all_sub_bookmarks
    # list out settings in a human-readable way for remote user support.
    # The file_details log has been removed as it was inefficiently opening files.
    user_settings_log = f"""\
        =============================================================================
        BUNTOOL -- BEGIN RECORD OF USER SETTINGS
        Time of use: {bundle_config.timestamp}
        STEP ONE:
        ..Bundle Title: {bundle_config.case_details.get("bundle_title", "")}
        ..Case Name: {bundle_config.case_details.get("case_name", "")}
        ..Claim Number: {bundle_config.case_details.get("claim_no", "")}
        STEP TWO:
        STEP THREE:
        ..Index Options:
        ....Index font: {bundle_config.index_font}
        ....Coversheet: {"Yes" if bundle_config.case_details.get("case_name", "") else "No coversheet provided."}
        ....Date column: {bundle_config.date_setting}
        ....Confidentiality: {bundle_config.confidential_bool}
        ..Page Numbering Options:
        ....Footer font: {bundle_config.footer_font}
        ....Preface numbering: {bundle_config.roman_for_preface}
        ....Page number alignment: {bundle_config.page_num_align}
        ....Page numbering style: {bundle_config.page_num_style}
        ....Footer prefix: {bundle_config.footer_prefix if bundle_config.footer_prefix else "No footer prefix"}
        END RECORD OF USER SETTINGS
        ================================================================================="""
    dedent_and_log(bundle_logger, user_settings_log)

    bundle_config.main_page_count = main_page_count
    return index_data, toc_entries, merged_pdf_obj, main_page_count, is_bundle_map


def _create_front_matter(bundle_config: BundleConfig, coversheet_pdf_obj: Pdf | None, toc_entries):
    """Create and merge front matter (coversheet and TOC). Returns any temporary files created."""
    length_of_coversheet = len(coversheet_pdf_obj.pages) if coversheet_pdf_obj else 0

    bundle_config.expected_length_of_frontmatter = length_of_coversheet  # global. This allows the toc to account for what comes before it.

    # Generate the TOC once with placeholder page numbers to get its length.
    # The real page numbers will be updated later.
    options = {"confidential": bundle_config.confidential_bool, "date_setting": bundle_config.date_setting, "dummy": True, "roman_numbering": False}
    try:
        _, length_of_toc = create_toc_pdf_reportlab(toc_entries, bundle_config, options)
    except Exception:
        bundle_logger.exception("[CB]Error during initial TOC creation")
        raise

    expected_length_of_frontmatter = length_of_coversheet + length_of_toc
    bundle_config.total_number_of_pages = bundle_config.main_page_count + expected_length_of_frontmatter

    bundle_config.expected_length_of_frontmatter = expected_length_of_frontmatter  # global
    bundle_logger.debug(f"[CB]Expected length of frontmatter: {expected_length_of_frontmatter}")
    return expected_length_of_frontmatter, length_of_coversheet


class TocParams(NamedTuple):  # Already defined
    bundle_config: BundleConfig
    temp_path: Path
    toc_entries: list
    expected_length_of_frontmatter: int
    toc_file_path: Path


class CreateTocError(Exception):
    def __init__(self, message="TOC PDF creation failed."):
        super().__init__("TOC creation future returned None." if message == "0" else message)


def _create_toc(toc_params: TocParams):
    (bundle_config, temp_path, toc_entries, expected_length_of_frontmatter, toc_file_path) = toc_params

    # bundle_config.expected_length_of_frontmatter = length_of_coversheet if length_of_coversheet is not None else 0  # janky reset for TOC
    bundle_config.expected_length_of_frontmatter = expected_length_of_frontmatter  # TODO: this is a mess.

    # Now, create TOC PDF For real:
    log_msg = f"""
        [CB]Calling create_toc_pdf_reportlab [CT] - final version -  with arguments:
        ....toc_entries: {toc_entries}
        ....casedetails: {bundle_config.case_details}
        ....toc_file_path: {toc_file_path}
        ....confidential: {bundle_config.confidential_bool}
        ....date_setting: {bundle_config.date_setting}
        ....index_font: {bundle_config.index_font}
        ....dummy: False
        ....length_of_frontmatter: {expected_length_of_frontmatter}"""
    dedent_and_log(bundle_logger, log_msg)
    # Use the number of workers needed, but cap it at the number of available CPUs.
    with ThreadPoolExecutor(max_workers=CPU_COUNT, initializer=init_worker, initargs=(count(1),)) as executor:
        # Submit PDF TOC creation
        pdf_options = {
            "confidential": bundle_config.confidential_bool,
            "date_setting": bundle_config.date_setting,
            "dummy": False,
            "roman_numbering": bundle_config.roman_for_preface,
        }
        pdf_future = executor.submit(create_toc_pdf_reportlab, toc_entries, bundle_config, pdf_options)

        # Submit DOCX TOC creation
        docx_output_path = temp_path / "docx_output.docx"
        docx_config = DocxConfig(
            confidential=bundle_config.confidential_bool,
            date_setting=(bundle_config.date_setting != "hide_date"),
            index_font_setting=bundle_config.index_font,
        )
        docx_future = executor.submit(create_toc_docx, toc_entries, bundle_config.case_details, docx_output_path, docx_config)

        # Wait for both to complete and get results
        try:
            toc_buffer, length_of_toc = pdf_future.result()
        except Exception as e:
            bundle_logger.exception("[CB]..Error during create_toc_pdf_reportlab")
            raise CreateTocError from e

        try:
            docx_future.result()  # We just need to know it finished without error
        except Exception:
            bundle_logger.exception("[CB]..Error during create_toc_docx")
            # We can continue without the docx if it fails
            docx_output_path = None

    return docx_output_path, toc_buffer, length_of_toc


class HyperlinkingError(Exception):
    details: str

    def __init__(self, option, details):
        self.details = details
        super().__init__(f"Hyperlinking process failed: {option}")


class BookmarkingError(Exception):
    def __init__(self, option, details):
        self.details = details
        super().__init__(f"Bookmarking process failed: {option}")


class PageLabelsError(Exception):
    def __init__(self, option, details):
        self.details = details
        super().__init__(f"Page labels process failed: {option}")


def _adjust_inner_bundle_links(pdf: Pdf, toc_entries: list, index_data: dict, length_of_frontmatter: int, is_bundle_map: dict):
    """Adjusts the hyperlink destinations within any nested bundles in the final PDF."""
    bundle_logger.debug(f"Adjusting inner bundle links for {pdf.filename} with final frontmatter length {length_of_frontmatter}")
    # Create a map from original filename to its starting page in the main content
    filename_to_start_page = {
        index_data_filename: entry[3]
        for entry in toc_entries
        if "SECTION_BREAK" not in entry[0] and len(entry) > MIN_TOC_ENTRY_FIELDS
        for index_data_filename, index_data_entry in index_data.items()
        if index_data_entry[0] == entry[1]
    }

    for filename, start_page_in_main_content in filename_to_start_page.items():
        num_toc_pages = is_bundle_map.get(filename, 0)
        if num_toc_pages > 0:
            # This is a nested bundle. Adjust its links.
            # The final start page of this inner bundle's content in the assembled PDF.
            final_start_page = start_page_in_main_content + length_of_frontmatter
            bundle_logger.debug(
                f"Found inner bundle '{filename}' starting at final page {final_start_page}. Adjusting its {num_toc_pages} TOC pages."
            )

            # The links are on the TOC pages of the inner bundle.
            # These pages are located at the beginning of where the inner bundle was placed.
            for i in range(num_toc_pages):
                page_to_adjust: Page = pdf.pages[final_start_page + i]
                annots = cast(list[Dictionary], page_to_adjust.get("/Annots")) or []
                for j, annot in enumerate(annots):
                    if annot.get("/Subtype") == "/Link":
                        try:
                            if annot.Dest:
                                # The destination is an indirect object. We can't just add to it.
                                # We need to find the original destination page index and create a new destination.
                                original_dest_page_obj = cast(Page, annot.Dest[0])
                                new_dest_page_index = pdf.pages.index(original_dest_page_obj)
                                annot.Dest = Array([pdf.pages[new_dest_page_index].obj, Name.Fit])
                        except Exception:
                            bundle_logger.debug(f"No need to adjust relative link {j} on page {i + 1}")


class AssembleFinalBundleParams(NamedTuple):
    bundle_config: BundleConfig
    temp_path: Path
    merged_pdf_obj: Pdf
    toc_entries: list
    index_data: dict
    length_of_coversheet: int | None
    coversheet_pdf_obj: Pdf | None
    tmp_output_file: Path


class PaginationError(Exception):
    """Custom exception for pagination errors."""

    def __init__(self, option):
        self.message = f"Pagination process failed: {option}"
        super().__init__(self.message)


@profile
def paginate_merged_main_files(pdf_obj: Pdf, bundle_config: BundleConfig) -> Pdf:
    """Paginates an in-memory PDF object and returns a sanitized in-memory pikepdf.Pdf object."""
    log_msg = f"""
        [CB]Calling pdf_paginator_reportlab [PPRL] with arguments:
        ....page_num_alignment: {bundle_config.page_num_align}
        ....page_num_font: {bundle_config.footer_font}
        ....page_numbering_style: {bundle_config.page_num_style}
        ....footer_prefix: {bundle_config.footer_prefix}"""
    dedent_and_log(bundle_logger, log_msg)
    paginated_count = pdf_paginator_reportlab(pdf_obj, bundle_config)
    if paginated_count != bundle_config.main_page_count:
        bundle_logger.warning(f"Pagination count mismatch: expected {bundle_config.main_page_count}, but got {paginated_count}. Continuing.")
    # To prevent content stream errors when merging, we "sanitize" the PDF
    # by saving it to an in-memory buffer and reopening it.
    buffer = io.BytesIO()
    pdf_obj.save(buffer)
    buffer.seek(0)
    sanitized_pdf = Pdf.open(buffer)
    bundle_logger.debug("[PPRL]..Sanitized paginated PDF in memory.")
    return sanitized_pdf


class FrontMatterError(Exception):
    details: str

    def __init__(self, option, details):
        self.details = details
        super().__init__(f"Frontmatter process failed: {option}")


class SaveMergedFilesWithFrontmasterParams(NamedTuple):
    paginated_pdf_obj: Pdf
    toc_buffer: io.BytesIO
    coversheet_pdf_obj: Pdf | None


@profile
def save_merged_files_with_frontmaster(params: SaveMergedFilesWithFrontmasterParams):
    """Merges frontmatter (coversheet, TOC) with the main content, all in memory."""
    paginated_pdf_obj, toc_buffer, coversheet_pdf_obj = params

    final_pdf = Pdf.new()

    # 1. Add coversheet if it exists
    if coversheet_pdf_obj:
        final_pdf.pages.extend(coversheet_pdf_obj.pages)

    # 2. Add Table of Contents
    if toc_buffer:
        try:
            with Pdf.open(toc_buffer) as toc_pdf:
                final_pdf.pages.extend(toc_pdf.pages)
        except Exception as e:
            raise FrontMatterError("C", f"Failed to open in-memory TOC buffer: {e}") from e
    else:
        bundle_logger.info("[CB]No coversheet specified. TOC is the only frontmatter.")

    # Get the length of the frontmatter we just added
    length_of_frontmatter = len(final_pdf.pages)
    bundle_logger.debug(f"[CB]In-memory frontmatter created with {length_of_frontmatter} pages.")

    # 3. Add the main paginated content
    final_pdf.pages.extend(paginated_pdf_obj.pages)

    bundle_logger.info("[CB]..Successfully merged frontmatter and main content in memory.")
    return final_pdf, length_of_frontmatter


@profile
def _calculate_hyperlink_coords(pdf_buffer: io.BytesIO, length_of_coversheet: int | None, length_of_frontmatter: int, toc_entries: list) -> list:
    """Calculates the coordinates for TOC hyperlinks by extracting text in parallel from an in-memory PDF object."""
    bundle_logger.debug("[HYP]Starting hyperlink coordinate calculation from in-memory PDF")

    with PDF.open(pdf_buffer) as plumberPdf, ThreadPoolExecutor(max_workers=CPU_COUNT, initializer=init_worker, initargs=(count(1),)) as executor:
        # Step 1: Parallelize the text extraction from each TOC page.
        num_pages = len(plumberPdf.pages)
        bundle_logger.debug(f"[HYP]..Coversheet length: {length_of_coversheet}, Frontmatter length: {length_of_frontmatter}, PDF pages: {num_pages}")

        toc_page_indices = range(length_of_coversheet if length_of_coversheet is not None else 0, length_of_frontmatter)
        # Pass the opened pdfplumber object to each worker
        extract_futures = {executor.submit(get_scraped_pages_text, plumberPdf, idx): idx for idx in toc_page_indices}

        results_dict = {}
        for future in as_completed(extract_futures):
            page_idx = extract_futures[future]
            results_dict[page_idx] = future.result()
        scraped_pages_text = [results_dict[i] for i in sorted(results_dict.keys())]

        # Step 2: Parallelize the search for each TOC entry within the extracted text.
        search_futures = {
            executor.submit(_find_match_for_entry, entry, scraped_pages_text, length_of_coversheet, length_of_frontmatter)
            for entry in toc_entries
            if "SECTION_BREAK" not in entry[0] and not (len(entry) > MIN_TOC_ENTRY_FIELDS and str(entry[3]) == "Page")
        }

        # Collect valid results as they complete.
        return [future.result() for future in as_completed(search_futures) if future.result() is not None]


def _get_toc_creation_result(toc_future: Future[tuple[Path | None, io.BytesIO, int]]):
    """Get the result from the TOC creation future, raising an error if it's None."""
    result = toc_future.result()
    if result is None:
        raise CreateTocError("0")
    return result


class ParallelAssemblyParams(NamedTuple):
    merged_pdf_obj: Pdf
    bundle_config: BundleConfig
    temp_path: Path
    toc_entries: list
    toc_file_path: Path


def _run_parallel_assembly_tasks(params: ParallelAssemblyParams):
    """Run pagination and TOC creation in parallel."""
    (merged_pdf_obj, bundle_config, temp_path, toc_entries, toc_file_path) = params
    with ThreadPoolExecutor(max_workers=CPU_COUNT, initializer=init_worker, initargs=(count(1),)) as executor:
        # Submit pagination and TOC creation to run in parallel
        pagination_future = executor.submit(paginate_merged_main_files, merged_pdf_obj, bundle_config)
        toc_params = TocParams(bundle_config, temp_path, toc_entries, bundle_config.expected_length_of_frontmatter, toc_file_path)
        toc_future = executor.submit(_create_toc, toc_params)

        try:
            # Retrieve results
            paginated_pdf = pagination_future.result()
            docx_output_path, toc_buffer, length_of_toc = _get_toc_creation_result(toc_future)
        except Exception as e:
            # Handle exceptions from either task
            if isinstance(e, CreateTocError):
                bundle_logger.exception(f"[CB]..Creating TOC file unsuccessful: cannot locate expected output {toc_file_path}.")
            elif isinstance(e, PaginationError):
                bundle_logger.exception("[CB]..paginate_merged_main_files failed.")
            else:
                bundle_logger.exception("[CB]..An unexpected error occurred during final assembly.")
            # Ensure both tasks are cancelled if one fails
            pagination_future.cancel()
            toc_future.cancel()
            raise
        else:
            return paginated_pdf, docx_output_path, toc_buffer, length_of_toc


class FinalModificationsParams(NamedTuple):
    final_pdf_obj: Pdf
    length_of_coversheet: int | None
    length_of_frontmatter: int
    toc_entries: list
    index_data: dict
    bundle_config: BundleConfig
    coversheet_pdf_obj: Pdf | None
    tmp_output_file: Path


@profile
def _apply_final_pdf_modifications(params: FinalModificationsParams):
    """Apply final modifications (hyperlinks, bookmarks, etc.) to the PDF."""
    (
        final_pdf_obj,
        length_of_coversheet,
        length_of_frontmatter,
        toc_entries,
        index_data,
        bundle_config,
        coversheet_pdf_obj,
        tmp_output_file,
    ) = params
    try:
        # Create a buffer for pdfplumber to read the current state of the PDF
        pdf_buffer = io.BytesIO()
        final_pdf_obj.save(pdf_buffer)
        pdf_buffer.seek(0)

        list_of_annotation_coords = _calculate_hyperlink_coords(pdf_buffer, length_of_coversheet, length_of_frontmatter, toc_entries)
        add_annotations_with_transform(final_pdf_obj, list_of_annotation_coords)
        _adjust_inner_bundle_links(final_pdf_obj, toc_entries, index_data, length_of_frontmatter, bundle_config.is_bundle_map)
        add_bookmarks_to_pdf(final_pdf_obj, toc_entries, length_of_frontmatter, bundle_config)
        bookmark_the_index(final_pdf_obj, coversheet_pdf_obj)
        if bundle_config.roman_for_preface:
            add_roman_labels(final_pdf_obj, length_of_frontmatter)
        final_pdf_obj.save(tmp_output_file)

    except Exception as e:
        if isinstance(e, HyperlinkingError):
            bundle_logger.exception("[CB]..Hyperlinking process failed.")
        elif isinstance(e, BookmarkingError):
            bundle_logger.exception("[CB]..Bookmarking process failed.")
        elif isinstance(e, PageLabelsError):
            bundle_logger.exception("[CB]..Page labeling process failed.")
        else:
            bundle_logger.exception("[CB]..An unexpected error occurred during final assembly steps.")
        raise


def _assemble_final_bundle(
    assemble_final_bundle_params: AssembleFinalBundleParams,
):
    """Assembles the final PDF bundle by paginating, creating TOC, and adding bookmarks. Returns a list of created temp files."""
    (
        bundle_config,
        temp_dir,
        merged_pdf_obj,  # Already defined
        toc_entries,  # Already defined
        index_data,  # Already defined
        length_of_coversheet,
        coversheet_pdf_obj,
        tmp_output_file,
    ) = assemble_final_bundle_params

    temp_path = Path(temp_dir)
    toc_file_path = temp_path / "index.pdf"  # Still needed for logging and error messages

    paginated_pdf = None
    final_pdf_obj = None

    try:
        try:
            paginated_pdf, docx_output_path, toc_buffer, length_of_toc = _run_parallel_assembly_tasks(
                ParallelAssemblyParams(
                    merged_pdf_obj,
                    bundle_config,
                    temp_path,
                    toc_entries,
                    toc_file_path,
                )
            )
        except Exception:
            return None

        bundle_config.expected_length_of_frontmatter = (length_of_coversheet or 0) + length_of_toc
        try:
            final_pdf_obj, length_of_frontmatter = save_merged_files_with_frontmaster(
                SaveMergedFilesWithFrontmasterParams(paginated_pdf_obj=paginated_pdf, toc_buffer=toc_buffer, coversheet_pdf_obj=coversheet_pdf_obj)
            )
        except FrontMatterError:
            bundle_logger.exception("CB..Saving merged files with frontmatter failed.")
            return None

        try:
            _apply_final_pdf_modifications(
                FinalModificationsParams(
                    final_pdf_obj,
                    length_of_coversheet,
                    length_of_frontmatter,
                    toc_entries,
                    index_data,
                    bundle_config,
                    coversheet_pdf_obj,
                    tmp_output_file,
                )
            )
        except Exception:
            return None

        # Return the path to the docx and the list of all temp files created in this function
        return docx_output_path
    finally:
        if paginated_pdf:
            paginated_pdf.close()
        if coversheet_pdf_obj:
            coversheet_pdf_obj.close()
        if final_pdf_obj:
            final_pdf_obj.close()


def _handle_zip_creation(bundle_config, input_files, docx_output_path, temp_path, tmp_output_file):
    """Handle the creation of a zip file containing the bundle and source files."""
    zip_filepath = None
    if bundle_config.zip_bool:
        zip_timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        bundletitleforfilename = bundle_config.case_details["bundle_title"] or "Bundle"
        casenameforfilename = bundle_config.case_details["case_name"] or ""
        bundle_logger.debug("[CB]Calling create_zip_file:")
        try:
            zip_filepath = create_zip_file(
                CreateZipFileParams(
                    bundletitleforfilename,
                    casenameforfilename,
                    zip_timestamp,
                    input_files,
                    docx_output_path,
                    temp_path,
                    tmp_output_file,
                )
            )
        except Exception:
            bundle_logger.exception("[CB]..Error during create_zip_file")
            raise
        if not zip_filepath or not Path(zip_filepath).exists():
            bundle_logger.exception(f"[CB]..Creating zip file unsuccessful: cannot locate expected output {zip_filepath}.")
        else:
            bundle_logger.info(f"[CB]..Zip file created at {Path(zip_filepath).name}")
    return zip_filepath


@profile
def create_bundle(
    input_files: list, output_file, coversheet_file: FileStorage | None, csv_index_content: str | None, bundle_config_data: BundleConfig
):
    """Create a bundle from input files and configuration."""
    docx_output_path = None
    merged_pdf_obj = None
    coversheet_pdf_obj = None

    bundle_config, temp_path, tmp_output_file, coversheet_pdf_obj = _initialize_bundle_creation(
        bundle_config_data, output_file, coversheet_file, input_files
    )

    try:
        index_data, toc_entries, merged_pdf_obj, main_page_count, is_bundle_map = _process_index_and_merge(
            bundle_config, csv_index_content, temp_path, input_files
        )
        if not merged_pdf_obj:
            bundle_logger.error("Merging process failed, merged PDF object is None.")
            return None, None

        index_data = index_data or {}
        expected_length_of_frontmatter, length_of_coversheet = _create_front_matter(bundle_config, coversheet_pdf_obj, toc_entries)
        if expected_length_of_frontmatter is None:
            return None, None

        if toc_entries is None:
            bundle_logger.error("[CB]toc_entries is None, cannot assemble bundle.")
            return None, None
        bundle_config.is_bundle_map = is_bundle_map or {}

        result = _assemble_final_bundle(
            AssembleFinalBundleParams(
                bundle_config=bundle_config,
                temp_path=temp_path,
                merged_pdf_obj=cast(Pdf, merged_pdf_obj),
                toc_entries=toc_entries,
                index_data=index_data,
                length_of_coversheet=length_of_coversheet,
                coversheet_pdf_obj=coversheet_pdf_obj,
                tmp_output_file=tmp_output_file,
            )
        )
        if result is None:
            bundle_logger.error("[CB].._assemble_final_bundle failed.")
            return None, None
        docx_output_path = result

    except Exception:
        bundle_logger.exception("[CB]Error during create_bundle")
        raise
    finally:
        if merged_pdf_obj:
            merged_pdf_obj.close()
        if coversheet_pdf_obj:
            coversheet_pdf_obj.close()

    # Create zip file if requested:
    zip_filepath = _handle_zip_creation(bundle_config, input_files, docx_output_path, temp_path, tmp_output_file)

    final_zip_path = str(zip_filepath) if zip_filepath else None
    gc.collect()
    return str(tmp_output_file), final_zip_path


class CreateZipFileParams(NamedTuple):
    bundle_title: str
    case_name: str
    timestamp: str
    input_files: list[FileStorage]
    docx_path: Path | None
    temp_path: Path
    tmp_output_file: str


@profile
def create_zip_file(create_zip_file_params: CreateZipFileParams):
    """Package up everything into a zip for the user's reproducibility and record keeping.

    for the user's reproducability and record keeping.
    """
    (bundle_title, case_name, timestamp, input_files, docx_path, temp_dir, tmp_output_file) = create_zip_file_params

    # int_zip_filepath = os.path.join(temp_dir, zip_filename)
    int_zip_filepath = Path(temp_dir) / f"{secure_filename(bundle_title)}_{secure_filename(case_name)}_{timestamp}.zip"
    bundle_logger.debug(f"[CZF]Creating zip file at {int_zip_filepath}")

    with zipfile.ZipFile(int_zip_filepath, cast(Any, "w")) as zipf:
        # Add input files to a subdirectory
        for file_storage in input_files:
            # Since we have the file in memory, we write its content directly
            file_storage.stream.seek(0)
            zipf.writestr(f"input_files/{file_storage.filename}", file_storage.stream.read())
        # Add index.csv if it exists
        index_csv_path = temp_dir / "index.csv"
        if index_csv_path.exists():
            zipf.write(index_csv_path, "index.csv")
        # Add coversheet to the root directory
        if docx_path:
            zipf.write(docx_path, Path(docx_path).name)
        # Add outputfile (whole bundle) to the root directory
        if tmp_output_file and Path(tmp_output_file).exists():
            zipf.write(tmp_output_file, Path(tmp_output_file).name)
    return int_zip_filepath


def _parse_cli_args():
    parser = argparse.ArgumentParser(description="Merge PDFs with bookmarks and optional coversheet.")
    parser.add_argument("input_files", nargs="+", help="Input PDF files")
    parser.add_argument("-o", "--output_file", help="Output PDF file", default=None)
    parser.add_argument("-b", "--bundlename", help="Title of the bundle", default="Bundle")
    parser.add_argument("-c", "--casename", help="Name of case e.g. Smith v Jones & ors", default="")
    parser.add_argument("-n", "--claimno", help="Claim number", default="")
    parser.add_argument("-coversheet", help="Optional coversheet PDF file", default=None)
    parser.add_argument("-index", help="Optional CSV file with predefined index data", default=None)
    parser.add_argument("-csv_index", help="CSV index data as a string", default=None)
    parser.add_argument("-zip", help="Flag to indicate if a zip file should be created", action="store_true", default=False)
    parser.add_argument("-confidential", help="Flag to indicate if bundle is confidential", action="store_true", default=False)
    return parser.parse_args()


def main():
    """Command-line usage.

    Mainly used for spot-testing during development. As such it is at present poorly tested and doesn't implement the full range
    of functionality from create_bundle.
    """
    args = _parse_cli_args()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    input_files = args.input_files
    output_file = secure_filename(args.output_file) if args.output_file else secure_filename(f"{args.bundlename}-{timestamp}.pdf")
    coversheet = args.coversheet
    csv_index_content = args.csv_index
    confidential_bool = args.confidential
    zip_bool = args.zip if args.zip else False

    bundle_config = BundleConfig(
        BundleConfigParams(
            timestamp=timestamp,
            case_details={"bundle_title": args.bundlename, "claim_no": args.claimno, "case_name": args.casename},
            csv_string=csv_index_content,
            confidential_bool=confidential_bool,
            zip_bool=zip_bool,
            session_id=timestamp,
            user_agent="CLI",
            page_num_align="centre",
            index_font="sans",
            footer_font="sans",
            page_num_style="page_x_of_y",
            footer_prefix="",
            date_setting="DD_MM_YYYY",
            roman_for_preface=False,
        )
    )

    create_bundle(
        input_files,  # For CLI, this would need to be a list of file paths opened as streams
        output_file,
        coversheet,
        csv_index_content,  # Pass the in-memory CSV content
        bundle_config,
    )


if __name__ == "__main__":
    main()
