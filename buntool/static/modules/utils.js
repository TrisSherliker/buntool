import * as chrono from 'chrono-node';

export const sanitizeFilename = (filename) => {
  let nameWithoutExt = filename;
  nameWithoutExt = nameWithoutExt.replace(/[\s_]+/g, '-');
  nameWithoutExt = nameWithoutExt.replace(/[^a-zA-Z0-9-.]/g, '');
  return nameWithoutExt;
}

export const prettifyTitle = (title) => {
  title = title.replace(/_+/g, ' ');
  title = title.replace(/[^\p{L}\p{N}\p{P}\p{S}\p{Z}]/gu, '');
  return title.trim();
}

export const escapeCsvField = (field) => {
  if (!field) return '';
  if (field.includes(',') || field.includes('"') || field.includes('\n')) {
    return `"${field.replace(/"/g, '""')}"`;
  }
  return field;
}

export const parseDateFromFilename = (filename, title) => {
  console.log("Parsing date and cleaning title. Input:", { filename, title });
  let titleWithoutDate = title;
  let matchedDate = null;

  const year_first_regex = /[\[\(]{0,1}(1\d{3}|20\d{2})[-._]?(0[1-9]|1[0-2])[-._]?(0[1-9]|[12][0-9]|3[01])[\]\)]{0,1}/;
  const year_last_regex = /[\[\(]{0,1}(0[1-9]|[12][0-9]|3[01])[-._]?(0[1-9]|1[0-2])[-._]?(1\d{3}|20\d{2})[\]\)]{0,1}/;

  const year_first_match = filename.match(year_first_regex);
  if (year_first_match) {
    const [fullMatch, year, month, day] = year_first_match;
    const parsedDate = new Date(`${year}-${month}-${day}T00:00:00Z`);
    matchedDate = parsedDate.toISOString().split('T')[0];
    if (titleWithoutDate) {
      titleWithoutDate = titleWithoutDate.replace(fullMatch, '').replace(/^[\s-_]+|[\s-_]+$/g, '');
    }
    console.log("Year-first match found:", { matchedDate, titleWithoutDate });
    return { date: matchedDate, titleWithoutDate };
  }

  const year_last_match = filename.match(year_last_regex);
  if (year_last_match) {
    const [fullMatch, day, month, year] = year_last_match;
    const parsedDate = new Date(`${year}-${month}-${day}T00:00:00Z`);
    matchedDate = parsedDate.toISOString().split('T')[0];
    if (titleWithoutDate) {
      titleWithoutDate = titleWithoutDate.replace(fullMatch, '').replace(/^[\s-_]+|[\s-_]+$/g, '');
    }
    console.log("Year-last match found:", { matchedDate, titleWithoutDate });
    return { date: matchedDate, titleWithoutDate };
  }

  // chrono is global from CDN
  const chrono_parsedDate = chrono.strict.parseDate(filename);
  if (chrono_parsedDate) {
    matchedDate = chrono_parsedDate.toISOString().split('T')[0];
    console.log("Chrono date found:", { matchedDate, titleWithoutDate });
    return { date: matchedDate, titleWithoutDate };
  }

  console.log("No date found, returning:", { date: null, titleWithoutDate });
  return { date: null, titleWithoutDate };
}
