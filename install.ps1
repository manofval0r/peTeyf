# PDF Studio install (Windows)
# Run from an elevated PowerShell terminal:
#     .\install.ps1

$dst = "$env:USERPROFILE\.config\opencode\skills\pdf"
New-Item -ItemType Directory -Path $dst -Force | Out-Null

Write-Host "Installing PDF Studio to $dst ..."

# Copy the skill contents (copy from project root, not from previous install)
$src = Split-Path $PSScriptRoot -Parent
Copy-Item "$src\assets", "$src\pdfstudio", "$src\SKILL.md", "$src\README.md", "$src\requirements.txt", "$src\install.ps1" -Destination $dst -Recurse -Force

Write-Host "Done. Verify with: python -m pdfstudio scenarios"
