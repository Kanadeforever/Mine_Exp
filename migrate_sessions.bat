@echo off
cd /d "%~dp0"
if not exist "Session\" (echo Session dir not found && pause && exit /b)
powershell -NoProfile -ExecutionPolicy Bypass -Command "$d=Join-Path (Get-Location) 'Session';Get-ChildItem $d\*.json|Where{$_.Name -notmatch '^\.'}|ForEach-Object{$data=Get-Content $_.FullName -Raw|ConvertFrom-Json;if($data -isnot [array] -or $data.Count -eq 0){return};if(@($data|Where{-not $_.GroupId}).Count -eq 0){return};$m=@{};$g=1;$data|ForEach-Object{$k=''+$_.Left+','+$_.Top+','+$_.Width+','+$_.Height;if(-not $m[$k]){$m[$k]=$g;$g++};$_|Add-Member -NotePropertyName GroupId -NotePropertyValue $m[$k] -Force};$j=$data|ConvertTo-Json -Depth 3;[System.IO.File]::WriteAllText($_.FullName,$j,(New-Object System.Text.UTF8Encoding $false));Write-Host ('Migrated: '+$_.Name)};Write-Host 'Done'"
pause
