# Build all TikZ standalone PDFs
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$texs = @(
  "tikz_system.tex",
  "tikz_attack_tree.tex",
  "tikz_architecture.tex",
  "tikz_budget_chain.tex",
  "tikz_protocol.tex"
)
foreach ($t in $texs) {
  Write-Host "pdflatex $t"
  pdflatex -interaction=nonstopmode -halt-on-error $t | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "pdflatex failed on $t" }
}
Copy-Item -Force tikz_system.pdf fig_system.pdf
Copy-Item -Force tikz_attack_tree.pdf fig_attack_tree.pdf
Copy-Item -Force tikz_architecture.pdf fig_architecture.pdf
Copy-Item -Force tikz_budget_chain.pdf fig_budget_chain.pdf
Copy-Item -Force tikz_protocol.pdf fig_protocol.pdf
Write-Host "TikZ PDFs ready."
