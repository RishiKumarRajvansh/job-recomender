# Create a simple deployment package for Hostinger
Write-Host "Creating deployment package for Hostinger..." -ForegroundColor Green

# Define the source and output paths
$sourceDir = "d:\Vega 6\job_recommender_system"
$outputZip = "d:\job_recommender_hostinger.zip"

# Create the deployment ZIP file directly
if (Test-Path $outputZip) {
    Remove-Item $outputZip -Force
}

# Explicitly list files to include
Write-Host "Adding essential files to ZIP..." -ForegroundColor Yellow

# Create a temporary list file
$tempFile = "d:\temp_deploy_files.txt"
@(
    "app.py",
    "wsgi.py",
    "passenger_wsgi.py",
    ".htaccess",
    "config.py",
    "security.py",
    "deploy.sh",
    "init_database.py",
    "requirements.txt",
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
    "resume_parser.py", 
    "scraper.py",
    "utils.py",
    ".env.production",
    "QUICK_START.md",
    "HOSTINGER_BASIC_GUIDE.md"
) | ForEach-Object { "$sourceDir\$_" } | Out-File -FilePath $tempFile

# Add directories
@(
    "static",
    "templates",
    "migrations",
    "instance"
) | ForEach-Object { 
    Get-ChildItem -Path "$sourceDir\$_" -Recurse -File | 
    ForEach-Object { $_.FullName } | 
    Out-File -FilePath $tempFile -Append 
}

# Create the ZIP file
Compress-Archive -Path (Get-Content $tempFile) -DestinationPath $outputZip -Force

# Clean up
Remove-Item $tempFile -Force

# Verify the ZIP was created
if (Test-Path $outputZip) {
    Write-Host "Deployment package created successfully at: $outputZip" -ForegroundColor Green
    Write-Host "Size: $([math]::Round((Get-Item $outputZip).Length / 1MB, 2)) MB"
    Write-Host "You can now upload this file to your Hostinger account."
} else {
    Write-Host "Failed to create deployment package!" -ForegroundColor Red
}
