import contextlib
import logging
import re
import statistics
from collections import defaultdict
from logging import Logger
from pathlib import Path
from typing import NamedTuple

import pdfplumber
from pdfplumber._typing import T_obj, T_obj_list
from pdfplumber.page import Page
from pdfplumber.pdf import PDF

SPLIT_RANGE_NUMBER_ELEMENTS = 3


class ParseTocLineReturn(NamedTuple):
    title: str
    page: int | None
    indent_level: int
    raw_text: str
    toc_page_num: int = 0


class ExtractTocDataReturn(NamedTuple):
    entries: list[ParseTocLineReturn]
    total_entries: int
    has_hierarchy: bool
    page_range: tuple[int, int] | None
    column_count: int | None
    row_patterns: list[list[str]] | None


class DetectReturn(NamedTuple):
    toc_page: int
    confidence: float
    entries: list[ParseTocLineReturn]
    total_entries: int
    has_hierarchy: bool
    page_range: tuple[int, int] | None
    column_count: int | None
    row_patterns: list[list[str]] | None


class ScanForCandidatesReturn(NamedTuple):
    page: int
    score: float
    method: str
    word_count: int


class NotEnoughContentError(Exception):
    def __init__(self, words_length: int, page_number: int) -> None:
        super().__init__(f"Page {page_number}: Skipped (too few words: {words_length})")


class TOCDetector:
    """Robust table of contents detector for PDF files.

    Combines multiple heuristics for high accuracy.
    """

    # Key indicators - expanded for robustness
    TOC_HEADERS = ["table of contents", "contents", "index", "toc"]

    # Patterns that strongly indicate TOC entries
    ENTRY_PATTERNS = [
        r"[A-Za-z].*?[\.\s…]{2,}\s*\d+\s*$",  # Title ... 123
        r"^\s*\d+(\.\d+)*\s+.*?\s+\d+\s*$",  # 1.1 Title 123
        r"^\s*[IVXLCDM]+\.\s+.*?\s+\d+\s*$",  # I. Title 123
        r"^\s*[A-Z]\.\s+.*?\s+\d+\s*$",  # A. Title 123
    ]

    # Constants
    MIN_WORDS_ON_PAGE = 10
    CONFIDENCE_THRESHOLD = 0.3
    HEADER_SCORE_THRESHOLD = 0.8
    PATTERN_SCORE_THRESHOLD = 0.6
    LAYOUT_SCORE_THRESHOLD = 0.5
    MIN_LINES_FOR_PATTERN_CHECK = 5
    MIN_LINE_LENGTH = 3
    MAX_PAGE_NUMBER_DIGITS = 4
    MIN_INDENTATION_LINES = 5
    HIGH_CONFIDENCE_THRESHOLD = 0.6
    MIN_TOC_LIKE_LINES = 3
    MIN_WORDS_FOR_TOC_LINE = 2
    MIN_ENTRIES_FOR_HIERARCHY = 5
    MIN_INDENT_LEVELS_FOR_HIERARCHY = 2
    MIN_ENTRIES_FOR_VALIDATION = 3
    MIN_TITLE_LENGTH = 2
    MIN_ENTRIES_WITH_PAGES_FOR_SEQUENCE = 3
    MIN_INCREASING_PAGE_RATIO = 0.6
    VALID_TITLE_RATIO = 0.7
    VALID_PAGE_RATIO = 0.5
    RIGHT_ALIGNED_THRESHOLD = 0.75
    RIGHT_ALIGNED_DENSITY_THRESHOLD = 0.85
    LINE_MERGE_THRESHOLD = 5
    COLUMN_TYPE_THRESHOLD = 0.8

    logger: Logger

    def __init__(self, logger=None, max_pages_to_check: int = 10):
        self.max_pages_to_check = max_pages_to_check
        self.logger = logger if logger else logging.getLogger(__name__)

    def detect(self, pdf: PDF | None = None, pdf_path: Path | None = None) -> DetectReturn | None:
        """Main detection function.

        Returns TOC info or None if not found.
        """

        def _process_pdf(pdf: PDF):
            self.logger.info(f"Starting TOC detection. Total pages: {len(pdf.pages)}")
            # Step 1: Find candidate pages
            candidates = self._scan_for_candidates(pdf)

            if not candidates:
                self.logger.info("No TOC candidates found.")
                return None

            # Step 2: Select best candidate
            best_candidate = self._select_best_candidate(candidates, pdf)

            if not best_candidate:
                self.logger.info("No suitable TOC candidate selected.")
                return None

            # Step 3: Extract structured TOC
            toc_page_num = best_candidate.page
            self.logger.info(f"Extracting TOC from page {toc_page_num} (score: {best_candidate.score:.2f})")
            toc_data = self._extract_toc_data(pdf, toc_page_num)

            # Step 4: Validate TOC structure
            if not self._validate_toc(toc_data.entries):
                self.logger.warning(f"TOC extracted from page {toc_page_num} failed validation.")
                return None

            # Apply indentation adjustment here for the single-page result
            adjusted_entries = self._adjust_indentation_for_sections(toc_data.entries)

            self.logger.info(f"Successfully detected TOC on page {toc_page_num} with {toc_data.total_entries} entries.")
            return DetectReturn(
                toc_page_num,
                best_candidate.score,
                adjusted_entries,
                toc_data.total_entries,
                toc_data.has_hierarchy,
                toc_data.page_range,
                toc_data.column_count,
                toc_data.row_patterns,
            )

        try:
            if pdf:
                return _process_pdf(pdf)

            if pdf_path:
                with pdfplumber.open(pdf_path) as just_opened_pdf:
                    return _process_pdf(just_opened_pdf)

        except Exception:
            self.logger.exception(f"Error processing {pdf_path}")
            return None

    def get_full_toc(self, pdf: PDF) -> list[ParseTocLineReturn]:
        """Detects and returns the full list of TOC entries across all TOC pages."""
        start_info = self.detect(pdf=pdf)
        if not start_info:
            return []

        all_entries = list(start_info.entries)

        # Detect continuation pages and get their entries
        continuation_entries = self.detect_continuation(pdf, start_info)
        all_entries.extend(continuation_entries)

        # Apply indentation adjustment globally to handle cross-page sections
        return self._adjust_indentation_for_sections(all_entries)

    def detect_continuation(self, pdf: PDF, start_info: DetectReturn) -> list[ParseTocLineReturn]:
        """Detects continuation pages based on the pattern of the first detected page."""
        all_continuation_entries: list[ParseTocLineReturn] = []
        current_page_idx = start_info.toc_page  # 1-based index, so this points to the next page in 0-indexed list

        # Analyze pattern from first page
        first_page_has_numbers = any(e.page is not None for e in start_info.entries)
        expected_columns = start_info.column_count
        expected_row_patterns = start_info.row_patterns

        while current_page_idx < len(pdf.pages):
            next_page_num = current_page_idx + 1
            try:
                toc_data = self._extract_toc_data(pdf, next_page_num)
                entries = toc_data.entries

                if not entries:
                    break

                structure_match = True
                if (expected_columns is not None and toc_data.column_count is not None) and (
                    (toc_data.column_count != expected_columns)
                    or (
                        expected_row_patterns
                        and toc_data.row_patterns
                        and not self._validate_row_patterns(expected_row_patterns, toc_data.row_patterns)
                    )
                ):
                    structure_match = False

                if not structure_match:
                    self.logger.debug(f"Page {next_page_num}: Table structure mismatch. Attempting word fallback.")
                    page = pdf.pages[next_page_num - 1]
                    fallback_entries = self._extract_entries_from_words(page, len(pdf.pages))
                    if fallback_entries:
                        fallback_entries = [e._replace(toc_page_num=next_page_num) for e in fallback_entries]
                        entries = fallback_entries
                    else:
                        break

                current_has_numbers = any(e.page is not None for e in entries)
                if first_page_has_numbers and not current_has_numbers:
                    break

                all_continuation_entries.extend(entries)
                current_page_idx += 1
            except Exception:
                break

        return all_continuation_entries

    def _validate_row_patterns(self, expected: list[list[str]], actual: list[list[str]]) -> bool:
        """Validate that the row patterns match the expected patterns."""
        # Check if there is any overlap in patterns (e.g. items pattern)
        expected_set = {tuple(p) for p in expected}
        actual_set = {tuple(p) for p in actual}
        return not expected_set.isdisjoint(actual_set)

    def _get_row_patterns(self, table: list[list[str | None]]) -> list[list[str]]:
        """Identify unique row patterns in the table."""
        patterns = set()
        for row in table:
            pattern = []
            for cell in row:
                pattern.append(self._classify_cell(cell))
            patterns.add(tuple(pattern))
        return [list(p) for p in patterns]

    def _classify_cell(self, text: str | None) -> str:
        if not text or not text.strip():
            return "empty"
        text = text.strip()
        if re.match(r"^\d+\.$", text):
            return "tab_number"
        if re.match(r"^\d{1,2}[\./-]\d{1,2}[\./-]\d{2,4}", text):
            return "date"
        if re.match(r"^(\d+(\.\d+)*\.?|(\d+)\s*[\-–]\s*\d+)$", text):
            return "number"
        return "text"

    def extract_data(self, page: Page, page_num: int):
        text = page.extract_text()
        words = page.extract_words()

        # Quick filter: Must have enough content
        if len(words) < self.MIN_WORDS_ON_PAGE:
            raise NotEnoughContentError(len(words), page_num)

        # Calculate detection scores
        return self._calculate_page_score(page, text, words), words

    def _scan_for_candidates(self, pdf: PDF) -> list[ScanForCandidatesReturn]:
        """Scan initial pages for TOC candidates."""
        candidates: list[ScanForCandidatesReturn] = []
        self.logger.debug(f"Scanning first {self.max_pages_to_check} pages for candidates.")

        for page_num, page in enumerate(pdf.pages[: self.max_pages_to_check], 1):
            try:
                score_and_method, words = self.extract_data(page, page_num)
            except Exception:
                self.logger.debug(f"Skipping page {page_num}")
                break

            score, method = score_and_method
            self.logger.debug(f"Page {page_num}: Score {score:.2f} ({method})")

            if score >= self.CONFIDENCE_THRESHOLD:
                candidates.append(ScanForCandidatesReturn(page_num, score, method, len(words)))
            else:
                break

        self.logger.debug(f"Found {len(candidates)} candidates: {[c.page for c in candidates]}")
        return candidates

    def _calculate_page_score(self, page: Page, text: str, words: T_obj_list) -> tuple[float, str]:
        """Calculate TOC likelihood score for a page.

        Returns (score, detection_method)
        """
        text_lower = text.lower()

        # 1. Header Check (Strongest Signal)
        header_score = 0.0
        for header in self.TOC_HEADERS:
            if re.search(r"\b" + re.escape(header) + r"\b", text_lower):
                header_score = 1.0
                break

        # 2. Entry Pattern Detection
        pattern_score = self._calculate_pattern_score(text)

        # 3. Layout Analysis
        layout_score = self._calculate_layout_score(page, words)

        # 4. Statistical Features
        stat_score = self._calculate_statistical_score(words, page.width)

        # Combined score with weighted components
        combined_score = (
            header_score * 0.4  # Header is strongest indicator
            + pattern_score * 0.3  # Entry patterns are important
            + layout_score * 0.2  # Layout provides supporting evidence
            + stat_score * 0.1  # Statistics help filter false positives
        )

        # Determine detection method
        if header_score >= self.HEADER_SCORE_THRESHOLD:
            method = "header_match"
        elif pattern_score >= self.PATTERN_SCORE_THRESHOLD:
            method = "pattern_match"
        elif layout_score >= self.LAYOUT_SCORE_THRESHOLD:
            method = "layout_match"
        else:
            method = "combined"

        return combined_score, method

    def _calculate_pattern_score(self, text: str) -> float:
        """Score based on TOC entry patterns."""
        lines = text.split("\n")
        if len(lines) < self.MIN_LINES_FOR_PATTERN_CHECK:
            return 0.0

        pattern_matches = 0
        for raw_line in lines[:50]:
            line = raw_line.strip()
            if not line:
                continue

            # Skip very short lines
            if len(line) < self.MIN_LINE_LENGTH:
                continue

            # Check for common TOC patterns
            for pattern in self.ENTRY_PATTERNS:
                if re.match(pattern, line, re.IGNORECASE):
                    pattern_matches += 1
                    break

            # Also check for page number at end
            if re.search(r"\d{1,4}$", line) and not re.match(r"^\d+$", line):
                pattern_matches += 0.5

        # Normalize score
        max_expected = min(20, len(lines))
        if max_expected == 0:
            return 0.0
        return min(pattern_matches / max_expected, 1.0)

    def _calculate_layout_score(self, page: Page, words: T_obj_list) -> float:
        """Analyze page layout for TOC characteristics."""
        if len(words) < self.MIN_WORDS_ON_PAGE:
            return 0.0

        # 1. Right-aligned numbers (page numbers)
        def _is_right_aligned_page_number(word: T_obj, page_width):
            text: str = word.get("text", "")
            return text.isdigit() and 1 <= len(text) <= self.MAX_PAGE_NUMBER_DIGITS and word["x1"] > page_width * self.RIGHT_ALIGNED_THRESHOLD

        right_numbers = [word for word in words if _is_right_aligned_page_number(word, page.width)]

        # 2. Dotted leaders
        dotted_lines = [word for word in words if re.search(r"\.{2,}|…", word["text"])]

        score_components = [min(len(right_numbers) / 10, 1.0), min(len(dotted_lines) / 8, 1.0)]

        # 3. Multiple indentation levels
        lines: defaultdict[float, T_obj_list] = defaultdict(list)
        for word in words:
            y = round(word["top"] / 5) * 5
            lines[y].append(word)

        if lines:
            first_word_positions = [line_words[0]["x0"] for y in lines if (line_words := sorted(lines[y], key=lambda w: w["x0"]))]

            if len(first_word_positions) >= self.MIN_INDENTATION_LINES:
                # Calculate variance in starting positions
                try:
                    if len(first_word_positions) > 1:
                        variance = statistics.variance(first_word_positions)
                        indentation_score = min(variance / 500, 1.0)
                        score_components.append(indentation_score)
                except statistics.StatisticsError:
                    pass

        # Average the components
        if not score_components:
            return 0.0
        return sum(score_components) / len(score_components)

    def _calculate_statistical_score(self, words: T_obj_list, page_width: float) -> float:
        """Statistical analysis of page content."""
        if len(words) < self.MIN_WORDS_ON_PAGE:
            return 0.0

        stats = {
            "digit_ratio": sum(1 for w in words if w["text"].isdigit()) / len(words),
            "right_aligned_ratio": sum(1 for w in words if w["x1"] > page_width * self.RIGHT_ALIGNED_DENSITY_THRESHOLD) / len(words),
            "avg_word_len": sum(len(w["text"]) for w in words) / len(words),
        }

        # TOCs tend to have:
        # - Higher digit ratio (page numbers)
        # - More right-aligned content
        # - Shorter average word length (concise titles)

        score = (
            min(stats["digit_ratio"] * 3, 1.0) * 0.4
            + min(stats["right_aligned_ratio"] * 2, 1.0) * 0.4
            + max(0, 1 - (stats["avg_word_len"] - 5) / 10) * 0.2
        )

        return score

    def _select_best_candidate(self, candidates: list[ScanForCandidatesReturn], pdf: PDF) -> ScanForCandidatesReturn | None:
        """Select the best TOC page from candidates."""
        if not candidates:
            return None

        # Sort by score (highest first), then by page number (lowest first)
        candidates.sort(key=lambda x: (-x.score, x.page))

        best = candidates[0]
        self.logger.debug(f"Best candidate: Page {best.page} with score {best.score:.2f}")

        # Additional validation for borderline cases
        if best.score < self.HIGH_CONFIDENCE_THRESHOLD and not self._is_strong_toc_candidate(best.page, pdf):
            self.logger.debug(f"Candidate page {best.page} rejected: low confidence and failed strong validation")
            return None

        return best

    def _is_strong_toc_candidate(self, page_num: int, pdf: PDF) -> bool:
        """Apply stricter validation for low-confidence TOC candidates."""
        page = pdf.pages[page_num - 1]
        text = page.extract_text()
        lines = text.split("\n")

        toc_like_lines = [
            line
            for raw_line in lines[:30]
            if (line := raw_line.strip())
            and any((re.search(r"[\.\s…]{2,}\d+$", line), re.search(r"^\d+\.\d+\s+", line), re.search(r"^[IVX]+\.[\s\d]", line, re.IGNORECASE)))
        ]

        return len(toc_like_lines) >= self.MIN_TOC_LIKE_LINES

    def _extract_toc_data(self, pdf: PDF, page_num: int) -> ExtractTocDataReturn:
        """Extract structured TOC data from a confirmed TOC page."""
        self.logger.debug(f"Parsing lines on page {page_num}")
        page = pdf.pages[page_num - 1]
        max_pages = len(pdf.pages)

        table = page.extract_table()
        column_count = None
        row_patterns = None

        entries: list[ParseTocLineReturn] = []
        page_numbers: list[int] = []

        if table:
            if len(table) > 0:
                column_count = len(table[0])
                row_patterns = self._get_row_patterns(table)
            for row in table:
                entry = self._parse_table_row(row)

                # Validate page number against document length
                if entry and entry.page and entry.page > max_pages:
                    entry = entry._replace(title=entry.raw_text, page=None)

                if entry and entry.title and entry.title.strip():
                    # Skip header lines
                    if self._is_header_line(entry.title):
                        self.logger.debug(f"Skipping header line: {entry.title}")
                        continue

                    # Set the TOC page number
                    entry = entry._replace(toc_page_num=page_num)

                    entries.append(entry)
                    if entry.page:
                        page_numbers.append(entry.page)

        # Determine if TOC has hierarchy
        # Ensure all entries have the correct toc_page_num
        entries = [e._replace(toc_page_num=page_num) for e in entries]

        has_hierarchy = self._detect_hierarchy(entries)

        # Calculate page range if available
        page_range = None
        if page_numbers:
            with contextlib.suppress(ValueError, TypeError):
                page_range = (min(page_numbers), max(page_numbers))

        self.logger.debug(f"Extracted {len(entries)} entries. Hierarchy: {has_hierarchy}")
        return ExtractTocDataReturn(entries, len(entries), has_hierarchy, page_range, column_count, row_patterns)

    def _adjust_indentation_for_sections(self, entries: list[ParseTocLineReturn]) -> list[ParseTocLineReturn]:
        """Adjust indentation: entries without pages act as section headers."""
        if not entries:
            return entries

        adjusted_entries = []
        current_min_indent = 0

        for entry in entries:
            if entry.page is None:
                # This is a section header
                current_min_indent = entry.indent_level + 1
                adjusted_entries.append(entry)
            elif entry.indent_level < current_min_indent:
                adjusted_entries.append(entry._replace(indent_level=current_min_indent))
            else:
                adjusted_entries.append(entry)

        return adjusted_entries

    def _extract_entries_from_words(self, page: Page, max_pages: int | None = None) -> list[ParseTocLineReturn]:
        """Extract TOC entries using word clustering fallback."""
        entries = []
        words = page.extract_words()
        # Group words by line using clustering
        words.sort(key=lambda w: w["top"])
        lines = []
        if words:
            current_line = [words[0]]
            current_line_y = words[0]["top"]
            for word in words[1:]:
                if abs(word["top"] - current_line_y) < self.LINE_MERGE_THRESHOLD:
                    current_line.append(word)
                else:
                    lines.append(current_line)
                    current_line = [word]
                    current_line_y = word["top"]
            lines.append(current_line)

        for line_words in lines:
            line_words.sort(key=lambda w: w["x0"])
            row = [w["text"] for w in line_words]
            entry = self._parse_table_row(row)

            # Validate page number against document length
            if entry and max_pages and entry.page and entry.page > max_pages:
                entry = entry._replace(title=entry.raw_text, page=None)

            if entry and entry.title and entry.title.strip() and not self._is_header_line(entry.title):
                entries.append(entry)
        return entries

    def _parse_table_row(self, row: list[str | None]) -> ParseTocLineReturn | None:
        """Parse a table row into a TOC entry."""
        # Filter empty cells
        content = [cell.strip() for cell in row if cell and cell.strip()]
        if not content:
            return None

        raw_text = " ".join(content)
        title = ""
        page_num = None

        # Try to find page number at the end
        last_part = content[-1]

        # Clean dots/spaces
        clean_last = re.sub(r"[.\s]+$", "", re.sub(r"^[.\s]+", "", last_part))

        # Check for range 12-15
        range_match = re.match(r"^(\d+)[\-–]\d+$", clean_last)

        if range_match:
            page_num = int(range_match.group(1))
            title_parts = content[:-1]
        elif clean_last.isdigit() and len(clean_last) <= self.MAX_PAGE_NUMBER_DIGITS:
            page_num = int(clean_last)
            title_parts = content[:-1]
        else:
            # Check for split range: "12", "-", "15"
            if len(content) >= SPLIT_RANGE_NUMBER_ELEMENTS:
                p1, sep, p2 = content[-SPLIT_RANGE_NUMBER_ELEMENTS:]
                if p1.isdigit() and re.match(r"^[\-–]$", sep) and p2.isdigit():
                    page_num = int(p1)
                    title_parts = content[:-SPLIT_RANGE_NUMBER_ELEMENTS]
                else:
                    title_parts = content
            else:
                title_parts = content

            # If still no page number, check if it's embedded in the last part
            if page_num is None and title_parts:
                text_to_check = " ".join(title_parts)
                match = re.search(r"[\s\.]+(\d+|(\d+)[\-–]\d+)$", text_to_check)
                if match:
                    num_str = match.group(1)
                    range_match_inner = re.match(r"^(\d+)[\-–]\d+$", num_str)
                    page_num = int(range_match_inner.group(1) if range_match_inner else num_str)
                    title = text_to_check[: match.start()].strip()
                    title_parts = []  # Title already set
                else:
                    title = text_to_check
                    title_parts = []

        if title_parts:
            title = " ".join(title_parts)

        # Clean title
        title = re.sub(r"[\.\s]+$", "", title)

        def get_indent_level(row: list[str | None]):
            indent_level = 0
            for cell in row:
                if cell is None or not cell.strip():
                    indent_level += 1
                else:
                    break
            return indent_level

        # Calculate indent level based on empty cells at start of row
        indent_level = get_indent_level(row)

        # Note: toc_page_num is not set here as we don't have it in this context.
        # It should be set by the caller (_extract_toc_data).
        return ParseTocLineReturn(title, page_num, indent_level, raw_text, 0)

    def _is_header_line(self, text: str) -> bool:
        """Check if text is a TOC header rather than an entry."""
        text_lower = text.lower().strip()

        # Check for TOC headers
        for header in self.TOC_HEADERS:
            if header in text_lower:
                return True

        # Check for common non-entry lines
        non_entry_patterns = [r"^page\s*\d*$", r"^\.+$", r"^\d+$", r"^[ivxlcdm]+$", r"^contents$", r"^index$", r"^table of contents$"]

        return any(re.match(pattern, text_lower, re.IGNORECASE) for pattern in non_entry_patterns)

    def _detect_hierarchy(self, entries: list[ParseTocLineReturn]) -> bool:
        """Detect if TOC has hierarchical structure."""
        if len(entries) < self.MIN_ENTRIES_FOR_HIERARCHY:
            return False

        # Count unique indentation levels
        indent_levels: set[int] = set()
        for entry in entries:
            indent_levels.add(entry.indent_level)

        # Multiple indent levels suggest hierarchy
        return len(indent_levels) >= self.MIN_INDENT_LEVELS_FOR_HIERARCHY

    def _validate_toc(self, entries: list[ParseTocLineReturn]) -> bool:
        """Validate that extracted entries form a plausible TOC."""
        if len(entries) < self.MIN_ENTRIES_FOR_VALIDATION:
            self.logger.debug(f"Validation failed: Too few entries ({len(entries)} < {self.MIN_ENTRIES_FOR_VALIDATION})")
            return False

        # Check for reasonable titles
        valid_titles = 0
        for entry in entries:
            if entry.title and len(entry.title) >= self.MIN_TITLE_LENGTH:
                valid_titles += 1

        if valid_titles < len(entries) * self.VALID_TITLE_RATIO:
            self.logger.debug(f"Validation failed: Low valid title ratio ({valid_titles}/{len(entries)})")
            return False

        # Check for page numbers (most TOCs have them)
        entries_with_pages = sum(1 for e in entries if e.page is not None)
        if entries_with_pages < len(entries) * self.VALID_PAGE_RATIO:
            self.logger.debug(f"Validation failed: Low page number ratio ({entries_with_pages}/{len(entries)})")
            return False

        # Check that page numbers generally increase
        if entries_with_pages >= self.MIN_ENTRIES_WITH_PAGES_FOR_SEQUENCE:
            page_numbers = [e.page for e in entries if e.page]
            increasing = sum(1 for i in range(1, len(page_numbers)) if page_numbers[i] >= page_numbers[i - 1])

            if increasing / len(page_numbers) < self.MIN_INCREASING_PAGE_RATIO:
                self.logger.debug("Validation failed: Page numbers not increasing sufficiently")
                return False

        return True


def detect_table_of_contents(pdf_path: Path) -> DetectReturn | None:
    """High-level function to detect TOC in a PDF.

    Args:
        pdf_path: Path to PDF file

    Returns:
        Dict with TOC data or None if not found

    """
    detector = TOCDetector()
    return detector.detect(pdf_path=pdf_path)


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    pdf_file = Path("document.pdf")
    toc_info = detect_table_of_contents(pdf_file)

    if toc_info:
        logging.info(f"✓ TOC found on page {toc_info.toc_page}")
        logging.info(f"  Confidence: {toc_info.confidence:.0%}")
        logging.info(f"  Entries: {toc_info.total_entries}")
        logging.info(f"  Hierarchical: {toc_info.has_hierarchy}")

        if toc_info.page_range:
            logging.info(f"  Page range: {toc_info.page_range[0]}-{toc_info.page_range[1]}")

        logging.info("\nSample entries:")
        for i, entry in enumerate(toc_info.entries[:5], 1):
            indent = "  " * (entry.indent_level or 0)
            page_num = entry.page or "N/A"
            logging.info(f"  {i}. {indent}{entry.title} → Page {page_num}")
    else:
        logging.info("✗ No TOC detected")
