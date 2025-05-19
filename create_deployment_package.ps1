# Create deployment package for Hostinger
Write-Host "Creating deployment package for Hostinger..." -ForegroundColor Green

# Define the source directory and output zip file
$sourceDir = "d:\Vega 6\job_recommender_system"
$outputZip = "d:\job_recommender_hostinger.zip"

# Set up exclusion patterns for files/folders we don't want to include
$excludePatterns = @(
    "*.pyc",
    ".git",
    ".env",
    "__pycache__",
    "venv",
    "env",
    "*.log",
    "*.bak",
    "*.tmp",
    "*.zip"
)

# Create a temporary directory to prepare files
$tempDir = "d:\temp_deploy_job_recommender"
if (Test-Path $tempDir) {
    Remove-Item -Recurse -Force $tempDir
}
New-Item -ItemType Directory -Path $tempDir | Out-Null

Write-Host "Copying files to temporary directory..." -ForegroundColor Yellow
# Copy files to temp directory, excluding unwanted patterns
Get-ChildItem -Path $sourceDir -Recurse | Where-Object {
    $item = $_
    $exclude = $false
    foreach ($pattern in $excludePatterns) {
        if ($item.FullName -like "*$pattern*") {
            $exclude = $true
            break
        }
    }
    -not $exclude
} | ForEach-Object {
    $targetPath = $_.FullName.Replace($sourceDir, $tempDir)
    
    if ($_.PSIsContainer) {
        # Create directory if it doesn't exist
        if (-not (Test-Path $targetPath)) {
            New-Item -ItemType Directory -Path $targetPath | Out-Null
        }
    } else {
        # Copy file to target directory, creating parent directories if needed
        $targetDir = Split-Path -Parent $targetPath
        if (-not (Test-Path $targetDir)) {
            New-Item -ItemType Directory -Path $targetDir | Out-Null
        }
        Copy-Item -Path $_.FullName -Destination $targetPath -Force
    }
}

# Rename .env.production to .env in the temp directory
Copy-Item -Path "$tempDir\.env.production" -Destination "$tempDir\.env" -Force
Write-Host "Created .env file from .env.production" -ForegroundColor Green

# Create the ZIP file
Write-Host "Creating ZIP file..." -ForegroundColor Yellow
if (Test-Path $outputZip) {
    Remove-Item $outputZip -Force
}

# Use Compress-Archive to create the ZIP
Compress-Archive -Path "$tempDir\*" -DestinationPath $outputZip

# Clean up the temporary directory
Remove-Item -Recurse -Force $tempDir

# Output success message
Write-Host "Deployment package created successfully at: $outputZip" -ForegroundColor Green
Write-Host "You can now upload this file to your Hostinger account."
