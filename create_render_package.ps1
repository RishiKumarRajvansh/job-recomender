# Create a deployment package for Render.com
Write-Host "Creating deployment package for Render.com..." -ForegroundColor Green

# Define the source directory and output zip file
$sourceDir = "d:\Vega 6\job_recommender_system"
$outputZip = "d:\job_recommender_render.zip"

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
    "*.zip",
    "create_deployment_package.ps1",
    "create_simple_package.ps1"
)

# Create a temporary list file
$tempFile = "d:\temp_render_files.txt"

# Add specific files to include
@(
    "app.py",
    "wsgi.py",
    "build.sh",
    "config.py",
    "security.py",
    "init_database.py",
    "requirements.txt",
    "runtime.txt",
    "render.yaml",
    "cleanup_utils.py",
    "courses.py",
    "database_manager.py",
    "forms.py",
    "health_check.py",
    "insights.py",
    "job_counter.py",
    "job_utils.py",
    "models.py",
    "nlp_utils.py",
    "public_health.py",
    "README.md",
    "RENDER_DEPLOYMENT.md",
    "resume_parser.py", 
    "scraper.py",
    "utils.py",
    "Procfile"
) | ForEach-Object { 
    $filePath = "$sourceDir\$_"
    if (Test-Path $filePath) {
        $filePath | Out-File -FilePath $tempFile -Append
    } else {
        Write-Host "Warning: File not found - $_" -ForegroundColor Yellow
    }
}

# Add directories
@(
    "static",
    "templates",
    "migrations"
) | ForEach-Object { 
    $dirPath = "$sourceDir\$_"
    if (Test-Path $dirPath) {
        Get-ChildItem -Path $dirPath -Recurse -File | 
        ForEach-Object { $_.FullName } | 
        Out-File -FilePath $tempFile -Append 
    } else {
        Write-Host "Warning: Directory not found - $_" -ForegroundColor Yellow
    }
}

# Create instance directory with placeholder
$instanceDir = "$sourceDir\instance"
if (-not (Test-Path "$instanceDir\.gitkeep")) {
    if (-not (Test-Path $instanceDir)) {
        New-Item -ItemType Directory -Path $instanceDir -Force | Out-Null
    }
    "" | Out-File -FilePath "$instanceDir\.gitkeep"
    "$instanceDir\.gitkeep" | Out-File -FilePath $tempFile -Append
}

# Create the ZIP file
if (Test-Path $outputZip) {
    Remove-Item $outputZip -Force
}

# Create the ZIP file with the files in the temp file
Compress-Archive -Path (Get-Content $tempFile) -DestinationPath $outputZip -Force

# Clean up
Remove-Item $tempFile -Force

# Verify the ZIP was created
if (Test-Path $outputZip) {
    Write-Host "Render deployment package created successfully at: $outputZip" -ForegroundColor Green
    Write-Host "Size: $([math]::Round((Get-Item $outputZip).Length / 1MB, 2)) MB"
    Write-Host "You can now upload this code to a Git repository and deploy on Render."
} else {
    Write-Host "Failed to create deployment package!" -ForegroundColor Red
}
