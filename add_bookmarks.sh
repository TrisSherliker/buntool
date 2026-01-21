#!/bin/bash
# Usage: ./add_bookmarks.sh input.pdf output.pdf "Title 1" 1 "Title 2" 18 ...
INPUT="$1"
OUTPUT="$2"
shift 2
BOOKMARKS_FILE="bookmarks.txt"
rm -f "$BOOKMARKS_FILE"
while [[ $# -gt 1 ]]; do
    TITLE="$1"
    PAGE="$2"
    echo "BookmarkBegin" >> "$BOOKMARKS_FILE"
    echo "BookmarkTitle: $TITLE" >> "$BOOKMARKS_FILE"
    echo "BookmarkLevel: 1" >> "$BOOKMARKS_FILE"
    echo "BookmarkPageNumber: $PAGE" >> "$BOOKMARKS_FILE"
    shift 2
done
pdftk "$INPUT" update_info "$BOOKMARKS_FILE" output "$OUTPUT"
echo "Bookmarks added to $OUTPUT"
