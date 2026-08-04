Set-Location 'c:\Users\Administrator\Desktop\AI_Folder\clbs'
Write-Host '=== STAGE 1: p3 + opendispatch_nols (80 runs) ==='
py -m tools.run_matrix --preset p3 --run p3 --arms opendispatch_nols --n-seeds 10
Write-Host '=== STAGE 2: lowmid + opendispatch_nols (80 runs) ==='
py -m tools.run_matrix --preset full --run lowmid --tags low mid --het 0 0.15 0.3 0.5 --arms opendispatch_nols --n-seeds 10 --pop 60 --budget auto
Write-Host '=== ALL STAGES DONE ==='
