// Real Azure config — gitignored. Do NOT commit.
window.AZURE_CONFIG = {
  account: "fptstorageai",
  videosContainer: "videos",
  modelsContainer: "3dmodels",
  // SAS for the videos container (expires 2026-06-23)
  sasToken: "sp=rl&st=2026-06-16T12:27:13Z&se=2026-06-23T20:42:13Z&spr=https&sv=2026-02-06&sr=c&sig=ExXipv3mceW3Q%2BgmMuBKwMvR1BqgAndv93gYzBsHaMQ%3D",
  // SAS for the 3dmodels container (expires 2027-06-17)
  modelsSasToken: "se=2027-06-17T11%3A22%3A33Z&sp=rl&sv=2026-06-06&sr=c&sig=umOgMMf8uE3jIx/ecLcUiNP%2B4zbDrZNutK7BTkzHM%2BE%3D",
};
