// ===================================================================
// FTP-AI — Frontend Azure Blob Storage config
// Kopieer dit bestand naar  Frontend/azure-config.js  en vul de waarden in.
// azure-config.js is gitignored — commit NOOIT echte tokens.
//
// WHERE: Azure Portal -> Storage accounts -> <account> -> Containers
//        -> <container> -> Shared access tokens -> Generate SAS
// ===================================================================

window.AZURE_CONFIG = {
  // Naam van het storage account (NIET de volledige URL, NIET een key).
  account: "<storage-account-name>",

  // Container met de drone video's.
  videosContainer: "videos",

  // Container met 3D modellen (GLB, PLY).
  modelsContainer: "3dmodels",

  // SAS token voor de videos container (Read + List rechten).
  // Vervaldatum instellen op minimaal 1 jaar.
  sasToken: "",

  // SAS token voor de 3dmodels container (Read + List rechten).
  // Vervaldatum instellen op minimaal 1 jaar.
  modelsSasToken: "",
};
