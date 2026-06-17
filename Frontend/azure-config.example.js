// ===================================================================
// FPT AI — Frontend Azure Blob Storage config
// Copy this file to  Frontend/azure-config.js  and fill in the values.
// azure-config.js is gitignored.
//
// The frontend reads the drone videos directly from an Azure Blob container.
// ===================================================================

window.AZURE_CONFIG = {
  // Storage account name only (NOT the full URL, NOT a key).
  // WHERE: Azure Portal -> your Storage account -> "Storage account name".
  account: "<storage-account-name>",

  // Container holding the drone videos.
  // WHERE: Storage account -> Data storage -> Containers.
  videosContainer: "videos",

  // (Optional) container for 3D models — not wired yet (3D loads from the backend).
  modelsContainer: "models",

  // Leave "" if the container allows ANONYMOUS access (public).
  // Otherwise paste a container-level SAS token (with Read + List permission),
  // e.g. "sv=2023-01-03&ss=b&srt=co&sp=rl&se=...&sig=...".
  // WHERE (SAS): Storage account -> Security + networking -> Shared access signature,
  // or a container-scoped SAS from the container's "Generate SAS".
  sasToken: "",
};
