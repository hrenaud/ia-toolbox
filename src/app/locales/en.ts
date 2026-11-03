export const en = {
  appName: "IA Toolbox",
  tagline: "Your documents, on your computer",
  skip: "Skip to content",
  workflows: "Document tools",
  convert: "Convert to Markdown",
  anonymize: "Anonymize documents",
  convertDescription:
    "Turn documents into readable Markdown for your notes and writing.",
  anonymizeDescription:
    "Review personal information and create an anonymized copy of your documents.",
  local: "Designed for local processing",
  privacy: "Your documents stay on your computer.",
  settings: "Settings",
  preferences: "Choose your language and appearance.",
  language: "Language",
  appearance: "Appearance",
  system: "System",
  english: "English",
  french: "Français",
  light: "Light",
  dark: "Dark",
  close: "Close settings",
  saved: "Changes are saved on this computer.",
  // Conversion page
  "conversion.formatLoadError":
    "Failed to load supported formats. Please restart the app.",
  "conversion.outputSelectError": "Failed to select output folder.",
  "conversion.fileSelectError": "Failed to select files.",
  "conversion.outputRequired":
    "Please select an output folder before converting.",
  "conversion.noSupportedFiles": "No supported files selected for conversion.",
  "conversion.unknownError": "An unexpected error occurred during conversion.",
  "conversion.selectFiles": "Select files",
  "conversion.dragHint": "or drag files here",
  "conversion.supportedFormats": "Supported formats",
  "conversion.selectedFiles": "Selected files",
  "conversion.unsupported": "Unsupported",
  "conversion.requiresOcr": "Requires OCR (not available)",
  "conversion.unsupportedWarning":
    "file(s) have unsupported format and will be skipped.",
  "conversion.ocmInfo":
    "file(s) require OCR, which is not available in this version.",
  "conversion.changeOutput": "Change output folder",
  "conversion.selectOutput": "Select output folder",
  "conversion.outputPath": "Output: ",
  "conversion.outputHelp":
    "Output files will be named originalname.md. If a file already exists, a numbered suffix like originalname (2).md is used automatically.",
  "conversion.convert": "Convert",
  "conversion.converting": "Converting...",
  "conversion.clearSelection": "Clear selection",
  "conversion.progress": "Progress",
  "conversion.queued": "Queued",
  "conversion.running": "Running",
  "conversion.success": "Success",
  "conversion.error": "Error",
  "conversion.processing": "Processing",
  "conversion.successfullyConverted": "Successfully converted",
  "conversion.errorConverting": "Error converting",
  "conversion.errorPrefix": "Error:",
  "conversion.removeFile": "Remove",
  "conversion.closeError": "Close error",
  // Per-file failures reported by the worker, keyed by its error code
  "conversion.failure.input_not_found":
    "This file could not be found. It may have been moved or renamed.",
  "conversion.failure.invalid_output_directory":
    "The output folder is no longer available. Select another folder.",
  "conversion.failure.unsupported_format":
    "This format is not supported. Choose one of the supported formats.",
  "conversion.failure.password_protected":
    "This file is protected by a password. Remove the protection in the original application, save a copy, then retry.",
  "conversion.failure.processing_failed":
    "This file could not be read. It may be damaged or incomplete.",
  "conversion.failure.write_failed":
    "The Markdown file could not be written. Check that you can write to the output folder.",
  // Where a detection is, keyed by the worker's location code. "{detail}" is
  // the part number or the column heading the worker appended to the code.
  "anonymization.location.document": "The whole document",
  "anonymization.location.column": "Column “{detail}”",
  "anonymization.location.column_number": "Column {detail}",
  "anonymization.location.line": "Line {detail}",
  "anonymization.location.document_body": "Document body",
  "anonymization.location.header": "Page header {detail}",
  "anonymization.location.footer": "Page footer {detail}",
  "anonymization.location.footnotes": "Footnotes",
  "anonymization.location.endnotes": "Endnotes",
  "anonymization.location.comments": "Comments",
  "anonymization.location.slide": "Slide {detail}",
  "anonymization.location.slide_notes": "Slide {detail} notes",
  "anonymization.location.slide_layout": "Slide layout {detail}",
  "anonymization.location.slide_master": "Slide master {detail}",
  "anonymization.location.notes_master": "Notes master {detail}",
  "anonymization.location.slide_comments": "Slide comments",
  "anonymization.location.cell_values": "Cell values",
  "anonymization.location.sheet": "Sheet {detail}",
  "anonymization.location.cell_comments": "Cell comments",
  "anonymization.location.sheet_formulas": "Sheet {detail} formulas",
  "anonymization.location.sheet_names": "Sheet names",
  // What was found, keyed by the worker's entity type
  "anonymization.entity.PERSON": "Person name",
  "anonymization.entity.ORGANIZATION": "Organization",
  "anonymization.entity.LOCATION": "Place",
  "anonymization.entity.EMAIL_ADDRESS": "Email address",
  "anonymization.entity.PHONE_NUMBER": "Phone number",
  "anonymization.entity.IBAN_CODE": "Bank account number (IBAN)",
  "anonymization.entity.CREDIT_CARD": "Payment card number",
  "anonymization.entity.FR_NIR": "French social security number",
  "anonymization.entity.DATE_TIME": "Date or time",
  // How sure the detector is, in words, because colour alone says nothing
  "anonymization.confidence.high": "High confidence",
  "anonymization.confidence.medium": "Medium confidence",
  "anonymization.confidence.low": "Low confidence",
  // Anonymization page
  "anonymization.formatLoadError":
    "Failed to load the formats that can be anonymized. Please restart the app.",
  "anonymization.fileSelectError": "Failed to select files.",
  "anonymization.outputSelectError": "Failed to select output folder.",
  "anonymization.outputRequired":
    "Please select an output folder before analyzing.",
  "anonymization.noSupportedFiles": "No file selected can be anonymized.",
  "anonymization.unknownError":
    "An unexpected error occurred during anonymization.",
  "anonymization.selectFiles": "Select files",
  "anonymization.dragHint": "or drag files here",
  "anonymization.supportedFormats": "Formats that can be anonymized",
  "anonymization.selectedFiles": "Selected files",
  "anonymization.unsupported": "Cannot be anonymized",
  "anonymization.pdfNotice":
    "A PDF cannot be rewritten without rebuilding it, which would lose its layout. Convert it to Markdown first, then anonymize the Markdown file.",
  "anonymization.removeFile": "Remove",
  "anonymization.clearSelection": "Clear selection",
  "anonymization.changeOutput": "Change output folder",
  "anonymization.selectOutput": "Select output folder",
  "anonymization.outputPath": "Output: ",
  "anonymization.outputHelp":
    "The copy is named originalname-anonymized and keeps the original format. Your file is never modified, and an existing file is never overwritten: a numbered suffix is added instead.",
  "anonymization.analyze": "Find personal information",
  "anonymization.analyzing": "Reading documents...",
  "anonymization.review": "What was found",
  "anonymization.reviewHelp":
    "Choose what to replace. Nothing is written until you confirm.",
  "anonymization.nothingFound":
    "No personal information was found in these documents.",
  "anonymization.kept": "{count} of {total} selected",
  "anonymization.selectGroup": "Select everything of this type",
  "anonymization.selectAll": "Select everything",
  "anonymization.clearAll": "Select nothing",
  "anonymization.occurrences": "{count} times in the document",
  "anonymization.lessLikely": "Less likely",
  "anonymization.lessLikelyHelp":
    "One word, opening a line or a heading: often an ordinary word the detector took for a name. Check before ticking.",
  "anonymization.notRewritable": "Shown only",
  "anonymization.notRewritableHelp":
    "This text cannot be rewritten in this format without breaking the document, so it is shown and left as it is.",
  "anonymization.sharedValue":
    "This value is shared: replacing it changes every cell that uses it.",
  "anonymization.operator": "Replace with",
  "anonymization.operator.replace": "A label, such as [PERSON 1]",
  "anonymization.operator.mask": "Characters, such as ●●●●●",
  "anonymization.confirm": "Create the anonymized copy",
  "anonymization.confirmFile": "Will be written as {name}",
  "anonymization.writing": "Writing the copies...",
  "anonymization.written": "Anonymized copy created",
  "anonymization.notes": "Worth knowing about these documents",
  "anonymization.back": "Back to the file selection",
  "anonymization.errorPrefix": "Error:",
  "anonymization.closeError": "Close error",
  "anonymization.status.queued": "Waiting",
  "anonymization.status.analyzing": "Reading",
  "anonymization.status.success": "Done",
  "anonymization.status.error": "Error",
  // Content the adapters read but do not rewrite, keyed by the worker's note code
  "anonymization.note.markup_code_not_analyzed":
    "Code and markup in this document were not analyzed, only the text a reader sees.",
  "anonymization.note.xml_attributes_not_analyzed":
    "Values stored inside tags were not analyzed, only the text between them.",
  "anonymization.note.tracked_changes_not_rewritten":
    "This document has tracked changes. Deleted and inserted text is not rewritten, so accepting the revisions later can bring personal information back.",
  "anonymization.note.document_properties_not_rewritten":
    "Document properties, such as the author name, are not rewritten.",
  "anonymization.note.xlsx_shared_strings_reused":
    "This workbook shares text between cells, so one replacement can change several cells at once.",
  // Failures reported by the anonymizer, keyed by its error code
  "anonymization.failure.input_not_found":
    "This file could not be found. It may have been moved or renamed.",
  "anonymization.failure.unsupported_format":
    "This format cannot be anonymized. Choose one of the formats listed above.",
  "anonymization.failure.password_protected":
    "This file is protected by a password. Remove the protection in the original application, save a copy, then retry.",
  "anonymization.failure.invalid_output_directory":
    "The output folder is no longer available. Select another folder.",
  "anonymization.failure.document_changed":
    "This document changed since it was read. Find the personal information again, then retry.",
  "anonymization.failure.not_rewritable":
    "Part of what was selected cannot be rewritten in this format. Nothing was written.",
  "anonymization.failure.invalid_request":
    "This request could not be processed. Start over from the file selection.",
  "anonymization.failure.write_failed":
    "The copy could not be written. Check that you can write to the output folder.",
};
