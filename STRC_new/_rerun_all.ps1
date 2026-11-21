$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot
$log = "experiments\_rerun_log.txt"
"start $(Get-Date)" | Out-File $log -Encoding utf8
$steps = @(
  "py -m tools.cheap_baselines",
  "py -m tools.cheap_baselines --block-len 5 --out experiments/cheap_baselines_L5.csv",
  "py -m tools.cheap_baselines --block-len 2 --out experiments/cheap_baselines_L2.csv",
  "py -m tools.cheap_baselines --suite scale --out experiments/cheap_scale_full.csv",
  "py -m tools.cheap_baselines --suite scale --block-len 5 --out experiments/cheap_scale_L5.csv",
  "py -m tools.cheap_baselines --suite scale --block-len 2 --out experiments/cheap_scale_L2.csv",
  "py -m tools.expand_batch",
  "py -m tools.scale_curve",
  "py -m tools.e4_structure",
  "py -m tools.pub_batch",
  "py -m tools.edge_probe --full",
  "py -m tools.seg_completion",
  "py -m tools.weight_sweep",
  "py -m tools.paper_numbers"
)
foreach ($s in $steps) {
  "=== $s  $(Get-Date)" | Out-File $log -Append -Encoding utf8
  $out = "experiments\_rerun_" + (($s -replace "py -m tools\.", "") -replace "[^A-Za-z0-9_]+", "_") + ".txt"
  cmd /c "$s > $out 2>&1"
  "exit $LASTEXITCODE" | Out-File $log -Append -Encoding utf8
}
"done $(Get-Date)" | Out-File $log -Append -Encoding utf8
