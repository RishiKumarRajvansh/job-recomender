# Deploying Job Recommender System on Render.com

This guide explains how to deploy the Job Recommender System on Render.com using your free account.

## Prerequisites

- A Render.com account (free tier is sufficient to start)
- Git repository with your Job Recommender System code

## Deployment Steps

### 1. Push Your Code to a Git Repository (GitHub, GitLab, etc.)

If your code is already in a Git repository, make sure it's up to date. Otherwise, create a new repository and push your code.

### 2. Connect Your Repository to Render

1. Log in to your Render.com account
2. Click the "New +" button and select "Web Service"
3. Connect to your Git repository:
   - Select the repository that contains your Job Recommender System
   - If you haven't connected your Git provider yet, you'll be prompted to do so

### 3. Configure Your Web Service

Enter the following information:
- **Name**: job-recommender-system (or any name you prefer)
- **Environment**: Python 3
- **Build Command**: `./build.sh`
- **Start Command**: `gunicorn wsgi:app`

Under "Advanced" settings:
- Set the environment variables as specified in render.yaml
- You can modify the region if needed

### 4. Deploy Your Application

1. Click "Create Web Service"
2. Render will automatically fetch your code, install dependencies, and start your application
3. Wait for the deployment to complete (this may take a few minutes)

### 5. Access Your Application

Once deployment is complete, you can access your application at the URL provided by Render:
- `https://job-recommender-system.onrender.com` (or whatever name you chose)

### 6. Monitor Your Application

Render provides logs and metrics for your application. You can:
- View application logs by clicking on "Logs"
- Monitor resource usage and performance
- Set up alerts for issues

## Important Notes

1. **Database Persistence**: 
   - On the free tier, the filesystem is ephemeral. This means your SQLite database will reset when your service restarts.
   - For a production application, consider upgrading to a paid plan or using an external database service.

2. **Resource Limits**:
   - The free tier has limitations on RAM, CPU, and runtime
   - Your service will spin down after 15 minutes of inactivity
   - Startup may take a moment when a request comes in after inactivity

3. **Custom Domains**:
   - Custom domains are available on paid plans
   - The free tier provides a subdomain at onrender.com

## Troubleshooting

- **Application Crashes**: Check the logs for errors
- **Slow Performance**: This is normal for the free tier, especially after inactivity
- **Database Issues**: Make sure the instance directory has proper permissions
