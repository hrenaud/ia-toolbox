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
  unavailable: "Document processing is not available in this version yet.",
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
};
