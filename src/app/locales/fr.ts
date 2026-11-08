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
  // Échecs par fichier signalés par le moteur, indexés par son code d’erreur
  "conversion.failure.input_not_found":
    "Ce fichier est introuvable. Il a peut-être été déplacé ou renommé.",
  "conversion.failure.invalid_output_directory":
    "Le dossier de sortie n’est plus disponible. Sélectionnez un autre dossier.",
  "conversion.failure.unsupported_format":
    "Ce format n’est pas pris en charge. Choisissez un des formats pris en charge.",
  "conversion.failure.password_protected":
    "Ce fichier est protégé par un mot de passe. Retirez la protection dans l’application d’origine, enregistrez une copie, puis réessayez.",
  "conversion.failure.processing_failed":
    "Ce fichier n’a pas pu être lu. Il est peut-être endommagé ou incomplet.",
  "conversion.failure.write_failed":
    "Le fichier Markdown n’a pas pu être écrit. Vérifiez que vous pouvez écrire dans le dossier de sortie.",
  // Emplacement d’une détection, indexé par le code du moteur. « {detail} » est
  // le numéro de la partie ou l’intitulé de colonne ajouté après le code.
  "anonymization.location.document": "Tout le document",
  "anonymization.location.column": "Colonne « {detail} »",
  "anonymization.location.column_number": "Colonne {detail}",
  "anonymization.location.line": "Ligne {detail}",
  "anonymization.location.document_body": "Corps du document",
  "anonymization.location.header": "En-tête de page {detail}",
  "anonymization.location.footer": "Pied de page {detail}",
  "anonymization.location.footnotes": "Notes de bas de page",
  "anonymization.location.endnotes": "Notes de fin",
  "anonymization.location.comments": "Commentaires",
  "anonymization.location.slide": "Diapositive {detail}",
  "anonymization.location.slide_notes": "Notes de la diapositive {detail}",
  "anonymization.location.slide_layout": "Disposition {detail}",
  "anonymization.location.slide_master": "Masque des diapositives {detail}",
  "anonymization.location.notes_master": "Masque des notes {detail}",
  "anonymization.location.slide_comments": "Commentaires des diapositives",
  "anonymization.location.cell_values": "Contenu des cellules",
  "anonymization.location.sheet": "Feuille {detail}",
  "anonymization.location.cell_comments": "Commentaires des cellules",
  "anonymization.location.sheet_formulas": "Formules de la feuille {detail}",
  "anonymization.location.sheet_names": "Noms des feuilles",
  // Ce qui a été trouvé, indexé par le type d’entité du moteur
  "anonymization.entity.PERSON": "Nom de personne",
  "anonymization.entity.ORGANIZATION": "Organisation",
  "anonymization.entity.LOCATION": "Lieu",
  "anonymization.entity.EMAIL_ADDRESS": "Adresse électronique",
  "anonymization.entity.PHONE_NUMBER": "Numéro de téléphone",
  "anonymization.entity.IBAN_CODE": "Numéro de compte bancaire (IBAN)",
  "anonymization.entity.CREDIT_CARD": "Numéro de carte de paiement",
  "anonymization.entity.FR_NIR": "Numéro de sécurité sociale",
  "anonymization.entity.DATE_TIME": "Date ou heure",
  // Le degré de certitude, en mots : une couleur seule ne dit rien
  "anonymization.confidence.high": "Certitude élevée",
  "anonymization.confidence.medium": "Certitude moyenne",
  "anonymization.confidence.low": "Certitude faible",
  // Page d’anonymisation
  "anonymization.formatLoadError":
    "Impossible de charger les formats qui peuvent être anonymisés. Veuillez redémarrer l’application.",
  "anonymization.fileSelectError": "Impossible de sélectionner les fichiers.",
  "anonymization.outputSelectError":
    "Impossible de sélectionner le dossier de sortie.",
  "anonymization.outputRequired":
    "Veuillez sélectionner un dossier de sortie avant l’analyse.",
  "anonymization.noSupportedFiles":
    "Aucun fichier sélectionné ne peut être anonymisé.",
  "anonymization.unknownError":
    "Une erreur inattendue s’est produite lors de l’anonymisation.",
  "anonymization.selectFiles": "Sélectionner les fichiers",
  "anonymization.dragHint": "ou déposez les fichiers ici",
  "anonymization.supportedFormats": "Formats qui peuvent être anonymisés",
  "anonymization.selectedFiles": "Fichiers sélectionnés",
  "anonymization.unsupported": "Ne peut pas être anonymisé",
  "anonymization.pdfNotice":
    "Un PDF ne peut pas être réécrit sans être reconstruit, ce qui ferait perdre sa mise en page. Convertissez-le d’abord en Markdown, puis anonymisez le fichier Markdown.",
  "anonymization.removeFile": "Supprimer",
  "anonymization.clearSelection": "Effacer la sélection",
  "anonymization.changeOutput": "Modifier le dossier de sortie",
  "anonymization.selectOutput": "Sélectionner le dossier de sortie",
  "anonymization.outputPath": "Sortie : ",
  "anonymization.outputHelp":
    "La copie est nommée nomoriginal-anonymise et conserve le format d’origine. Votre fichier n’est jamais modifié, et un fichier existant n’est jamais remplacé : un suffixe numéroté est ajouté.",
  "anonymization.analyze": "Rechercher les informations personnelles",
  "anonymization.analyzing": "Lecture des documents…",
  "anonymization.review": "Ce qui a été trouvé",
  "anonymization.reviewHelp":
    "Choisissez ce qui doit être remplacé. Rien n’est écrit avant votre confirmation.",
  "anonymization.nothingFound":
    "Aucune information personnelle n’a été trouvée dans ces documents.",
  "anonymization.kept": "{count} élément(s) sélectionné(s) sur {total}",
  "anonymization.typeOf": "Type de « {value} »",
  "anonymization.language": "Langue du document",
  "anonymization.language.fr": "Français",
  "anonymization.language.en": "Anglais",
  "anonymization.languageHelp":
    "Les noms sont lus dans cette langue. Si elle est fausse, corrigez-la : le document est relu et vos choix sont remis à zéro.",
  "anonymization.selectAll": "Tout sélectionner",
  "anonymization.clearAll": "Ne rien sélectionner",
  "anonymization.occurrences": "{count} fois dans le document",
  "anonymization.columnCells": "colonne entière, {count} cellules",
  "anonymization.lessLikely": "Moins probables",
  "anonymization.lessLikelyHelp":
    "Un seul mot, en début de ligne ou de titre : c’est souvent un mot ordinaire que le détecteur a pris pour un nom. Vérifiez avant de cocher.",
  "anonymization.notRewritable": "Signalé seulement",
  "anonymization.notRewritableHelp":
    "Ce texte ne peut pas être réécrit dans ce format sans abîmer le document : il est signalé et laissé tel quel.",
  "anonymization.sharedValue":
    "Cette valeur est partagée : la remplacer modifie toutes les cellules qui l’utilisent.",
  "anonymization.operator": "Remplacer par",
  "anonymization.operator.replace": "Une étiquette, comme [PERSONNE 1]",
  "anonymization.operator.mask": "Des caractères, comme ●●●●●",
  "anonymization.confirm": "Créer la copie anonymisée",
  "anonymization.confirmFile": "Sera écrite sous le nom {name}",
  "anonymization.writing": "Écriture des copies…",
  "anonymization.written": "Copie anonymisée créée",
  "anonymization.notes": "À savoir sur ces documents",
  "anonymization.back": "Revenir à la sélection des fichiers",
  "anonymization.errorPrefix": "Erreur :",
  "anonymization.closeError": "Fermer l’erreur",
  "anonymization.status.queued": "En attente",
  "anonymization.status.analyzing": "Lecture",
  "anonymization.status.success": "Terminé",
  "anonymization.status.error": "Erreur",
  // Contenu lu mais non réécrit, indexé par le code de remarque du moteur
  "anonymization.note.markup_code_not_analyzed":
    "Le contenu des scripts et des styles de ce document n’a pas été analysé.",
  "anonymization.note.xml_attributes_not_analyzed":
    "Les valeurs stockées dans les balises n’ont pas été analysées, uniquement le texte entre les balises.",
  "anonymization.note.tracked_changes_not_rewritten":
    "Ce document contient des modifications suivies. Le texte supprimé ou inséré n’est pas réécrit : accepter les révisions plus tard peut faire réapparaître des informations personnelles.",
  "anonymization.note.document_properties_not_rewritten":
    "Les propriétés du document, comme le nom de l’auteur, ne sont pas réécrites.",
  "anonymization.note.xlsx_shared_strings_reused":
    "Ce classeur partage du texte entre les cellules : un seul remplacement peut modifier plusieurs cellules à la fois.",
  // Échecs signalés par l’anonymiseur, indexés par son code d’erreur
  "anonymization.failure.input_not_found":
    "Ce fichier est introuvable. Il a peut-être été déplacé ou renommé.",
  "anonymization.failure.unsupported_format":
    "Ce format ne peut pas être anonymisé. Choisissez un des formats listés ci-dessus.",
  "anonymization.failure.password_protected":
    "Ce fichier est protégé par un mot de passe. Retirez la protection dans l’application d’origine, enregistrez une copie, puis réessayez.",
  "anonymization.failure.invalid_output_directory":
    "Le dossier de sortie n’est plus disponible. Sélectionnez un autre dossier.",
  "anonymization.failure.document_changed":
    "Ce document a changé depuis sa lecture. Recherchez à nouveau les informations personnelles, puis réessayez.",
  "anonymization.failure.not_rewritable":
    "Une partie de la sélection ne peut pas être réécrite dans ce format. Rien n’a été écrit.",
  "anonymization.failure.invalid_request":
    "Cette demande n’a pas pu être traitée. Reprenez depuis la sélection des fichiers.",
  "anonymization.failure.write_failed":
    "La copie n’a pas pu être écrite. Vérifiez que vous pouvez écrire dans le dossier de sortie.",
};
