# Quick Start Deployment Guide for Hostinger Basic Plan

This guide provides step-by-step instructions for deploying your Job Recommender System to a Hostinger Basic Plan.

## Step 1: Create the Deployment Package

Run the PowerShell script to create your deployment package:

```powershell
# On your local machine
.\create_deployment_package.ps1
```

This will create a file called `job_recommender_hostinger.zip` in the D:\ directory.

## Step 2: Upload to Hostinger

1. Log in to your Hostinger account
2. Go to hPanel
3. Click on "File Manager"
4. Navigate to the `public_html` folder
5. Click "Upload" and select your `job_recommender_hostinger.zip` file
6. Once uploaded, right-click on the ZIP file and select "Extract"

## Step 3: Configure Python

1. In hPanel, go to "Advanced" > "Python"
2. Enable Python support
3. Set application path to your `public_html` directory
4. Set Python version to 3.8 or the highest available version
5. Set application startup file to `passenger_wsgi.py`
6. Save the changes

## Step 4: Deploy via SSH

1. In hPanel, go to "Advanced" > "SSH Access"
2. Enable SSH access if not already enabled
3. Connect to your server using an SSH client (like PuTTY)
   ```
   ssh u123456789@your-server-name.com
   ```
   Replace `u123456789` with your Hostinger username and `your-server-name.com` with your server address
4. Navigate to the `public_html` directory:
   ```
   cd public_html
   ```
5. Run the deployment script:
   ```
   bash deploy.sh
   ```

## Step 5: Test Your Application

1. Visit your domain in a web browser
2. You should see the Job Recommender System homepage
3. Test core functionality like user registration and job search

## Troubleshooting

If you encounter any issues:

1. **500 Internal Server Error**:
   - Check the Python configuration in hPanel
   - Check the logs in the `logs` directory

2. **Database Issues**:
   - Ensure the `instance` directory has proper permissions
   - Run `python3 init_database.py` via SSH

3. **Module Import Errors**:
   - Try reinstalling Python packages:
     ```
     pip3 install --user -r requirements.txt
     ```

## Regular Maintenance

- Back up your database regularly:
  ```
  cp instance/job_recommender.db instance/job_recommender.db.backup
  ```
- Monitor your application logs:
  ```
  tail -f logs/app.log
  ```

For more detailed instructions, see `HOSTINGER_BASIC_GUIDE.md` in this package.
