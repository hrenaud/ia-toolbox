import type { en } from "./en";

export const fr: Record<keyof typeof en, string> = {
  appName: "IA Toolbox",
  tagline: "Vos documents, sur votre ordinateur",
  skip: "Aller au contenu",
  workflows: "Outils pour les documents",
  convert: "Convertir en Markdown",
  anonymize: "Anonymiser des documents",
  convertDescription:
    "Transformez vos documents en Markdown pour vos notes et vos rédactions.",
  anonymizeDescription:
    "Vérifiez les informations personnelles et créez une copie anonymisée de vos documents.",
  unavailable:
    "Le traitement des documents n’est pas encore disponible dans cette version.",
  local: "Conçu pour un traitement local",
  privacy: "Vos documents restent sur votre ordinateur.",
  settings: "Paramètres",
  preferences: "Choisissez votre langue et votre apparence.",
  language: "Langue",
  appearance: "Apparence",
  system: "Système",
  english: "English",
  french: "Français",
  light: "Clair",
  dark: "Sombre",
  close: "Fermer les paramètres",
  saved: "Les modifications sont enregistrées sur cet ordinateur.",
  // Conversion page
  "conversion.formatLoadError":
    "Impossible de charger les formats pris en charge. Veuillez redémarrer l’application.",
  "conversion.outputSelectError":
    "Impossible de sélectionner le dossier de sortie.",
  "conversion.fileSelectError": "Impossible de sélectionner les fichiers.",
  "conversion.outputRequired":
    "Veuillez sélectionner un dossier de sortie avant de convertir.",
  "conversion.noSupportedFiles":
    "Aucun fichier pris en charge sélectionné pour la conversion.",
  "conversion.unknownError":
    "Une erreur inattendue s’est produite lors de la conversion.",
  "conversion.selectFiles": "Sélectionner les fichiers",
  "conversion.dragHint": "ou déposez les fichiers ici",
  "conversion.supportedFormats": "Formats pris en charge",
  "conversion.selectedFiles": "Fichiers sélectionnés",
  "conversion.unsupported": "Non pris en charge",
  "conversion.requiresOcr": "Nécessite la ROC (non disponible)",
  "conversion.unsupportedWarning":
    "fichier(s) ont un format non pris en charge et seront ignorés.",
  "conversion.ocmInfo":
    "fichier(s) nécessitent la ROC, qui n’est pas disponible dans cette version.",
  "conversion.changeOutput": "Modifier le dossier de sortie",
  "conversion.selectOutput": "Sélectionner le dossier de sortie",
  "conversion.outputPath": "Sortie : ",
  "conversion.outputHelp":
    "Les fichiers de sortie seront nommés nomoriginal.md. Si un fichier existe déjà, un suffixe numéroté comme nomoriginal (2).md est utilisé automatiquement.",
  "conversion.convert": "Convertir",
  "conversion.converting": "Conversion en cours...",
  "conversion.clearSelection": "Effacer la sélection",
  "conversion.progress": "Progression",
  "conversion.queued": "En attente",
  "conversion.running": "En cours",
  "conversion.success": "Succès",
  "conversion.error": "Erreur",
  "conversion.processing": "Traitement",
  "conversion.successfullyConverted": "Converti avec succès :",
  "conversion.errorConverting": "Erreur lors de la conversion",
  "conversion.errorPrefix": "Erreur :",
  "conversion.removeFile": "Supprimer",
  "conversion.closeError": "Fermer l’erreur",
};
